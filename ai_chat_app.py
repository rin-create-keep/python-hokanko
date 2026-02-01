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


# ========== 新機能: タスク割り当て管理 ==========
def init_task_assignments():
    """タスク割り当てデータの初期化"""
    if "task_assignments" not in st.session_state:
        st.session_state.task_assignments = []

def add_task_assignment(task_name, assigned_to, deadline=None, description=""):
    """タスク割り当てを追加"""
    task = {
        "id": len(st.session_state.task_assignments) + 1,
        "task_name": task_name,
        "assigned_to": assigned_to,
        "deadline": deadline,
        "description": description,
        "status": "未着手",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    st.session_state.task_assignments.append(task)

def parse_minutes_for_tasks(minutes_text):
    """議事録からタスクを抽出してAIに提案させる"""
    try:
        client = OpenAI()
        
        prompt = f"""
以下の議事録から、タスクとその担当者を抽出してください。
JSON形式で出力してください。

形式:
{{
    "tasks": [
        {{
            "task_name": "タスク名",
            "assigned_to": "担当者名",
            "deadline": "期限（YYYY-MM-DD形式、不明な場合はnull）",
            "description": "タスクの詳細"
        }}
    ]
}}

議事録:
{minutes_text}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはタスク管理のエキスパートです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("tasks", [])
    except Exception as e:
        st.error(f"タスク抽出エラー: {e}")
        return []

def display_task_assignment_ui():
    """タスク割り当てUIを表示"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📋 タスク管理")
    
    if st.sidebar.button("タスク管理画面を開く"):
        st.session_state.show_task_manager = True
    
    if st.session_state.get("show_task_manager", False):
        with st.expander("📋 タスク割り当て管理", expanded=True):
            st.markdown("### 新規タスクを追加")
            
            col1, col2 = st.columns(2)
            with col1:
                task_name = st.text_input("タスク名")
                assigned_to = st.text_input("担当者")
            with col2:
                deadline = st.date_input("期限")
                description = st.text_area("説明")
            
            if st.button("タスクを追加"):
                if task_name and assigned_to:
                    add_task_assignment(task_name, assigned_to, deadline.strftime("%Y-%m-%d"), description)
                    st.success(f"タスク「{task_name}」を{assigned_to}に割り当てました")
                    st.rerun()
            
            st.markdown("---")
            st.markdown("### 現在のタスク一覧")
            
            if st.session_state.task_assignments:
                for task in st.session_state.task_assignments:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.markdown(f"**{task['task_name']}**")
                            st.caption(task['description'])
                        with col2:
                            st.markdown(f"👤 {task['assigned_to']}")
                            st.caption(f"期限: {task['deadline']}")
                        with col3:
                            status = st.selectbox(
                                "状態",
                                ["未着手", "進行中", "完了"],
                                key=f"status_{task['id']}",
                                index=["未着手", "進行中", "完了"].index(task['status'])
                            )
                            task['status'] = status
                        st.markdown("---")
            else:
                st.info("タスクがまだありません")


# ========== 新機能: スケジュール管理 ==========
def init_schedule():
    """スケジュールデータの初期化"""
    if "schedule_items" not in st.session_state:
        st.session_state.schedule_items = []

