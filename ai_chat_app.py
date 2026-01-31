import os
import streamlit as st
from openai import OpenAI
import anthropic
from google.genai import Client
import json   
import base64
from datetime import datetime
from urllib.parse import urlencode, parse_qs
from io import BytesIO
from google.genai import types
import re

# ===== Gemini Client（Streamlit用）=====
gemini_client = Client(
    api_key=st.secrets["GOOGLE_API_KEY"]
)

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
        "claude-3-haiku-20240307": 3 / 1_000_000,
        "gemini-2.5-flash": 0.35 / 1_000_000
    },
    "output": {
        "gpt-3.5-turbo": 1.5 / 1_000_000,
        "gpt-4o": 15 / 1_000_000,
        "claude-3-haiku-20240307": 15 / 1_000_000,
        "gemini-2.5-flash": 0.70 / 1_000_000
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
        if role == "user" and isinstance(msg, dict) and msg.get("type") == "text":
            content = msg.get("content", "").strip()
            if content:
                title = content[:30] + ("..." if len(content) > 30 else "")
            break

    
    # 保存
    chat_data = {
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": st.session_state.message_history.copy(),
        "model": st.session_state.get("model_name", "gpt-3.5-turbo"),
        "room": st.session_state.get("current_room", "default")
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
        # 🔽 修正①：Base64 パディングを復元
        padding = '=' * (-len(encoded_str) % 4)
        encoded_str += padding

        json_str = base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
        return json.loads(json_str)
    except Exception as e:
        st.error(f"デコードエラー: {e}")
        return None
        
MAX_SHARE_CHARS = 1500

def compress_messages_for_share(messages):
    compressed = []
    total_len = 0

    for role, msg in messages:
        # dict形式（今の実装に合わせる）
        if isinstance(msg, dict):
            if msg.get("type") != "text":
                continue
            content = msg.get("content", "")
        else:
            content = str(msg)

        # assistant は短く
        if role == "assistant":
            content = content[:300] + ("…" if len(content) > 300 else "")

        item_len = len(content)
        if total_len + item_len > MAX_SHARE_CHARS:
            break

        compressed.append((role, {"type": "text", "content": content}))
        total_len += item_len

    return compressed

def create_share_url():
    if "message_history" not in st.session_state:
        return None

    history = st.session_state.message_history

    system = [m for m in history if m[0] == "system"]

    others = [
        m for m in history
        if m[0] != "system"
        and isinstance(m[1], dict)
        and m[1].get("type") == "text"
    ][-12:]

    messages = system + others

    # 🔽 ここが肝
    messages = compress_messages_for_share(messages)

    encoded = encode_conversation(messages)
    if not encoded:
        return None

    # 最終防衛ライン
    if len(encoded) > 4000:
        st.warning("⚠️ 会話が長すぎるため、共有URLを生成できません")
        return None

    return encoded



def load_conversation_from_url():
    query_params = st.query_params
    decoded = None

    if "chat" in query_params:
        encoded = query_params.get("chat")

        if isinstance(encoded, list):
            encoded = encoded[0]

        if encoded and len(encoded) > 10:
            decoded = decode_conversation(encoded)

    if decoded:
        st.session_state.message_history = decoded
        st.success("会話を読み込みました！")


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
        st.session_state.model_name = "claude-3-haiku-20240307"
    else:
        st.session_state.model_name = "gemini-2.5-flash"


def get_llm_response(user_input: str, image_file=None):
    model = st.session_state.model_name
    
    # 現在の日時情報を追加
    current_time = datetime.now().strftime("%Y年%m月%d日 %H時%M分")
    enhanced_input = f"[現在時刻: {current_time}]\n{user_input}"

    # ===== GPT（画像対応）=====
    if model.startswith("gpt"):
        client = OpenAI()
    
        use_model = model
    
        # 🔽 画像があるのに GPT-3.5 の場合は自動で GPT-4o に切替
        if image_file and model == "gpt-3.5-turbo":
            use_model = "gpt-4o"
    
        content = [{"type": "text", "text": enhanced_input}]
    
        if image_file:
            img_b64 = image_to_base64(image_file)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}"
                }
            })
    
        stream = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "user", "content": content}],
            stream=True,
        )
    
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


    # ===== Claude（テキストのみ）=====
    elif model.startswith("claude"):
        # 🔽 画像がアップロードされている場合
        if image_file:
            yield "申し訳ありません。このモデルでは画像を読み込むことができません。テキストでご質問ください。"
            return
    
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": enhanced_input
                }
            ],
        ) as stream:
            for text in stream.text_stream:
                yield text

    # ===== Gemini（画像対応）=====
    elif model.startswith("gemini"):
        client = Client(api_key=os.environ["GOOGLE_API_KEY"])
    
        contents = []
        
        # テキスト
        contents.append({
            "text": enhanced_input
        })
        
        # 画像がある場合
        if image_file:
            image_bytes = image_file.read()
            image_file.seek(0)
        
            contents.append({
                "inline_data": {
                    "mime_type": image_file.type,
                    "data": image_bytes
                }
            })


    
        try:
            response = client.models.generate_content_stream(
                model="models/gemini-flash-latest",
                contents=contents
            )

    
            for chunk in response:
                if chunk.text:
                    yield chunk.text
    
        except Exception as e:
            yield f"⚠️ Geminiエラー: {e}"


