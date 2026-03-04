import os
import streamlit as st
from openai import OpenAI
import anthropic
from google.genai import Client
import json   
import base64
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, parse_qs, quote
from io import BytesIO
from google.genai import types
from pypdf import PdfReader

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


def init_task_assignment():
    if "team_members" not in st.session_state:
        st.session_state.team_members = []
    if "show_tasks" not in st.session_state:
        st.session_state.show_tasks = True


def get_current_room_tasks():
    room_id = st.session_state.get("current_room", "default")
    if "rooms" in st.session_state and room_id in st.session_state.rooms:
        if "tasks" not in st.session_state.rooms[room_id]:
            st.session_state.rooms[room_id]["tasks"] = []
        return st.session_state.rooms[room_id]["tasks"]
    return []


def add_task_assignment(task_name, assignee, deadline=None):
    room_id = st.session_state.get("current_room", "default")
    if "rooms" in st.session_state and room_id in st.session_state.rooms:
        if "tasks" not in st.session_state.rooms[room_id]:
            st.session_state.rooms[room_id]["tasks"] = []
        task = {
            "id": len(st.session_state.rooms[room_id]["tasks"]) + 1,
            "name": task_name,
            "assignee": assignee,
            "deadline": deadline,
            "status": "未着手",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.rooms[room_id]["tasks"].append(task)
        return task
    return None


def delete_task(index):
    tasks = get_current_room_tasks()
    if 0 <= index < len(tasks):
        tasks.pop(index)
        st.rerun()


def update_task(index, task_name=None, assignee=None, deadline=None, status=None):
    tasks = get_current_room_tasks()
    if 0 <= index < len(tasks):
        if task_name is not None:
            tasks[index]["name"] = task_name
        if assignee is not None:
            tasks[index]["assignee"] = assignee
        if deadline is not None:
            tasks[index]["deadline"] = deadline
        if status is not None:
            tasks[index]["status"] = status


def display_task_management():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📋 タスク管理")
    st.sidebar.checkbox(
        "タスクを表示",
        key="show_tasks"
    )
    if not st.session_state.show_tasks:
        return
    with st.sidebar.expander("👥 チームメンバー管理"):
        new_member = st.text_input("メンバー名", key="new_member")
        if st.button("メンバー追加", key="add_member"):
            if new_member and new_member not in st.session_state.team_members:
                st.session_state.team_members.append(new_member)
                st.success(f"{new_member}を追加しました")
                st.rerun()
        if st.session_state.team_members:
            st.write("現在のメンバー:")
            for i, member in enumerate(st.session_state.team_members):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"- {member}")
                with col2:
                    if st.button("❌", key=f"delete_member_{i}"):
                        st.session_state.team_members.remove(member)
                        st.rerun()
    with st.sidebar.expander("➕ 新規タスク追加"):
        task_name = st.text_input("タスク名", key="task_name")
        assignee = st.selectbox("担当者", st.session_state.team_members if st.session_state.team_members else ["メンバーを先に追加してください"], key="task_assignee")
        deadline = st.date_input("期限", key="task_deadline")
        if st.button("タスク追加", key="add_task"):
            if task_name and st.session_state.team_members:
                add_task_assignment(task_name, assignee, deadline.strftime("%Y-%m-%d"))
                st.success(f"タスク「{task_name}」を追加しました")
                st.rerun()
    current_tasks = get_current_room_tasks()
    if current_tasks:
        st.sidebar.write("### 📝 タスク一覧")
        for i, task in enumerate(current_tasks):
            with st.sidebar.expander(f"📌 {task['name']}", expanded=False):
                edit_mode = st.checkbox("編集モード", key=f"edit_task_{i}")
                if edit_mode:
                    new_name = st.text_input("タスク名", value=task["name"], key=f"edit_name_{i}")
                    new_assignee = st.selectbox(
                        "担当者",
                        st.session_state.team_members,
                        index=st.session_state.team_members.index(task["assignee"]) if task["assignee"] in st.session_state.team_members else 0,
                        key=f"edit_assignee_{i}"
                    )
                    if task.get("deadline"):
                        try:
                            default_date = datetime.strptime(task["deadline"], "%Y-%m-%d").date()
                        except:
                            default_date = datetime.now().date()
                    else:
                        default_date = datetime.now().date()
                    new_deadline = st.date_input("期限", value=default_date, key=f"edit_deadline_{i}")
                    new_status = st.selectbox(
                        "状態",
                        ["未着手", "進行中", "完了"],
                        index=["未着手", "進行中", "完了"].index(task['status']),
                        key=f"edit_status_{i}"
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("保存", key=f"save_task_{i}"):
                            update_task(i, new_name, new_assignee, new_deadline.strftime("%Y-%m-%d"), new_status)
                            st.success("更新しました")
                            st.rerun()
                    with col2:
                        if st.button("🗑️ 削除", key=f"delete_task_{i}"):
                            delete_task(i)
                else:
                    st.write(f"**担当**: {task['assignee']}")
                    st.write(f"**期限**: {task.get('deadline', '未設定')}")
                    st.write(f"**状態**: {task['status']}")
                    st.caption(f"作成日時: {task['created_at']}")


def extract_schedule_from_minutes(minutes_text):
    try:
        client = OpenAI()
        prompt = f"""
以下の議事録から、スケジュール情報を抽出してJSON形式で出力してください。
【抽出する情報】
- 日時（開始時刻と終了時刻）
- イベント/会議名
- 参加者
- 場所（あれば）
- アクションアイテム（誰が何をいつまでにやるか）
【出力形式】
{{
  "events": [
    {{
      "date": "YYYY-MM-DD",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "title": "イベント名",
      "participants": ["参加者1", "参加者2"],
      "location": "場所",
      "actions": [
        {{
          "assignee": "担当者",
          "task": "タスク内容",
          "deadline": "YYYY-MM-DD"
        }}
      ]
    }}
  ]
}}
【議事録】
{minutes_text}
"""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたは議事録からスケジュール情報を抽出する専門家です。JSON形式で正確に出力してください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        result = response.choices[0].message.content
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
        return json.loads(result)
    except Exception as e:
        st.error(f"スケジュール抽出エラー: {e}")
        return None


def get_current_room_schedules():
    room_id = st.session_state.get("current_room", "default")
    if "rooms" in st.session_state and room_id in st.session_state.rooms:
        if "schedules" not in st.session_state.rooms[room_id]:
            st.session_state.rooms[room_id]["schedules"] = []
        return st.session_state.rooms[room_id]["schedules"]
    return []


def add_schedule_manually(title, date, start_time, end_time, location, participants):
    room_id = st.session_state.get("current_room", "default")
    if "rooms" in st.session_state and room_id in st.session_state.rooms:
        if "schedules" not in st.session_state.rooms[room_id]:
            st.session_state.rooms[room_id]["schedules"] = []
        schedule = {
            "id": len(st.session_state.rooms[room_id]["schedules"]) + 1,
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "participants": participants,
            "actions": [],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.rooms[room_id]["schedules"].append(schedule)
        return schedule
    return None


def delete_schedule(index):
    schedules = get_current_room_schedules()
    if 0 <= index < len(schedules):
        schedules.pop(index)
        st.rerun()


def update_schedule(index, title=None, date=None, start_time=None, end_time=None, location=None, participants=None):
    schedules = get_current_room_schedules()
    if 0 <= index < len(schedules):
        if title is not None:
            schedules[index]["title"] = title
        if date is not None:
            schedules[index]["date"] = date
        if start_time is not None:
            schedules[index]["start_time"] = start_time
        if end_time is not None:
            schedules[index]["end_time"] = end_time
        if location is not None:
            schedules[index]["location"] = location
        if participants is not None:
            schedules[index]["participants"] = participants


def create_google_calendar_url(schedule):
    try:
        date_str = schedule['date']
        start_time_str = schedule.get('start_time', '09:00')
        end_time_str = schedule.get('end_time', '10:00')
        start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
        start_formatted = start_dt.strftime("%Y%m%dT%H%M%S")
        end_formatted = end_dt.strftime("%Y%m%dT%H%M%S")
        details = []
        if schedule.get('participants'):
            details.append(f"参加者: {', '.join(schedule['participants'])}")
        if schedule.get('actions'):
            details.append("\\n\\nアクションアイテム:")
            for action in schedule['actions']:
                details.append(f"- {action['assignee']}: {action['task']}")
        params = {
            'action': 'TEMPLATE',
            'text': schedule['title'],
            'dates': f"{start_formatted}/{end_formatted}",
            'details': '\\n'.join(details) if details else '',
            'location': schedule.get('location', ''),
        }
        query_string = urlencode(params, quote_via=quote)
        url = f"https://calendar.google.com/calendar/render?{query_string}"
        return url
    except Exception as e:
        st.error(f"URL生成エラー: {e}")
        return None


def display_schedule():
    if "show_schedules" not in st.session_state:
        st.session_state.show_schedules = True
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📅 スケジュール")
    st.sidebar.checkbox(
        "スケジュールを表示",
        key="show_schedules"
    )
    if not st.session_state.show_schedules:
        return
    with st.sidebar.expander("➕ 新規スケジュール追加"):
        new_title = st.text_input("タイトル", key="schedule_title")
        new_date = st.date_input("日付", key="schedule_date")
        col1, col2 = st.columns(2)
        with col1:
            new_start_time = st.time_input("開始時刻", key="schedule_start")
        with col2:
            new_end_time = st.time_input("終了時刻", key="schedule_end")
        new_location = st.text_input("場所（任意）", key="schedule_location")
        new_participants_text = st.text_input("参加者（カンマ区切り）", key="schedule_participants")
        if st.button("スケジュール追加", key="add_schedule_btn"):
            if new_title:
                participants = [p.strip() for p in new_participants_text.split(",")] if new_participants_text else []
                add_schedule_manually(
                    new_title,
                    new_date.strftime("%Y-%m-%d"),
                    new_start_time.strftime("%H:%M"),
                    new_end_time.strftime("%H:%M"),
                    new_location,
                    participants
                )
                st.success(f"スケジュール「{new_title}」を追加しました")
                st.rerun()
    current_schedules = get_current_room_schedules()
    if current_schedules:
        for i, schedule in enumerate(current_schedules):
            with st.sidebar.expander(f"📌 {schedule['title']}", expanded=False):
                edit_mode = st.checkbox("編集モード", key=f"edit_schedule_{i}")
                if edit_mode:
                    new_title = st.text_input("タイトル", value=schedule["title"], key=f"edit_schedule_title_{i}")
                    try:
                        default_date = datetime.strptime(schedule["date"], "%Y-%m-%d").date()
                    except:
                        default_date = datetime.now().date()
                    new_date = st.date_input("日付", value=default_date, key=f"edit_schedule_date_{i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        try:
                            default_start = datetime.strptime(schedule.get("start_time", "09:00"), "%H:%M").time()
                        except:
                            default_start = datetime.strptime("09:00", "%H:%M").time()
                        new_start = st.time_input("開始", value=default_start, key=f"edit_schedule_start_{i}")
                    with col2:
                        try:
                            default_end = datetime.strptime(schedule.get("end_time", "10:00"), "%H:%M").time()
                        except:
                            default_end = datetime.strptime("10:00", "%H:%M").time()
                        new_end = st.time_input("終了", value=default_end, key=f"edit_schedule_end_{i}")
                    new_location = st.text_input("場所", value=schedule.get("location", ""), key=f"edit_schedule_location_{i}")
                    participants_str = ", ".join(schedule.get("participants", []))
                    new_participants_text = st.text_input("参加者", value=participants_str, key=f"edit_schedule_participants_{i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("保存", key=f"save_schedule_{i}"):
                            new_participants = [p.strip() for p in new_participants_text.split(",")] if new_participants_text else []
                            update_schedule(
                                i, new_title, new_date.strftime("%Y-%m-%d"),
                                new_start.strftime("%H:%M"), new_end.strftime("%H:%M"),
                                new_location, new_participants
                            )
                            st.success("更新しました")
                            st.rerun()
                    with col2:
                        if st.button("🗑️ 削除", key=f"delete_schedule_{i}"):
                            delete_schedule(i)
                else:
                    st.write(f"**日時**: {schedule['date']} {schedule.get('start_time', '')} - {schedule.get('end_time', '')}")
                    if schedule.get('location'):
                        st.write(f"**場所**: {schedule['location']}")
                    if schedule.get('participants'):
                        st.write(f"**参加者**: {', '.join(schedule['participants'])}")
                    if schedule.get('actions'):
                        st.write("**アクションアイテム**:")
                        for action in schedule['actions']:
                            st.write(f"- {action['assignee']}: {action['task']} (期限: {action.get('deadline', '未設定')})")
                    google_url = create_google_calendar_url(schedule)
                    if google_url:
                        st.markdown(f"[📅 Googleカレンダーに追加]({google_url})", unsafe_allow_html=False)


def get_current_datetime_info():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y年%m月%d日"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "weekday_jp": ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"][now.weekday()]
    }


def check_time_query(user_input):
    time_keywords = ["時間", "何時", "今何時", "現在時刻", "時刻"]
    date_keywords = ["日付", "今日", "何日", "曜日"]
    for keyword in time_keywords + date_keywords:
        if keyword in user_input:
            return True
    return False


def generate_time_response(user_input):
    dt_info = get_current_datetime_info()
    if "時間" in user_input or "何時" in user_input or "時刻" in user_input:
        return f"現在の時刻は{dt_info['time']}です。"
    elif "日付" in user_input or "何日" in user_input:
        return f"今日は{dt_info['date']}です。"
    elif "曜日" in user_input:
        return f"今日は{dt_info['weekday_jp']}です。"
    else:
        return f"現在は{dt_info['date']}（{dt_info['weekday_jp']}）の{dt_info['time']}です。"


def init_rooms():
    if "rooms" not in st.session_state:
        st.session_state.rooms = {
            "default": {
                "name": "デフォルトルーム",
                "members": [],
                "messages": [("system", "You are a helpful assistant.")],
                "tasks": [],
                "schedules": []
            }
        }
    if "current_room" not in st.session_state:
        st.session_state.current_room = "default"


def create_room(room_name, members):
    room_id = f"room_{len(st.session_state.rooms)}"
    st.session_state.rooms[room_id] = {
        "name": room_name,
        "members": members,
        "messages": [("system", "You are a helpful assistant.")],
        "tasks": [],
        "schedules": []
    }
    return room_id


def delete_room(room_id):
    if room_id in st.session_state.rooms and room_id != "default":
        del st.session_state.rooms[room_id]
        if st.session_state.current_room == room_id:
            st.session_state.current_room = "default"
            st.session_state.message_history = st.session_state.rooms["default"]["messages"]
        st.rerun()


def update_room(room_id, room_name=None, members=None):
    if room_id in st.session_state.rooms:
        if room_name is not None:
            st.session_state.rooms[room_id]["name"] = room_name
        if members is not None:
            st.session_state.rooms[room_id]["members"] = members


def add_member_to_room(room_id, member_name):
    if room_id in st.session_state.rooms:
        if member_name not in st.session_state.rooms[room_id]["members"]:
            st.session_state.rooms[room_id]["members"].append(member_name)
            return True
    return False


def remove_member_from_room(room_id, member_name):
    if room_id in st.session_state.rooms:
        if member_name in st.session_state.rooms[room_id]["members"]:
            st.session_state.rooms[room_id]["members"].remove(member_name)
            return True
    return False


def display_room_management():
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🏠 ルーム管理")
    room_names = {room_id: room["name"] for room_id, room in st.session_state.rooms.items()}
    selected_room = st.sidebar.selectbox(
        "現在のルーム",
        options=list(room_names.keys()),
        format_func=lambda x: room_names[x],
        key="room_selector"
    )
    if selected_room != st.session_state.current_room:
        st.session_state.current_room = selected_room
        st.session_state.message_history = st.session_state.rooms[selected_room]["messages"]
        st.rerun()
    with st.sidebar.expander("➕ 新規ルーム作成"):
        new_room_name = st.text_input("ルーム名", key="new_room_name")
        if st.session_state.team_members:
            selected_members = st.multiselect(
                "メンバー選択",
                st.session_state.team_members,
                key="room_members"
            )
        else:
            st.info("先にチームメンバーを追加してください")
            selected_members = []
        if st.button("ルーム作成", key="create_room"):
            if new_room_name:
                room_id = create_room(new_room_name, selected_members)
                st.success(f"ルーム「{new_room_name}」を作成しました")
                st.rerun()
    current_room_data = st.session_state.rooms[st.session_state.current_room]
    with st.sidebar.expander("✏️ 現在のルームを編集"):
        edit_room_name = st.text_input("ルーム名", value=current_room_data["name"], key="edit_room_name")
        st.markdown("**メンバーを追加**")
        available_members = [m for m in st.session_state.team_members if m not in current_room_data["members"]]
        if available_members:
            member_to_add = st.selectbox(
                "追加するメンバー",
                available_members,
                key="add_member_select"
            )
            if st.button("➕ メンバー追加", key="add_member_to_room_btn"):
                if add_member_to_room(st.session_state.current_room, member_to_add):
                    st.success(f"{member_to_add}を追加しました")
                    st.rerun()
        else:
            st.info("追加可能なメンバーがいません")
        st.markdown("**現在のメンバー**")
        if current_room_data["members"]:
            for member in current_room_data["members"]:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"- {member}")
                with col2:
                    if st.button("❌", key=f"remove_member_{member}"):
                        if remove_member_from_room(st.session_state.current_room, member):
                            st.success(f"{member}を削除しました")
                            st.rerun()
        else:
            st.write("メンバーなし")
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("保存", key="save_room"):
                update_room(st.session_state.current_room, edit_room_name)
                st.success("更新しました")
                st.rerun()
        with col2:
            if st.session_state.current_room != "default":
                if st.button("🗑️ 削除", key="delete_room"):
                    delete_room(st.session_state.current_room)


def _get_room_histories():
    """現在のルームの chat_histories リストを返す（なければ初期化して返す）。"""
    room_id = st.session_state.get("current_room", "default")
    room = st.session_state.get("rooms", {}).get(room_id, {})
    if "chat_histories" not in room:
        room["chat_histories"] = []
    return room["chat_histories"]


def save_chat_history():
    if "message_history" not in st.session_state or len(st.session_state.message_history) <= 1:
        return
    title = "New Chat"
    for role, msg in st.session_state.message_history:
        if role == "user" and isinstance(msg, dict) and msg.get("type") == "text":
            content = msg.get("content", "").strip()
            if content:
                title = content[:30] + ("..." if len(content) > 30 else "")
                break
    chat_data = {
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": st.session_state.message_history.copy(),
        "model": st.session_state.get("model_name", "gpt-3.5-turbo")
    }
    histories = _get_room_histories()
    histories.insert(0, chat_data)
    if len(histories) > 50:
        del histories[50:]


def load_chat_history(index):
    histories = _get_room_histories()
    if 0 <= index < len(histories):
        chat_data = histories[index]
        st.session_state.message_history = chat_data["messages"].copy()
        st.session_state.model_name = chat_data.get("model", "gpt-3.5-turbo")
        st.rerun()


def delete_chat_history(index):
    histories = _get_room_histories()
    if 0 <= index < len(histories):
        histories.pop(index)
        st.rerun()


def encode_conversation(message_history):
    try:
        json_str = json.dumps(message_history, ensure_ascii=False)
        encoded = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8')
        return encoded
    except Exception as e:
        st.error(f"エンコードエラー: {e}")
        return None


def decode_conversation(encoded_str):
    try:
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
        if isinstance(msg, dict):
            if msg.get("type") != "text":
                continue
            content = msg.get("content", "")
        else:
            content = str(msg)
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
    messages = compress_messages_for_share(messages)
    encoded = encode_conversation(messages)
    if not encoded:
        return None
    if len(encoded) > 4000:
        st.warning("⚠️ 会話が長すぎるため、共有URLを生成できません")
        return None
    return encoded


def load_conversation_from_url():
    """
    URLパラメータから会話を読み込む。
    セッション開始時に1回だけ実行される。
    rooms / tasks / schedules / chat_histories は一切上書きしない。
    """
    query_params = st.query_params
    decoded = None
    if "chat" in query_params:
        encoded = query_params.get("chat")
        if isinstance(encoded, list):
            encoded = encoded[0]
        if encoded and len(encoded) > 10:
            decoded = decode_conversation(encoded)
    if decoded:
        # rooms がまだ存在しない場合のみ初期化してから反映
        if "rooms" not in st.session_state:
            st.session_state.rooms = {
                "default": {
                    "name": "デフォルトルーム",
                    "members": [],
                    "messages": decoded,
                    "tasks": [],
                    "schedules": []
                }
            }
            st.session_state.current_room = "default"
        else:
            # 既存 rooms がある場合は現在のルームの messages だけ更新
            current_room = st.session_state.get("current_room", "default")
            st.session_state.rooms[current_room]["messages"] = decoded
        st.session_state.message_history = decoded
        st.success("会話を読み込みました！")


def transcribe_audio(audio_file):
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


def extract_text_from_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        st.error(f"PDF読み込みエラー: {e}")
        return None


def generate_similar_problems(pdf_text):
    try:
        client = OpenAI()
        prompt = f"""
以下は教材・資料の内容です。
この内容をもとに、理解度を確認するための
「同種の問題（練習問題）」を5問作成してください。
【条件】
- 問題文のみ（解答は不要）
- 難易度は元の内容と同程度
- 箇条書きで出力
【資料内容】
{pdf_text[:8000]}
"""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたは教材作成の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"問題生成エラー: {e}")
        return None


