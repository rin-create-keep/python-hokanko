import os
import json
import streamlit as st
from openai import OpenAI
import anthropic
import google.generativeai as genai
from datetime import datetime
import time
from io import BytesIO
import base64

# dotenvを利用しない場合は消してください
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    import warnings
    warnings.warn("dotenv not found. Please make sure to set your environment variables manually.", ImportWarning)

# tiktokenのインポート(トークン数正確計算用)
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    import warnings
    warnings.warn("tiktoken not installed. Using approximate token counting.", ImportWarning)

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

SYSTEM_PROMPTS = {
    "親切なアシスタント": "You are a helpful assistant.",
    "プログラミング専門家": "You are an expert programmer who provides clear, concise code solutions with explanations.",
    "翻訳者": "You are a professional translator. Translate text accurately while preserving the original meaning and tone.",
    "文章校正者": "You are a professional editor. Review and improve text for clarity, grammar, and style.",
    "創造的な作家": "You are a creative writer who crafts engaging stories and content.",
    "カスタム": ""
}

PRESET_PROMPTS = [
    "このコードをレビューして改善点を教えてください",
    "この文章を要約してください",
    "この英文を日本語に翻訳してください",
    "このエラーの解決方法を教えてください",
    "〜について簡単に説明してください"
]

def get_accurate_token_count(text: str, model: str) -> int:
    """正確なトークン数をカウント"""
    if not text:
        return 0
    
    if not TIKTOKEN_AVAILABLE:
        return max(1, len(text) // 4)
    
    try:
        if model.startswith("gpt"):
            encoding = tiktoken.encoding_for_model(model)
        elif model.startswith("claude"):
            encoding = tiktoken.get_encoding("cl100k_base")
        else:
            encoding = tiktoken.get_encoding("cl100k_base")
        
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)

