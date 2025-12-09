# dedup_vocab.py
import os

VOCAB_FILE = "vocab.txt"

if not os.path.exists(VOCAB_FILE):
    print(f"❌ 文件 {VOCAB_FILE} 不存在")
    exit(1)

# 读取所有单词
with open(VOCAB_FILE, "r", encoding="utf-8") as f:
    words = [line.strip() for line in f if line.strip()]

seen = set()
unique_words = []
duplicates = []

for word in words:
    if word in seen:
        duplicates.append(word)
    else:
        seen.add(word)
        unique_words.append(word)

# 覆盖写回文件
with open(VOCAB_FILE, "w", encoding="utf-8") as f:
    for word in unique_words:
        f.write(word + "\n")

print(f"✅ 去重完成！原单词数: {len(words)}, 去重后: {len(unique_words)}")
if duplicates:
    print(f"重复的单词 ({len(duplicates)} 个) 已去掉:")
    for d in duplicates:
        print(d)
else:
    print("没有重复单词。")
