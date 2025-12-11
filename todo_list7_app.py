import streamlit as st
import json
import os

DATA_FILE = "todo_list.json"


# -----------------------
# タスクを読み込む関数
# -----------------------
def load_tasks():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


# -----------------------
# タスクを書き込む関数
# -----------------------
def save_tasks(tasks):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# -----------------------
# 初期データの読み込み
# -----------------------
if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()


# -----------------------
# タイトル
# -----------------------
st.title("📋 Streamlit TODO アプリ")


# -----------------------
# タスク追加フォーム
# -----------------------
st.subheader("タスクを追加")
new_task = st.text_input("新しいタスクを入力")

if st.button("追加"):
    if new_task.strip() != "":
        st.session_state.tasks.append({"title": new_task, "done": False})
        save_tasks(st.session_state.tasks)
        st.success("追加しました！")
    else:
        st.warning("タスク内容を入力してください。")


# -----------------------
# タスク一覧表示
# -----------------------
st.subheader("タスク一覧")

if not st.session_state.tasks:
    st.info("タスクはまだありません。")
else:
    for i, task in enumerate(st.session_state.tasks):
        col1, col2, col3 = st.columns([0.1, 0.7, 0.2])

        # チェックボックス
        done = col1.checkbox("", value=task["done"], key=f"task_{i}")

        # 内容
        col2.write(f"**{task['title']}**" if not done else f"~~{task['title']}~~")

        # 完了状態を更新
        if done != task["done"]:
            st.session_state.tasks[i]["done"] = done
            save_tasks(st.session_state.tasks)

        # 削除ボタン
        if col3.button("削除", key=f"del_{i}"):
            st.session_state.tasks.pop(i)
            save_tasks(st.session_state.tasks)
            st.experimental_rerun()  # 即反映させる


# -----------------------
# 全削除
# -----------------------
if st.button("すべて削除"):
    st.session_state.tasks = []
    save_tasks([])
    st.experimental_rerun()