def generate_minutes(transcript):
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
        # 現在の会話を履歴に保存してからリセット
        save_chat_history()
        # ── 修正: message_history のみリセット。rooms/tasks/schedules/chat_histories は保持 ──
        new_messages = [("system", "You are a helpful assistant.")]
        st.session_state.message_history = new_messages
        # 現在のルームの messages だけ同期してリセット（他ルームは触らない）
        if "current_room" in st.session_state and "rooms" in st.session_state:
            st.session_state.rooms[st.session_state.current_room]["messages"] = new_messages
        # アップロード画像のみクリア
        st.session_state.current_uploaded_image = None
        st.rerun()

    # ── 修正: message_history が未初期化の場合のみ初期化（rerun後は上書きしない）──
    if "message_history" not in st.session_state:
        if "rooms" in st.session_state and "current_room" in st.session_state:
            current_room = st.session_state.current_room
            st.session_state.message_history = st.session_state.rooms[current_room]["messages"]
        else:
            st.session_state.message_history = [("system", "You are a helpful assistant.")]


def select_model():
    st.session_state.temperature = st.sidebar.slider(
        "Temperature", 0.0, 2.0, 0.0, 0.01
    )
    model = st.sidebar.radio(
        "Choose a model",
        ("GPT-3.5", "GPT-4", "Claude 3.5 Sonnet", "gemini-flash-latest")
    )
    if model == "GPT-3.5":
        st.session_state.model_name = "gpt-3.5-turbo"
    elif model == "GPT-4":
        st.session_state.model_name = "gpt-4o"
    elif model == "Claude 3.5 Sonnet":
        st.session_state.model_name = "claude-3-haiku-20240307"
    else:
        st.session_state.model_name = "gemini-2.5-flash"


