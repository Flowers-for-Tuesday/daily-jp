import sqlite3
import json
import random
import requests
from datetime import datetime, timedelta
from jisho_api import jisho_api

DB_FILE = 'vocab/vocab.db'

# --- 计算下次复习日期 ---
def calculate_next_review_date(current_stage):
    intervals = [1, 2, 4, 7, 15, 30, 60, 90, 180]
    base_interval = intervals[current_stage] if current_stage < len(intervals) else intervals[-1]
    fuzz = random.randint(-max(1, int(base_interval * 0.15)), max(1, int(base_interval * 0.15))) if base_interval > 4 else 0
    return max(1, base_interval + fuzz)

# --- 添加单词到数据库 ---
def add_word_to_db(word):
    """添加新单词到数据库"""
    print(f"正在获取单词 '{word}' 的信息...")
    
    # 调用Jisho API获取单词信息
    word_data = jisho_api(word)
    
    if "error" in word_data:
        print(f"获取单词信息失败: {word_data['error']}")
        return False
    
    # 提取API返回的数据
    word_form = word_data.get("word", word)  # 如果API返回空，使用原词
    reading = word_data.get("reading", "")
    definitions = word_data.get("definitions", [])
    part_of_speech = word_data.get("part_of_speech", [])
    is_common = word_data.get("is_common", 0)
    jlpt = word_data.get("jlpt", [])
    
    # 将列表转换为JSON字符串
    definitions_json = json.dumps(definitions) if definitions else ""
    part_of_speech_json = json.dumps(part_of_speech) if part_of_speech else ""
    jlpt_json = json.dumps(jlpt) if jlpt else ""
    
    # 连接数据库
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # 检查单词是否已存在
        cursor.execute("SELECT word FROM vocab_progress WHERE word=?", (word_form,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"单词 '{word_form}' 已在数据库中。")
            conn.close()
            return False
        
        # 插入新单词
        cursor.execute('''
        INSERT INTO vocab_progress 
        (word, stage, first_seen, last_review, next_review, 
         reading, definitions, part_of_speech, is_common, jlpt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            word_form, 0, "", "", "",  # stage=0, 其他时间字段为空
            reading, definitions_json, part_of_speech_json, is_common, jlpt_json
        ))
        
        conn.commit()
        print(f"✓ 单词 '{word_form}' 已成功添加到数据库")
        print(f"  读音: {reading if reading else '暂无'}")
        print(f"  释义: {', '.join(definitions[:3]) if definitions else '暂无'}")
        print(f"  阶段: 0 (未学习)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"添加单词失败: {e}")
        conn.rollback()
        conn.close()
        return False

# --- 统计功能 ---
def get_statistics():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 总单词数
    cursor.execute("SELECT COUNT(*) FROM vocab_progress")
    total_words = cursor.fetchone()[0]
    
    # 未学习单词数 (stage = 0)
    cursor.execute("SELECT COUNT(*) FROM vocab_progress WHERE stage = 0")
    unlearned_words = cursor.fetchone()[0]
    
    # 已学习单词数 (stage > 0)
    cursor.execute("SELECT COUNT(*) FROM vocab_progress WHERE stage > 0")
    learned_words = cursor.fetchone()[0]
    
    # 今日需要复习的单词数
    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM vocab_progress WHERE next_review <= ? AND stage > 0", (today,))
    today_review = cursor.fetchone()[0]
    
    # 各个stage的分布数
    cursor.execute("SELECT stage, COUNT(*) FROM vocab_progress GROUP BY stage ORDER BY stage")
    stage_distribution = cursor.fetchall()
    
    # 常用单词统计
    cursor.execute("SELECT COUNT(*) FROM vocab_progress WHERE is_common = 1")
    common_words = cursor.fetchone()[0]
    
    # JLPT级别统计 - 使用精确解析
    cursor.execute("SELECT jlpt FROM vocab_progress WHERE jlpt IS NOT NULL AND jlpt != ''")
    jlpt_rows = cursor.fetchall()
    
    # 解析JLPT数据
    jlpt_stats = {'N1': 0, 'N2': 0, 'N3': 0, 'N4': 0, 'N5': 0}
    for row in jlpt_rows:
        jlpt_str = row[0]
        if jlpt_str:
            try:
                jlpt_list = json.loads(jlpt_str)
                if isinstance(jlpt_list, list):
                    for item in jlpt_list:
                        if 'jlpt-n1' in item.lower():
                            jlpt_stats['N1'] += 1
                        elif 'jlpt-n2' in item.lower():
                            jlpt_stats['N2'] += 1
                        elif 'jlpt-n3' in item.lower():
                            jlpt_stats['N3'] += 1
                        elif 'jlpt-n4' in item.lower():
                            jlpt_stats['N4'] += 1
                        elif 'jlpt-n5' in item.lower():
                            jlpt_stats['N5'] += 1
            except:
                continue
    
    conn.close()
    
    return {
        'total_words': total_words,
        'unlearned_words': unlearned_words,
        'learned_words': learned_words,
        'today_review': today_review,
        'stage_distribution': dict(stage_distribution),
        'common_words': common_words,
        'jlpt_stats': jlpt_stats
    }

# --- 显示统计信息 ---
def show_statistics():
    stats = get_statistics()
    
    print("\n" + "="*60)
    print("单词学习统计")
    print("="*60)
    print(f"总单词数: {stats['total_words']}")
    print(f"未学习单词: {stats['unlearned_words']}")
    print(f"已学习单词: {stats['learned_words']}")
    print(f"今日需要复习的单词: {stats['today_review']}")
    print(f"常用单词: {stats['common_words']}")
    
    # 显示JLPT分布（如果有数据）
    jlpt_total = sum(stats['jlpt_stats'].values())
    if jlpt_total > 0:
        print("\nJLPT级别分布:")
        print("-"*30)
        for level in ['N5', 'N4', 'N3', 'N2', 'N1']:  # 按级别从低到高显示
            count = stats['jlpt_stats'][level]
            if count > 0:
                percentage = (count / jlpt_total * 100)
                print(f"  {level}: {count} 个 ({percentage:.1f}%)")
    
    print("\n各阶段单词分布:")
    print("-"*30)
    for stage, count in sorted(stats['stage_distribution'].items()):
        percentage = (count / stats['total_words'] * 100) if stats['total_words'] > 0 else 0
        print(f"Stage {stage}: {count:4d} 个 ({percentage:5.1f}%)")
    
    # 显示学习进度条
    if stats['total_words'] > 0:
        learned_percentage = (stats['learned_words'] / stats['total_words']) * 100
        
        print("\n学习进度:")
        progress_bar = '█' * int(learned_percentage/5) + '░' * (20 - int(learned_percentage/5))
        print(f"已学习: [{progress_bar}] {learned_percentage:.1f}%")
    
    print("="*60 + "\n")

# --- 重置单词（删除并重新添加） ---
def reset_word(word):
    """重置单词，删除后重新添加"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 删除原单词
    cursor.execute("DELETE FROM vocab_progress WHERE word=?", (word,))
    conn.commit()
    conn.close()
    
    # 重新添加单词
    return add_word_to_db(word)

# --- 查询单词 ---
def query_word(word):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM vocab_progress WHERE word=?", (word,))
    row = cursor.fetchone()
    
    if not row:
        # 单词不存在，询问是否添加
        print(f"单词 '{word}' 不在数据库中。")
        add_option = input("是否添加该单词到数据库？(y/n): ").strip().lower()
        
        if add_option == 'y':
            conn.close()
            # 调用添加单词功能
            if add_word_to_db(word):
                # 添加成功后，重新查询显示
                query_word(word)
            return
        else:
            conn.close()
            return
    
    # 解析数据
    columns = ['word', 'stage', 'first_seen', 'last_review', 'next_review', 
               'reading', 'definitions', 'part_of_speech', 'is_common', 'jlpt']
    data = dict(zip(columns, row))
    
    # JSON 字段解析
    for field in ['definitions', 'part_of_speech', 'jlpt']:
        try:
            data[field] = json.loads(data[field]) if data[field] else []
        except:
            data[field] = []
    
    # 显示单词信息
    print("\n" + "="*60)
    print(f"单词: {data['word']}")
    print("="*60)
    
    # 基本信息
    print(f"读音: {data.get('reading', 'N/A')}")
    print(f"阶段 (Stage): {data.get('stage', 0)}")
    print(f"是否常用: {'是' if data.get('is_common') else '否'}")
    print(f"首次出现: {data.get('first_seen', '从未学习')}")
    print(f"上次复习: {data.get('last_review', '从未')}")
    print(f"下次复习: {data.get('next_review', '未设置')}")
    
    # 释义
    if data.get('definitions'):
        print(f"释义: {', '.join(data['definitions'])}")
    
    # 词性
    if data.get('part_of_speech'):
        print(f"词性: {', '.join(data['part_of_speech'])}")
    
    # JLPT级别
    if data.get('jlpt'):
        jlpt_levels = [item.upper() for item in data['jlpt'] if item]
        if jlpt_levels:
            print(f"JLPT级别: {', '.join(jlpt_levels)}")
    
    print("="*60)
    
    # 操作选择
    while True:
        print("\n请选择操作:")
        print("1. 修改单词阶段 (stage)")
        print("2. 从数据库中删除此单词")
        print("3. 返回主菜单")
        
        choice = input("请输入选项 (1-3): ").strip()
        
        if choice == '1':
            # 修改 stage
            try:
                current_stage = data.get('stage', 0)
                new_stage = int(input(f"输入新的 stage（当前: {current_stage}, 0表示重置为未学习）: ").strip())
                
                if new_stage == 0:
                    # 特殊处理：stage=0表示重置单词
                    print("重置单词为未学习状态，将重新获取单词信息...")
                    conn.close()
                    if reset_word(word):
                        # 重置成功后，重新查询显示
                        query_word(word)
                    return
                else:
                    data['stage'] = new_stage
                    
                    # 计算下次复习日期
                    days_until_next = calculate_next_review_date(new_stage-1)
                    next_review_date = datetime.today() + timedelta(days=days_until_next)
                    data['next_review'] = next_review_date.strftime("%Y-%m-%d")
                    data['last_review'] = datetime.today().strftime("%Y-%m-%d")
                    
                    # 如果是第一次学习，设置first_seen
                    if not data.get('first_seen'):
                        data['first_seen'] = datetime.today().strftime("%Y-%m-%d")
                    
                    # 更新数据库
                    cursor.execute('''
                    UPDATE vocab_progress
                    SET stage=?, last_review=?, next_review=?, first_seen=?
                    WHERE word=?
                    ''', (data['stage'], data['last_review'], data['next_review'], 
                          data.get('first_seen'), word))
                    
                    conn.commit()
                    print(f"\n✓ 更新完成！现在单词 '{word}' 的状态:")
                    print(f"  Stage: {data['stage']}")
                    print(f"  Last review: {data['last_review'] or '从未'}")
                    print(f"  Next review: {data['next_review'] or '未设置'}")
                    print(f"  将在 {days_until_next} 天后再次复习")
                
            except ValueError:
                print("✗ 无效输入，修改取消。")
            
            # 询问是否继续其他操作
            continue_option = input("\n是否继续对此单词进行其他操作？(y/n): ").strip().lower()
            if continue_option != 'y':
                break
        
        elif choice == '2':
            # 删除单词
            confirm = input(f"确认要删除单词 '{word}' 吗？此操作不可撤销！(输入 'yes' 确认): ").strip().lower()
            
            if confirm == 'yes':
                cursor.execute("DELETE FROM vocab_progress WHERE word=?", (word,))
                conn.commit()
                print(f"✓ 单词 '{word}' 已从数据库中删除。")
                conn.close()
                return  # 直接返回主菜单
            else:
                print("✗ 删除操作已取消。")
        
        elif choice == '3':
            # 返回主菜单
            break
        
        else:
            print("✗ 无效选项，请重新选择。")
    
    conn.close()

# --- 解析命令 ---
def parse_command(user_input):
    """解析用户输入的命令"""
    parts = user_input.strip().split(maxsplit=1)
    
    if not parts:
        return None, None
    
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""
    
    return command, argument

# --- 主程序 ---
if __name__ == "__main__":
    print("日语单词学习系统")
    print("="*30)
    print("输入 'help' 查看可用命令\n")
    
    while True:
        user_input = input("请输入命令: ").strip()
        
        if not user_input:
            continue
        
        command, argument = parse_command(user_input)
        
        if command == 'exit':
            print("バイバイ！")
            break
        
        elif command == 'stats':
            show_statistics()
        
        elif command == 'help':
            print("\n可用命令:")
            print("  query [单词]     - 查询单词信息")
            print("  add [单词]       - 添加新单词")
            print("  stats           - 显示统计信息")
            print("  exit            - 退出程序")
            print("  help            - 显示此帮助")
            print("\n示例:")
            print("  query 夜         - 查询单词'夜'")
            print("  add 山           - 添加单词'山'")
            print("  stats           - 显示学习统计\n")
        
        elif command == 'query':
            if not argument:
                print("✗ 请指定要查询的单词。")
                print("  用法: query [单词]")
            else:
                query_word(argument)
        
        elif command == 'add':
            if not argument:
                print("✗ 请指定要添加的单词。")
                print("  用法: add [单词]")
            else:
                add_word_to_db(argument)
        
        else:
            print(f"✗ 未知命令: {command}")
            print("  输入 'help' 查看可用命令")