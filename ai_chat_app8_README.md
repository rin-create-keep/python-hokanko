# Fusion AI Hub

概要  
Fusion AI Hub は、Streamlit 上で動作するマルチAI統合型チャットアプリケーションです。  
OpenAI、Anthropic、Google Gemini の各モデルに対応し、チャット・画像生成・音声文字起こし・議事録作成・PDF問題生成・タスク管理・スケジュール管理・ルーム管理・会話共有などを一つのアプリに統合しています。

会話、タスク、スケジュール、チャット履歴はファイルベースで永続化され、ブラウザのリロードやサーバー再起動後も状態を保持します。

---

# 主な機能

## 1. マルチモデル対応チャット

・ GPT-3.5  
・ GPT-4o  
・ Claude 3.5 Sonnet（Haiku API指定）  
・ Gemini Flash  

ストリーミング出力対応  
Temperature 調整可能  
トークン数簡易計算によるコスト表示  

---

## 2. ルーム管理機能

・ 複数ルーム作成  
・ ルームごとにメンバー管理  
・ ルーム単位で会話・タスク・スケジュールを分離  
・ ルーム編集 / 削除  

---

## 3. タスク管理

・ メンバー追加 / 削除  
・ タスク新規作成  
・ 担当者割り当て  
・ 期限設定  
・ ステータス管理（未着手 / 進行中 / 完了）  
・ ルーム単位で独立管理  

---

## 4. スケジュール管理

・ 手動スケジュール追加  
・ 日時 / 場所 / 参加者設定  
・ アクションアイテム管理  
・ Googleカレンダー用URL自動生成  
・ 議事録から自動抽出  

---

## 5. 音声議事録生成

・ 音声ファイルアップロード  
・ Whisperによる文字起こし  
・ GPTによる議事録自動生成  
・ スケジュール抽出  
・ タスク自動生成  
・ テキストダウンロード対応  

---

## 6. PDFから問題生成

・ PDFアップロード  
・ テキスト抽出  
・ 元資料に基づいた同種問題を5問生成  

---

## 7. 画像機能

・ テキストから画像生成（gpt-image-1）  
・ 生成画像の表示・ダウンロード  
・ アップロード画像を含めたチャット  
・ 生成済み画像の内容説明  

---

## 8. 会話共有機能

・ 会話をBase64エンコード  
・ URLパラメータで共有  
・ 最大文字数制限による安全な共有  

---

## 9. チャット履歴管理

・ ルーム単位で履歴保存  
・ 最大50件保存  
・ 履歴ロード / 削除  

---

## 10. ファイルベース永続化

保存対象:
・ rooms  
・ current_room  
・ team_members  

保存先:
app_state.json  

F5リロード、ブラウザ再起動、サーバー再起動後もデータを保持します。

---

# コスト計算

文字数 ÷ 4 でトークンを概算。  
モデルごとに input / output 単価を設定。  

Gemini は 128,000 トークン超過時に料金倍増計算。

---

# 動作環境

Python 3.9以上  

対応OS:
・ Windows  
・ macOS  
・ Linux  

必要ライブラリ:
- streamlit  
- openai  
- anthropic  
- google-generativeai  
- pypdf  
- python-dotenv

---

# インストール

```bash
pip install streamlit openai anthropic google-generativeai pypdf python-dotenv
```

---

# 環境変数設定

.env または Streamlit Secrets に以下を設定してください。

```
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
```

Streamlit Cloud 使用時は `secrets.toml` に設定してください。

---

# 実行方法

```bash
streamlit run app.py
```

---

# データ構造概要

## ルーム構造

```python
rooms = {
    "default": {
        "name": "デフォルトルーム",
        "members": [],
        "messages": [],
        "tasks": [],
        "schedules": [],
        "chat_histories": []
    }
}
```

## メッセージ形式

```python
("assistant", {"type": "text", "content": "回答内容"})
("assistant", {"type": "image", "content": "base64文字列"})
("assistant", {"type": "minutes", "content": "議事録テキスト"})
```

---

# 注意事項

・ APIキー未設定時は動作しません  
・ Claudeは画像入力非対応  
・ 共有URLには要約済みテキストのみ含まれます  
・ 画像データはBase64形式で保存されます  

---

# 今後の拡張例

・ データベース永続化  
・ ユーザー認証機能  
・ Slack連携  
・ Google Calendar API直接連携  
・ ベクトル検索による会話検索  

---

# ライセンス

MIT License