def describe_image(image_bytes):
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "この画像について詳しく説明してください。"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_to_base64(image_bytes)}"
                            }
                        }
                    ]
                }
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"画像説明エラー: {e}")
        return None


def check_if_asking_about_generated_image(user_input):
    keywords = ["この画像", "その画像", "今の画像", "画像について", "生成した画像", "作った画像"]
    for keyword in keywords:
        if keyword in user_input:
            return True
    return False


def get_last_generated_image():
    if "message_history" not in st.session_state:
        return None
    for role, message in reversed(st.session_state.message_history):
        if role == "assistant" and isinstance(message, dict) and message.get("type") == "image":
            return message.get("content")
    return None


def get_llm_response(user_input: str, image_file=None):
    model = st.session_state.model_name
    if model.startswith("gpt"):
        client = OpenAI()
        use_model = model
        if image_file and model == "gpt-3.5-turbo":
            use_model = "gpt-4o"
        content = [{"type": "text", "text": user_input}]
        if image_file:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_to_base64(image_file)}"
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
    elif model.startswith("claude"):
        if image_file:
            yield "申し訳ありません。このモデルでは画像を読み込むことができません。テキストでご質問ください。"
            return
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": user_input}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    elif model.startswith("gemini"):
        client = Client(api_key=os.environ["GOOGLE_API_KEY"])
        contents = [{"text": user_input}]
        if image_file:
            contents.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": image_file
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


