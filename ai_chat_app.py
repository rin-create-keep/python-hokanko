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
        "room": st.session_state.get("current_room", "デフォルトルーム")
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


# ========== 新機能: タスク割り振り ==========
def extract_tasks_from_minutes(minutes_text):
    """議事録からタスクを抽出"""
    try:
        client = OpenAI()
        
        prompt = f"""
以下の議事録からタスク（アクションアイテム）を抽出してください。
各タスクについて以下の形式でJSON配列として出力してください:

[
  {{"task": "タスク内容", "assignee": "担当者名（もしあれば）", "deadline": "期限（もしあれば）"}},
  ...
]

担当者や期限が明記されていない場合は空文字列にしてください。

【議事録】
{minutes_text}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはタスク管理の専門家です。JSON形式で出力してください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON部分を抽出
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        tasks = json.loads(content)
        return tasks
    except Exception as e:
        st.error(f"タスク抽出エラー: {e}")
        return []


def assign_task_to_member(task, member):
    """タスクをメンバーに割り当て"""
    if "task_assignments" not in st.session_state:
        st.session_state.task_assignments = []
    
    assignment = {
        "task": task["task"],
        "assignee": member,
        "deadline": task.get("deadline", ""),
        "status": "未着手",
        "assigned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    st.session_state.task_assignments.append(assignment)


# ========== 新機能: スケジュール管理 ==========
def convert_minutes_to_schedule(minutes_text):
    """議事録をスケジュール形式に変換"""
    try:
        client = OpenAI()
        
        prompt = f"""
以下の議事録から、日時が含まれるイベントやタスクをスケジュール形式で抽出してください。
以下の形式でJSON配列として出力してください:

[
  {{"date": "YYYY-MM-DD", "time": "HH:MM", "event": "イベント内容", "participants": "参加者（もしあれば）"}},
  ...
]

日時が明記されていない場合は推測せず、空配列を返してください。

【議事録】
{minutes_text}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたはスケジュール管理の専門家です。JSON形式で出力してください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSON部分を抽出
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        schedules = json.loads(content)
        return schedules
    except Exception as e:
        st.error(f"スケジュール変換エラー: {e}")
        return []


def add_to_schedule(schedule_item):
    """スケジュールに追加"""
    if "schedules" not in st.session_state:
        st.session_state.schedules = []
    
    st.session_state.schedules.append(schedule_item)
    # 日付順にソート
    st.session_state.schedules.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))


# ========== 新機能: グループルーム管理 ==========
def init_rooms():
    """ルーム機能の初期化"""
    if "rooms" not in st.session_state:
        st.session_state.rooms = {
            "デフォルトルーム": {
                "message_history": [("system", "You are a helpful assistant.")],
                "members": []
            }
        }
    
    if "current_room" not in st.session_state:
        st.session_state.current_room = "デフォルトルーム"


