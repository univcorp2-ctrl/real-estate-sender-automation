# 初期設定ガイド

## 0. 露出済みAPIキーのローテーション

チャットや共有画面に貼ったAPIキーは露出済みとして扱います。最初にCloudflareとSenderの管理画面で新しいAPIキーを発行し、古いキーを無効化してください。

## 1. Sender.net設定

1. Senderにログインします。
2. Settings → Domains / Sending domain で独自ドメインを追加します。
3. Senderが表示するSPF/DKIM/DMARCなどのDNSレコードをCloudflare DNSに登録します。
4. Sender側でドメイン認証が完了したことを確認します。
5. Settings → API access tokens でAPI Tokenを作成します。
6. 配信先のGroupまたはSegmentを作成し、IDを控えます。

## 2. Cloudflare D1作成

```bash
cd worker
npm install
npx wrangler login
npx wrangler d1 create property-mailer-db
```

表示された `database_id` を `worker/wrangler.toml` の `database_id` に入れます。

```bash
npx wrangler d1 migrations apply property-mailer-db --remote
```

## 3. Cloudflare Worker Secret登録

実値はコマンド履歴に残さないよう、対話入力で入れます。

```bash
cd worker
npx wrangler secret put SENDER_API_TOKEN
npx wrangler secret put WORKER_SHARED_SECRET
```

WorkerからGitHub Actionsを発火したい場合だけ、以下も設定します。

```bash
npx wrangler secret put GITHUB_TOKEN
```

`GITHUB_TOKEN` はfine-grained PATを推奨します。対象リポジトリのActions workflow dispatchに必要な最小権限だけを付けます。

`worker/wrangler.toml` またはCloudflare DashboardのVariablesに以下を設定します。

- `GITHUB_OWNER`
- `GITHUB_REPO`
- `GITHUB_WORKFLOW_FILE=property-mailer.yml`

## 4. Cloudflare Workerデプロイ

```bash
cd worker
npx wrangler deploy
```

デプロイ後、URLを控えます。

```bash
curl https://<worker-url>/health
```

## 5. GitHub Secrets / Variables設定

GitHubリポジトリ → Settings → Secrets and variables → Actions で設定します。

Secrets:

- `AUTOMATION_WORKER_URL`: Cloudflare Worker URL
- `WORKER_SHARED_SECRET`: Cloudflare Worker側と同じ共有Secret
- `GOOGLE_DRIVE_FOLDER_ID`: 物件DBフォルダID
- `GOOGLE_SERVICE_ACCOUNT_JSON`: GoogleサービスアカウントJSON
- `CLOUDFLARE_API_TOKEN`: Workerデプロイ用。必要な場合のみ
- `CLOUDFLARE_ACCOUNT_ID`: Workerデプロイ用。必要な場合のみ

Variables:

- `SENDER_FROM_EMAIL`: 認証済み独自ドメインの送信元メール
- `SENDER_FROM_NAME`: 送信者名
- `SENDER_REPLY_TO`: 問い合わせ返信先
- `SENDER_GROUP_IDS`: Sender Group ID。カンマ区切り
- `SENDER_SEGMENT_IDS`: Sender Segment ID。使わない場合は空

## 6. Google Drive設定

1. Google Cloudでサービスアカウントを作成します。
2. Drive APIを有効化します。
3. サービスアカウントキーJSONを作成します。
4. 対象Google Driveフォルダをサービスアカウントのメールアドレスに閲覧権限で共有します。
5. JSON全文をGitHub Secret `GOOGLE_SERVICE_ACCOUNT_JSON` に保存します。

## 7. 物件DBファイル

Google DriveフォルダにCSV/JSON/XLSXのいずれかを置きます。最新更新日のファイルが使われます。

必須列:

- `property_id`
- `title`
- `price`
- `area`
- `address`
- `status`
- `updated_at`
- `detail_url`

推奨列:

- `brochure_url`
- `station`
- `layout`
- `notes`

## 8. テスト実行

GitHub Actions → Property mailer automation → Run workflow で `verify_only` を実行します。

問題なければ `run_daily` を `dry_run=true` で実行し、Artifactsの `campaign.html`、`campaign.txt`、`validation-issues.json` を確認します。

最後に `dry_run=false` で実行します。デフォルトはSender側の予約送信です。

## 9. 本番スケジュール

`.github/workflows/property-mailer.yml` は月・水・金の09:15 JSTに起動します。Sender側の予約送信を使い、実際の配信は `SENDER_SCHEDULE_TIME_JST` で指定した時刻に予約されます。
