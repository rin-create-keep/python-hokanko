import os 
import datetime
import unicodedata
import streamlit as st

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
# Streamlit用表示ラッパー
# ---------------------------
def st_print(text):
    st.text(text)

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
        st_print("タスクはありません。")
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
        st_print(header)
        st_print("-" * (max_idx_width + status_width + max_title_width + max_cat_width + max_prio_width + max_dl_width + 8))

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

            st_print(f"{idx_str} {status_str} {title_str} {cat_str} {prio_str} {dl_str}")

        incomplete_count = sum(1 for t in todos if t['status'] != "完")
        st_print(f"\n📋 未完了タスク数: {incomplete_count}/{len(todos)}")
    except Exception as e:
        st_print(f"タスク表示エラー: {e}")

# ---------------------------
# タスク操作（変更禁止のためそのまま）
# ---------------------------
def add(todos):
    print("入力例：買い物に行く,私用,3,2025-10-10")
    line = input("タスク名(複数;区切り),カテゴリ,優先度(1:緊急 2:高 3:中 4:低),期限: ").strip()
    if not line:
        print("入力が空です。")
        return

    parts = [p.strip() for p in line.split(",")]
    titles = [x.strip() for x in parts[0].split(";")] if parts else []
    cat = parts[1] if len(parts) > 1 and parts[1] else "未分類"
    prio = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 4 else 3
    dl = None

    if len(parts) > 3 and parts[3]:
        date_input = parts[3]
        while True:
            if validate_date(date_input):
                dl = date_input
                break
            date_input = input("再入力してください (YYYY-MM-DD または Enterでスキップ): ").strip()
            if not date_input:
                dl = None
                break

    for t in titles:
        todos.append({"title": t, "cat": cat, "prio": prio, "dl": dl, "status": "未"})
    save(todos)
    print(f"{len(titles)}件のタスクを追加しました。")

# ------------------------------------------------------
# Streamlit UI（既存コードの最後に追加するだけ）
# ------------------------------------------------------
st.title("タスク管理アプリ（Streamlit版）")

todos = load()

st.header("タスク一覧")
display_todos(todos)

st.header("タスク追加")
title = st.text_input("タスク名（複数の場合 ; で区切る）")
cat = st.text_input("カテゴリ", "未分類")
prio = st.selectbox("優先度", [1, 2, 3, 4])
dl = st.date_input("期限（任意）", None)

if st.button("追加"):
    tlist = [x.strip() for x in title.split(";")] if title else []
    for t in tlist:
        todos.append({
            "title": t,
            "cat": cat,
            "prio": prio,
            "dl": dl.strftime("%Y-%m-%d") if dl else None,
            "status": "未"
        })
    save(todos)
    st.success("追加しました！")
    st.rerun()  # ←← 唯一の変更点（experimental_rerun → rerun）