def create_room(room_name, members):
    """新しいルームを作成"""
    if room_name in st.session_state.rooms:
        return False
    
    st.session_state.rooms[room_name] = {
        "message_history": [("system", "You are a helpful assistant.")],
        "members": members,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return True


def switch_room(room_name):
    """ルームを切り替え"""
    if room_name in st.session_state.rooms:
        # 現在のルームの履歴を保存
        if st.session_state.current_room in st.session_state.rooms:
            st.session_state.rooms[st.session_state.current_room]["message_history"] = st.session_state.message_history
        
        # 新しいルームに切り替え
        st.session_state.current_room = room_name
        st.session_state.message_history = st.session_state.rooms[room_name]["message_history"]
        st.rerun()


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


def check_datetime_query(user_input):
    """日時に関する質問かチェック"""
    datetime_keywords = ["今日", "日付", "何日", "何月", "何年", "今", "時間", "何時", "曜日"]
    return any(keyword in user_input for keyword in datetime_keywords)


def get_datetime_response(user_input):
    """日時に関する応答を生成"""
    now = datetime.now()
    
    weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    weekday = weekdays[now.weekday()]
    
    response = f"現在の日時は、{now.year}年{now.month}月{now.day}日({weekday}) {now.hour}時{now.minute}分です。"
    return response


def get_llm_response(user_input: str, image_file=None):
    # 日時に関する質問かチェック
    if check_datetime_query(user_input):
        yield get_datetime_response(user_input)
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
    init_rooms()

    # 🔽 修正②：一度だけURLロード
    if "loaded_from_url" not in st.session_state:
        st.session_state.loaded_from_url = True
        load_conversation_from_url()

    init_messages()
    select_model()

    # ========== 新機能: グループルーム管理UI ==========
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 👥 グループルーム")
    
    # 現在のルーム表示
    st.sidebar.info(f"現在のルーム: **{st.session_state.current_room}**")
    
    # ルーム切り替え
    if len(st.session_state.rooms) > 1:
        selected_room = st.sidebar.selectbox(
            "ルームを選択",
            options=list(st.session_state.rooms.keys()),
            index=list(st.session_state.rooms.keys()).index(st.session_state.current_room)
        )
        if st.sidebar.button("切り替え"):
            switch_room(selected_room)
    
    # 新規ルーム作成
    with st.sidebar.expander("➕ 新規ルーム作成"):
        new_room_name = st.text_input("ルーム名")
        members_input = st.text_area("メンバー（1行に1人）")
        if st.button("ルーム作成"):
            if new_room_name:
                members = [m.strip() for m in members_input.split("\n") if m.strip()]
                if create_room(new_room_name, members):
                    st.success(f"ルーム「{new_room_name}」を作成しました！")
                    st.rerun()
                else:
                    st.error("同名のルームが既に存在します")
    
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
                
                # ========== 新機能: タスク抽出と割り振り ==========
                with st.spinner("タスクを抽出中..."):
                    tasks = extract_tasks_from_minutes(minutes)
                
                if tasks:
                    st.markdown("### ✅ 抽出されたタスク")
                    
                    # ルームのメンバー取得
                    room_members = st.session_state.rooms[st.session_state.current_room].get("members", [])
                    
                    for idx, task in enumerate(tasks):
                        with st.expander(f"タスク {idx + 1}: {task['task'][:50]}..."):
                            st.write(f"**タスク:** {task['task']}")
                            st.write(f"**現在の担当者:** {task.get('assignee', '未割当')}")
                            st.write(f"**期限:** {task.get('deadline', '未設定')}")
                            
                            # メンバーに割り振り
                            if room_members:
                                selected_member = st.selectbox(
                                    "担当者を選択",
                                    options=[""] + room_members,
                                    key=f"assign_{idx}"
                                )
                                if st.button("割り振る", key=f"btn_assign_{idx}"):
                                    if selected_member:
                                        assign_task_to_member(task, selected_member)
                                        st.success(f"{selected_member}にタスクを割り振りました！")
                
                # ========== 新機能: スケジュール変換 ==========
                with st.spinner("スケジュールを抽出中..."):
                    schedules = convert_minutes_to_schedule(minutes)
                
                if schedules:
                    st.markdown("### 📅 スケジュール")
                    for schedule in schedules:
                        add_to_schedule(schedule)
                        st.write(f"- **{schedule.get('date', '')} {schedule.get('time', '')}**: {schedule.get('event', '')}")
                        if schedule.get('participants'):
                            st.write(f"  参加者: {schedule['participants']}")
                
                # ダウンロードボタン
                st.download_button(
                    label="議事録をダウンロード",
                    data=minutes,
                    file_name="minutes.txt",
                    mime="text/plain"
                )

    # ========== 新機能: タスク管理UI ==========
    if "task_assignments" in st.session_state and st.session_state.task_assignments:
        st.sidebar.markdown("---")
        st.sidebar.markdown("## ✅ タスク管理")
        
        with st.sidebar.expander("タスク一覧を表示"):
            for idx, task in enumerate(st.session_state.task_assignments):
                st.write(f"**{task['assignee']}**: {task['task'][:30]}...")
                st.caption(f"期限: {task['deadline']} | 状態: {task['status']}")
    
    # ========== 新機能: スケジュール表示UI ==========
    if "schedules" in st.session_state and st.session_state.schedules:
        st.sidebar.markdown("---")
        st.sidebar.markdown("## 📅 スケジュール")
        
        with st.sidebar.expander("スケジュール一覧を表示"):
            for schedule in st.session_state.schedules:
                st.write(f"**{schedule.get('date', '')} {schedule.get('time', '')}**")
                st.write(f"{schedule.get('event', '')}")
                if schedule.get('participants'):
                    st.caption(f"参加者: {schedule['participants']}")
                st.markdown("---")
