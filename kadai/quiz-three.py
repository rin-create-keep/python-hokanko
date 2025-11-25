import random

# 〇☓クイズランダム3問（5つから3つ選ぶ）
quiz_data = [
    {"q": "タバコ、ジャガイモ、トマトはナス科の植物か？〇☓かで答えなさい", "a": "〇"},
    {"q": "「QRコード」の「QR」は「クイック・リリース」の言葉の略？〇☓で答えなさい", "a": "☓"},
    {"q": "6、28、497は完全数か?", "a": "☓"},
    {"q": "にんじんに一番多く含まれているビタミンといえばビタミンC", "a": "☓"},
    {"q": "ブカレストはルーマニアの首都", "a": "〇"}
]

while True:
    # ランダムに3問選ぶ
    questions = random.sample(quiz_data, 3)
    score = 0

    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q['q']}")
        ans = input("〇☓どちらかを入力してください:").strip().lower()
        if ans == q['a']:
            print("正解！")
            score += 1
        else:
            print(f"不正解！ 正解は「{q['a']}」でした。")

    # 正答率を計算
    percent = score / 3
    print(f"\n今回の正答率: {percent*100}%")

    # 50％超えたら終了
    if percent > 0.5:  # 正答率が50%より大きいとき
        print("おめでとう！正答率が50％を超えました")
        break
    else:
        print("残念！もう一度挑戦してみましょう\n")
