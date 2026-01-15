import os
import streamlit as st
from openai import OpenAI
import anthropic
import google.generativeai as genai
import json
import base64
from datetime import datetime
from urllib.parse import urlencode, parse_qs
from io import BytesIO

###### dotenv を利用しない場合は消してください ######
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    import warnings
    warnings.warn("dotenv not found. Please make sure to set your environment variables manually.", ImportWarning)
################################################


MODEL_PRICES = {
    "input": {
        "gpt-3.5-turbo": 0.5 / 1_000_000,
        "gpt-4o": 5 / 1_000_000,
        "claude-3-5-sonnet-20241022": 3 / 1_000_000,
        "gemini-1.5-pro-latest": 3.5 / 1_000_000
    },
    "output": {
        "gpt-3.5-turbo": 1.5 / 1_000_000,
        "gpt-4o": 15 / 1_000_000,
        "claude-3-5-sonnet-20241022": 15 / 1_000_000,
        "gemini-1.5-pro-latest": 10.5 / 1_000_000
    }
}

def get_message_counts(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)

def init_page():
    st.set_page_config(
        page_title="My Great ChatGPT",
        page_icon="🤗"
    )
    st.header("My Great ChatGPT 🤗")
    st.sidebar.title("Options")


def save_chat_history():
    """現在の会話を履歴に保存"""
    if "message_history" not in st.session_state or len(st.session_state.message_history) <= 1:
        return
    
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = []
    
    # タイトルを最初のユーザーメッセージから生成
    title = "New Chat"
    for role, msg in st.session_state.message_history:
        if role == "user":
            title = msg[:30] + ("..." if len(msg) > 30 else "")
            break
    
    # 保存
    chat_data = {
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": st.session_state.message_history.copy(),
        "model": st.session_state.get("model_name", "gpt-3.5-turbo")
    }
    
    st.session_state.chat_histories.insert(0, chat_data)
    
    # 最大50件まで保持
    if len(st.session_state.chat_histories) > 50:
        st.session_state.chat_histories = st.session_state.chat_histories[:50]


def load_chat_history(index):
    """保存された会話を読み込む"""
    if "chat_histories" in st.session_state and 0 <= index < len(st.session_state.chat_histories):
        chat_data = st.session_state.chat_histories[index]
        st.session_state.message_history = chat_data["messages"].copy()
        st.session_state.model_name = chat_data.get("model", "gpt-3.5-turbo")
        st.rerun()


def delete_chat_history(index):
    """特定の会話履歴を削除"""
    if "chat_histories" in st.session_state and 0 <= index < len(st.session_state.chat_histories):
        st.session_state.chat_histories.pop(index)
        st.rerun()


def encode_conversation(message_history):
    """会話履歴をBase64エンコード"""
    try:
        json_str = json.dumps(message_history, ensure_ascii=False)
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded
    except Exception as e:
        st.error(f"エンコードエラー: {e}")
        return None


def decode_conversation(encoded_str):
    """Base64エンコードされた会話履歴をデコード"""
    try:
        json_str = base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
        return json.loads(json_str)
    except Exception as e:
        st.error(f"デコードエラー: {e}")
        return None


def create_share_url():
    """共有用URLを生成"""
    if "message_history" not in st.session_state:
        return None
    
    encoded = encode_conversation(st.session_state.message_history)
    if encoded:
        base_url = st.get_option("browser.serverAddress") or "localhost:8501"
        share_url = f"http://{base_url}?chat={encoded}"
        return share_url
    return None


def load_conversation_from_url():
    """URLパラメータから会話をロード"""
    query_params = st.query_params
    if "chat" in query_params:
        encoded = query_params["chat"]
        decoded = decode_conversation(encoded)
        if decoded:
            st.session_state.message_history = decoded
            st.success("会話を読み込みました！")
            st.query_params.clear()


def transcribe_audio(audio_file):
    """音声ファイルを文字起こし"""
    try:
        client = OpenAI()
        audio_bytes = audio_file.read()
        audio_file.seek(0)
        
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
        
        return transcript
    except Exception as e:
        st.error(f"文字起こしエラー: {e}")
        return None


