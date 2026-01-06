import os
import streamlit as st
from openai import OpenAI
import anthropic
import google.generativeai as genai

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
        "claude-3-5-sonnet-20241022": 3 / 1_000_000, # 正式名に変更
        "gemini-1.5-pro-latest": 3.5 / 1_000_000
    },
    "output": {
        "gpt-3.5-turbo": 1.5 / 1_000_000,
        "gpt-4o": 15 / 1_000_000,
        "claude-3-5-sonnet-20241022": 15 / 1_000_000, # 正式名に変更
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


def init_messages():
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    # clear_button が押された場合や message_history がまだ存在しない場合に初期化
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
        # 確実に存在する日付付きIDを指定
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
            messages=messages[1:],  # systemは別扱い
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
        # 【修正】"ai" から "assistant" に変更
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

        # チャット履歴に追加
        st.session_state.message_history.append(("user", user_input))
        # 【修正】"ai" から "assistant" に変更
        st.session_state.message_history.append(("assistant", response_text))

    calc_and_display_costs()

if __name__ == '__main__':
    main()
