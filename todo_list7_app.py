import streamlit as st
import pandas as pd
import datetime
import os
import unicodedata

# =========================================
# 基本設定
# =========================================
TODO_FILE = "todo_list.txt"

PRIORITY_LABELS = {1: "緊急", 2: "高", 3: "中", 4: "低"}


# =========================================
# Unicode 幅 → 絵文字などのズレ対策（元コードより）
# =========================================
def str_width_unicode(s):
    width = 0
    for ch in s:
        if unicodedata.category(ch) in ('Cc', 'Cf'):
            continue
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            width += 2
        elif 'EMOJI' in unicicode.name(ch, ''):
            width += 2
        else:
            width += 1
    return width


# =========================================
# タスク一覧の読み込み
# =========================================
def load_todos():
    todos = []
    if not os.path.exists(TODO_FILE):
        return todos

    with open(TODO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) < 5:
                continue
            todos.append({
                "title": parts[0],
                "cat": parts[1],
                "prio": int(parts[2]),
                "dl": parts[3] if parts[3] != "None" else None,
                "status": parts[4]
            })
    return todos


# =========================================
# タスク保存
# =========================================
def save_todos(todos):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        for t in todos:
            f.write("|".join([
                t["title"],
                t["cat"],
                str(t["prio"]),
                str(t["dl"]),
                t["status"]
            ]) + "\n")


# =========================================
# 日付バリデーション
# =========================================
def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except Exception:
        return False


# =========================================
# セッションステート初期化
# =========================================
if "todos" not in st.session_state:
    st.session_state.todos = load_todos()

if "sort_count" not in st.session_state:
    st.session_state.sort_count = 0


# =========================================
# タスク DataFrame 化（UI 表示用）
# =========================================
def todos_to_df():
    data = []
    for i, t in enumerate(st.session_state.todos, start=1):
        dl = t["dl"] if t["dl"] else "----------"
        prio_label = PRIORITY_LABELS.get(t["prio"], "中")
        data.append([i, t["title"], t["cat"], prio_label, dl, t["status"]])
    return pd.DataFrame(data, columns=["No", "タイトル", "カテゴリ", "優先度", "期限", "状態"])

# =========================================
# 追加 / まとめて追加 / 検索 UI
# =========================================

# ------- 追加機能（複数タイトル ; 区切り対応） -------
def add_tasks_from_input(titles_str, cat, prio, dl):
    if not titles_str:
        return 0

    titles = [t.strip() for t in titles_str.split(";") if t.strip()]
    if not titles:
        return 0

    added = 0
    for title in titles:
        st.session_state.todos.append({
            "title": title,
            "cat": cat if cat else "未分類",
            "prio": prio if prio in (1,2,3,4) else 3,
            "dl": dl if dl else None,
            "status": "未"
        })
        added += 1

    save_todos(st.session_state.todos)
    return added


# ------- ファイルからまとめて追加（アップロード対応） -------
def import_from_uploaded_file(uploaded_file):
    if not uploaded_file:
        return 0, "ファイルがアップロードされていません。"

    try:
        content = uploaded_file.read().decode("utf-8").splitlines()
    except Exception as e:
        return 0, f"ファイル読み込みに失敗しました: {e}"

    added = 0
    for raw in content:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        title = parts[0] if len(parts) > 0 else None
        if not title:
            continue
        cat = parts[1] if len(parts) > 1 and parts[1] else "未分類"
        prio = 3
        if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 4:
            prio = int(parts[2])
        dl = None
        if len(parts) > 3 and parts[3]:
            if validate_date(parts[3]):
                dl = parts[3]

        st.session_state.todos.append({
            "title": title,
            "cat": cat,
            "prio": prio,
            "dl": dl,
            "status": "未"
        })
        added += 1

    save_todos(st.session_state.todos)
    return added, None


# ------- 検索機能 -------
def filter_todos(keyword):
    if not keyword:
        return st.session_state.todos
    kw = keyword.strip()
    filtered = [t for t in st.session_state.todos if kw in t["title"] or kw in t["cat"]]
    return filtered


