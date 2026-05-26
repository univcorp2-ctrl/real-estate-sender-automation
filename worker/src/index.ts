interface Env {
  DB: D1Database;
  SENDER_API_TOKEN?: string;
  WORKER_SHARED_SECRET?: string;
  GITHUB_TOKEN?: string;
  GITHUB_OWNER?: string;
  GITHUB_REPO?: string;
  GITHUB_WORKFLOW_FILE?: string;
}

const json = (data: unknown, status = 200): Response =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

async function requireAuth(request: Request, env: Env): Promise<Response | null> {
  const expected = env.WORKER_SHARED_SECRET || "";
  const provided = request.headers.get("authorization") || "";
  if (!expected || provided !== `Bearer ${expected}`) {
    return json(
      {
        ok: false,
        error: "unauthorized",
        message: "WORKER_SHARED_SECRET mismatch. Check GitHub Actions secret and Cloudflare Worker secret.",
        debug: {
          has_shared_secret: Boolean(expected),
          has_authorization_header: Boolean(provided),
          auth_scheme_is_bearer: provided.toLowerCase().startsWith("bearer "),
          provided_length: provided.length,
        },
      },
      401,
    );
  }
  return null;
}

async function bodyJson<T = Record<string, unknown>>(request: Request): Promise<T> {
  return (await request.json()) as T;
}

async function senderFetch(env: Env, path: string, payload?: unknown): Promise<Response> {
  const token = env.SENDER_API_TOKEN || "";
  if (!token) return json({ ok: false, error: "missing_sender_api_token" }, 500);
  const response = await fetch(`https://api.sender.net/v2${path}`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${token}`,
      "content-type": "application/json",
      accept: "application/json",
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const text = await response.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    parsed = { raw: text };
  }
  if (!response.ok) {
    return json({ ok: false, status: response.status, sender: parsed }, response.status);
  }
  return json({ ok: true, sender: parsed });
}

async function filterUnsent(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<{ audience_key?: string; fingerprints?: string[] }>(request);
  const audienceKey = payload.audience_key || "default";
  const fingerprints = payload.fingerprints || [];
  const unsent: string[] = [];
  for (const fingerprint of fingerprints) {
    const row = await env.DB.prepare(
      "SELECT fingerprint FROM sent_log WHERE audience_key = ? AND fingerprint = ? LIMIT 1",
    )
      .bind(audienceKey, fingerprint)
      .first();
    if (!row) unsent.push(fingerprint);
  }
  return json({ ok: true, unsent });
}

async function markSent(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<{
    audience_key?: string;
    records?: Array<{
      fingerprint: string;
      property_id: string;
      campaign_id?: string;
      status?: string;
      sent_at?: string;
    }>;
  }>(request);
  const audienceKey = payload.audience_key || "default";
  const records = payload.records || [];
  const now = new Date().toISOString();
  const statements = records.map((record) =>
    env.DB.prepare(
      "INSERT OR IGNORE INTO sent_log(audience_key, fingerprint, property_id, campaign_id, status, sent_at) VALUES(?, ?, ?, ?, ?, ?)",
    ).bind(
      audienceKey,
      record.fingerprint,
      record.property_id,
      record.campaign_id || "",
      record.status || "sent",
      record.sent_at || now,
    ),
  );
  if (statements.length > 0) await env.DB.batch(statements);
  return json({ ok: true, inserted: records.length });
}

async function acquireLock(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<{ key?: string; ttl_seconds?: number }>(request);
  const key = payload.key || "default";
  const ttlSeconds = payload.ttl_seconds || 1800;
  const now = new Date();
  const expiresAt = new Date(now.getTime() + ttlSeconds * 1000).toISOString();
  await env.DB.prepare("DELETE FROM job_locks WHERE expires_at < ?").bind(now.toISOString()).run();
  try {
    await env.DB.prepare("INSERT INTO job_locks(lock_key, expires_at) VALUES(?, ?)")
      .bind(key, expiresAt)
      .run();
    return json({ ok: true, acquired: true, expires_at: expiresAt });
  } catch {
    return json({ ok: true, acquired: false });
  }
}

async function releaseLock(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<{ key?: string }>(request);
  await env.DB.prepare("DELETE FROM job_locks WHERE lock_key = ?").bind(payload.key || "default").run();
  return json({ ok: true });
}

async function campaign(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<Record<string, unknown>>(request);
  const sendAction = String(payload.send_action || "draft");
  const scheduleTime = payload.schedule_time as string | undefined;
  delete payload.send_action;
  delete payload.schedule_time;

  const createdResponse = await senderFetch(env, "/campaigns", payload);
  const created = (await createdResponse.clone().json()) as {
    ok?: boolean;
    sender?: { data?: { id?: string }; id?: string };
  };
  if (!createdResponse.ok || !created.ok) return createdResponse;
  const campaignId = String(created.sender?.data?.id || created.sender?.id || "");
  if (!campaignId) return json({ ok: false, error: "missing_campaign_id", sender: created.sender }, 502);

  if (sendAction === "schedule") {
    const scheduled = await senderFetch(env, `/campaigns/${campaignId}/schedule`, {
      schedule_time: scheduleTime,
    });
    const data = await scheduled.json();
    return json({ ok: scheduled.ok, mode: "schedule", campaign_id: campaignId, sender: data });
  }
  if (sendAction === "send") {
    const sent = await senderFetch(env, `/campaigns/${campaignId}/send`);
    const data = await sent.json();
    return json({ ok: sent.ok, mode: "send", campaign_id: campaignId, sender: data });
  }
  return json({ ok: true, mode: "draft", campaign_id: campaignId, sender: created.sender });
}

async function transactional(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<Record<string, unknown>>(request);
  return senderFetch(env, "/message/send", payload);
}

async function dispatchGitHub(env: Env, inputs: Record<string, string>): Promise<Response> {
  const token = env.GITHUB_TOKEN || "";
  if (!token || !env.GITHUB_OWNER || !env.GITHUB_REPO) {
    return json({ ok: false, error: "missing_github_dispatch_config" }, 500);
  }
  const workflow = env.GITHUB_WORKFLOW_FILE || "property-mailer.yml";
  const response = await fetch(
    `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        accept: "application/vnd.github+json",
        "user-agent": "real-estate-sender-automation-worker",
        "content-type": "application/json",
      },
      body: JSON.stringify({ ref: "main", inputs }),
    },
  );
  if (!response.ok) return json({ ok: false, status: response.status, body: await response.text() }, 502);
  return json({ ok: true, dispatched: true });
}