def image_to_base64(image_bytes: bytes):
    return base64.b64encode(image_bytes).decode("utf-8")


def generate_image(prompt: str):
    client = OpenAI()
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024"
    )
    image_base64 = result.data[0].b64_json
    return base64.b64decode(image_base64)


def calc_and_display_costs():
    output_count = 0
    input_count = 0
    for role, message in st.session_state.message_history:
        if isinstance(message, dict):
            token_count = get_message_counts(message.get("content", ""))
        else:
            token_count = get_message_counts(str(message))
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
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📚 チャット履歴")
    histories = _get_room_histories()
    if not histories:
        return
    for i, chat in enumerate(histories):
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            if st.button(f"📝 {chat['title']}", key=f"load_{i}"):
                load_chat_history(i)
        with col2:
            if st.button("🗑️", key=f"delete_{i}"):
                delete_chat_history(i)
        st.sidebar.caption(f"{chat['timestamp']} | {chat['model']}")



# =============================================================
# ===== ファイルベース永続化 =====
# F5リロード・ブラウザ閉じる・サーバー再起動後もデータを保持する。
# app.py と同じディレクトリに app_state.json を保存する。
# セッションIDはF5で変わるため使用せず、固定ファイル名を使う。
# =============================================================
_PERSIST_KEYS = ["rooms", "current_room", "team_members"]
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_state.json")