def generate_minutes(transcript):
    """文字起こしテキストから議事録を生成"""
    try:
        client = OpenAI()
        
        prompt = f"""
以下は会議の文字起こしテキストです。これを読みやすい議事録形式にまとめてください。

【要件】
- 日時、参加者、議題を推測して記載
- 主要な議論ポイントを箇条書き
- 決定事項を明確に記載
- アクションアイテム（誰が何をするか）を整理
- 次回の予定があれば記載

【文字起こしテキスト】
{transcript}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたは優秀な議事録作成アシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"議事録生成エラー: {e}")
        return None


def init_messages():
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    if clear_button:
        # 現在の会話を保存してから新規作成
        save_chat_history()
        st.session_state.message_history = [
            ("system", "You are a helpful assistant.")
        ]
        st.rerun()
    
    if "message_history" not in st.session_state:
        st.session_state.message_history = [
            ("system", "You are a helpful assistant.")
        ]


def select_model():
    st.session_state.temperature = st.sidebar.slider(
        "Temperature", 0.0, 2.0, 0.0, 0.01
    )

    model = st.sidebar.radio(
        "Choose a model",
        ("GPT-3.5", "GPT-4", "Claude 3.5 Sonnet", "Gemini 1.5 Pro")
    )
    if model == "GPT-3.5":
        st.session_state.model_name = "gpt-3.5-turbo"
    elif model == "GPT-4":
        st.session_state.model_name = "gpt-4o"
    elif model == "Claude 3.5 Sonnet":
        st.session_state.model_name = "claude-3-5-sonnet-20241022"
    else:
        st.session_state.model_name = "gemini-1.5-pro-latest"


def get_llm_response(user_input: str) -> str:
    model = st.session_state.model_name
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        *[
            {"role": role, "content": msg}
            for role, msg in st.session_state.message_history
            if role != "system"
        ],
        {"role": "user", "content": user_input}
    ]

    # GPT
    if model.startswith("gpt"):
        client = OpenAI()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=st.session_state.temperature,
            stream=True,
        )

        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                response += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content

    # Claude
    if model.startswith("claude"):
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            messages=messages[1:],
        ) as stream:
            response = ""
            for text in stream.text_stream:
                response += text
                yield text

    # Gemini
    if model.startswith("gemini"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(model)
        response = model.generate_content(user_input, stream=True)
        full = ""
        for chunk in response:
            if chunk.text:
                full += chunk.text
                yield chunk.text


def calc_and_display_costs():
    output_count = 0
    input_count = 0
    for role, message in st.session_state.message_history:
        token_count = get_message_counts(message)
        if role == "assistant":
            output_count += token_count
        else:
            input_count += token_count

    if len(st.session_state.message_history) == 1:
        return

    input_cost = MODEL_PRICES['input'][st.session_state.model_name] * input_count
    output_cost = MODEL_PRICES['output'][st.session_state.model_name] * output_count
    if "gemini" in st.session_state.model_name and (input_count + output_count) > 128000:
        input_cost *= 2
        output_cost *= 2

    cost = output_cost + input_cost

    st.sidebar.markdown("## Costs")
    st.sidebar.markdown(f"**Total cost: ${cost:.5f}**")
    st.sidebar.markdown(f"- Input cost: ${input_cost:.5f}")
    st.sidebar.markdown(f"- Output cost: ${output_cost:.5f}")


def display_chat_history_sidebar():
    """サイドバーにチャット履歴を表示"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📚 チャット履歴")
    
    if "chat_histories" not in st.session_state or len(st.session_state.chat_histories) == 0:
        st.sidebar.info("まだ保存された会話はありません")
        return
    
    for i, chat in enumerate(st.session_state.chat_histories):
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            if st.button(f"📝 {chat['title']}", key=f"load_{i}"):
                load_chat_history(i)
        with col2:
            if st.button("🗑️", key=f"delete_{i}"):
                delete_chat_history(i)
        st.sidebar.caption(f"{chat['timestamp']} | {chat['model']}")


def main():
    init_page()
    
    # URLから会話をロード
    load_conversation_from_url()
    
    init_messages()
    select_model()
    
    # チャット履歴表示
    display_chat_history_sidebar()
    
    # サイドバーに共有機能を追加
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🔗 会話の共有")
    if st.sidebar.button("共有URLを生成"):
        share_url = create_share_url()
        if share_url:
            st.sidebar.text_area("共有URL", share_url, height=100)
            st.sidebar.info("このURLをコピーして共有してください")
    
    # 音声議事録機能
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎙️ 音声議事録")
    audio_file = st.sidebar.file_uploader(
        "音声ファイルをアップロード",
        type=["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]
    )
    
    if audio_file and st.sidebar.button("議事録を作成"):
        with st.spinner("文字起こし中..."):
            transcript = transcribe_audio(audio_file)
        
        if transcript:
            st.sidebar.success("文字起こし完了！")
            
            with st.spinner("議事録を生成中..."):
                minutes = generate_minutes(transcript)
            
            if minutes:
                st.sidebar.success("議事録生成完了！")
                
                # 議事録を表示
                st.markdown("## 📝 生成された議事録")
                st.markdown(minutes)
                
                # ダウンロードボタン
                st.download_button(
                    label="議事録をダウンロード",
                    data=minutes,
                    file_name="minutes.txt",
                    mime="text/plain"
                )

    # チャット履歴を表示
    for role, message in st.session_state.get("message_history", []):
        if role != "system":
            st.chat_message(role).markdown(message)

    # ユーザー入力
    if user_input := st.chat_input("聞きたいことを入力してね！"):
        st.chat_message("user").markdown(user_input)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            for token in get_llm_response(user_input):
                response_text += token
                response_placeholder.markdown(response_text)

        # チャット履歴に追加
        st.session_state.message_history.append(("user", user_input))
        st.session_state.message_history.append(("assistant", response_text))

    calc_and_display_costs()

if __name__ == '__main__':
    main()
