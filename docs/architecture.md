# アーキテクチャ

## 目的

1000人以上の顧客に週3回、最新の不動産物件情報を安定して配信します。配信前に自動ダブルチェックを行い、誤配信・重複配信・Secret漏洩を防ぎます。

## 全体像

```mermaid
flowchart TB
  subgraph Source[データソース]
    GDrive[Google Drive\n物件DB CSV/JSON/XLSX]
    SenderList[Sender Groups/Segments\n配信先リスト]
  end

  subgraph GitHub[GitHub]
    Actions[GitHub Actions\n月水金 09:15 JST]
    Python[Python Pipeline\nDrive取得・検証・HTML生成]
    Artifacts[Audit Artifacts\nplan/html/txt/issues]
  end

  subgraph Cloudflare[Cloudflare]
    Worker[Worker API\nSecret Gateway]
    D1[(D1\n送信ログ・ジョブロック)]
    Cron[Worker Cron\nバックアップ発火]
  end

  subgraph Sender[Sender.net]
    Campaign[Campaign API\n作成・予約・即時送信]
    Transactional[Transactional API\n問い合わせ返信]
  end

  Customers[顧客]
  Inquiry[問い合わせ]

  GDrive --> Actions --> Python
  Python --> Worker
  Worker <--> D1
  Worker --> Campaign --> Customers
  Inquiry --> Worker --> Actions
  Python --> Worker --> Transactional --> Customers
  Python --> Artifacts
  Cron --> Worker --> Actions
  SenderList --> Campaign
```

## なぜCloudflare D1を使うか

GitHub Actionsのスケジュール実行は便利ですが、実行環境は毎回作り直されます。送信済みログやジョブロックをローカルSQLiteだけに置くと、次回実行時に重複判定が不安定になります。そのため、本番ではCloudflare D1に以下を保存します。

- `sent_log`: audienceと物件fingerprintの組み合わせを一意に保存
- `job_locks`: 二重起動防止
- `webhook_events`: 問い合わせWebhookの監査ログ

## 配信フロー

```mermaid
sequenceDiagram
  participant GH as GitHub Actions
  participant PY as Python Pipeline
  participant GD as Google Drive
  participant CF as Cloudflare Worker
  participant D1 as Cloudflare D1
  participant SN as Sender API

  GH->>PY: run-daily
  PY->>GD: 最新物件ファイル取得
  PY->>PY: 1回目チェック データ整合性
  PY->>CF: lock/acquire
  CF->>D1: job_locks insert
  PY->>CF: state/filter-unsent
  CF->>D1: sent_log照会
  PY->>PY: HTML/TXT生成
  PY->>PY: 2回目チェック レンダリング・配信文面
  PY->>CF: sender/campaign
  CF->>SN: campaigns create + schedule/send
  PY->>CF: state/mark-sent
  CF->>D1: sent_log insert
  PY->>GH: audit artifact保存
  PY->>CF: lock/release
```

## 問い合わせ返信フロー

```mermaid
sequenceDiagram
  participant User as 顧客/フォーム
  participant CF as Cloudflare Worker
  participant GH as GitHub Actions
  participant PY as Python Pipeline
  participant GD as Google Drive
  participant SN as Sender Transactional API

  User->>CF: /webhook/inquiry
  CF->>GH: workflow_dispatch reply_inquiry
  GH->>PY: reply-inquiry
  PY->>GD: 対象物件取得
  PY->>PY: 物件資料URLと内容チェック
  PY->>CF: /sender/transactional
  CF->>SN: /message/send
  SN->>User: 資料メール
```

## Secret設計

```mermaid
flowchart LR
  GHSecrets[GitHub Secrets\nWORKER_SHARED_SECRET\nAUTOMATION_WORKER_URL\nGOOGLE_SERVICE_ACCOUNT_JSON] --> GHA[GitHub Actions]
  CFSecrets[Cloudflare Worker Secrets\nSENDER_API_TOKEN\nWORKER_SHARED_SECRET\nGITHUB_TOKEN] --> Worker[Worker]
  GHA -- Bearer WORKER_SHARED_SECRET --> Worker
  Worker -- Bearer SENDER_API_TOKEN --> Sender[Sender API]
```

Sender API TokenはCloudflare Workerだけに保存するのが推奨です。GitHub ActionsにはWorker呼び出し用の共有Secretだけを置きます。

## 失敗時の考え方

- Worker認証失敗: `WORKER_SHARED_SECRET` の不一致
- Sender 401/403: Cloudflare側 `SENDER_API_TOKEN` の期限切れ・権限不足
- Drive取得失敗: Googleサービスアカウントの共有権限不足
- 重複送信の疑い: D1の `sent_log` を確認
- 二重起動: D1の `job_locks` とGitHub Actionsの `concurrency` を確認