def _restore_message_tuples(data):
    """
    JSON はタプルをリストとして復元するため、
    rooms の messages と rooms 内の chat_histories の messages を
    list[tuple] に変換し直す。
    """
    if "rooms" in data:
        for room in data["rooms"].values():
            if "messages" in room:
                room["messages"] = [tuple(m) for m in room["messages"]]
            # ルーム内チャット履歴のメッセージも復元
            if "chat_histories" in room:
                for chat in room["chat_histories"]:
                    if "messages" in chat:
                        chat["messages"] = [tuple(m) for m in chat["messages"]]
    return data


def save_state() -> None:
    """
    永続化対象の session_state を固定 JSON ファイルに書き出す。
    毎 rerun の末尾で呼ぶことで常に最新状態を保存する。
    """
    data = {}
    for k in _PERSIST_KEYS:
        if k in st.session_state:
            data[k] = st.session_state[k]
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass  # 書き込み失敗は無視（機能には影響しない）


def load_state() -> None:
    """
    固定 JSON ファイルから session_state を復元する。
    session_state に既にキーが存在する場合は上書きしない。
    F5リロード後は session_state がリセットされるため
    loaded_from_file フラグもリセットされ、ここで正しく復元される。
    """
    if not os.path.exists(_STATE_FILE):
        return
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = _restore_message_tuples(data)
    except Exception:
        return  # 壊れたファイルは無視
    for k in _PERSIST_KEYS:
        if k in data and k not in st.session_state:
            st.session_state[k] = data[k]

