# SNS Club Portal - 設計書

## 1. システムアーキテクチャ

### 1.1 全体構成

```
┌─────────────────────────────────────────────────────────────────┐
│                    SNS Club Portal System                        │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │  入力層   │    │  処理層       │    │  出力層                │ │
│  │          │    │              │    │                        │ │
│  │ Zoom     │───▶│ main.py      │───▶│ YouTube（限定公開）     │ │
│  │ Webhook  │    │ (Orchestrator)│    │ Discord（Webhook通知） │ │
│  │          │    │              │    │ Notion（動画DB更新）    │ │
│  │ Web Form │───▶│ Pipeline     │    │ Notionポータル（公開）  │ │
│  │ (Flask)  │    │ Steps 1-8    │    │                        │ │
│  └──────────┘    └──────────────┘    └────────────────────────┘ │
│                         │                                        │
│                  ┌──────┴──────┐                                 │
│                  │  外部API     │                                 │
│                  │             │                                 │
│                  │ Gemini API  │                                 │
│                  │ Zoom API    │                                 │
│                  │ YouTube API │                                 │
│                  │ Notion API  │                                 │
│                  │ Discord API │                                 │
│                  └─────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 開発・運用オーケストレーション

Claude Code をオーケストレーターとして、以下のエージェント体制で開発・運用する。

```
ユーザー依頼
    │
    ▼
Claude Code (Manager & Agent Orchestrator)
    │
    ├─▶ Explore Agent ── コード探索・調査
    ├─▶ Plan Agent ───── 計画策定・設計
    ├─▶ General Agent ── 汎用タスク実行
    ├─▶ GLM (Z.ai) ──── コード・テキスト生成
    └─▶ Codex (OpenAI) ─ コードレビュー・品質検証
```

#### 実装フロー

```
1. ユーザー依頼を受領
2. タスクを細分化（TaskCreate）
3. GLM でコード実装
4. Codex レビューで品質検証
5. エラー・指摘があれば修正
6. 再レビュー → ok: true になるまで反復
7. ユーザーに報告
```

#### デバッグフロー

```
1. エラー発生 → エラー内容を解析
2. Claude Code / GLM で修正実装
3. テスト実行
4. Codex レビューで最終確認
5. ok: true になるまで反復
```

---

## 2. ディレクトリ構成

```
cs-movie-correction/
├── src/                          # コアモジュール（7ファイル）
│   ├── main.py                  # パイプラインオーケストレーター
│   ├── zoom.py                  # Zoom OAuth & 録画ダウンロード
│   ├── trim.py                  # FFmpeg 無音トリミング
│   ├── thumbnail.py             # Gemini サムネイル生成
│   ├── youtube.py               # YouTube アップロード
│   ├── notion.py                # Notion API ラッパー
│   └── discord.py               # Discord Webhook 通知
│
├── web/                          # 講師入力Webフォーム（Flask）
│   ├── app.py                   # Flask 本体 + パイプライン実行
│   ├── templates/
│   │   ├── form.html            # 入力フォーム
│   │   └── success.html         # 完了画面
│   └── static/
│       ├── css/style.css
│       └── js/form.js
│
├── scripts/                      # ユーティリティ・移行スクリプト群
│   ├── full_pipeline.py         # フルパイプライン実行
│   ├── notion_gallery_final.py  # Gallery View 自動設定
│   ├── populate_*.py            # Notion DB 投入
│   ├── discord_*.py             # Discord スクレイピング
│   └── ...                      # その他ユーティリティ
│
├── templates/                    # サムネイルテンプレート
│   ├── pattern1/                # 対談（2人丸枠）
│   ├── pattern2/                # グルコン（スマホ埋没）
│   └── pattern3/                # 1on1（テキストのみ）
│
├── assets/                       # 画像素材
│   ├── lecturer-images/         # 講師画像（21ファイル）
│   ├── generated/               # 生成済みサムネイル
│   └── gallery/                 # ギャラリー用サムネイル
│
├── docs/                         # ドキュメント
│   ├── specification.md         # 仕様書
│   ├── design.md                # 設計書（本ファイル）
│   └── lecturer-registry.md     # 講師画像レジストリ
│
├── .github/workflows/
│   └── pipeline.yml             # GitHub Actions（6時間ごと実行）
│
├── .env                          # API キー（git管理外）
├── .env.example                  # 環境変数テンプレート
├── .mcp.json                     # Notion MCP Server 設定
├── Procfile                      # Railway デプロイ用
├── requirements.txt              # Python 依存パッケージ
└── .gitignore
```

---

## 3. モジュール設計

### 3.1 モジュール依存関係

```
main.py (Orchestrator)
  ├── zoom.py      ─ Zoom録画取得
  ├── trim.py      ─ 無音トリミング
  ├── thumbnail.py ─ サムネイル生成
  ├── youtube.py   ─ YouTube アップロード
  ├── notion.py    ─ Notion DB 操作
  └── discord.py   ─ Discord 通知

