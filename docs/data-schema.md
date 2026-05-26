# データ仕様

## 物件データ

CSV/JSON/XLSXをサポートします。Google Driveフォルダ内の最新更新ファイルが読み込まれます。

| 列名 | 必須 | 例 | 説明 |
|---|---:|---|---|
| `property_id` | yes | `P-1001` | 物件の一意ID |
| `title` | yes | `渋谷区 新築マンション 2LDK` | 物件名 |
| `price` | yes | `92800000` | 価格。数値 |
| `area` | yes | `62.4` | 面積㎡ |
| `address` | yes | `東京都渋谷区...` | 所在地 |
| `status` | yes | `active` | active/available/公開/募集中/販売中のみ配信対象 |
| `updated_at` | yes | `2026-05-20T09:00:00+09:00` | 更新日時 |
| `detail_url` | yes | `https://...` | HTTPS必須 |
| `brochure_url` | no | `https://...pdf` | 資料URL。HTTPS必須 |
| `station` | no | `渋谷駅 徒歩7分` | 最寄り |
| `layout` | no | `2LDK` | 間取り |
| `notes` | no | `南向き` | 備考 |

## fingerprint

重複防止には、以下の項目を連結してSHA-256化したfingerprintを使います。

- property_id
- title
- price
- area
- address
- status
- updated_at
- detail_url
- brochure_url

同じ物件でも価格や更新日が変わった場合は新しい案内対象になります。

## 配信先

本番ではSenderのGroupまたはSegmentで管理します。GitHub側に1000人分の顧客CSVを保存しない設計です。

ローカル検証では `data/sample_recipients.csv` を使用できます。