def add_schedule_item(date, time, title, description="", participants=""):
    """スケジュールアイテムを追加"""
    item = {
        "id": len(st.session_state.schedule_items) + 1,
        "date": date,
        "time": time,
        "title": title,
        "description": description,
        "participants": participants,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    st.session_state.schedule_items.append(item)

def transfer_minutes_to_schedule(minutes_text):
    """議事録からスケジュールを抽出"""
    try:
        client = OpenAI()
        
        prompt = f"""
以下の議事録から、今後の予定やミーティングを抽出してください。
JSON形式で出力してください。

形式:
{{
    "schedules": [
        {{
            "date": "日付（YYYY-MM-DD形式）",
            "time": "時刻（HH:MM形式、不明な場合はnull）",
            "title": "予定のタイトル",
            "description": "詳細",
            "participants": "参加者（カンマ区切り）"
        }}
    ]
}}

議事録:
{minutes_text}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはスケジュール管理のエキスパートです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("schedules", [])
    except Exception as e:
        st.error(f"スケジュール抽出エラー: {e}")
        return []

def display_schedule_ui():
    """スケジュール管理UIを表示"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📅 スケジュール")
    
    if st.sidebar.button("スケジュール画面を開く"):
        st.session_state.show_schedule = True
    
    if st.session_state.get("show_schedule", False):
        with st.expander("📅 スケジュール管理", expanded=True):
            st.markdown("### スケジュール一覧")
            
            if st.session_state.schedule_items:
                sorted_items = sorted(st.session_state.schedule_items, key=lambda x: (x['date'], x['time'] or ""))
                
                for item in sorted_items:
                    with st.container():
                        st.markdown(f"### 📌 {item['title']}")
                        st.markdown(f"**日時:** {item['date']} {item['time'] or ''}")
                        if item['description']:
                            st.markdown(f"**詳細:** {item['description']}")
                        if item['participants']:
                            st.markdown(f"**参加者:** {item['participants']}")
                        st.markdown("---")
            else:
                st.info("スケジュールがまだありません")


# ========== 新機能: ルーム管理 ==========
def init_rooms():
    """ルームデータの初期化"""
    if "rooms" not in st.session_state:
        st.session_state.rooms = {
            "default": {
                "name": "デフォルトルーム",
                "members": [],
                "messages": [("system", "You are a helpful assistant.")]
            }
        }
    if "current_room" not in st.session_state:
        st.session_state.current_room = "default"

def create_room(room_name, members):
    """新しいルームを作成"""
    room_id = f"room_{len(st.session_state.rooms)}"
    st.session_state.rooms[room_id] = {
        "name": room_name,
        "members": members,
        "messages": [("system", f"このルームは{room_name}です。メンバー: {', '.join(members)}")]
    }
    return room_id

