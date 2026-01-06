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
        "claude-3-5-sonnet-20240620": 3 / 1_000_000,
        "gemini-1.5-pro-latest": 3.5 / 1_000_000
    },
    "output": {
        "gpt-3.5-turbo": 1.5 / 1_000_000,
        "gpt-4o": 15 / 1_000_000,
        "claude-3-5-sonnet-20240620": 15 / 1_000_000,
        "gemini-1.5-pro-latest": 10.5 / 1_000_000
    }
}


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
    # スライダーを追加し、temperatureを0から2までの範囲で選択可能にする
    # 初期値は0.0、刻み幅は0.01とする
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
        st.session_state.model_name = "claude-3-5-sonnet-20240620"
    else:
        st.session_state.model_name = "gemini-1.5-pro-latest"


def init_chain():
    st.session_state.llm = select_model()
    prompt = ChatPromptTemplate.from_messages([
        *st.session_state.message_history,
        ("user", "{user_input}")  # ここにあとでユーザーの入力が入る
    ])
    output_parser = StrOutputParser()
    return prompt | st.session_state.llm | output_parser


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
        return response

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
        return response

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
        return full

    # フォールバック（全モデル共通）
    return max(1, len(text) // 4)


def calc_and_display_costs():
    output_count = 0
    input_count = 0
    for role, message in st.session_state.message_history:
        # tiktoken でトークン数をカウント
        token_count = get_message_counts(message)
        if role == "ai":
            output_count += token_count
        else:
            input_count += token_count

    # 初期状態で System Message のみが履歴に入っている場合はまだAPIコールが行われていない
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
    chain = init_chain()

    # チャット履歴の表示 (第2章から少し位置が変更になっているので注意)
    for role, message in st.session_state.get("message_history", []):
        st.chat_message(role).markdown(message)

    # ユーザーの入力を監視
    if user_input := st.chat_input("聞きたいことを入力してね！"):
        st.chat_message("user").markdown(user_input)

        # LLMの返答を Streaming 表示する
        with st.chat_message("assistant"):
            response_text = ""
            for token in get_llm_response(user_input):
                response_text += token
                st.markdown(response_text)

        # チャット履歴に追加
        st.session_state.message_history.append(("user", user_input))
        st.session_state.message_history.append(("ai", response_text))

    # コストを計算して表示
    calc_and_display_costs()


if __name__ == '__main__':
    main()
