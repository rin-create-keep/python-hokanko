import os
import streamlit as st
from openai import OpenAI
import anthropic
import google.generativeai as genai
import base64
import json
import urllib.parse

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

def encode_conversation(messages):
    """会話履歴をBase64エンコード"""
    try:
        json_str = json.dumps(messages, ensure_ascii=False)
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded
    except Exception as e:
        st.error(f"エンコードエラー: {e}")
        return None

def decode_conversation(encoded_str):
    """Base64エンコードされた会話履歴をデコード"""
    try:
        decoded = base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
        messages = json.loads(decoded)
        return messages
    except Exception as e:
        st.error(f"デコードエラー: {e}")
        return None

def init_messages():
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    
    # URLパラメータから会話履歴を読み込み
    query_params = st.query_params
    if "conversation" in query_params and "message_history" not in st.session_state:
        decoded_messages = decode_conversation(query_params["conversation"])
        if decoded_messages:
            st.session_state.message_history = decoded_messages
            st.success("会話履歴を読み込みました！")
            return
    
    if clear_button or "message_history" not in st.session_state:
        st.session_state.message_history = [
            ("system", "You are a helpful assistant.")
        ]

def share_conversation():
    """会話をURLで共有する機能"""
    if len(st.session_state.message_history) <= 1:
        st.sidebar.warning("共有する会話がありません")
        return
    
    with st.sidebar.expander("📤 会話を共有"):
        encoded = encode_conversation(st.session_state.message_history)
        if encoded:
            # 現在のURLを取得
            base_url = st.get_option("browser.serverAddress") or "localhost"
            port = st.get_option("browser.serverPort") or 8501
            share_url = f"http://{base_url}:{port}/?conversation={encoded}"
            
            st.text_area("共有URL", share_url, height=100)
            st.caption("このURLをコピーして共有してください")

def transcribe_audio(audio_file):
    """音声ファイルを文字起こし"""
    try:
        client = OpenAI()
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ja"
        )
        return transcript.text
    except Exception as e:
        st.error(f"音声認識エラー: {e}")
        return None

def create_minutes(transcript: str) -> str:
    """文字起こしテキストから議事録を作成"""
    client = OpenAI()
    
    prompt = f"""以下の会議の文字起こしテキストから、議事録を作成してください。

文字起こしテキスト:
{transcript}

以下の形式で議事録を作成してください:
# 議事録

## 日時・参加者
[推測される情報があれば記載]

## 議題
[主な議題をリストアップ]

## 議論内容
[重要なポイントを箇条書きで]

## 決定事項
[決まったことを明確に]

## アクションアイテム
[誰が何をするか]

## 次回予定
[あれば記載]
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは議事録作成の専門家です。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    return response.choices[0].message.content

def audio_to_minutes():
    """音声から議事録を作成する機能"""
    with st.sidebar.expander("🎤 音声から議事録作成"):
        st.write("音声ファイルをアップロードして議事録を自動生成")
        
        audio_file = st.file_uploader(
            "音声ファイルを選択",
            type=['mp3', 'wav', 'm4a', 'webm', 'mp4'],
            key="audio_uploader"
        )
        
        if audio_file and st.button("議事録を作成", key="create_minutes"):
            with st.spinner("音声を文字起こし中..."):
                transcript = transcribe_audio(audio_file)
            
            if transcript:
                st.success("文字起こし完了！")
                with st.expander("文字起こしテキスト"):
                    st.text_area("Transcript", transcript, height=200)
                
                with st.spinner("議事録を作成中..."):
                    minutes = create_minutes(transcript)
                
                if minutes:
                    st.success("議事録作成完了！")
                    st.markdown(minutes)
                    
                    # 議事録をダウンロード可能にする
                    st.download_button(
                        label="議事録をダウンロード",
                        data=minutes,
                        file_name="minutes.md",
                        mime="text/markdown"
                    )

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

def main():
    init_page()
    init_messages()
    select_model()
    
    # 会話共有機能
    share_conversation()
    
    # 音声議事録機能
    audio_to_minutes()

    for role, message in st.session_state.get("message_history", []):
        if role != "system":
            st.chat_message(role).markdown(message)

    if user_input := st.chat_input("聞きたいことを入力してね！"):
        st.chat_message("user").markdown(user_input)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            for token in get_llm_response(user_input):
                response_text += token
                response_placeholder.markdown(response_text)

        st.session_state.message_history.append(("user", user_input))
        st.session_state.message_history.append(("assistant", response_text))

    calc_and_display_costs()

if __name__ == '__main__':
    main()