web/app.py (Web Orchestrator)
  ├── thumbnail.py
  ├── youtube.py
  ├── notion.py
  └── discord.py
```

### 3.2 各モジュール詳細

#### main.py — パイプラインオーケストレーター（375行）

| 関数 | 役割 |
|------|------|
| `_process_recording()` | 単一録画の End-to-End 処理 |
| リトライロジック | エラーレコードの自動リトライ（上限3回） |

**処理フロー:**
```
Zoom録画一覧取得 → Notionレコードとマッチング → ダウンロード
→ 無音トリミング → サムネイル生成 → YouTube アップロード
→ Discord 通知 → Notion 更新
```

#### zoom.py — Zoom API クライアント（214行）

| 関数 | 役割 |
|------|------|
| `get_access_token()` | Server-to-Server OAuth（Basic認証） |
| `list_recordings()` | 直近24時間のクラウド録画取得 |
| `download_recording()` | レジューマブルダウンロード（リトライ付き） |

**対象録画タイプ:**
- `shared_screen_with_speaker_view`
- `shared_screen_with_speaker_view(CC)`
- `active_speaker`

#### trim.py — FFmpeg 無音トリミング（297行）

| 関数 | 役割 |
|------|------|
| `_get_duration()` | ffprobe による尺取得 |
| `_find_silence()` | 無音区間検出（閾値: -40dB） |

**トリミング対象:**
- 冒頭の無音（受講生待ち）
- 末尾の無音（録画停止忘れ）

#### thumbnail.py — Gemini サムネイル生成（583行）

| 関数 | 役割 |
|------|------|
| パターンマッピング | 種別 → テンプレートパターン自動選択 |
| Base64エンコード | 講師画像をAPI用に変換 |
| 画像生成 | Gemini API 呼び出し + 結果保存 |

**モデル:** `gemini-3-pro-image-preview`（Thinking mode 有効）

**パターンマッピング:**
| 種別 | テンプレート | 構成 |
|------|------------|------|
| 対談 | pattern1 | 丸枠×2 + テキスト3箇所 |
| グルコン | pattern2 | スマホ画面（下部45%埋没）+ テキスト3箇所 |
| 1on1 | pattern3 | テキストのみ（画像差し替えなし） |

#### youtube.py — YouTube Data API v3 クライアント（274行）

| 関数 | 役割 |
|------|------|
| `get_access_token()` | OAuth リフレッシュトークン交換 |
| `upload_video()` | レジューマブルアップロード（10MBチャンク） |
| `set_thumbnail()` | カスタムサムネイル設定 |

**公開設定:** すべて `unlisted`（限定公開）

#### notion.py — Notion API ラッパー（466行）

| 関数 | 役割 |
|------|------|
| `query_master_records()` | ペンディングレコード取得 |
| `create_video_record()` | 動画アーカイブDB にレコード作成 |
| `update_record_status()` | ステータス更新（成功/エラー/リトライ） |

**マッチングロジック:** Zoom start_time ± 30分以内のレコードを照合

#### discord.py — Discord Webhook クライアント（146行）

| 関数 | 役割 |
|------|------|
| `_build_embed()` | リッチ Embed 構築 |
| `notify()` | 非ブロッキング送信（失敗時ログのみ） |

---

## 4. データフロー設計

### 4.1 正常系パイプライン

```
[トリガー]
  │
  ├─ A. Zoom Webhook受信（自動）
  │     └─ main.py → _process_recording()
  │
  └─ B. Webフォーム送信（手動）
        └─ web/app.py → POST /submit
  │
  ▼
[Step 1] Zoom録画ダウンロード
  │  zoom.py: download_recording()
  │  入力: recording_id
  │  出力: /tmp/recording_{id}.mp4
  │
  ▼
