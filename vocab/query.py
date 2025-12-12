import sqlite3
import json
import random
from datetime import datetime, timedelta

DB_FILE = 'vocab/vocab.db'

# --- 计算下次复习日期 ---
def calculate_next_review_date(current_stage):
    intervals = [1, 2, 4, 7, 15, 30, 60, 90, 180]
    base_interval = intervals[current_stage] if current_stage < len(intervals) else intervals[-1]
    fuzz = random.randint(-max(1, int(base_interval * 0.15)), max(1, int(base_interval * 0.15))) if base_interval > 4 else 0
    return max(1, base_interval + fuzz)

# --- 查询单词 ---
def query_word(word):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM vocab_progress WHERE word=?", (word,))
    row = cursor.fetchone()
    
    if not row:
        print(f"单词 '{word}' 不在数据库中。")
        conn.close()
        return
    
    # 解析数据
    columns = [desc[0] for desc in cursor.description]
    data = dict(zip(columns, row))
    
    # JSON 字段解析
    for field in ['definitions', 'part_of_speech', 'jlpt']:
        try:
            data[field] = json.loads(data[field]) if data[field] else []
        except:
            data[field] = []
    
    # 显示全部信息
    print("=== 单词信息 ===")
    for k, v in data.items():
        print(f"{k}: {v}")
    
    # 修改 stage
    modify = input("是否修改 stage？(y/n): ").strip().lower()
    if modify == 'y':
        try:
            new_stage = int(input("输入新的 stage（整数）: ").strip())
            data['stage'] = new_stage
            # 更新 next_review
            days_until_next = calculate_next_review_date(new_stage-1)
            next_review_date = datetime.today() + timedelta(days=days_until_next)
            data['next_review'] = next_review_date.strftime("%Y-%m-%d")
            data['last_review'] = datetime.today().strftime("%Y-%m-%d")
            
            # 写回数据库
            cursor.execute('''
            UPDATE vocab_progress
            SET stage=?, last_review=?, next_review=?
            WHERE word=?
            ''', (data['stage'], data['last_review'], data['next_review'], word))
            
            conn.commit()
            print(f"更新完成！现在单词 '{word}' 状态如下：")
            print(f"Stage: {data['stage']}, Last review: {data['last_review']}, Next review: {data['next_review']}")
        except ValueError:
            print("无效输入，修改取消。")
    
    conn.close()

# --- 主程序 ---
if __name__ == "__main__":
    while True:
        word = input("请输入要查询的单词（或输入 'exit' 退出）: ").strip()
        if word.lower() == 'exit':
            break
        query_word(word)