# ------- UI：追加 / 取り込み / 検索 -------
def ui_add_and_import_and_search():
    st.sidebar.header("タスク操作")

    # --- 追加フォーム ---
    st.sidebar.subheader("タスクを追加")
    with st.sidebar.form("add_form", clear_on_submit=True):
        titles_str = st.text_input("タイトル（複数は ; で区切る）", help="例: 買い物;振込する")
        cat = st.text_input("カテゴリ", value="未分類")
        prio = st.selectbox("優先度", options=[1,2,3,4], format_func=lambda x: f"{x} - {PRIORITY_LABELS.get(x)}", index=2)
        dl_date = st.text_input("期限 (YYYY-MM-DD、空でなし)", value="")
        submitted_add = st.form_submit_button("追加")

    if submitted_add:
        dl = None
        if dl_date:
            if validate_date(dl_date):
                dl = dl_date
            else:
                st.warning("期限は YYYY-MM-DD の形式で入力してください。期限は保存されません。")
                dl = None
        added = add_tasks_from_input(titles_str, cat, prio, dl)
        if added:
            st.success(f"{added} 件のタスクを追加しました。")
        else:
            st.info("追加されたタスクはありません。")

    # --- ファイル取り込み ---
    st.sidebar.subheader("テキストファイルからまとめて追加")
    st.sidebar.write("1行ごとに: タイトル,カテゴリ,優先度,期限")
    uploaded_file = st.sidebar.file_uploader("ファイルをアップロード（UTF-8テキスト）", type=["txt","csv"])
    if uploaded_file is not None:
        added_cnt, err = import_from_uploaded_file(uploaded_file)
        if err:
            st.sidebar.error(err)
        else:
            st.sidebar.success(f"{added_cnt} 件をインポートしました。")

    # --- 検索 ---
    st.sidebar.subheader("検索")
    search_kw = st.sidebar.text_input("キーワードで検索（タイトル or カテゴリ）")
    if st.sidebar.button("検索実行"):
        filtered = filter_todos(search_kw)
        if not filtered:
            st.sidebar.info("該当タスクはありません。")
        else:
            st.session_state.last_search = search_kw
            st.sidebar.success(f"{len(filtered)} 件が見つかりました。メイン画面で表示します。")


# 自動で UI を初期化
ui_add_and_import_and_search()

# ──────────────────────────────
# ▼▼▼ ここから修正対象 ▼▼▼
# ──────────────────────────────

# 必要最小限の修正①：new_task を事前に初期化
new_task = None

# Priority
new_priority = st.selectbox("Priority", ["High", "Medium", "Low"], key="priority_input")

# Tags (comma-separated)
new_tags = st.text_input("Tags (comma separated)", key="tags_input")

# Due Date
new_due_date = st.date_input("Due Date", key="due_date_input")

# Category
new_category = st.text_input("Category (optional)", key="category_input")

# --- Submit ---
if st.button("Add Task"):
    new_task = torigoe_add_task(
        title=new_title,
        description=new_description,
        priority=new_priority,
        tags=new_tags,
        due_date=str(new_due_date),
        category=new_category,
    )

    # 必要最小限の修正②：この処理を Add Task 内に入れる
    if new_task:
        tasks.append(new_task)
        torigoe_save_tasks(filepath, tasks)
        st.success("Task added successfully!")
        st.rerun()

# ──────────────────────────────
# ▲▲▲ 修正はここまで ▲▲▲
# ──────────────────────────────

st.header("📋 Task List")

if not tasks:
    st.write("No tasks available.")
else:
    task_df = pd.DataFrame(tasks)

    preferred_order = ["id", "title", "description", "priority", "tags", "due_date", "category", "completed_at"]
    task_df = task_df[[c for c in preferred_order if c in task_df.columns]]

    st.dataframe(task_df, use_container_width=True)

st.subheader("🔍 Search Tasks")
keyword = st.text_input("Search by keyword", key="search_box")

if keyword:
    lower_kw = keyword.lower()
    filtered = [
        t for t in tasks
        if lower_kw in t["title"].lower() or lower_kw in t["description"].lower()
    ]
    st.write(f"Found {len(filtered)} tasks")
    st.dataframe(pd.DataFrame(filtered), use_container_width=True)
else:
    filtered = tasks

st.header("🛠 Bulk Actions")

task_ids = [t["id"] for t in filtered]
selected = st.multiselect("Select tasks", task_ids, format_func=lambda x: f"Task {x}")

if st.button("❌ Delete Selected"):
    tasks = [t for t in tasks if t["id"] not in selected]
    torigoe_save_tasks(filepath, tasks)
    st.success(f"Deleted {len(selected)} tasks.")
    st.rerun()

if st.button("✔ Complete Selected"):
    for t in tasks:
        if t["id"] in selected:
            t["completed_at"] = datetime.datetime.now().isoformat()

    torigoe_save_tasks(filepath, tasks)
    st.success(f"Completed {len(selected)} tasks.")
    st.rerun()

st.subheader("✏ Bulk Update")

new_pri = st.selectbox("New Priority", ["(No Change)", "High", "Medium", "Low"])
new_date = st.date_input("New Due Date (optional)", datetime.date.today())

if st.button("Update Selected"):
    for t in tasks:
        if t["id"] in selected:
            if new_pri != "(No Change)":
                t["priority"] = new_pri
            if new_date:
                t["due_date"] = str(new_date)

    torigoe_save_tasks(filepath, tasks)
    st.success("Tasks updated.")
    st.rerun()

st.header("📄 Bulk Add from Text File")

uploaded = st.file_uploader("Upload text file", type=["txt"])

if uploaded:
    lines = uploaded.read().decode("utf-8").splitlines()
    added_count = 0

    for line in lines:
        if line.strip():
            new_task = torigoe_add_task(
                title=line.strip(),
                description="",
                priority="Medium",
                tags="",
                due_date=str(datetime.date.today())
            )
            tasks.append(new_task)
            added_count += 1

    torigoe_save_tasks(filepath, tasks)
    st.success(f"Added {added_count} tasks from file!")
    st.rerun()

st.info("All changes are automatically saved to todo_list.txt.")
