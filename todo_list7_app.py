import os 
import datetime
import unicodedata

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

# ---------------------------
# タスク操作
# ---------------------------
def add(todos):
    try:
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
    except Exception as e:
        print(f"追加エラー: {e}")

def import_from_file(todos):
    try:
        file_path = input("読み込むファイル名を入力してください（例: import_todo.txt）: ").strip()
        if not os.path.exists(file_path):
            print("ファイルが見つかりません。")
            return

        added_count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                title = parts[0] if len(parts) > 0 else None
                if not title:
                    continue
                cat = parts[1] if len(parts) > 1 and parts[1] else "未分類"
                prio = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 4 else 3
                dl = parts[3] if len(parts) > 3 and validate_date(parts[3]) else None

                todos.append({"title": title, "cat": cat, "prio": prio, "dl": dl, "status": "未"})
                added_count += 1

        save(todos)
        print(f"{added_count}件のタスクをファイルから登録しました。")
    except Exception as e:
        print(f"ファイル登録エラー: {e}")

# ---------------------------
# ソート回数カウント
# ---------------------------
sort_count = 0

def sort_todos(todos):
    global sort_count
    try:
        sort_count += 1
        if sort_count % 2 == 0:
            # 偶数回目は期限順
            def key_dl(x):
                if x['dl']:
                    try:
                        return datetime.datetime.strptime(x['dl'], "%Y-%m-%d").date()
                    except:
                        pass
                return datetime.date.max
            todos.sort(key=key_dl)
            save(todos)
            print("期限順に並び替えました。")
        else:
            # 奇数回目は優先度+期限
            def key_prio_dl(x):
                dl = datetime.date.max
                if x['dl']:
                    try:
                        dl = datetime.datetime.strptime(x['dl'], "%Y-%m-%d").date()
                    except:
                        pass
                return (x['prio'], dl)
            todos.sort(key=key_prio_dl)
            save(todos)
            print("タスクを優先度と期限で並び替えました。")

        show(todos)
    except Exception as e:
        print(f"ソートエラー: {e}")

def show(todos):
    today = datetime.date.today()
    if not todos:
        print("タスクはありません。")
        return
    try:
        max_idx_width = len(str(len(todos))) + 1
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

        for i, t in enumerate(todos, start=1):
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

            idx_str = pad_right_unicode(f"{i}:", max_idx_width)
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

# ---------------------------
# 追加: 複数削除対応関数
# ---------------------------
def delete_multi(todos):
    """
    複数削除（範囲・複数指定対応）
    入力例:
      1,3,5
      2-4
      1,3-5,8
    入力は 1 ベース。無効な番号は無視されます。
    """
    try:
        show(todos)
        raw = input("削除するNoを複数指定してください（例: 1,3-5,8）: ").strip()
        if not raw:
            print("入力が空です。")
            return

        to_delete = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                    if start <= end:
                        to_delete.update(range(start, end + 1))
            elif part.isdigit():
                to_delete.add(int(part))

        # 有効な1ベース番号に限定
        valid = [i for i in to_delete if 1 <= i <= len(todos)]
        if not valid:
            print("削除対象が見つかりません。")
            return

        for i in sorted(valid, reverse=True):
            todos.pop(i - 1)

        save(todos)
        print(f"{len(valid)} 件のタスクを削除しました。")
        show(todos)
    except Exception as e:
        print(f"複数削除エラー: {e}")

# ---------------------------
# 追加: 複数完了対応関数
# ---------------------------
def complete_multi(todos):
    """
    複数完了（範囲・複数指定対応）
    入力例:
      1,3,5
      2-4
      1,3-5,8
    入力は 1 ベース。無効な番号は無視されます。
    """
    try:
        show(todos)
        raw = input("完了にするNoを複数指定してください（例: 1,3-5,8）: ").strip()
        if not raw:
            print("入力が空です。")
            return

        to_complete = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                    if start <= end:
                        to_complete.update(range(start, end + 1))
            elif part.isdigit():
                to_complete.add(int(part))

        valid = [i for i in to_complete if 1 <= i <= len(todos)]
        if not valid:
            print("完了対象が見つかりません。")
            return

        for i in sorted(valid):
            todos[i - 1]['status'] = "完"

        save(todos)
        print(f"{len(valid)} 件のタスクを完了にしました。")
        show(todos)
    except Exception as e:
        print(f"複数完了エラー: {e}")