def image_to_base64(uploaded_file):
    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    return base64.b64encode(image_bytes).decode("utf-8")

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
    
    # 現在のルームでフィルタリング
    current_room = st.session_state.get("current_room", "default")
    filtered_histories = [
        (i, chat) for i, chat in enumerate(st.session_state.chat_histories)
        if chat.get("room", "default") == current_room
    ]
    
    for i, chat in filtered_histories:
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            if st.button(f"📝 {chat['title']}", key=f"load_{i}"):
                load_chat_history(i)
        with col2:
            if st.button("🗑️", key=f"delete_{i}"):
                delete_chat_history(i)
        st.sidebar.caption(f"{chat['timestamp']} | {chat['model']}")


# ========== 新機能: タスク割り振り ==========
def task_assignment_feature():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 👥 タスク割り振り")
    
    if "tasks" not in st.session_state:
        st.session_state.tasks = []
    
    with st.sidebar.expander("新しいタスクを追加"):
        task_name = st.text_input("タスク名", key="new_task_name")
        assignee = st.text_input("担当者", key="new_task_assignee")
        deadline = st.date_input("期限", key="new_task_deadline")
        
        if st.button("タスクを追加", key="add_task_btn"):
            if task_name and assignee:
                st.session_state.tasks.append({
                    "name": task_name,
                    "assignee": assignee,
                    "deadline": deadline.strftime("%Y-%m-%d"),
                    "status": "未着手"
                })
                st.success(f"タスク '{task_name}' を追加しました！")
                st.rerun()
    
    if st.session_state.tasks:
        st.sidebar.markdown("### 📋 タスク一覧")
        for idx, task in enumerate(st.session_state.tasks):
            with st.sidebar.container():
                col1, col2 = st.sidebar.columns([4, 1])
                with col1:
                    st.markdown(f"**{task['name']}**")
                    st.caption(f"担当: {task['assignee']} | 期限: {task['deadline']}")
                with col2:
                    if st.button("✓", key=f"complete_task_{idx}"):
                        st.session_state.tasks[idx]["status"] = "完了"
                        st.rerun()


# ========== 新機能: 画像生成 ==========
def image_generation_feature():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎨 画像生成")
    
    with st.sidebar.expander("DALL-E で画像を生成"):
        prompt = st.text_area("生成したい画像の説明", key="image_gen_prompt")
        
        if st.button("画像を生成", key="generate_image_btn"):
            if prompt:
                try:
                    client = OpenAI()
                    with st.spinner("画像を生成中..."):
                        response = client.images.generate(
                            model="dall-e-3",
                            prompt=prompt,
                            size="1024x1024",
                            quality="standard",
                            n=1,
                        )
                    
                    image_url = response.data[0].url
                    
                    # 画像をチャット履歴に追加
                    st.session_state.message_history.append(
                        ("assistant", {"type": "generated_image", "content": image_url, "prompt": prompt})
                    )
                    st.success("画像を生成しました！")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"画像生成エラー: {e}")


