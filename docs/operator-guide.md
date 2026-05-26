# 運用ガイド

## 毎日の使い方

通常はGitHub Actionsが月・水・金に自動実行します。運用者が毎回コマンドを実行する必要はありません。

## 配信前チェック

GitHub ActionsのArtifactsに以下が保存されます。

- `campaign-plan.json`: 対象物件ID、fingerprint、audience
- `campaign.html`: 実際に送るHTML
- `campaign.txt`: 実際に送るテキスト版
- `validation-issues.json`: チェック結果
- `run-result.json`: 実行結果

`validation-issues.json` に `error` がある場合、配信は停止します。`warning` は配信停止にはなりませんが、確認対象です。

## 手動で検証だけ行う

GitHub Actions → Property mailer automation → Run workflow:

- mode: `verify_only`
- dry_run: `true`

## 手動でドライランする

- mode: `run_daily`
- dry_run: `true`

この場合Senderには送信されません。ただし `RECORD_DRY_RUNS=true` の場合は重複防止ログに記録されます。本番では通常 `false` です。

## 問い合わせ返信

GitHub Actionsから手動実行できます。

mode: `reply_inquiry`

inquiry_payload例:

```json
{"email":"customer@example.com","name":"山田太郎","property_id":"P-1001"}
```

Cloudflare Workerの `/webhook/inquiry` に同じJSONをPOSTすると、WorkerからGitHub Actionsを発火できます。

## 重複配信を確認する

Cloudflare D1の `sent_log` を確認します。

```bash
cd worker
npx wrangler d1 execute property-mailer-db --remote --command "select * from sent_log order by id desc limit 20;"
```

## 二重起動を確認する

```bash
cd worker
npx wrangler d1 execute property-mailer-db --remote --command "select * from job_locks;"
```

ロックが残っている場合でも、有効期限を過ぎると次回起動時に自動削除されます。

## 配信停止依頼

顧客から配信停止依頼が来た場合は、Sender側のSubscriberまたはGroup/Segmentから除外します。メール本文には「配信停止」と返信する案内を入れています。
