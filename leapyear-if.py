year = int(input("何年生まれですか？"))

is_leap = (year % 400 == 0)or((year % 100 != 0)and(year % 4 == 0))

if is_leap:
    print(year, "はうるう年です")
else:

    print(year, "はうるう年ではありません")
