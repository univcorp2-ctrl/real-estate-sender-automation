CREATE TABLE IF NOT EXISTS sent_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  audience_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  property_id TEXT NOT NULL,
  campaign_id TEXT,
  status TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  UNIQUE(audience_key, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_sent_log_audience ON sent_log(audience_key);

CREATE TABLE IF NOT EXISTS job_locks (
  lock_key TEXT PRIMARY KEY,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
