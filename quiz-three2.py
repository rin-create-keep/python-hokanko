import random
import threading

# 〇☓クイズランダム3問（5つから3つ選ぶ）
quiz_data = [
    {"q": "タバコ、ジャガイモ、トマトはナス科の植物か？〇☓かで答えなさい", "a": "〇"},
    {"q": "「QRコード」の「QR」は「クイック・リリース」の言葉の略？〇☓で答えなさい", "a": "☓"},
    {"q": "6、28、497は完全数か?", "a": "☓"},
    {"q": "にんじんに一番多く含まれているビタミンといえばビタミンC", "a": "☓"},
    {"q": "ブカレストはルーマニアの首都", "a": "〇"}
]

# タイマー（10秒）
def input_with_timeout(prompt, timeout=10):
    """タイムアウト付き入力"""
    ans = [None]

    def get_input():
        ans[0] = input(prompt)

    thread = threading.Thread(target=get_input)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        print("\n時間切れ！")
        return None
    return ans[0]

while True:
    # ランダムに3問選ぶ
    questions = random.sample(quiz_data, 3)
    score = 0

    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q['q']}")

        while True:
            ans = input_with_timeout("〇☓どちらかを入力してください（10秒以内）: ", timeout=10)
            if ans is None:  # タイムアウト
                print("不正解！ 正解は「{}」でした。".format(q["a"]))
                break

            # 〇☓の促し
            ans = ans.strip()
            if ans not in ["〇", "☓"]:
                print("〇☓を入れてください")
                continue

            if ans == q['a']:
                print("正解！")
                score += 1
            else:
                print(f"不正解！ 正解は「{q['a']}」でした。")
            break

    # 正答率を計算
    percent = score / 3
    print(f"\n今回の正答率: {percent*100}%")

    # 50％超えたら終了
    if percent > 0.5:  # 正答率が50%より大きいとき
        print("おめでとう！正答率が50％を超えました")
        break
    else:
        print("残念！もう一度挑戦してみましょう\n")