# ========== 新機能: PDF問題作成 ==========
def pdf_problem_generator():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📄 PDF問題作成")
    
    pdf_file = st.sidebar.file_uploader("PDFをアップロード", type=["pdf"], key="pdf_uploader")
    
    if pdf_file and st.sidebar.button("類似問題を作成", key="create_problems_btn"):
        try:
            # PyPDF2を使ってPDFを読み込む（外部APIは使わない）
            import PyPDF2
            
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            
            # GPTで類似問題を作成
            client = OpenAI()
            prompt = f"""
以下のPDFから抽出したテキストを分析し、同じような形式・難易度の問題を3問作成してください。

【抽出テキスト】
{text[:2000]}

【要件】
- 元の問題の形式を踏襲すること
- 難易度を同程度に保つこと
- 解答と解説も含めること
"""
            
            with st.spinner("問題を作成中..."):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "あなたは優秀な問題作成者です。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
            
            problems = response.choices[0].message.content
            
            # チャット履歴に追加
            st.session_state.message_history.append(
                ("assistant", {"type": "problems", "content": problems})
            )
            st.success("問題を作成しました！")
            st.rerun()
            
        except Exception as e:
            st.error(f"PDF処理エラー: {e}")
            st.info("PyPDF2がインストールされていない可能性があります: pip install PyPDF2")


# ========== 新機能: 議事録→スケジュール変換 ==========
def minutes_to_schedule():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📅 議事録→スケジュール")
    
    if st.sidebar.button("議事録からスケジュール作成", key="create_schedule_btn"):
        # 最新の議事録を取得
        minutes_content = None
        for role, msg in reversed(st.session_state.message_history):
            if isinstance(msg, dict) and msg.get("type") == "minutes":
                minutes_content = msg.get("content")
                break
        
        if minutes_content:
            try:
                client = OpenAI()
                prompt = f"""
以下の議事録から、スケジュール形式のドキュメントを作成してください。

【要件】
- 日時、場所、参加者を記載
- タスクと担当者を一覧化
- 期限がある項目は明記
- Googleカレンダーなどにコピペできる形式

【議事録】
{minutes_content}
"""
                
                with st.spinner("スケジュールを作成中..."):
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "あなたはスケジュール管理の専門家です。"},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3
                    )
                
                schedule = response.choices[0].message.content
                
                st.session_state.message_history.append(
                    ("assistant", {"type": "schedule", "content": schedule})
                )
                st.success("スケジュールを作成しました！")
                st.rerun()
                
            except Exception as e:
                st.error(f"スケジュール作成エラー: {e}")
        else:
            st.warning("議事録が見つかりません。先に議事録を作成してください。")


# ========== 新機能: ルーム管理 ==========
def room_management():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🏠 ルーム管理")
    
    if "rooms" not in st.session_state:
        st.session_state.rooms = {"default": {"name": "デフォルト", "members": []}}
    
    if "current_room" not in st.session_state:
        st.session_state.current_room = "default"
    
    # ルーム選択
    room_options = {k: v["name"] for k, v in st.session_state.rooms.items()}
    selected_room = st.sidebar.selectbox(
        "現在のルーム",
        options=list(room_options.keys()),
        format_func=lambda x: room_options[x],
        key="room_selector"
    )
    
    if selected_room != st.session_state.current_room:
        st.session_state.current_room = selected_room
        save_chat_history()
        st.session_state.message_history = [
            ("system", "You are a helpful assistant.")
        ]
        st.rerun()
    
    # 新しいルームを作成
    with st.sidebar.expander("新しいルームを作成"):
        room_name = st.text_input("ルーム名", key="new_room_name")
        members = st.text_area("メンバー（改行区切り）", key="new_room_members")
        
        if st.button("ルームを作成", key="create_room_btn"):
            if room_name:
                room_id = f"room_{len(st.session_state.rooms)}"
                st.session_state.rooms[room_id] = {
                    "name": room_name,
                    "members": [m.strip() for m in members.split("\n") if m.strip()]
                }
                st.success(f"ルーム '{room_name}' を作成しました！")
                st.rerun()
    
    # 現在のルーム情報を表示
    current_room_info = st.session_state.rooms[st.session_state.current_room]
    if current_room_info["members"]:
        st.sidebar.markdown("### 👥 メンバー")
        for member in current_room_info["members"]:
            st.sidebar.markdown(f"- {member}")


