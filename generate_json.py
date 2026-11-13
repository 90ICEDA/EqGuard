import json

# 根据你提供的列表手动构建映射
gatelookup = {
    "ANDX": 0,
    "AOIX": 1,
    "AOX": 2,
    "BUFX": 3,
    "DFFARX": 4,
    "DFFNX": 5,
    "DFFX": 6,
    "HADDX": 7,
    "HARD_INC": 8,
    "INVX": 9,
    "ISOLANDX": 10,
    "LSDNENX": 11,
    "LSDNX": 12,
    "MUXX": 13,
    "NANDX": 14,
    "NORX": 15,
    "OAIX": 16,
    "OAX": 17,
    "ORX": 18,
    "SDFFSRX": 19,
    "SDFFX": 20,
    "TOP_HARD": 21,
    "TOP_RVT": 22,
    "XNORX": 23,
    "XORX": 24
}

# 最终保存的格式要符合 train.py 的加载逻辑
data = {
    "gatelookup": gatelookup
}

with open('gatelookup_recommended.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4)

print("成功生成 gatelookup_recommended.json！")