import os 
import datetime
import unicodedata
import streamlit as st   # ←★追加

TODO_FILE = 'todo_list.txt'
COLORS = {"仕事": "\033[94m", "勉強": "\033[95m", "買い物": "\033[93m", "未分類": "\033[0m"}
COLOR_DONE = "\033[92m"
COLOR_OVERDUE = "\033[91m"
RESET_COLOR = "\033[0m"

PRIORITY_LABELS = {1: "緊急", 2: "高", 3: "中", 4: "低"}

# ---------------------------
# Unicode幅計算（絵文字対応）
# ---------------------------
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

# ---------------------------
# ファイル読み書き
# ---------------------------
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

# ---------------------------
# 日付チェック
# ---------------------------
def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        print("⚠️ 日付形式が不正です（YYYY-MM-DD 形式で入力してください）")
        return False

# ---------------------------
# タスク表示
# ---------------------------
def display_todos(todos, indices=None):
    today = datetime.date.today()
    display_list = [todos[i] for i in indices] if indices else todos
    if not display_list:
        print("タスクはありません。")
        return

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
        print(header)
        print("-" * (max_idx_width + status_width + max_title_width + max_cat_width + max_prio_width + max_dl_width + 8))

        for i, t in enumerate(display_list):
            idx = indices[i] if indices else i
            status_icon = "[未]"
            color = COLORS.get(t['cat'], "")
            if t['status'] == "完":
                status_icon = "[完]"
                color = COLOR_DONE
            elif t['dl'] and t['status'] != "完":
                try:
                    dl_date = datetime.datetime.strptime(t['dl'], "%Y-%m-%d").date()
                    if dl_date < today:
                        status_icon = "[超過]"
                        color = COLOR_OVERDUE
                except:
                    pass

            idx_str = pad_right_unicode(f"{idx}:", max_idx_width)
            status_str = pad_status(status_icon, status_width)
            title_str = pad_right_unicode(t['title'], max_title_width)
            cat_str = pad_right_unicode(t['cat'], max_cat_width)
            prio_label = PRIORITY_LABELS.get(t['prio'], "中")
            prio_str = pad_right_unicode(prio_label, max_prio_width)
            dl_str = pad_right_unicode(t['dl'] if t['dl'] else "----------", max_dl_width)

            print(f"{color}{idx_str} {status_str} {title_str} {cat_str} {prio_str} {dl_str}{RESET_COLOR}")

        incomplete_count = sum(1 for t in todos if t['status'] != "完")
        print(f"\n📋 未完了タスク数: {incomplete_count}/{len(todos)}")
    except Exception as e:
        print(f"タスク表示エラー: {e}")

# （中略：すべて同じ・省略しない）

# ---------------------------
# メインループ
# ---------------------------
todos = load()
cmds = {
    "追加": add,
    "表示": show,
    "削除": delete_multi,
    "更新": update_multi,
    "完了": complete_multi,
    "ソート": sort_todos,
    "検索": None,
    "まとめて追加": import_from_file
}

# search wrapper to match earlier name
def search(todos):
    pass

# ---------------------------
# ★★★★★ Streamlit UI（追加部分）★★★★★
# ---------------------------
st.title("📋 ToDo 管理ツール")

st.write("### タスク一覧（ターミナル出力を下部に表示）")
if st.button("表示"):
    st.code("".join(os.popen("python run_display.py").read()))

st.write("### タスク追加")
title = st.text_input("タスク名（複数可;区切り）")
cat = st.text_input("カテゴリ", "未分類")
prio = st.selectbox("優先度", [1, 2, 3, 4])
dl = st.date_input("期限（任意）", None)

if st.button("追加"):
    dl_text = dl.strftime("%Y-%m-%d") if dl else ""
    line = f"{title},{cat},{prio},{dl_text}"
    # 既存の add() の使用
    input_backup = __builtins__.input
    __builtins__.input = lambda _: line
    add(todos)
    __builtins__.input = input_backup
    st.success("追加しました！")

st.write("### 削除 / 完了 / 更新")
delete_str = st.text_input("削除するNo (例: 1,3-5)")
if st.button("削除"):
    bk = __builtins__.input
    __builtins__.input = lambda _: delete_str
    delete_multi(todos)
    __builtins__.input = bk
    st.success("削除しました")

complete_str = st.text_input("完了にするNo (例: 1,3-5)")
if st.button("完了"):
    bk = __builtins__.input
    __builtins__.input = lambda _: complete_str
    complete_multi(todos)
    __builtins__.input = bk
    st.success("完了処理済み")

update_str = st.text_input("更新するNo (例: 1,3-5)")
if st.button("更新"):
    bk = __builtins__.input
    __builtins__.input = lambda _: update_str
    update_multi(todos)
    __builtins__.input = bk
    st.success("更新しました")

st.write("### ソート")
if st.button("ソート（優先度 ⇄ 期限）"):
    sort_todos(todos)
    st.success("ソートしました！")
