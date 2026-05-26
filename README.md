# Real Estate Sender Automation

Google Drive上の物件データを取り込み、配信前に自動ダブルチェックを行い、Sender.netで週3回の物件案内メールを配信するための運用基盤です。問い合わせが来た場合は、物件資料URL付きのTransactionalメールを自動返信できます。

SecretをGitHubに置きすぎない設計です。Sender API Tokenなどの高権限SecretはCloudflare WorkerのSecretとして保存し、GitHub ActionsはCloudflare Workerを安全に呼び出します。

## できること

- Google DriveまたはローカルCSV/JSON/XLSXから物件データを取得
- 物件データのスキーマ検証、価格・面積・URL・公開状態チェック
- HTML/TXTメール生成後の二重チェック
- Cloudflare D1による送信済み物件の重複防止
- Cloudflare D1によるジョブロックで二重起動を防止
- Sender APIによるキャンペーン作成、予約送信、即時送信
- Sender Transactional APIによる問い合わせ返信
- GitHub Actionsの週3回スケジュールと手動実行
- Cloudflare Worker CronからGitHub Actionsを発火する冗長構成
- CI、テスト、README、運用ドキュメント、Mermaid構成図

## アーキテクチャ概要

```mermaid
flowchart LR
  Drive[Google Drive\n物件CSV/JSON/XLSX] --> GHA[GitHub Actions\n週3回・手動実行]
  GHA --> Py[Python mailer\n検証・生成・監査]
  Py --> Worker[Cloudflare Worker\nSecret Gateway]
  Worker --> D1[(Cloudflare D1\n送信ログ・ロック)]
  Worker --> Sender[Sender.net API\nCampaign / Transactional]
  Sender --> Customers[顧客 1000+]
  Inquiry[問い合わせWebhook/手動入力] --> Worker
  Worker --> GHA
  GHA --> Py
  Py --> Worker
```

## 重要

チャットに貼られたCloudflare/SenderのAPIキーは露出済みとして扱い、実運用前にローテーションしてください。このリポジトリには実値を保存していません。

## 初期セットアップ

詳細は `docs/setup.md` を確認してください。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m property_mailer run-daily --dry-run
```