[Step 2] Notionマスターテーブル照合
  │  notion.py: query_master_records()
  │  マッチング: Zoom start_time ± 30分
  │  ステータス → "処理中"
  │
  ▼
[Step 3] 無音トリミング
  │  trim.py: trim()
  │  入力: recording.mp4
  │  出力: recording_trimmed.mp4
  │
  ▼
[Step 4] サムネイル生成
  │  thumbnail.py: generate()
  │  入力: テンプレート + サムネ文言 + 講師画像
  │  出力: thumbnail.png
  │
  ▼
[Step 5] YouTube アップロード
  │  youtube.py: upload_video() + set_thumbnail()
  │  入力: trimmed.mp4 + thumbnail.png
  │  出力: YouTube video_id + URL
  │
  ▼
[Step 6] Discord 通知
  │  discord.py: notify()
  │  入力: タイトル, URL, サムネURL, 講師名, 種別
  │  ※ 失敗時はスキップ（パイプライン続行）
  │
  ▼
[Step 7] Notion 動画DB 更新
  │  notion.py: create_video_record()
  │  入力: タイトル, 種別, 日付, 講師名, YouTubeリンク, サムネイル
  │
  ▼
[Step 8] Notionマスター ステータス更新
     notion.py: update_record_status() → "完了"
     YouTubeリンク記入
```

### 4.2 エラー系フロー

```
エラー発生
  │
  ▼
マスターテーブル更新
  ├── ステータス → "エラー"
  ├── エラー内容を記録
  └── リトライ回数 +1
  │
  ▼
次回トリガー時に自動リトライ
  ├── リトライ回数 < 3 → 再実行
  └── リトライ回数 >= 3 → ステータス → "要手動対応"
```

| エラーパターン | 対応 | パイプライン |
|--------------|------|------------|
| Zoom録画DL失敗 | リトライ | 中断 |
| マッチ失敗 | エラー記録 → リトライ | 中断 |
| サムネ生成失敗（IMAGE_SAFETY等） | リトライ | 中断 |
| YouTube Upload失敗 | リトライ | 中断 |
| Discord通知失敗 | ログ記録 | **続行** |
| Notion更新失敗 | 外部ログ記録 | 中断 |

---

## 5. 外部API 設計

### 5.1 API一覧と認証方式

| サービス | 認証方式 | エンドポイント |
|---------|---------|--------------|
| Zoom | Server-to-Server OAuth (Basic) | `https://zoom.us/oauth/token` |
| YouTube | OAuth 2.0 (Refresh Token) | `https://www.googleapis.com/upload/youtube/v3/` |
| Notion | Integration Token (Bearer) | `https://api.notion.com/v1/` |
| Discord | Webhook URL (認証不要) | `https://discord.com/api/webhooks/{id}/{token}` |
| Gemini | API Key (query param) | `https://generativelanguage.googleapis.com/v1beta/` |

### 5.2 レート制限・注意事項

| サービス | 制限 | 対策 |
|---------|------|------|
| Zoom API | 中程度 | 24時間ウィンドウで取得 |
| YouTube Data API | 10,000 units/day | 動画アップロード = 1,600 units |
| Notion API | 3 req/sec | 処理間に適切なインターバル |
| Gemini API | モデル依存 | IMAGE_SAFETY 時はリトライ |
| Discord Webhook | 30 req/min | 通知は1件ずつ |

---

## 6. Notion データベース設計

### 6.1 DB構成

```
SNS Club Portal (a2e14c7f-b93a-4b81-b25d-d8689241e10a)
│
├── サムネイル生成マスター DB (300f3b0f-ba85-81a7-b097-e41110ce3148)
│   └── 講師入力 → パイプライン処理の入口
│
├── 動画アーカイブ DB (301f3b0f-ba85-815a-a696-d4836fe88bb6)
│   └── Gallery View で公開表示（タグでグループ化）
│
└── テンプレート一覧 DB (301f3b0f-ba85-814e-a61f-e450f95ba7e9)
    └── サムネイルテンプレートの管理
```

### 6.2 マスターテーブル スキーマ

