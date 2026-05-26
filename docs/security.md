# セキュリティ設計

## 原則

- APIキーの実値はリポジトリに保存しません。
- Sender API TokenはCloudflare Worker Secretに保存します。
- GitHub ActionsはSender API Tokenを直接持たず、WorkerをBearer認証で呼びます。
- Cloudflare Workerは認証失敗時にSecret実値を返しません。
- 送信済みログにはAPIキーや個人情報を保存しません。

## Secretの保存先

| Secret | 推奨保存先 | 理由 |
|---|---|---|
| `SENDER_API_TOKEN` | Cloudflare Worker Secret | Senderの高権限TokenをGitHubに置かない |
| `WORKER_SHARED_SECRET` | Cloudflare + GitHub | Worker呼び出し認証用 |
| `GITHUB_TOKEN` | Cloudflare Worker Secret | Worker Cron/WebhookからActionsを発火 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | GitHub Actions Secret | Drive読み取り専用でPythonが使う |
| `CLOUDFLARE_API_TOKEN` | GitHub Actions Secret | Worker自動デプロイ時のみ |

## APIキーを貼ってしまった場合

1. Sender側で該当API Tokenを削除します。
2. Cloudflare側で該当API TokenをRevokeします。
3. 新しいTokenを作成します。
4. Cloudflare Worker Secretを更新します。
5. GitHubやチャット、ドキュメントに実値が残っていないか確認します。

## Worker認証失敗の切り分け

Workerが `unauthorized` を返す場合、最初に疑うのは `WORKER_SHARED_SECRET` の不一致です。Cloudflare側のSecretとGitHub Actions側のSecretが同じ文字列か確認してください。

GitHub TokenやSender Tokenを疑うのは、Worker認証が通った後にGitHub APIまたはSender APIが401/403を返す場合です。

## 個人情報

顧客メールアドレスは原則Sender側で管理します。ローカルCSVでテストする場合を除き、GitHub Artifactsに顧客リストを出力しないでください。

## 監査

GitHub Actions Artifactsには、送信予定本文、対象物件ID、validation結果、実行結果が保存されます。トラブル時はまずArtifactsとCloudflare D1を確認します。