def main():
    init_page()

    # 🔽 修正②：一度だけURLロード
    if "loaded_from_url" not in st.session_state:
        st.session_state.loaded_from_url = True
        load_conversation_from_url()

    init_messages()
    select_model()

    
    # チャット履歴表示
    display_chat_history_sidebar()
    
    # サイドバーに共有機能を追加
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🔗 会話の共有")
    if st.sidebar.button("共有URLを生成"):
        encoded = create_share_url()
        if encoded:
            st.query_params["chat"] = [encoded]
            st.sidebar.success("URLを生成しました！ブラウザのURLをコピーしてください")
            st.sidebar.caption("※ 共有URLには要約された会話のみが含まれます")

    
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
            
                st.markdown("## 📝 生成された議事録")
                st.markdown(minutes)
            
                # 🔽 チャット履歴に保存
                st.session_state.message_history.append(
                    ("assistant", {"type": "minutes", "content": minutes})
                )
                
                # ダウンロードボタン
                st.download_button(
                    label="議事録をダウンロード",
                    data=minutes,
                    file_name="minutes.txt",
                    mime="text/plain"
                )

    # ========== 新機能を呼び出し ==========
    task_assignment_feature()
    image_generation_feature()
    pdf_problem_generator()
    minutes_to_schedule()
    room_management()

    # チャット履歴を表示
    for role, message in st.session_state.get("message_history", []):
        if role == "system":
            continue
    
        with st.chat_message(role):
            if isinstance(message, dict):
                if message["type"] == "text":
                    st.markdown(message["content"])
        
                elif message["type"] == "image":
                    try:
                        image_bytes = base64.b64decode(message["content"])
                        st.image(
                            BytesIO(image_bytes),
                            use_container_width=True
                        )
                    except Exception:
                        st.warning("⚠️ 画像を表示できませんでした")
        
                elif message["type"] == "minutes":
                    st.markdown("### 📝 議事録")
                    st.markdown(message["content"])
                
                elif message["type"] == "generated_image":
                    st.markdown(f"**生成プロンプト:** {message.get('prompt', '')}")
                    st.image(message["content"], use_container_width=True)
                
                elif message["type"] == "problems":
                    st.markdown("### 📚 作成された問題")
                    st.markdown(message["content"])
                
                elif message["type"] == "schedule":
                    st.markdown("### 📅 スケジュール")
                    st.markdown(message["content"])
        
            else:
                # message が str のとき（旧形式対策）
                st.markdown(message)


    # ===== 画像アップロード =====
    uploaded_image = st.file_uploader(
        "画像をアップロード（質問と一緒に送れます）",
        type=["png", "jpg", "jpeg"]
    )

    # ユーザー入力
    if user_input := st.chat_input("聞きたいことを入力してね！"):
        st.chat_message("user").markdown(user_input)
    
        # テキストを保存
        st.session_state.message_history.append(
            ("user", {"type": "text", "content": user_input})
        )
    
        # 画像があれば保存して表示
        if uploaded_image:
            img_b64 = image_to_base64(uploaded_image)
            st.session_state.message_history.append(
                ("user", {"type": "image", "content": img_b64})
            )
            
            # 画像をチャットに表示
            with st.chat_message("user"):
                try:
                    image_bytes = base64.b64decode(img_b64)
                    st.image(BytesIO(image_bytes), use_container_width=True)
                except Exception as e:
                    st.warning(f"⚠️ 画像表示エラー: {e}")
    
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            for token in get_llm_response(user_input, uploaded_image):
                response_text += token
                response_placeholder.markdown(response_text)
    
        st.session_state.message_history.append(
            ("assistant", {"type": "text", "content": response_text})
        )


    calc_and_display_costs()

if __name__ == '__main__':
    main()
