# Indeed求人作る君

企業URLと採用依頼文から、AIが求職者にとって魅力的なIndeed形式の求人票を自動生成するシステム。

## セットアップ

### 1. APIキーの設定

```bash
copy .env.example .env
```

`.env` を開いて Anthropic API キーを設定:
```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. Python環境 & パッケージインストール

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 起動

```bash
venv\Scripts\uvicorn main:app --reload
```

または `start.bat` をダブルクリック（初回は自動でvenv作成＆パッケージインストール）。

### 4. ブラウザでアクセス

http://localhost:8000

---

## 使い方

### 求人作成タブ

| 入力項目 | 必須 | 説明 |
|---------|------|------|
| 企業URL | ✅ | 企業の公式サイト（AIが自動でスクレイピング） |
| 採用依頼文 | ✅ | メール本文などをそのまま貼り付け |
| 応募URL | 任意 | Indeed上の応募先URL |
| 担当者情報 | 任意 | 担当者名・電話・メール |

「AIで求人票を生成する」→ 内容確認・編集 → 「保存する」

### 保存済み求人タブ

- 保存した求人の一覧表示
- チェックボックスで複数選択
- **CSVエクスポート**: Indeed形式のCSVファイルをダウンロード
- 編集・削除

## CSV出力フィールド

求人タイトル / 会社名 / 都道府県 / 市区町村 / 雇用形態 / 給与（下限・上限・単位） / 仕事内容 / 応募資格 / 歓迎スキル / 勤務時間 / 休日休暇 / 福利厚生 / 選考プロセス / 応募URL / 担当者情報 / 会社URL / 作成日
