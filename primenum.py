num = int(input("数字を入力してください"))
is_num = False
if num <= 1:
    s_num = False
else:
    for i in range(2, int(num**0.5)+1):
        if num % i == 0:
            break
    else:
        is_num = True
    
if is_num:
    print("素数です")
else:
    print("素数ではありません")