async function inquiryWebhook(env: Env, request: Request): Promise<Response> {
  const payload = await bodyJson<Record<string, unknown>>(request);
  await env.DB.prepare("INSERT INTO webhook_events(event_type, payload, created_at) VALUES(?, ?, ?)")
    .bind("inquiry", JSON.stringify(payload), new Date().toISOString())
    .run();
  return dispatchGitHub(env, {
    mode: "reply_inquiry",
    inquiry_payload: JSON.stringify(payload),
    dry_run: "false",
  });
}

async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname === "/health") return json({ ok: true, service: "property-mailer-worker" });
  const authError = await requireAuth(request, env);
  if (authError) return authError;
  if (request.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);

  if (url.pathname === "/state/filter-unsent") return filterUnsent(env, request);
  if (url.pathname === "/state/mark-sent") return markSent(env, request);
  if (url.pathname === "/lock/acquire") return acquireLock(env, request);
  if (url.pathname === "/lock/release") return releaseLock(env, request);
  if (url.pathname === "/sender/campaign") return campaign(env, request);
  if (url.pathname === "/sender/transactional") return transactional(env, request);
  if (url.pathname === "/github/dispatch") {
    const payload = await bodyJson<Record<string, string>>(request);
    return dispatchGitHub(env, payload);
  }
  if (url.pathname === "/webhook/inquiry") return inquiryWebhook(env, request);
  return json({ ok: false, error: "not_found" }, 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    return route(request, env);
  },
  async scheduled(_event: ScheduledEvent, env: Env): Promise<void> {
    await dispatchGitHub(env, { mode: "run_daily", dry_run: "false", inquiry_payload: "" });
  },
};