def main():
    init_page()

    # ── ファイルからの復元を最初に実行 ──
    # init_rooms() / init_task_assignment() より前に呼ぶことで、
    # ファイルに保存済みの rooms / team_members が session_state に入り、
    # 各 init_* 関数は「キーが既にある」と判断してデフォルト値で上書きしない。
    # F5リロード後は session_state がリセットされるため
    # loaded_from_file フラグもリセットされ、ここで正しく復元される。
    if "loaded_from_file" not in st.session_state:
        st.session_state.loaded_from_file = True
        load_state()

    # ── ファイル復元後に各種初期化（未設定のキーのみデフォルト値をセット）──
    init_task_assignment()
    init_rooms()

    # ── URL パラメータからの会話読み込み（セッション開始時に1回だけ）──
    if "loaded_from_url" not in st.session_state:
        st.session_state.loaded_from_url = True
        load_conversation_from_url()

    init_messages()
    select_model()

    display_room_management()
    display_task_management()
    display_schedule()
    display_chat_history_sidebar()

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎨 画像生成")
    room_id = st.session_state.get("current_room", "default")
    sidebar_image_prompt = st.sidebar.text_input(
        "生成したい画像の内容",
        key=f"sidebar_image_prompt_{room_id}"
    )
    if st.sidebar.button("画像を生成", key=f"sidebar_image_generate_{room_id}"):
        if sidebar_image_prompt:
            with st.chat_message("assistant"):
                with st.spinner("画像生成中..."):
                    img_bytes = generate_image(sidebar_image_prompt)
                    st.image(img_bytes, use_column_width=True)
                    st.download_button(
                        label="📥 画像をダウンロード",
                        data=img_bytes,
                        file_name=f"generated_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                        mime="image/png",
                        key=f"download_sidebar_image_{room_id}"
                    )
            # ── 修正: ルームの messages にも同期 ──
            img_message = ("assistant", {
                "type": "image",
                "content": base64.b64encode(img_bytes).decode("utf-8")
            })
            st.session_state.message_history.append(img_message)
            st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📄 PDFから問題生成")
    pdf_file = st.sidebar.file_uploader(
        "PDFをアップロード",
        type=["pdf"],
        key=f"pdf_problem_{room_id}"
    )
    if pdf_file and st.sidebar.button("問題を作成", key=f"create_problem_{room_id}"):
        with st.spinner("PDF解析中..."):
            pdf_text = extract_text_from_pdf(pdf_file)
        if pdf_text:
            with st.chat_message("assistant"):
                with st.spinner("問題生成中..."):
                    problems = generate_similar_problems(pdf_text)
                    st.markdown("### 📘 生成された練習問題")
                    st.markdown(problems)
            # ── 修正: ルームの messages にも同期 ──
            prob_message = ("assistant", {"type": "text", "content": problems})
            st.session_state.message_history.append(prob_message)
            st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🔗 会話の共有")
    if st.sidebar.button("共有URLを生成"):
        encoded = create_share_url()
        if encoded:
            st.query_params["chat"] = [encoded]
            st.sidebar.success("URLを生成しました！ブラウザのURLをコピーしてください")
            st.sidebar.caption("※ 共有URLには要約された会話のみが含まれます")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎙️ 音声議事録")
    audio_file = st.sidebar.file_uploader(
        "音声ファイルをアップロード",
        type=["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"],
        key=f"audio_file_{room_id}"
    )
    if audio_file and st.sidebar.button("議事録を作成", key=f"create_minutes_{room_id}"):
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
                # ── 修正: ルームの messages にも同期 ──
                min_message = ("assistant", {"type": "minutes", "content": minutes})
                st.session_state.message_history.append(min_message)
                st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history
                schedule_data = extract_schedule_from_minutes(minutes)
                if schedule_data and "events" in schedule_data:
                    for event in schedule_data["events"]:
                        current_schedules = get_current_room_schedules()
                        current_schedules.append(event)
                        if event.get("actions"):
                            for action in event["actions"]:
                                add_task_assignment(
                                    action["task"],
                                    action["assignee"],
                                    action.get("deadline")
                                )
                    st.success(f"スケジュールとタスクを追加しました（{len(schedule_data['events'])}件）")
                st.download_button(
                    label="議事録をダウンロード",
                    data=minutes,
                    file_name="minutes.txt",
                    mime="text/plain"
                )

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
                            caption="生成された画像",
                            use_column_width=True
                        )
                        st.download_button(
                            label="📥 画像をダウンロード",
                            data=image_bytes,
                            file_name=f"generated_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            key=f"download_history_image_{hash(message['content'])}"
                        )
                    except Exception:
                        st.warning("⚠️ 画像を表示できませんでした")
                elif message["type"] == "minutes":
                    st.markdown("### 📝 議事録")
                    st.markdown(message["content"])
            else:
                st.markdown(message)

    uploaded_image = st.file_uploader(
        "画像をアップロード（質問と一緒に送れます）",
        type=["png", "jpg", "jpeg"],
        key="image_uploader"
    )
    if "current_uploaded_image" not in st.session_state:
        st.session_state.current_uploaded_image = None
    uploaded_image_bytes = None
    if uploaded_image:
        uploaded_image_bytes = uploaded_image.getvalue()
        st.session_state.current_uploaded_image = uploaded_image_bytes
        with st.chat_message("user"):
            st.image(uploaded_image_bytes, caption="アップロードされた画像", use_column_width=True)
    elif st.session_state.current_uploaded_image is not None:
        st.session_state.current_uploaded_image = None
        st.rerun()

    if user_input := st.chat_input("聞きたいことを入力してね！"):
        if user_input.startswith("画像を生成"):
            prompt = user_input.replace("画像を生成", "").strip()
            st.session_state.message_history.append(
                ("user", {"type": "text", "content": user_input})
            )
            with st.chat_message("user"):
                st.markdown(user_input)
            with st.chat_message("assistant"):
                with st.spinner("画像生成中..."):
                    img_bytes = generate_image(prompt)
                    st.image(img_bytes, use_column_width=True)
                    st.download_button(
                        label="📥 画像をダウンロード",
                        data=img_bytes,
                        file_name=f"generated_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                        mime="image/png",
                        key="download_generated_image"
                    )
            st.session_state.message_history.append(
                ("assistant", {
                    "type": "image",
                    "content": base64.b64encode(img_bytes).decode("utf-8")
                })
            )
            # ── 修正: ルームの messages にも同期 ──
            st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history
            st.rerun()

        elif check_time_query(user_input):
            time_response = generate_time_response(user_input)
            st.chat_message("user").markdown(user_input)
            st.chat_message("assistant").markdown(time_response)
            st.session_state.message_history.append(
                ("user", {"type": "text", "content": user_input})
            )
            st.session_state.message_history.append(
                ("assistant", {"type": "text", "content": time_response})
            )
            st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history
            st.rerun()

        elif check_if_asking_about_generated_image(user_input) and not uploaded_image_bytes:
            last_image_b64 = get_last_generated_image()
            if last_image_b64:
                with st.chat_message("user"):
                    st.markdown(user_input)
                st.session_state.message_history.append(
                    ("user", {"type": "text", "content": user_input})
                )
                with st.chat_message("assistant"):
                    with st.spinner("画像を分析中..."):
                        image_bytes = base64.b64decode(last_image_b64)
                        description = describe_image(image_bytes)
                        if description:
                            st.markdown(description)
                            st.session_state.message_history.append(
                                ("assistant", {"type": "text", "content": description})
                            )
                st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history
                st.rerun()
            else:
                st.chat_message("assistant").markdown("申し訳ありません。参照できる画像が見つかりませんでした。")

        else:
            with st.chat_message("user"):
                st.markdown(user_input)
                if uploaded_image_bytes:
                    st.image(uploaded_image_bytes, use_column_width=True)
            st.session_state.message_history.append(
                ("user", {"type": "text", "content": user_input})
            )
            if uploaded_image_bytes:
                img_b64 = image_to_base64(uploaded_image_bytes)
                st.session_state.message_history.append(
                    ("user", {"type": "image", "content": img_b64})
                )
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response_text = ""
                for token in get_llm_response(user_input, uploaded_image_bytes):
                    response_text += token
                    response_placeholder.markdown(response_text)
            st.session_state.message_history.append(
                ("assistant", {"type": "text", "content": response_text})
            )
            st.session_state.rooms[st.session_state.current_room]["messages"] = st.session_state.message_history

    calc_and_display_costs()

    # ── 毎 rerun の末尾で最新状態をファイルに保存 ──
    save_state()


if __name__ == '__main__':
    main()
