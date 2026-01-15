import os
import streamlit as st
from openai import OpenAI
import anthropic
import google.generativeai as genai
import json
import base64
from urllib.parse import urlencode, parse_qs

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

def export_chat_to_url():
    """チャット履歴をURLで共有可能な形式にエンコード"""
    if len(st.session_state.message_history) <= 1:
        st.sidebar.warning("共有する会話がありません")
        return
    
    # システムメッセージ以外をエクスポート
    export_data = {
        "messages": [
            {"role": role, "content": msg}
            for role, msg in st.session_state.message_history
            if role != "system"
        ],
        "model": st.session_state.model_name
    }
    
    # JSONをBase64エンコード
    json_str = json.dumps(export_data, ensure_ascii=False)
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
    
    # 現在のURLに会話データを追加
    base_url = st.query_params.get("_url", "").split("?")[0] or "http://localhost:8501"
    share_url = f"{base_url}?chat={encoded}"
    
    st.sidebar.markdown("### 📤 会話を共有")
    st.sidebar.code(share_url, language=None)
    st.sidebar.info("このURLをコピーして共有してください")

def load_chat_from_url():
    """URLパラメータから会話を読み込み"""
    query_params = st.query_params
    if "chat" in query_params:
        try:
            encoded = query_params["chat"]
            json_str = base64.urlsafe_b64decode(encoded.encode()).decode()
            data = json.loads(json_str)
            
            # 会話を復元
            st.session_state.message_history = [
                ("system", "You are a helpful assistant.")
            ]
            for msg in data["messages"]:
                st.session_state.message_history.append((msg["role"], msg["content"]))
            
            if "model" in data:
                st.session_state.model_name = data["model"]
            
            st.success("会話を読み込みました")
            # URLパラメータをクリア
            st.query_params.clear()
        except Exception as e:
            st.error(f"会話の読み込みに失敗しました: {str(e)}")

def transcribe_audio(audio_file):
    """音声ファイルを文字起こし"""
    try:
        client = OpenAI()
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
        return transcript
    except Exception as e:
        st.error(f"文字起こしエラー: {str(e)}")
        return None

def generate_minutes(transcript: str) -> str:
    """文字起こしテキストから議事録を生成"""
    model = st.session_state.model_name
    prompt = f"""以下の文字起こしテキストから、議事録を作成してください。

【文字起こしテキスト】
{transcript}

【議事録の形式】
- 日時・参加者(推測可能であれば)
- 議題
- 討議内容の要約
- 決定事項
- TODO/アクションアイテム

簡潔かつ分かりやすくまとめてください。"""

    messages = [
        {"role": "system", "content": "You are a helpful assistant specialized in creating meeting minutes."},
        {"role": "user", "content": prompt}
    ]

    # GPT
    if model.startswith("gpt"):
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content

    # Claude
    elif model.startswith("claude"):
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # Gemini
    elif model.startswith("gemini"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(prompt)
        return response.text

def init_messages():
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    if clear_button or "message_history" not in st.session_state:
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

def audio_transcription_section():
    """音声議事録作成セクション"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎤 音声議事録作成")
    
    audio_file = st.sidebar.file_uploader(
        "音声ファイルをアップロード",
        type=["mp3", "wav", "m4a", "mp4"],
        help="会議やインタビューの音声から議事録を自動生成します"
    )
    
    if audio_file is not None:
        if st.sidebar.button("議事録を作成", key="create_minutes"):
            with st.spinner("音声を文字起こし中..."):
                transcript = transcribe_audio(audio_file)
            
            if transcript:
                st.sidebar.success("文字起こし完了!")
                
                with st.spinner("議事録を生成中..."):
                    minutes = generate_minutes(transcript)
                
                # 議事録をチャット履歴に追加
                st.session_state.message_history.append(
                    ("user", f"音声ファイル「{audio_file.name}」から議事録を作成してください")
                )
                st.session_state.message_history.append(
                    ("assistant", f"**【文字起こしテキスト】**\n\n{transcript}\n\n---\n\n**【議事録】**\n\n{minutes}")
                )
                st.rerun()

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
    elif model.startswith("claude"):
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
    elif model.startswith("gemini"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model_obj = genai.GenerativeModel(model)
        response = model_obj.generate_content(user_input, stream=True)
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

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 💰 Costs")
    st.sidebar.markdown(f"**Total cost: ${cost:.5f}**")
    st.sidebar.markdown(f"- Input cost: ${input_cost:.5f}")
    st.sidebar.markdown(f"- Output cost: ${output_cost:.5f}")

def main():
    init_page()
    
    # URLから会話を読み込み(初回のみ)
    if "loaded_from_url" not in st.session_state:
        load_chat_from_url()
        st.session_state.loaded_from_url = True
    
    init_messages()
    select_model()
    audio_transcription_section()
    
    # URL共有ボタン
    if st.sidebar.button("📤 会話をURLで共有", key="export_url"):
        export_chat_to_url()

    for role, message in st.session_state.get("message_history", []):
        if role != "system":
            st.chat_message(role).markdown(message)

    if user_input := st.chat_input("聞きたいことを入力してね!"):
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