| 列名 | 型 | 入力元 | 説明 |
|------|-----|-------|------|
| タイトル | title | 手動 | YouTube・ポータル表示用 |
| サムネ文言 | rich_text | 手動 | サムネ中央テキスト |
| 種別 | select | 手動 | 1on1 / グルコン / 講座 |
| 開始時間 | date | 手動 | Zoom照合用（±30分） |
| 講師名 | rich_text | 手動 | GUEST表示名 |
| 講師画像1 | files | 手動 | 左側丸枠画像 |
| 講師画像2 | files | 手動 | 右側丸枠画像 |
| ジャンル | select | 手動 | GENRE表示 |
| ステータス | select | 自動 | 入力済み/処理中/完了/エラー/要手動対応 |
| エラー内容 | rich_text | 自動 | エラー詳細 |
| リトライ回数 | number | 自動 | 上限3回 |
| YouTubeリンク | url | 自動 | 完了後に自動記入 |
| 処理日時 | date | 自動 | 処理実行日時 |

### 6.3 動画アーカイブDB スキーマ

| 列名 | 型 | 説明 |
|------|-----|------|
| タイトル | title | 動画名 |
| タグ | multi_select | グループコンサル / 1on1 / 講師対談 |
| 日付 | date | 録画日 |
| 講師名 | select | 講師名 |
| YouTubeリンク | url | 限定公開URL |
| サムネイル | files | サムネイル画像 |

**表示:** Gallery View + タグでグループ化

---

## 7. サムネイルテンプレート設計

### 7.1 テンプレート構成

各パターンは以下の3ファイルで構成される。

```
templates/pattern{N}/
├── base.png      # ベース画像（背景・レイアウト・装飾）
├── prompt.txt    # Gemini API 用プロンプト
└── config.json   # 変数定義・入力画像定義
```

### 7.2 パターン詳細

#### Pattern 1 — 対談（2人丸枠）
```
┌──────────────────────────────────┐
│                                  │
│   [GENRE]                        │
│                                  │
│  (○ 講師A)  ×  (○ 講師B)        │
│                                  │
│      [ サムネ文言 ]               │
│                                  │
│   [GUEST: 講師A × 講師B]         │
│                                  │
└──────────────────────────────────┘
```
- 動的要素: サムネ文言, 講師名(GUEST), ジャンル(GENRE), 右丸枠画像

#### Pattern 2 — グルコン（スマホ埋没）
```
┌──────────────────────────────────┐
│                                  │
│   [GENRE]                        │
│                                  │
│      [ サムネ文言 ]               │
│                                  │
│   [GUEST: 講師名]                │
│                                  │
│  ┌─────────┐                     │
│  │ スマホ   │ ← 下部45%が埋没    │
│  │ 画面    │                     │
└──┴─────────┴─────────────────────┘
```
- 動的要素: サムネ文言, 講師名, ジャンル, スマホ画面画像

#### Pattern 3 — 1on1アーカイブ（テキストのみ）
```
┌──────────────────────────────────┐
│                                  │
│   [講師名]                        │
│                                  │
│      [ サムネ文言（大） ]          │
│                                  │
│   [生徒名]                        │
│                                  │
└──────────────────────────────────┘
```
- 動的要素: 講師名, サムネ文言, 生徒名
- 画像差し替えなし

---

## 8. デプロイ設計

### 8.1 実行環境

| コンポーネント | 環境 | 起動方法 |
|-------------|------|---------|
| 自動パイプライン | GitHub Actions | cron: 6時間ごと + 手動 |
| Webフォーム | Railway | gunicorn (2 workers, timeout 600s) |
| ローカル実行 | macOS | `python src/main.py` |

### 8.2 GitHub Actions ワークフロー

```yaml
# .github/workflows/pipeline.yml
trigger: cron "0 */6 * * *" + workflow_dispatch
環境: Python 3.11 + ffmpeg
実行: python src/main.py
シークレット: 全APIキーを GitHub Secrets に格納
```

### 8.3 Railway デプロイ

```
Procfile: gunicorn web.app:app --bind 0.0.0.0:$PORT --timeout 600 --workers 2
除外: .railwayignore で不要ファイルを除外
```

---

## 9. セキュリティ設計

### 9.1 シークレット管理

| 格納場所 | 用途 |
|---------|------|
| `.env` | ローカル開発用（.gitignore で管理外） |
| GitHub Secrets | GitHub Actions 用 |
| Railway Environment | Webフォーム用 |

### 9.2 API キー一覧

