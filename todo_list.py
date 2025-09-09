import os

TODO_FILE = 'todo_list.txt'

def load_todos():
    """todo_list.txtからToDoリストを読み込む"""
    if os.path.exists(TODO_FILE):
        with open(TODO_FILE, 'r', encoding='utf-8') as f:
            return f.read().splitlines()
    return []

def save_todos(todos):
    """ToDoリストをtodo_list.txtに保存"""
    with open(TODO_FILE, 'w', encoding='utf-8') as f:
        f.writelines(f"{todo}\n" for todo in todos)

def add_todo(todos):
    """ToDoを追加"""
    item = input("ToDo項目を入力してください: ")
    todos.append(item)
    save_todos(todos)

def show_todos(todos):
    """ToDoを表示"""
    if not todos:
        print("ToDoはまだありません。")
    else:
        for i, todo in enumerate(todos):
            print(f"{i}: {todo}")

def delete_todo(todos):
    """ToDoを削除"""
    try:
        index = int(input("削除するToDoの番号を入力してください: "))
        todos.pop(index)
        save_todos(todos)
    except (ValueError, IndexError):
        print("正しい番号を入力してください。")

def main():
    todos = load_todos()
    commands = {
        "追加": add_todo,
        "表示": show_todos,
        "削除": delete_todo
    }

    while True:
        cmd = input("コマンドを入力してください（追加、表示、削除、終了）: ")
        if cmd == "終了":
            print("終了します。")
            break
        elif cmd in commands:
            commands[cmd](todos)
        else:
            print("無効なコマンドです。")

if __name__ == '__main__':
    main()
