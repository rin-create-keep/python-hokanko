import calendar

while True:
    year = int(input("何年生まれですか？"))
    if calendar.isleap(year):
        print(year, "年はうるう年です")
        break
    else:
        print(year, "年はうるう年ではありません")