def display_room_ui():
    """ルーム管理UIを表示"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 👥 ルーム管理")
    
    # ルーム作成
    with st.sidebar.expander("➕ 新しいルームを作成"):
        room_name = st.text_input("ルーム名")
        members_input = st.text_input("メンバー（カンマ区切り）")
        
        if st.button("ルームを作成"):
            if room_name:
                members = [m.strip() for m in members_input.split(",")] if members_input else []
                room_id = create_room(room_name, members)
                st.success(f"ルーム「{room_name}」を作成しました")
                st.session_state.current_room = room_id
                st.rerun()
    
    # ルーム選択
    st.sidebar.markdown("### 現在のルーム")
    room_options = {room_id: data["name"] for room_id, data in st.session_state.rooms.items()}
    
    selected_room = st.sidebar.selectbox(
        "ルームを選択",
        options=list(room_options.keys()),
        format_func=lambda x: room_options[x],
        index=list(room_options.keys()).index(st.session_state.current_room)
    )
    
    if selected_room != st.session_state.current_room:
        st.session_state.current_room = selected_room
        st.session_state.message_history = st.session_state.rooms[selected_room]["messages"]
        st.rerun()
    
    # 現在のルーム情報
    current_room_data = st.session_state.rooms[st.session_state.current_room]
    st.sidebar.info(f"📍 {current_room_data['name']}")
    if current_room_data['members']:
        st.sidebar.caption(f"メンバー: {', '.join(current_room_data['members'])}")


# ========== 既存の関数（変更なし）==========
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
        # ルーム対応: 現在のルームのメッセージをクリア
        st.session_state.rooms[st.session_state.current_room]["messages"] = [
            ("system", "You are a helpful assistant.")
        ]
        st.session_state.message_history = st.session_state.rooms[st.session_state.current_room]["messages"]
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
    """LLMレスポンスを取得（時刻・日付対応を追加）"""
    # 時刻・日付に関する質問を検出
    time_keywords = ["時間", "何時", "今何時", "time", "いま"]
    date_keywords = ["日付", "今日", "date", "曜日", "何日"]
    
    is_time_query = any(keyword in user_input.lower() for keyword in time_keywords)
    is_date_query = any(keyword in user_input.lower() for keyword in date_keywords)
    
    if is_time_query or is_date_query:
        now = datetime.now()
        
        if is_time_query:
            current_time = now.strftime("%H:%M:%S")
            yield f"現在の時刻は {current_time} です。"
            return
        
        if is_date_query:
            current_date = now.strftime("%Y年%m月%d日 (%A)")
            weekday_jp = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
            weekday = weekday_jp[now.weekday()]
            yield f"今日は {now.strftime('%Y年%m月%d日')} {weekday}です。"
            return
    
    model = st.session_state.model_name

    # ===== GPT（画像対応）=====
    if model.startswith("gpt"):
        client = OpenAI()
    
        use_model = model
    
        # 🔽 画像があるのに GPT-3.5 の場合は自動で GPT-4o に切替
        if image_file and model == "gpt-3.5-turbo":
            use_model = "gpt-4o"
    
        content = [{"type": "text", "text": user_input}]
    
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
                    "content": user_input
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
            "text": user_input
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
        if isinstance(message, dict):
            token_count = get_message_counts(message.get("content", ""))
        else:
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
    
    # 新機能の初期化
    init_task_assignments()
    init_schedule()
    init_rooms()

    # 🔽 修正②：一度だけURLロード
    if "loaded_from_url" not in st.session_state:
        st.session_state.loaded_from_url = True
        load_conversation_from_url()

    init_messages()
    select_model()

    # 新機能UI
    display_room_ui()
    display_task_assignment_ui()
    display_schedule_ui()
    
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

    
    # 音声議事録機能（拡張版）
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
            
                # チャット履歴に保存
                st.session_state.message_history.append(
                    ("assistant", {"type": "minutes", "content": minutes})
                )
                
                # 新機能: タスクを自動抽出
                st.markdown("---")
                st.markdown("### 📋 タスクを抽出中...")
                tasks = parse_minutes_for_tasks(minutes)
                
                if tasks:
                    st.success(f"{len(tasks)}件のタスクを抽出しました")
                    for task in tasks:
                        add_task_assignment(
                            task["task_name"],
                            task["assigned_to"],
                            task.get("deadline"),
                            task.get("description", "")
                        )
                    st.info("タスク管理画面で確認できます")
                
                # 新機能: スケジュールを自動抽出
                st.markdown("### 📅 スケジュールを抽出中...")
                schedules = transfer_minutes_to_schedule(minutes)
                
                if schedules:
                    st.success(f"{len(schedules)}件の予定を抽出しました")
                    for schedule in schedules:
                        add_schedule_item(
                            schedule["date"],
                            schedule.get("time"),
                            schedule["title"],
                            schedule.get("description", ""),
                            schedule.get("participants", "")
                        )
                    st.info("スケジュール画面で確認できます")
                
                # ダウンロードボタン
                st.download_button(
                    label="議事録をダウンロード",
                    data=minutes,
                    file_name="minutes.txt",
                    mime="text/plain"
                )

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
                            caption="アップロードされた画像",
                            use_container_width=True
                        )
                    except Exception:
                        st.warning("⚠️ 画像を表示できませんでした")
        
                elif message["type"] == "minutes":
                    st.markdown("### 📝 議事録")
                    st.markdown(message["content"])
        
            else:
                # message が str のとき（旧形式対策）
                st.markdown(message)


    # ===== 画像アップロード =====
    uploaded_image = st.file_uploader(
        "画像をアップロード（質問と一緒に送れます）",
        type=["png", "jpg", "jpeg"]
    )
    
    # 画像プレビュー表示（新機能）
    if uploaded_image:
        st.image(uploaded_image, caption="アップロードされた画像（送信前プレビュー）", use_container_width=True)

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
            
            # チャット画面に画像を表示（新機能）
            with st.chat_message("user"):
                st.image(
                    BytesIO(base64.b64decode(img_b64)),
                    caption="送信した画像",
                    use_container_width=True
                )
    
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_text = ""
            for token in get_llm_response(user_input, uploaded_image):
                response_text += token
                response_placeholder.markdown(response_text)
    
        st.session_state.message_history.append(
            ("assistant", {"type": "text", "content": response_text})
        )
        
        # ルームのメッセージも更新
        st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history


    calc_and_display_costs()

if __name__ == '__main__':
    main()