# ---------------------------
# 追加: 複数更新対応関数
# ---------------------------
def update_multi(todos):
    """
    複数更新（範囲・複数指定対応）
    各タスクごとに順に更新入力を求めます。Enterでその項目をスキップできます。
    入力例（タスク選択）:
      1,3-5,8
    入力は 1 ベース。無効な番号は無視されます。
    """
    try:
        show(todos)
        raw = input("更新するNoを複数指定してください（例: 1,3-5,8）: ").strip()
        if not raw:
            print("入力が空です。")
            return

        to_update = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                bounds = part.split("-")
                if len(bounds) == 2 and bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                    if start <= end:
                        to_update.update(range(start, end + 1))
            elif part.isdigit():
                to_update.add(int(part))

        valid = sorted(i for i in to_update if 1 <= i <= len(todos))
        if not valid:
            print("更新対象が見つかりません。")
            return

        updated_count = 0
        for i in valid:
            t = todos[i - 1]
            print(f"\n--- No {i} の更新 ---")
            print(f"現在のタイトル: {t['title']}")
            new_title = input(f"新タイトル（Enterで保持）: ").strip()
            if new_title:
                t['title'] = new_title

            print(f"現在のカテゴリ: {t['cat']}")
            new_cat = input(f"新カテゴリ（Enterで保持）: ").strip()
            if new_cat:
                t['cat'] = new_cat

            print(f"現在の優先度: {t['prio']}")
            new_pr = input(f"新優先度(1-4、Enterで保持）: ").strip()
            if new_pr.isdigit() and 1 <= int(new_pr) <= 4:
                t['prio'] = int(new_pr)

            print(f"現在の期限: {t['dl'] or 'なし'}")
            new_dl = input(f"新期限(YYYY-MM-DD、Enterで保持）: ").strip()
            if new_dl:
                if validate_date(new_dl):
                    t['dl'] = new_dl
                else:
                    print("期限は保存されませんでした（形式不正）。")

            updated_count += 1

        save(todos)
        print(f"\n{updated_count} 件のタスクを更新しました。")
        show(todos)
    except Exception as e:
        print(f"複数更新エラー: {e}")

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
    try:
        kw = input("検索キーワード: ")
        found = [i for i, t in enumerate(todos) if kw in t['title'] or kw in t['cat']]
        if found:
            display_todos(todos, indices=found)
        else:
            print("該当タスクはありません。")
    except Exception as e:
        print(f"検索エラー: {e}")

cmds["検索"] = search

while True:
    try:
        c = input("コマンド(追加,表示,削除,更新,完了,ソート,検索,まとめて追加,終了): ").strip()
        if c == "終了":
            break
        elif c in cmds:
            cmds[c](todos)
        else:
            print("無効なコマンドです。")
    except Exception as e:
        print(f"予期せぬエラー: {e}")


# =========================================
# ========== Streamlit GUI 部分 ============
# =========================================
import streamlit as st

st.title("📋 TODO 管理アプリ（Streamlit版）")

# ---------------------------
# データ読み込み
# ---------------------------
if "todos" not in st.session_state:
    st.session_state.todos = load()

todos = st.session_state.todos


# ---------------------------
# タスク追加フォーム
# ---------------------------
st.header("➕ タスク追加")

with st.form("add_task_form"):
    title = st.text_input("タイトル")
    category = st.text_input("カテゴリ（例：仕事・勉強・買い物・未分類）", "未分類")
    priority = st.selectbox("優先度 (1:緊急 / 4:低)", [1, 2, 3, 4])
    deadline = st.text_input("期限（YYYY-MM-DD ※任意）")

    add_button = st.form_submit_button("追加")

if add_button:
    dl = deadline if deadline.strip() != "" else None
    todos.append({
        "title": title,
        "cat": category,
        "prio": priority,
        "dl": dl,
        "status": "未"
    })
    save(todos)
    st.success("タスクを追加しました！")


# ---------------------------
# タスク一覧
# ---------------------------
st.header("📄 タスク一覧")

if len(todos) == 0:
    st.info("まだタスクがありません。")
else:
    for i, t in enumerate(todos):

        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])

        with col1:
            st.write(f"**{t['title']}**")
            st.write(f"カテゴリ：{t['cat']}")
            st.write(f"優先度：{PRIORITY_LABELS[t['prio']]}")
            st.write(f"期限：{t['dl'] if t['dl'] else 'なし'}")
            st.write(f"状態：{t['status']}")

        with col2:
            if st.button("完了", key=f"done_{i}"):
                t["status"] = "完"
                save(todos)
                st.experimental_rerun()

        with col3:
            if st.button("削除", key=f"del_{i}"):
                del todos[i]
                save(todos)
                st.experimental_rerun()

        with col4:
            st.write("")  # spacing


# ---------------------------
# 並び替えメニュー
# ---------------------------
st.header("🔃 並び替え")

sort_type = st.selectbox(
    "並び替え方法を選択",
    ["なし", "期限の早い順", "期限の遅い順", "優先度が高い順", "優先度が低い順"]
)

if sort_type != "なし":
    if sort_type == "期限の早い順":
        todos = sorted(todos, key=lambda x: (x['dl'] is None, x['dl']))
    elif sort_type == "期限の遅い順":
        todos = sorted(todos, key=lambda x: (x['dl'] is None, x['dl']), reverse=True)
    elif sort_type == "優先度が高い順":
        todos = sorted(todos, key=lambda x: x['prio'])
    elif sort_type == "優先度が低い順":
        todos = sorted(todos, key=lambda x: x['prio'], reverse=True)

    st.session_state.todos = todos
    save(todos)
    st.experimental_rerun()


# ---------------------------
# 更新ボタン
# ---------------------------
st.header("♻ 全体更新")

if st.button("最新状態を読み込み"):
    st.session_state.todos = load()
    st.success("更新しました！")
    st.experimental_rerun()