| サービス | 環境変数名 | 状態 |
|---------|----------|:----:|
| Zoom | `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` | 設定済 |
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | 設定済 |
| Notion | `NOTION_TOKEN`, `NOTION_MASTER_DB_ID`, `NOTION_VIDEO_DB_ID` | 設定済 |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` | 設定済 |
| Discord | `DISCORD_WEBHOOK_URL` | **未設定** |

---

## 10. Notion リンク・格納場所・設定ガイド

### 10.1 Notionページ リンク一覧

| ページ / DB | ID | URL |
|------------|-----|-----|
| SNS Club Portal | `a2e14c7f-b93a-4b81-b25d-d8689241e10a` | `https://notion.so/a2e14c7fb93a4b81b25dd8689241e10a` |
| マネタイズ講義 | `263f3b0f-ba85-809b-b668-dfad21e27b6c` | `https://notion.so/263f3b0fba85809bb668dfad21e27b6c` |
| サムネイル生成マスター DB | `300f3b0f-ba85-81a7-b097-e41110ce3148` | `https://notion.so/300f3b0fba8581a7b097e41110ce3148` |
| テンプレート一覧 DB | `301f3b0f-ba85-814e-a61f-e450f95ba7e9` | `https://notion.so/301f3b0fba85814ea61fe450f95ba7e9` |
| 動画アーカイブ DB | `301f3b0f-ba85-815a-a696-d4836fe88bb6` | `https://notion.so/301f3b0fba85815aa696d4836fe88bb6` |

### 10.2 コード内での設定箇所

| 設定項目 | ファイル | 環境変数 |
|---------|--------|---------|
| マスターDB ID | `src/notion.py` | `NOTION_MASTER_DB_ID` |
| 動画アーカイブDB ID | `src/notion.py` | `NOTION_VIDEO_DB_ID` |
| Notion Token | `src/notion.py` | `NOTION_TOKEN` |
| MCP Server Token | `.mcp.json` | `OPENAPI_MCP_HEADERS` 内 |

### 10.3 環境変数の設定場所

#### ローカル開発
```bash
# .env ファイル（プロジェクトルート）
NOTION_TOKEN=ntn_xxxxx
NOTION_MASTER_DB_ID=300f3b0f-ba85-81a7-b097-e41110ce3148
NOTION_VIDEO_DB_ID=301f3b0f-ba85-815a-a696-d4836fe88bb6
```

#### GitHub Actions
```
Settings → Secrets and variables → Actions → Repository secrets
  ├── NOTION_TOKEN
  ├── NOTION_MASTER_DB_ID
  ├── NOTION_VIDEO_DB_ID
  ├── ZOOM_ACCOUNT_ID
  ├── ZOOM_CLIENT_ID
  ├── ZOOM_CLIENT_SECRET
  ├── YOUTUBE_CLIENT_ID
  ├── YOUTUBE_CLIENT_SECRET
  ├── YOUTUBE_REFRESH_TOKEN
  ├── GEMINI_API_KEY
  └── DISCORD_WEBHOOK_URL
```
**URL:** `https://github.com/SnsCool/cs-movie-correction/settings/secrets/actions`

#### Railway
```
Dashboard → cs-movie-correction → Variables
```

#### Claude Code MCP Server
```json
// .mcp.json（プロジェクトルート）
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": {
        "OPENAPI_MCP_HEADERS": "{\"Authorization\":\"Bearer ntn_xxxxx\",\"Notion-Version\":\"2022-06-28\"}"
      }
    }
  }
}
```

### 10.4 Notion Integration 設定

Notion API を使用するには、Integration の設定と DB への接続が必要。

**設定場所:** `https://www.notion.so/my-integrations`

**接続手順:**
1. Notion Integration ページでトークン発行
2. 各データベースページを開く → `...` → `接続` → 作成した Integration を選択
3. `.env` に `NOTION_TOKEN` を設定

---

## 11. 未実装・保留事項

| # | 項目 | 状態 | 備考 |
|---|------|:----:|------|
| 1 | Discord Webhook URL | 未設定 | `.env` に `DISCORD_WEBHOOK_URL` を追加 |
| 2 | Zoom Webhook Secret | 未設定 | Zoom Marketplace で設定 |
| 3 | GitHub Actions 自動トリガー | 未構築 | Zoom Webhook → GitHub Actions 連携 |
| 4 | Gallery View 設定 | **完了** | `scripts/notion_gallery_final.py` |
| 5 | Nano Banana Pro 料金プラン確認 | 未確定 | 1K/2K: $0.134/枚、4K: $0.24/枚 |

---

## 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-02-20 | 初版作成 |
