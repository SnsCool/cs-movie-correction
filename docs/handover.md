# SNS Club Portal - 引き継ぎ書

## 1. システム概要

Zoom録画完了後、サムネイル生成→YouTube限定公開→Discord通知→Notion更新を全自動化するシステム。

---

## 2. アクセス情報・リンク一覧

### 2.1 GitHub（コード管理）

| 項目 | リンク / 値 |
|------|------------|
| リポジトリ | https://github.com/SnsCool/cs-movie-correction |
| GitHub Actions | https://github.com/SnsCool/cs-movie-correction/actions |
| Secrets 設定 | https://github.com/SnsCool/cs-movie-correction/settings/secrets/actions |
| プッシュ用アカウント | **SnsCool** |

### 2.2 Railway（Webフォーム）

| 項目 | リンク / 値 |
|------|------------|
| 本番フォーム（講師がアクセス） | https://sns-club-portal-production.up.railway.app |
| ダッシュボード | https://railway.com/project/042167f6-b6a4-4dcf-8e45-5a8ad7420518 |
| 環境変数設定 | ダッシュボード → Variables |
| プラン | Hobby（チーム招待は Pro プラン以上が必要） |

### 2.3 YouTube（動画アップロード先）

| 項目 | 値 |
|------|-----|
| チャンネル名 | **SnsCool AI** |
| 公開設定 | 限定公開（unlisted） |

### 2.4 Notion（データ管理・ポータル公開）

| 用途 | リンク |
|------|-------|
| ポータルトップ | https://notion.so/a2e14c7fb93a4b81b25dd8689241e10a |
| サムネイル生成マスターDB（講師入力先） | https://notion.so/300f3b0fba8581a7b097e41110ce3148 |
| 動画アーカイブDB（全ジャンル統合） | https://notion.so/306f3b0fba8581dfb1d5c50fa215c62a |
| 1on1 アーカイブ | https://notion.so/306f3b0fba8580858fa6d3f642d9dc49 |
| グルコン / 講師対談 アーカイブ | https://notion.so/306f3b0fba858000bc41eaed2d834e21 |
| マネタイズ講義 | https://notion.so/263f3b0fba85809bb668dfad21e27b6c |
| テンプレート一覧DB | https://notion.so/301f3b0fba85814ea61fe450f95ba7e9 |
| Integration 設定 | https://www.notion.so/my-integrations |

### 2.5 Zoom

| 項目 | 値 |
|------|-----|
| 認証方式 | Server-to-Server OAuth |
| 設定場所 | https://marketplace.zoom.us/ |
| Webhook Secret | **未設定** |

### 2.6 Discord

| 項目 | 値 |
|------|-----|
| 通知方式 | Webhook（共通1チャンネル） |
| Webhook URL | `.env` の `DISCORD_WEBHOOK_URL` に設定済み |

### 2.7 Gemini API（サムネイル生成）

| 項目 | 値 |
|------|-----|
| モデル | `gemini-3-pro-image-preview` |
| サービス名 | Nano Banana Pro |

---

## 3. 現状の運用フロー

### 3.1 全体の流れ

```
講師がWebフォームで入力
  (https://sns-club-portal-production.up.railway.app)
        │
        ▼
Notion マスターDB にレコード作成（ステータス: 入力済み）
        │
        ▼
Zoom で講義を実施・録画
        │
        ▼
GitHub Actions（6時間ごと）or 手動実行
  python src/main.py
        │
        ├── ① Zoom録画一覧を取得（直近24時間）
        ├── ② マスターDBの「入力済み」レコードと±30分で照合
        ├── ③ ステータス → 「処理中」
        ├── ④ 録画ダウンロード
        ├── ⑤ 冒頭・末尾の無音トリミング（FFmpeg）
        ├── ⑥ サムネイル生成（Gemini API）
        ├── ⑦ YouTube に限定公開アップロード + サムネ設定
        ├── ⑧ Discord に通知投稿
        ├── ⑨ Notion 動画アーカイブDB にレコード作成
        │     └── ジャンル別DB にもデュアルライト
        ├── ⑩ マスターDB ステータス → 「完了」+ YouTubeリンク記入
        │
        ▼
受講生が Notion ポータル（Gallery View）から YouTube で視聴
```

### 3.2 ジャンル別の格納先

パイプライン完了時、動画は以下の2箇所に同時に書き込まれる（デュアルライト）。

| カテゴリ | メインアーカイブDB | ジャンル別DB |
|---------|:----------------:|:----------:|
| 1on1 | ○ | 1on1アーカイブDB |
| グルコン | ○ | グルコンアーカイブDB |
| 講師対談 | ○ | グルコンアーカイブDB |
| 講座 | ○ | マネタイズDB |

### 3.3 エラー時の動き

```
エラー発生
  ├── マスターDB ステータス → 「エラー」
  ├── エラー内容を記録
  └── リトライ回数 +1
        │
        ▼
次回パイプライン実行時に自動リトライ
  ├── リトライ回数 < 3 → 再実行
  └── リトライ回数 >= 3 → ステータス → 「要手動対応」
```

Discord通知失敗のみ例外 → ログ記録してパイプライン続行。

---

## 4. 環境変数一覧

### 4.1 必要な環境変数（15個）

