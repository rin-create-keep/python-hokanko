import os
import streamlit as st
from openai import OpenAI
import anthropic
from google.genai import Client
import json   
import base64
from datetime import datetime

# ===== Gemini Client =====
gemini_client = Client(api_key=st.secrets["GOOGLE_API_KEY"])

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    import warnings
    warnings.warn("dotenv not found.", ImportWarning)

MODEL_PRICES = {
    "input": {"gpt-3.5-turbo": 0.5/1_000_000, "gpt-4o": 5/1_000_000, "claude-3-haiku-20240307": 3/1_000_000, "gemini-2.5-flash": 0.35/1_000_000},
    "output": {"gpt-3.5-turbo": 1.5/1_000_000, "gpt-4o": 15/1_000_000, "claude-3-haiku-20240307": 15/1_000_000, "gemini-2.5-flash": 0.70/1_000_000}
}

def get_message_counts(text: str) -> int:
    return max(1, len(text) // 4) if text else 0

def init_page():
    st.set_page_config(page_title="My Great ChatGPT", page_icon="🤗")
    st.header("My Great ChatGPT 🤗")
    st.sidebar.title("Options")

def save_chat_history():
    if "message_history" not in st.session_state or len(st.session_state.message_history) <= 1:
        return
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = []
    title = "New Chat"
    for role, msg in st.session_state.message_history:
        if role == "user" and isinstance(msg, dict) and msg.get("type") == "text":
            content = msg.get("content", "").strip()
            if content:
                title = content[:30] + ("..." if len(content) > 30 else "")
            break
    chat_data = {"title": title, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                 "messages": st.session_state.message_history.copy(), "model": st.session_state.get("model_name", "gpt-3.5-turbo")}
    st.session_state.chat_histories.insert(0, chat_data)
    if len(st.session_state.chat_histories) > 50:
        st.session_state.chat_histories = st.session_state.chat_histories[:50]

def load_chat_history(index):
    if "chat_histories" in st.session_state and 0 <= index < len(st.session_state.chat_histories):
        chat_data = st.session_state.chat_histories[index]
        st.session_state.message_history = chat_data["messages"].copy()
        st.session_state.model_name = chat_data.get("model", "gpt-3.5-turbo")
        st.rerun()

def delete_chat_history(index):
    if "chat_histories" in st.session_state and 0 <= index < len(st.session_state.chat_histories):
        st.session_state.chat_histories.pop(index)
        st.rerun()

def init_messages():
    if st.sidebar.button("Clear Conversation", key="clear"):
        save_chat_history()
        st.session_state.message_history = [("system", "You are a helpful assistant.")]
        if "uploaded_image_bytes" in st.session_state:
            del st.session_state.uploaded_image_bytes
        if "uploader_key" not in st.session_state:
            st.session_state.uploader_key = 0
        st.session_state.uploader_key += 1
        st.rerun()
    if "message_history" not in st.session_state:
        st.session_state.message_history = [("system", f"You are a helpful assistant. Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")]
    if "tasks" not in st.session_state:
        st.session_state.tasks = []
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

def select_model():
    st.session_state.temperature = st.sidebar.slider("Temperature", 0.0, 2.0, 0.0, 0.01)
    model = st.sidebar.radio("Choose a model", ("GPT-3.5", "GPT-4", "Claude 3.5 Sonnet", "Gemini 1.5 Pro"))
    if model == "GPT-3.5":
        st.session_state.model_name = "gpt-3.5-turbo"
    elif model == "GPT-4":
        st.session_state.model_name = "gpt-4o"
    elif model == "Claude 3.5 Sonnet":
        st.session_state.model_name = "claude-3-haiku-20240307"
    else:
        st.session_state.model_name = "gemini-2.5-flash"

def get_llm_response(user_input, image_bytes=None):
    model = st.session_state.model_name
    if model.startswith("gpt"):
        client = OpenAI()
        use_model = "gpt-4o" if image_bytes and model == "gpt-3.5-turbo" else model
        content = [{"type": "text", "text": user_input}]
        if image_bytes:
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})
        stream = client.chat.completions.create(model=use_model, messages=[{"role": "user", "content": content}], stream=True)
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    elif model.startswith("claude"):
        if image_bytes:
            yield "申し訳ありません。このモデルでは画像を読み込むことができません。"
            return
        client = anthropic.Anthropic()
        with client.messages.stream(model=model, max_tokens=1024, messages=[{"role": "user", "content": user_input}]) as stream:
            for text in stream.text_stream:
                yield text
    elif model.startswith("gemini"):
        client = Client(api_key=os.environ["GOOGLE_API_KEY"])
        contents = [{"text": user_input}]
        if image_bytes:
            contents.append({"inline_data": {"mime_type": "image/png", "data": image_bytes}})
        try:
            response = client.models.generate_content_stream(model="models/gemini-flash-latest", contents=contents)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"⚠️ Geminiエラー: {e}"

def calc_and_display_costs():
    output_count = input_count = 0
    for role, message in st.session_state.message_history:
        token_count = get_message_counts(message.get("content", "") if isinstance(message, dict) else message)
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
    st.sidebar.markdown(f"**Total cost: ${cost:.5f}**\n- Input cost: ${input_cost:.5f}\n- Output cost: ${output_cost:.5f}")

def display_chat_history_sidebar():
    st.sidebar.markdown("---\n## 📚 チャット履歴")
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
    init_messages()
    select_model()
    if st.session_state.get("tasks"):
        st.table(st.session_state.tasks)
    display_chat_history_sidebar()
    
    for role, message in st.session_state.get("message_history", []):
        if role == "system":
            continue
        with st.chat_message(role):
            if isinstance(message, dict):
                if message["type"] == "text":
                    st.markdown(message["content"])
                elif message["type"] == "image":
                    try:
                        img_bytes = base64.b64decode(message["content"])
                        st.image(img_bytes, use_column_width=True)
                    except:
                        st.warning("⚠️ 画像を表示できませんでした")
            else:
                st.markdown(message)
    
    uploaded_image = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"], key=f"image_uploader_{st.session_state.uploader_key}")
    if uploaded_image:
        image_bytes = uploaded_image.getvalue()
        st.session_state["uploaded_image_bytes"] = image_bytes
        st.image(image_bytes, caption="アップロードされた画像", use_column_width=True)
    else:
        if "uploaded_image_bytes" in st.session_state:
            del st.session_state["uploaded_image_bytes"]
    
    if user_input := st.chat_input("聞きたいことを入力してね！"):
        with st.chat_message("user"):
            st.markdown(user_input)
        image_bytes = st.session_state.get("uploaded_image_bytes")
        st.session_state.message_history.append(("user", {"type": "text", "content": user_input}))
        if isinstance(image_bytes, (bytes, bytearray)):
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")
            st.session_state.message_history.append(("user", {"type": "image", "content": img_b64}))
            del st.session_state["uploaded_image_bytes"]
            st.session_state.uploader_key += 1
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            for token in get_llm_response(user_input, image_bytes):
                response_text += token
                response_placeholder.markdown(response_text)
            st.session_state.message_history.append(("assistant", {"type": "text", "content": response_text}))
        st.rerun()
    calc_and_display_costs()

if __name__ == '__main__':
    main()