def save_conversation(conversation_name: str, messages: list, model: str):
    """会話を保存"""
    if not os.path.exists("conversations"):
        os.makedirs("conversations")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversations/{conversation_name}_{timestamp}.json"
    
    data = {
        "name": conversation_name,
        "timestamp": timestamp,
        "model": model,
        "messages": messages
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename

def load_conversation(filename: str):
    """会話を読み込み"""
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def list_saved_conversations():
    """保存された会話のリストを取得"""
    if not os.path.exists("conversations"):
        return []
    
    files = [f for f in os.listdir("conversations") if f.endswith(".json")]
    conversations = []
    
    for f in files:
        try:
            with open(f"conversations/{f}", "r", encoding="utf-8") as file:
                data = json.load(file)
                conversations.append({
                    "filename": f,
                    "name": data.get("name", "Unnamed"),
                    "timestamp": data.get("timestamp", ""),
                    "model": data.get("model", "")
                })
        except Exception:
            continue
    
    return sorted(conversations, key=lambda x: x["timestamp"], reverse=True)

def export_conversation_as_markdown(messages: list) -> str:
    """会話をMarkdown形式でエクスポート"""
    md = f"# Chat Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for role, message in messages:
        if role == "system":
            md += f"**System Prompt:** {message}\n\n---\n\n"
        elif role == "user":
            md += f"## 👤 User\n\n{message}\n\n"
        elif role == "assistant":
            md += f"## 🤖 Assistant\n\n{message}\n\n"
    
    return md

def process_uploaded_file(uploaded_file):
    """アップロードされたファイルを処理"""
    file_type = uploaded_file.type
    
    if file_type.startswith("text"):
        content = uploaded_file.read().decode("utf-8")
        return f"[ファイル: {uploaded_file.name}]\n\n{content}"
    elif file_type == "application/pdf":
        return f"[PDFファイル: {uploaded_file.name}] ※PDF内容の読み取りには追加ライブラリが必要です"
    elif file_type.startswith("image"):
        bytes_data = uploaded_file.read()
        base64_image = base64.b64encode(bytes_data).decode()
        return f"[画像ファイル: {uploaded_file.name}]", base64_image
    else:
        return f"[ファイル: {uploaded_file.name}] ※このファイル形式は未対応です"

def init_page():
    st.set_page_config(
        page_title="My Great ChatGPT Pro",
        page_icon="🤗",
        layout="wide"
    )
    st.header("My Great ChatGPT Pro 🤗")

def init_session_state():
    """セッション状態の初期化"""
    if "conversations" not in st.session_state:
        st.session_state.conversations = {
            "conversation_1": {
                "name": "会話 1",
                "messages": [("system", "You are a helpful assistant.")],
                "created_at": datetime.now().isoformat()
            }
        }
    
    if "current_conversation" not in st.session_state:
        st.session_state.current_conversation = "conversation_1"
    
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.0
    
    if "model_name" not in st.session_state:
        st.session_state.model_name = "gpt-3.5-turbo"
    
    if "system_prompt_type" not in st.session_state:
        st.session_state.system_prompt_type = "親切なアシスタント"
    
    if "custom_system_prompt" not in st.session_state:
        st.session_state.custom_system_prompt = ""
    
    if "usage_stats" not in st.session_state:
        st.session_state.usage_stats = {
            "daily": {},
            "model_usage": {}
        }

def get_current_messages():
    """現在の会話のメッセージを取得"""
    return st.session_state.conversations[st.session_state.current_conversation]["messages"]

def set_current_messages(messages):
    """現在の会話のメッセージを設定"""
    st.session_state.conversations[st.session_state.current_conversation]["messages"] = messages

def sidebar_controls():
    """サイドバーのコントロール"""
    st.sidebar.title("🎛️ Options")
    
    # 会話管理セクション
    st.sidebar.markdown("### 💬 会話管理")
    
    # 現在の会話選択
    conversation_names = {
        conv_id: conv["name"] 
        for conv_id, conv in st.session_state.conversations.items()
    }
    
    selected = st.sidebar.selectbox(
        "会話を選択",
        options=list(conversation_names.keys()),
        format_func=lambda x: conversation_names[x],
        key="conversation_selector"
    )
    
    if selected != st.session_state.current_conversation:
        st.session_state.current_conversation = selected
        st.rerun()
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("➕ 新規会話", use_container_width=True):
            new_id = f"conversation_{len(st.session_state.conversations) + 1}"
            system_prompt = SYSTEM_PROMPTS[st.session_state.system_prompt_type]
            if st.session_state.system_prompt_type == "カスタム":
                system_prompt = st.session_state.custom_system_prompt
            
            st.session_state.conversations[new_id] = {
                "name": f"会話 {len(st.session_state.conversations) + 1}",
                "messages": [("system", system_prompt)],
                "created_at": datetime.now().isoformat()
            }
            st.session_state.current_conversation = new_id
            st.rerun()
    
    with col2:
        if st.button("🗑️ 削除", use_container_width=True):
            if len(st.session_state.conversations) > 1:
                del st.session_state.conversations[st.session_state.current_conversation]
                st.session_state.current_conversation = list(st.session_state.conversations.keys())[0]
                st.rerun()
    
    # 会話名の変更
    new_name = st.sidebar.text_input(
        "会話名を変更",
        value=st.session_state.conversations[st.session_state.current_conversation]["name"]
    )
    if new_name != st.session_state.conversations[st.session_state.current_conversation]["name"]:
        st.session_state.conversations[st.session_state.current_conversation]["name"] = new_name
    
    st.sidebar.markdown("---")
    
    # モデル選択
    st.sidebar.markdown("### 🤖 モデル設定")
    
    model = st.sidebar.radio(
        "モデルを選択",
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
    
    st.session_state.temperature = st.sidebar.slider(
        "Temperature", 0.0, 2.0, st.session_state.temperature, 0.01
    )
    
    st.sidebar.markdown("---")
    
    # システムプロンプト設定
    st.sidebar.markdown("### 📝 システムプロンプト")
    
    prompt_type = st.sidebar.selectbox(
        "プリセット選択",
        options=list(SYSTEM_PROMPTS.keys())
    )
    
    st.session_state.system_prompt_type = prompt_type
    
    if prompt_type == "カスタム":
        st.session_state.custom_system_prompt = st.sidebar.text_area(
            "カスタムプロンプト",
            value=st.session_state.custom_system_prompt,
            height=100
        )
        current_system_prompt = st.session_state.custom_system_prompt
    else:
        current_system_prompt = SYSTEM_PROMPTS[prompt_type]
    
    if st.sidebar.button("システムプロンプトを適用"):
        messages = get_current_messages()
        messages[0] = ("system", current_system_prompt)
        set_current_messages(messages)
        st.success("システムプロンプトを更新しました")
    
    st.sidebar.markdown("---")
    
    # 保存・読み込み
    st.sidebar.markdown("### 💾 保存・読み込み")
    
    save_name = st.sidebar.text_input("保存名", value="my_conversation")
    if st.sidebar.button("💾 会話を保存", use_container_width=True):
        try:
            filename = save_conversation(
                save_name,
                get_current_messages(),
                st.session_state.model_name
            )
            st.sidebar.success(f"保存しました: {filename}")
        except Exception as e:
            st.sidebar.error(f"保存エラー: {str(e)}")
    
    saved_convs = list_saved_conversations()
    if saved_convs:
        selected_file = st.sidebar.selectbox(
            "保存された会話",
            options=[c["filename"] for c in saved_convs],
            format_func=lambda x: next(c["name"] for c in saved_convs if c["filename"] == x)
        )
        
        if st.sidebar.button("📂 会話を読み込み", use_container_width=True):
            try:
                data = load_conversation(f"conversations/{selected_file}")
                new_id = f"conversation_{len(st.session_state.conversations) + 1}"
                st.session_state.conversations[new_id] = {
                    "name": data["name"],
                    "messages": data["messages"],
                    "created_at": datetime.now().isoformat()
                }
                st.session_state.current_conversation = new_id
                st.session_state.model_name = data.get("model", "gpt-3.5-turbo")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"読み込みエラー: {str(e)}")
    
    st.sidebar.markdown("---")
    
    # エクスポート
    st.sidebar.markdown("### 📤 エクスポート")
    
    if st.sidebar.button("📄 Markdownでエクスポート", use_container_width=True):
        md_content = export_conversation_as_markdown(get_current_messages())
        st.sidebar.download_button(
            label="ダウンロード",
            data=md_content,
            file_name=f"chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown"
        )
    
    st.sidebar.markdown("---")
    
    # コスト表示
    calc_and_display_costs()
    
    # 統計情報
    display_usage_stats()

def calc_and_display_costs():
    """コストを計算して表示"""
    messages = get_current_messages()
    output_count = 0
    input_count = 0
    
    for role, message in messages:
        token_count = get_accurate_token_count(message, st.session_state.model_name)
        if role == "assistant":
            output_count += token_count
        else:
            input_count += token_count
    
    if len(messages) <= 1:
        return
    
    input_cost = MODEL_PRICES['input'][st.session_state.model_name] * input_count
    output_cost = MODEL_PRICES['output'][st.session_state.model_name] * output_count
    
    if "gemini" in st.session_state.model_name and (input_count + output_count) > 128000:
        input_cost *= 2
        output_cost *= 2
    
    cost = output_cost + input_cost
    
    st.sidebar.markdown("### 💰 コスト")
    st.sidebar.markdown(f"**合計: ${cost:.5f}**")
    st.sidebar.markdown(f"- 入力: ${input_cost:.5f} ({input_count} tokens)")
    st.sidebar.markdown(f"- 出力: ${output_cost:.5f} ({output_count} tokens)")

def display_usage_stats():
    """使用統計を表示"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 使用統計")
    
    # 今日の日付
    today = datetime.now().strftime("%Y-%m-%d")
    
    # モデル別使用回数
    model_stats = st.session_state.usage_stats.get("model_usage", {})
    if model_stats:
        st.sidebar.markdown("**モデル別使用回数:**")
        for model, count in model_stats.items():
            st.sidebar.markdown(f"- {model}: {count}回")

def get_llm_response(user_input: str, uploaded_file=None):
    """LLMからレスポンスを取得(エラーハンドリング強化版)"""
    model = st.session_state.model_name
    messages = get_current_messages()
    
    # システムメッセージ以外を抽出
    chat_messages = [
        {"role": role, "content": msg}
        for role, msg in messages
        if role != "system"
    ]
    
    # システムプロンプトを取得
    system_prompt = next((msg for role, msg in messages if role == "system"), "You are a helpful assistant.")
    
    # ファイルが添付されている場合
    if uploaded_file:
        file_content = process_uploaded_file(uploaded_file)
        if isinstance(file_content, tuple):
            user_input = f"{user_input}\n\n{file_content[0]}"
        else:
            user_input = f"{user_input}\n\n{file_content}"
    
    chat_messages.append({"role": "user", "content": user_input})
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # GPT
            if model.startswith("gpt"):
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    yield "エラー: OPENAI_API_KEYが設定されていません。環境変数を確認してください。"
                    return
                
                client = OpenAI(api_key=api_key)
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}] + chat_messages,
                    temperature=st.session_state.temperature,
                    stream=True,
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                # 使用統計を更新
                update_usage_stats(model)
                return
            
            # Claude
            elif model.startswith("claude"):
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    yield "エラー: ANTHROPIC_API_KEYが設定されていません。環境変数を確認してください。"
                    return
                
                client = anthropic.Anthropic(api_key=api_key)
                with client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=chat_messages,
                    temperature=st.session_state.temperature,
                ) as stream:
                    for text in stream.text_stream:
                        yield text
                
                # 使用統計を更新
                update_usage_stats(model)
                return
            
            # Gemini
            elif model.startswith("gemini"):
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    yield "エラー: GOOGLE_API_KEYが設定されていません。環境変数を確認してください。"
                    return
                
                genai.configure(api_key=api_key)
                gemini_model = genai.GenerativeModel(model)
                response = gemini_model.generate_content(user_input, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                
                # 使用統計を更新
                update_usage_stats(model)
                return
        
        except Exception as e:
            error_msg = str(e)
            
            # レート制限エラーの場合
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                if attempt < max_retries - 1:
                    yield f"\n\n⚠️ レート制限に達しました。{retry_delay}秒後に再試行します...\n\n"
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    yield f"\n\n❌ エラー: レート制限に達しました。しばらく待ってから再試行してください。"
                    return
            
            # その他のエラー
            else:
                yield f"\n\n❌ エラーが発生しました: {error_msg}"
                if attempt < max_retries - 1:
                    yield f"\n\n再試行中... ({attempt + 1}/{max_retries})"
                    time.sleep(retry_delay)
                    continue
                else:
                    return

def update_usage_stats(model: str):
    """使用統計を更新"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 日別統計
    if today not in st.session_state.usage_stats["daily"]:
        st.session_state.usage_stats["daily"][today] = 0
    st.session_state.usage_stats["daily"][today] += 1
    
    # モデル別統計
    if model not in st.session_state.usage_stats["model_usage"]:
        st.session_state.usage_stats["model_usage"][model] = 0
    st.session_state.usage_stats["model_usage"][model] += 1

def main():
    init_page()
    init_session_state()
    sidebar_controls()
    
    # メインエリア
    messages = get_current_messages()
    
    # メッセージ履歴を表示
    for role, message in messages:
        if role != "system":
            with st.chat_message(role):
                st.markdown(message)
    
    # プリセットプロンプト
    with st.expander("📌 プリセットプロンプト"):
        cols = st.columns(3)
        for idx, preset in enumerate(PRESET_PROMPTS):
            if cols[idx % 3].button(preset, key=f"preset_{idx}"):
                st.session_state.preset_input = preset
    
    # ファイルアップロード
    uploaded_file = st.file_uploader(
        "📎 ファイルを添付 (テキスト/画像/PDF)",
        type=["txt", "md", "py", "json", "csv", "pdf", "png", "jpg", "jpeg"]
    )
    
    # ユーザー入力
    user_input = st.chat_input("聞きたいことを入力してね！")
    
    # プリセットが選択された場合
    if "preset_input" in st.session_state:
        user_input = st.session_state.preset_input
        del st.session_state.preset_input
    
    if user_input:
        # ユーザーメッセージを表示
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # アシスタントの応答
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            
            for token in get_llm_response(user_input, uploaded_file):
                response_text += token
                response_placeholder.markdown(response_text)
        
        # 履歴に追加
        messages.append(("user", user_input))
        messages.append(("assistant", response_text))
        set_current_messages(messages)

if __name__ == '__main__':
    main()