| 変数名 | 用途 | 設定場所 |
|--------|------|---------|
| `ZOOM_ACCOUNT_ID` | Zoom OAuth | .env / Secrets |
| `ZOOM_CLIENT_ID` | Zoom OAuth | .env / Secrets |
| `ZOOM_CLIENT_SECRET` | Zoom OAuth | .env / Secrets |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth | .env / Secrets |
| `YOUTUBE_CLIENT_SECRET` | YouTube OAuth | .env / Secrets |
| `YOUTUBE_REFRESH_TOKEN` | YouTube OAuth | .env / Secrets |
| `NOTION_TOKEN` | Notion API | .env / Secrets / .mcp.json |
| `NOTION_MASTER_DB_ID` | マスターDB | .env / Secrets |
| `NOTION_VIDEO_DB_ID` | メインアーカイブDB | .env / Secrets |
| `NOTION_1ON1_DB_ID` | 1on1ジャンルDB | .env / Secrets |
| `NOTION_GRUCON_DB_ID` | グルコンジャンルDB | .env / Secrets |
| `NOTION_MONETIZE_DB_ID` | マネタイズジャンルDB | .env / Secrets |
| `GEMINI_API_KEY` | Gemini API | .env / Secrets |
| `GEMINI_MODEL` | Geminiモデル名 | .env / Secrets |
| `DISCORD_WEBHOOK_URL` | Discord通知 | .env / Secrets |

### 4.2 設定が必要な3つの場所

| 環境 | 設定場所 | 用途 |
|------|---------|------|
| ローカル | `.env` | 開発・手動実行 |
| GitHub Actions | Settings → Secrets → Actions | 自動パイプライン |
| Railway | Dashboard → Variables | Webフォーム |

---

## 5. コードベース構成

```
src/                  ← コアモジュール
  main.py             ← パイプラインオーケストレーター
  zoom.py             ← Zoom録画取得
  trim.py             ← 無音トリミング
  thumbnail.py        ← Geminiサムネイル生成
  youtube.py          ← YouTubeアップロード
  notion.py           ← Notion API（ジャンル別ルーティング含む）
  discord.py          ← Discord通知

web/                  ← 講師入力Webフォーム（Flask → Railway）
  app.py
  templates/form.html
  templates/success.html
  static/css/style.css
  static/js/form.js

templates/            ← サムネイルテンプレート
  pattern1/           ← 対談（丸枠×2）
  pattern2/           ← グルコン（スマホ埋没45%）
  pattern3/           ← 1on1（テキストのみ）

scripts/              ← ユーティリティ（移行・メンテナンス用）

docs/                 ← ドキュメント
  specification.md    ← 仕様書
  design.md           ← 設計書
  requirements.md     ← 要件定義書
  lecturer-registry.md ← 講師画像レジストリ
  handover.md         ← 引き継ぎ書（本ファイル）
```

---

## 6. 講師一覧（8名）

| # | 講師名 | 画像 |
|---|--------|:----:|
| 1 | 陸 | `assets/lecturer-images/` に格納 |
| 2 | たっちー | 同上 |
| 3 | しゅうへい | 同上 |
| 4 | はなこ | 同上 |
| 5 | ちゃみ | 同上 |
| 6 | かりん | 同上 |
| 7 | じゅん | 同上 |
| 8 | みくぽん | 同上 |

講師の追加・削除は `assets/lecturer-images/` に画像を追加するだけで対応可能。
命名規則: `{連番}_{講師名}_{人数パターン}.png`

---

## 7. 手動操作が必要なケース

| ケース | 対処方法 |
|--------|---------|
| ステータスが「要手動対応」 | NotionマスターDBのエラー内容を確認し手動で修正 |
| サムネ生成がIMAGE_SAFETYでブロック | 講師画像を変更して再実行 |
| YouTube トークン期限切れ | Google Cloud Console でリフレッシュトークンを再取得 |
| パイプラインを今すぐ実行したい | GitHub Actions → Run workflow（手動実行） |
| Gallery Viewの設定変更 | `scripts/notion_gallery_final.py` or Notion UIから手動 |

---

## 8. 未完了・保留タスク

| # | タスク | 状態 | 備考 |
|---|--------|:----:|------|
| 1 | Zoom Webhook Secret 設定 | 未設定 | https://marketplace.zoom.us/ で設定 |
| 2 | GitHub Secrets に全環境変数を設定 | 要確認 | 特にジャンルDB ID 3つの追加が必要 |
| 3 | Railway に環境変数を設定 | 要確認 | ジャンルDB ID 3つの追加が必要 |
| 4 | E2Eテスト完了 | 進行中 | Phase 5 |
| 5 | Gemini API 料金プラン確認 | 未確定 | |

---

## 9. 開発フェーズ進捗

| Phase | 内容 | 状態 |
|-------|------|:----:|
| 1 | Notionテーブル設計 + ポータル構築 | 完了 |
| 2 | 自動化パイプライン | 完了 |
| 3 | 講師入力Webフォーム + Railway デプロイ | 完了 |
| 4 | エラーハンドリング + リトライ機構 | 完了 |
| 5 | E2Eテスト + 運用開始 | **進行中** |

---

## 10. 処理済み動画一覧（パイプライン実績）

| # | 講師 | ジャンル | YouTube |
|---|------|---------|---------|
| 1 | みくぽん | グループコンサル | https://youtu.be/abr1g7gzzyw |
| 2 | かりん | 1on1 | https://youtu.be/P58XeyqVXSc |
| 3 | ちゃみ | グループコンサル | https://youtu.be/1IZh0QFkUmI |
| 4 | はなこ | 1on1 | https://youtu.be/RnJIkc6arDE |
| 5 | たっちー | 講師対談 | https://youtu.be/Nn8GVLaMgXY |

---

## 改訂履歴

| 日付 | 内容 |
|------|------|
| 2026-02-22 | 初版作成 |
