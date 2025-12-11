# app.py
import streamlit as st
import pandas as pd
import json
import base64
import requests
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

# -----------------------
# 設定（Streamlit Secrets から取得）
# -----------------------
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]  # owner/repo or repo depending on how user set it
    GITHUB_FILE = st.secrets["GITHUB_FILE"]
    GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", None)
except Exception as e:
    st.error("Streamlit Secrets に GITHUB_TOKEN / GITHUB_REPO / GITHUB_FILE を設定してください。")
    st.stop()

# If user provided only repo in GITHUB_REPO (owner/repo), derive owner/repo
if "/" in GITHUB_REPO:
    OWNER, REPO = GITHUB_REPO.split("/", 1)
else:
    if GITHUB_OWNER:
        OWNER, REPO = GITHUB_OWNER, GITHUB_REPO
    else:
        st.error("GITHUB_REPO は 'owner/repo' 形式か、GITHUB_OWNER と組み合わせて設定してください。")
        st.stop()

API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{GITHUB_FILE}"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# -----------------------
# ユーティリティ：GitHub ファイル取得 / 更新
# -----------------------
def github_get_file() -> Tuple[List[Dict], Optional[str]]:
    """
    GitHub からファイルを取得して JSON を返す。
    戻り値: (tasks_list, sha) sha は更新時に必要。ファイルが無ければ ([], None)
    """
    try:
        r = requests.get(API_BASE, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            j = r.json()
            content = j.get("content", "")
            encoding = j.get("encoding", "base64")
            sha = j.get("sha")
            if encoding == "base64":
                raw = base64.b64decode(content.encode()).decode("utf-8")
                try:
                    data = json.loads(raw)
                    if isinstance(data, list):
                        return data, sha
                    else:
                        # 想定外のデータ型のときは空リストとして扱う
                        return [], sha
                except Exception:
                    return [], sha
            else:
                return [], sha
        elif r.status_code == 404:
            # ファイルがない
            return [], None
        else:
            st.error(f"GitHub からファイル取得に失敗しました (status={r.status_code})")
            return [], None
    except Exception as e:
        st.error(f"GitHub 取得エラー: {e}")
        return [], None

def github_put_file(tasks: List[Dict], message: str = "Update todo_list.json", sha: Optional[str] = None) -> bool:
    """
    tasks を JSON にして GitHub に PUT (create/update) する。
    sha を渡すと更新、None のときは作成。
    """
    try:
        payload_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        b64 = base64.b64encode(payload_text.encode("utf-8")).decode("utf-8")
        payload = {
            "message": message,
            "content": b64,
        }
        if sha:
            payload["sha"] = sha
        r = requests.put(API_BASE, headers=HEADERS, json=payload, timeout=20)
        if r.status_code in (200, 201):
            return True
        else:
            st.error(f"GitHub 書き込みエラー (status={r.status_code}): {r.text}")
            return False
    except Exception as e:
        st.error(f"GitHub 書き込み例外: {e}")
        return False

# -----------------------
# タスク管理ユーティリティ
# -----------------------
PRIORITY_LABELS = {1: "緊急", 2: "高", 3: "中", 4: "低"}

def normalize_task_for_display(t: Dict) -> Dict:
    """
    t: dict with keys title, cat, prio, dl, status
    Returns a normalized dict for frontend display.
    """
    return {
        "title": t.get("title", ""),
        "cat": t.get("cat", "未分類"),
        "prio": int(t.get("prio", 3)) if t.get("prio") is not None else 3,
        "dl": t.get("dl", None),
        "status": t.get("status", "未"),
        "created_at": t.get("created_at", None),
    }

def tasks_to_df(tasks: List[Dict]) -> pd.DataFrame:
    rows = []
    for i, t in enumerate(tasks, start=1):
        rows.append({
            "No": i,
            "タイトル": t.get("title", ""),
            "カテゴリ": t.get("cat", "未分類"),
            "優先度": PRIORITY_LABELS.get(int(t.get("prio", 3)), "中"),
            "prio_int": int(t.get("prio", 3)) if t.get("prio", None) is not None else 3,
            "期限": t.get("dl") if t.get("dl") else "----------",
            "状態": t.get("status", "未"),
            "created_at": t.get("created_at", "")
        })
    df = pd.DataFrame(rows)
    return df

def validate_date_str(s: str) -> bool:
    if not s:
        return True
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False

# -----------------------
# セッション初期化
# -----------------------
if "todos_raw" not in st.session_state:
    # 最初に GitHub からロード（tasks list と sha を保存）
    data, sha = github_get_file()
    # Ensure each entry normalized
    normalized = []
    for item in data:
        # Backward compatibility: if item missing fields, ensure defaults
        t = {
            "title": item.get("title", ""),
            "cat": item.get("cat", "未分類"),
            "prio": int(item.get("prio", 3)) if item.get("prio") is not None else 3,
            "dl": item.get("dl", None),
            "status": item.get("status", "未"),
            "created_at": item.get("created_at", None),
        }
        normalized.append(t)
    st.session_state.todos_raw = normalized
    st.session_state.github_sha = sha
    st.session_state.sort_count = 0
    st.session_state.last_search = ""
    st.session_state.ui_message = ""

# -----------------------
# UI
# -----------------------
st.title("✅ GitHub 永続化 TODO (Streamlit + GitHub)")

# サイドバー: 操作領域
st.sidebar.header("操作")

# ---- 追加（複数対応: ; 区切り） ----
st.sidebar.subheader("タスク追加")
titles_str = st.sidebar.text_input("タイトル（複数は ; で区切る）", help="例: 買い物;振込")
cat = st.sidebar.text_input("カテゴリ", value="未分類")
prio_sel = st.sidebar.selectbox("優先度", options=[1,2,3,4], index=2, format_func=lambda x: f"{x} - {PRIORITY_LABELS.get(x)}")
dl_input = st.sidebar.text_input("期限 (YYYY-MM-DD、空でなし)", value="")

if st.sidebar.button("追加"):
    titles = [s.strip() for s in titles_str.split(";") if s.strip()]
    if not titles:
        st.sidebar.info("タイトルを入力してください。")
    else:
        # reload latest before write (reduce collision)
        latest, sha = github_get_file()
        current = latest
        added = 0
        for t in titles:
            dl = dl_input.strip() if dl_input.strip() else None
            if dl and not validate_date_str(dl):
                st.sidebar.warning(f"期限 '{dl}' の形式が不正です。YYYY-MM-DD を使ってください。期限は未設定になります。")
                dl = None
            task_obj = {
                "title": t,
                "cat": cat if cat else "未分類",
                "prio": int(prio_sel) if prio_sel in (1,2,3,4) else 3,
                "dl": dl,
                "status": "未",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            current.append(task_obj)
            added += 1
        # write back
        ok = github_put_file(current, message=f"Add {added} task(s) via streamlit", sha=sha)
        if ok:
            st.sidebar.success(f"{added} 件を追加しました。")
            # update local session copy
            st.session_state.todos_raw = current
            st.session_state.github_sha = github_get_file()[1]
        else:
            st.sidebar.error("追加に失敗しました。")

# ---- ファイルからまとめて追加 ----
st.sidebar.subheader("ファイルからまとめて追加")
st.sidebar.write("1行: タイトル,カテゴリ,優先度(1-4),期限（YYYY-MM-DD） 先頭に#はコメント")
upload = st.sidebar.file_uploader("テキスト/CSV をアップロード", type=["txt","csv"])
if upload is not None:
    try:
        text_lines = upload.read().decode("utf-8").splitlines()
        latest, sha = github_get_file()
        current = latest or []

        st.write("sha:", sha)
        st.write("latest:", latest)
        
        added = 0
        for line in text_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            title = parts[0] if len(parts) > 0 else None
            if not title:
                continue
            cat_f = parts[1] if len(parts) > 1 and parts[1] else "未分類"
            prio_f = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= 4 else 3
            dl_f = parts[3] if len(parts) > 3 and parts[3] else None
            if dl_f and not validate_date_str(dl_f):
                dl_f = None
            obj = {
                "title": title,
                "cat": cat_f,
                "prio": prio_f,
                "dl": dl_f,
                "status": "未",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            current.append(obj)
            added += 1
        ok = github_put_file(current, message=f"Import {added} tasks via streamlit", sha=sha)
        if ok:
            st.sidebar.success(f"{added} 件インポートしました。")
            st.session_state.todos_raw = current
            st.session_state.github_sha = github_get_file()[1]
        else:
            st.sidebar.error("インポートに失敗しました。")
    except Exception as e:
        st.sidebar.error(f"ファイル読込エラー: {e}")

# ---- 検索 ----
st.sidebar.subheader("検索")
search_kw = st.sidebar.text_input("キーワード（タイトル or カテゴリ）")
if st.sidebar.button("検索実行"):
    st.session_state["last_search"] = search_kw
    st.sidebar.success("検索を適用しました。")

# ---- ソートトグル（奇数回：優先度+期限 / 偶数回：期限） ----
if st.sidebar.button("ソート (切替)"):
    st.session_state.sort_count = st.session_state.get("sort_count", 0) + 1
    st.experimental_rerun()

# -----------------------
# メイン領域：表示
# -----------------------
st.subheader("タスク一覧")

# ensure latest fetch to show current
raw_tasks, _ = github_get_file()
if raw_tasks is None:
    raw_tasks = []

# Use session copy for display to reduce API calls, but refresh if GitHub newer
# (we'll prefer the session copy that we update after writes)
display_tasks = st.session_state.get("todos_raw", raw_tasks)

# Apply search (session last_search has priority)
kw = st.session_state.get("last_search", "")
if kw:
    display_tasks = [t for t in display_tasks if kw.lower() in (t.get("title","").lower() + t.get("cat","").lower())]

# Apply sort toggle behavior (uses session sort_count)
def sort_display(tasks):
    sc = st.session_state.get("sort_count", 0)
    if sc % 2 == 1:
        # odd: priority (small first) then due date
        def keyfn(x):
            pr = int(x.get("prio", 3)) if x.get("prio") is not None else 3
            dl = x.get("dl") or ""
            try:
                dl_date = datetime.strptime(dl, "%Y-%m-%d").date() if dl else date.max
            except Exception:
                dl_date = date.max
            return (pr, dl_date)
        return sorted(tasks, key=keyfn)
    elif sc % 2 == 0 and sc != 0:
        # even but not zero: due date only
        def keyfn2(x):
            dl = x.get("dl") or ""
            try:
                return datetime.strptime(dl, "%Y-%m-%d").date() if dl else date.max
            except Exception:
                return date.max
        return sorted(tasks, key=keyfn2)
    else:
        return tasks

display_tasks = sort_display(display_tasks)

# Build dataframe and show
df = tasks_to_df(display_tasks)
if df.empty:
    st.info("タスクはありません。")
else:
    # show without the helper 'prio_int' column
    show_df = df[["No","タイトル","カテゴリ","優先度","期限","状態","created_at"]]
    st.dataframe(show_df, use_container_width=True)

# -----------------------
# 複数選択（Noベース）
# -----------------------
no_to_index = {row["No"]: idx for idx, row in enumerate(df.to_dict(orient="records"))}
available_nos = list(no_to_index.keys())
selected_nos = st.multiselect("操作するタスクNoを選択（複数可）", options=available_nos, default=[])

# 完了
if st.button("複数完了"):
    if not selected_nos:
        st.warning("少なくとも1つ選択してください。")
    else:
        latest, sha = github_get_file()
        current = latest or []
        for n in selected_nos:
            idx = n - 1
            if 0 <= idx < len(current):
                current[idx]["status"] = "完"
        ok = github_put_file(current, message=f"Mark {len(selected_nos)} tasks as done", sha=sha)
        if ok:
            st.success(f"{len(selected_nos)} 件を完了にしました。")
            st.session_state.todos_raw = current
            st.session_state.github_sha = github_get_file()[1]
            st.experimental_rerun()

# 削除
if st.button("複数削除"):
    if not selected_nos:
        st.warning("少なくとも1つ選択してください。")
    else:
        latest, sha = github_get_file()
        current = latest or []
        # build new list excluding selected indices
        sel_idxs = sorted([n-1 for n in selected_nos], reverse=True)
        for idx in sel_idxs:
            if 0 <= idx < len(current):
                current.pop(idx)
        ok = github_put_file(current, message=f"Delete {len(selected_nos)} tasks", sha=sha)
        if ok:
            st.success(f"{len(selected_nos)} 件を削除しました。")
            st.session_state.todos_raw = current
            st.session_state.github_sha = github_get_file()[1]
            st.experimental_rerun()

# 複数更新（対話式）
st.subheader("複数更新（選択したタスクに対して）")
upd_cat = st.text_input("新カテゴリ (空は変更しない)")
upd_prio = st.selectbox("新優先度 (空で変更しない)", options=["","1 - 緊急","2 - 高","3 - 中","4 - 低"])
upd_dl = st.text_input("新期限 (YYYY-MM-DD、空は変更しない)")

if st.button("複数更新実行"):
    if not selected_nos:
        st.warning("少なくとも1つ選択してください。")
    else:
        latest, sha = github_get_file()
        current = latest or []
        updated = 0
        for n in selected_nos:
            idx = n - 1
            if 0 <= idx < len(current):
                fields_changed = False
                if upd_cat:
                    current[idx]["cat"] = upd_cat
                    fields_changed = True
                if upd_prio and upd_prio != "":
                    current[idx]["prio"] = int(upd_prio.split(" - ")[0])
                    fields_changed = True
                if upd_dl:
                    if validate_date_str(upd_dl):
                        current[idx]["dl"] = upd_dl
                        fields_changed = True
                    else:
                        st.warning(f"{upd_dl} は不正な日付形式です。変更はスキップされます。")
                if fields_changed:
                    updated += 1
        ok = github_put_file(current, message=f"Update {updated} tasks", sha=sha)
        if ok:
            st.success(f"{updated} 件を更新しました。")
            st.session_state.todos_raw = current
            st.session_state.github_sha = github_get_file()[1]
            st.experimental_rerun()

# 検索クリア
if st.button("検索クリア"):
    st.session_state["last_search"] = ""
    st.experimental_rerun()

# 小さなメッセージ
if st.session_state.get("ui_message", ""):
    st.info(st.session_state["ui_message"])
