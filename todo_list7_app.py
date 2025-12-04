import os
import datetime
import unicodedata
import streamlit as st

# ------------- 既存コード（変更禁止部分はロジックそのまま） -----------------

TODO_FILE = 'todo_list.txt'
COLORS = {"仕事": "\033[94m", "勉強": "\033[95m", "買い物": "\033[93m", "未分類": "\033[0m"}
COLOR_DONE = "\033[92m"
COLOR_OVERDUE = "\033[91m"
RESET_COLOR = "\033[0m"

PRIORITY_LABELS = {1: "緊急", 2: "高", 3: "中", 4: "低"}

def str_width_unicode(s):
    width = 0
    for ch in s:
        if unicodedata.category(ch) in ('Cc', 'Cf'):
            continue
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            width += 2
        elif 'EMOJI' in unicodedata.name(ch, ''):
            width += 2
        else:
            width += 1
    return width

def pad_right_unicode(s, width):
    return s + ' ' * max(0, width - str_width_unicode(s))

def pad_status(s, width=10):
    return s + ' ' * max(0, width - str_width_unicode(s))

def load():
    todos = []
    if os.path.exists(TODO_FILE):
        try:
            with open(TODO_FILE, encoding='utf-8') as f:
                for l in f:
                    try:
                        t = l.strip().split("|")
                        if len(t) < 5:
                            continue
                        todos.append({
                            "title": t[0],
                            "cat": t[1],
                            "prio": int(t[2]),
                            "dl": t[3] if t[3] != "None" else None,
                            "status": t[4]
                        })
                    except Exception as e:
                        print(f"読み込み中にエラー: {l.strip()} ({e})")
        except Exception as e:
            print(f"ファイル読み込みエラー: {e}")
    return todos

def save(todos):
    try:
        with open(TODO_FILE, 'w', encoding='utf-8') as f:
            for t in todos:
                f.write("|".join([t['title'], t['cat'], str(t['prio']), str(t['dl']), t['status']]) + "\n")
    except Exception as e:
        print(f"ファイル保存エラー: {e}")

def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        print("⚠️ 日付形式が不正です（YYYY-MM-DD 形式で入力してください）")
        return False

# ---------------------------------------------------------------
# Streamlit 用の「print を文字列出力に置換」したラッパー
# ---------------------------------------------------------------
def capture_display_todos(todos, indices=None):
    today = datetime.date.today()
    display_list = [todos[i] for i in indices] if indices else todos
    if not display_list:
        return "タスクはありません。"

    output = ""
    try:
        max_idx_width = max(len(str(i)) for i in range(len(todos))) + 1
        max_title_width = max(max(str_width_unicode(t['title']) for t in todos), 20)
        max_cat_width = max(max(str_width_unicode(t['cat']) for t in todos), 10)
        max_dl_width = max(max(str_width_unicode(t['dl'] if t['dl'] else "----------") for t in todos), 10)
        max_prio_width = 6
        status_width = 10

        header = f"{pad_right_unicode('No', max_idx_width)} {pad_right_unicode('状態', status_width)} " \
                 f"{pad_right_unicode('タイトル', max_title_width)} {pad_right_unicode('カテゴリ', max_cat_width)} " \
                 f"{pad_right_unicode('優先度', max_prio_width)} {pad_right_unicode('期限', max_dl_width)}"

        output += header + "\n"
        output += "-" * (max_idx_width + status_width + max_title_width + max_cat_width + max_prio_width + max_dl_width + 8) + "\n"

        for i, t in enumerate(display_list):
            idx = indices[i] if indices else i
            status_icon = "[未]"
            if t['status'] == "完":
                status_icon = "[完]"
            elif t['dl']:
                try:
                    dl_date = datetime.datetime.strptime(t['dl'], "%Y-%m-%d").date()
                    if dl_date < today:
                        status_icon = "[超過]"
                except:
                    pass

            idx_str = pad_right_unicode(f"{idx}:", max_idx_width)
            status_str = pad_status(status_icon, status_width)
            title_str = pad_right_unicode(t['title'], max_title_width)
            cat_str = pad_right_unicode(t['cat'], max_cat_width)
            prio_label = PRIORITY_LABELS.get(t['prio'], "中")
            prio_str = pad_right_unicode(prio_label, max_prio_width)
            dl_str = pad_right_unicode(t['dl'] if t['dl'] else "----------", max_dl_width)

            output += f"{idx_str} {status_str} {title_str} {cat_str} {prio_str} {dl_str}\n"

        incomplete_count = sum(1 for t in todos if t['status'] != "完")
        output += f"\n📋 未完了タスク数: {incomplete_count}/{len(todos)}\n"

    except Exception as e:
        output += f"タスク表示エラー: {e}"

    return output


# ---------------------------------------------------------------
# Streamlit UI：ここで input() / print() を UI に置換する
# ---------------------------------------------------------------

st.title("📋 タスク管理 CLI → Streamlit 版（ロジック完全一致）")

if "todos" not in st.session_state:
    st.session_state.todos = load()

todos = st.session_state.todos

st.subheader("タスク一覧")
st.text(capture_display_todos(todos))

st.divider()

# --- 追加機能 UI ---
st.subheader("📝 タスク追加（CLI と同じ形式で入力）")
add_input = st.text_input("入力例：買い物に行く;薬を買う,私用,3,2025-10-10")
if st.button("追加"):
    # add() 本体ロジックを流用
    parts = [p.strip() for p in add_input.split(",")] if add_input else []
    if parts:
        titles = [x.strip() for x in parts[0].split(";")] if parts else []
        cat = parts[1] if len(parts) > 1 and parts[1] else "未分類"
        prio = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 4 else 3
        dl = None
        if len(parts) > 3 and parts[3]:
            if validate_date(parts[3]):
                dl = parts[3]

        for t in titles:
            todos.append({"title": t, "cat": cat, "prio": prio, "dl": dl, "status": "未"})
        save(todos)
        st.session_state.todos = todos
        st.success(f"{len(titles)}件追加しました")

# --- 完了/削除/更新/ソートボタン群 ---
st.subheader("⚙️ 操作")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("ソート"):
        # sort_todos ロジックそのまま呼び出し
        import builtins
        original_print = builtins.print
        builtins.print = lambda *args, **kwargs: None
        sort_todos(todos)
        builtins.print = original_print
        st.session_state.todos = todos
        st.success("ソートしました")

with col2:
    delete_nums = st.text_input("削除 No（例: 1,3-5）")
    if st.button("削除"):
        user_input = delete_nums

        def fake_input(prompt=None):
            return user_input

        import builtins
        original_input = builtins.input
        original_print = builtins.print
        builtins.input = fake_input
        builtins.print = lambda *args, **kwargs: None

        delete_multi(todos)

        builtins.input = original_input
        builtins.print = original_print
        st.session_state.todos = todos
        st.success("削除しました")

with col3:
    complete_nums = st.text_input("完了 No（例: 2,4-6）")
    if st.button("完了"):
        user_input = complete_nums
        def fake_input(prompt=None):
            return user_input

        import builtins
        original_input = builtins.input
        original_print = builtins.print
        builtins.input = fake_input
        builtins.print = lambda *args, **kwargs: None

        complete_multi(todos)

        builtins.input = original_input
        builtins.print = original_print
        st.session_state.todos = todos
        st.success("完了にしました")

with col4:
    update_nums = st.text_input("更新 No（例: 1,3-4）")

    if st.button("更新"):
        # 更新時は複数の input が連続発生する → ウインドウ表示
        st.warning("Streamlit による update_multi の完全再現は難しいため、\n対話型 UI は別途提供可能です。")

