# My Great ChatGPT

Streamlit を用いたマルチモデル対応チャットアプリケーションです。  
GPT / Claude / Gemini に対応し、画像生成、音声文字起こし、議事録生成、PDF問題生成、タスク管理、スケジュール管理、ルーム機能などを統合しています。

---

## 主な機能

### 1. マルチLLM対応
- GPT-3.5 / GPT-4o
- Claude 3.5 Haiku
- Gemini Flash

ストリーミング出力対応。

---

### 2. ルーム機能
- ルームごとに会話履歴を管理
- ルームごとにタスク・スケジュールを分離
- メンバー追加・削除
- ルーム削除・編集

---

### 3. タスク管理
- メンバー単位でタスク割り振り
- ステータス管理（未着手 / 進行中 / 完了）
- 期限設定
- ルームごとに独立管理

---

### 4. スケジュール管理
- 手動スケジュール追加
- 議事録から自動抽出
- Googleカレンダー連携URL生成
- アクションアイテム自動タスク化

---

### 5. 音声議事録生成
- 音声ファイルを文字起こし（Whisper）
- 議事録自動生成
- スケジュール抽出
- タスク自動生成
- ダウンロード機能

---

### 6. PDFから問題生成
- PDF内容を解析
- 同種の練習問題を自動生成

---

### 7. 画像機能
- テキストから画像生成
- 画像アップロード対応
- 画像内容説明
- ダウンロード機能

---

### 8. 会話共有
- 会話履歴をBase64圧縮
- URLパラメータ共有
- 最大文字数制限対応

---

### 9. コスト計算
- モデル別料金設定
- 入力・出力トークン推定
- セッションごとのコスト表示

---

## 必要環境

- Python 3.9+
- Streamlit
- OpenAI SDK
- Anthropic SDK
- Google Generative AI SDK
- pypdf

---

## インストール

```bash
pip install streamlit openai anthropic google-generativeai pypdf python-dotenv
```

---

## 環境変数設定

`.env` または Streamlit Secrets に以下を設定してください。

```
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
```

Streamlit Cloud 使用時は `secrets.toml` に設定してください。

---

## 起動方法

```bash
streamlit run app.py
```

---

## アーキテクチャ概要

- `session_state` を用いた状態管理
- ルーム単位でデータ構造を分離
- メッセージ形式は以下の辞書形式

```python
("assistant", {"type": "text", "content": "内容"})
("assistant", {"type": "image", "content": "base64文字列"})
("assistant", {"type": "minutes", "content": "議事録"})
```

---

## データ構造例

```python
rooms = {
    "room_0": {
        "name": "開発チーム",
        "members": ["Alice", "Bob"],
        "messages": [],
        "tasks": [],
        "schedules": []
    }
}
```

---

## コスト計算ロジック

- 文字数 ÷ 4 で簡易トークン推定
- モデルごとに単価設定
- Geminiは128k超過時に料金倍増

---

## 注意事項

- APIキー未設定時は動作しません
- Geminiは画像をBase64ではなく inline_data 形式で送信
- Claudeは画像非対応
- 共有URLは要約された会話のみ含まれます

---

## ライセンス

MIT License
自由に改変・利用・再配布可能です。
