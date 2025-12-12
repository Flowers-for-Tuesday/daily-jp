import os
import json
import smtplib
import datetime
import random
import sqlite3
import requests
from email.mime.text import MIMEText
from email.utils import formataddr
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置信息
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_APIKEY")
NEW_WORDS_PER_DAY = int(os.getenv("NEW_WORDS_PER_DAY", 20)) 
MAX_STAGES = int(os.getenv("MAX_REVIEWS", 8))
DB_PATH = "vocab/vocab.db"

# ---------- 数据库辅助函数 ----------

def get_db_connection():
    # 确保连接到 vocab/vocab.db
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 允许通过列名访问数据
    return conn

def safe_parse_json_field(field_value):
    """即使数据库存的是字符串格式的列表 (如 "['n5']"), 也要安全解析"""
    if not field_value:
        return []
    if isinstance(field_value, list):
        return field_value
    try:
        # 将单引号替换为双引号以符合 JSON 标准 (简单的容错处理)
        # 注意：如果是复杂的嵌套结构，这可能不够完美，但对于简单的 list 字符串通常有效
        cleaned_val = str(field_value).replace("'", '"')
        return json.loads(cleaned_val)
    except:
        # 如果解析失败，直接作为单元素列表返回
        return [str(field_value)]

# ---------- 遗忘曲线计算下一次复习 ----------
def calculate_next_review_date(current_stage):
    intervals = [1, 2, 4, 7, 15, 30, 60, 90, 180]
    base_interval = intervals[current_stage] if current_stage < len(intervals) else intervals[-1]
    fuzz = random.randint(-max(1, int(base_interval * 0.15)), max(1, int(base_interval * 0.15))) if base_interval > 4 else 0
    return max(1, base_interval + fuzz)

# ---------- 核心逻辑：DeepSeek API 调用 ----------
def fetch_word_details_deepseek(word, db_info):
    """
    word: 单词文本
    db_info: 数据库中的原始行数据 (作为参考 context)
    """
    print(f"🤖 正在向 DeepSeek 查询单词: {word} ...")
    
    url = "https://api.deepseek.com/chat/completions"
    
    # 提取数据库参考信息 (仅供 AI 参考)
    # 使用 .get() 并非必须，因为 row_factory=sqlite3.Row 支持字典式访问，但为了安全起见
    ref_reading = db_info['reading'] if db_info['reading'] else "未知"
    ref_defs = db_info['definitions'] if db_info['definitions'] else "未知"
    ref_pos = db_info['part_of_speech'] if db_info['part_of_speech'] else "未知"
    
    # is_common 是 0/1，转换显示
    ref_is_common = "是" if db_info['is_common'] == 1 else "否"
    ref_jlpt = db_info['jlpt'] if db_info['jlpt'] else "未知"
    
    # Prompt 逻辑：将数据库信息作为 Context 给 AI
    prompt = f"""
    请作为日语老师，详细分析日语单词: 「{word}」。
    
    【参考信息 (来自数据库，仅供确认词义，请勿直接照抄英文)】
    - 参考读音: {ref_reading}
    - 原始释义: {ref_defs}
    - 参考词性: {ref_pos}
    - 是否常用: {ref_is_common}
    - 参考等级: {ref_jlpt}

    【任务要求】
    1. **读音**: 给出准确的平假名读音。
    2. **释义**: 结合参考信息，给出**中文**释义。如果有多个常用义项，请分条列出。
    3. **例句**: 为每个义项编写一个地道的日语例句，并附带中文翻译。
    4. **属性**: 判断 JLPT 等级、是否常用、详细词性。
    5. **变形**: 列出常见的动词/形容词变形，或名词的常见搭配。

    最终请返回严格的 JSON 格式 (不要包含 markdown 代码块标记)：
    {{
        "word": "{word}",
        "readings": ["平假名1", "平假名2"],
        "jlpt": ["N5" 或 "N3" 等],
        "is_common": true/false,
        "pos": "详细词性 (例如: 五段动词·他动词)",
        "variations": ["变形1", "搭配1"],
        "meanings": [
            {{ "meaning": "中文释义1", "example_jp": "日语例句1", "example_cn": "中文例句1" }},
            {{ "meaning": "中文释义2", "example_jp": "日语例句2", "example_cn": "中文例句2" }}
        ]
    }}
    """
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that outputs JSON only."},
        {"role": "user", "content": prompt}
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        response = requests.post(url, json={
            "model": "deepseek-chat",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 1.0 
        }, headers=headers)
        
        response.raise_for_status()
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        return json.loads(content)

    except Exception as e:
        print(f"❌ 获取 {word} 详情失败: {e}")
        # 降级返回（使用数据库的基础信息兜底）
        return {
            "word": word,
            "readings": [str(ref_reading)],
            "jlpt": safe_parse_json_field(ref_jlpt),
            "is_common": bool(db_info['is_common']),
            "pos": str(ref_pos),
            "variations": [],
            "meanings": [{"meaning": f"API调用失败，原始释义: {ref_defs}", "example_jp": "", "example_cn": ""}]
        }

# ---------- 发送邮件 (保持 UI 美观) ----------
def send_email(review_list):
    if not review_list:
        print("📭 今日无复习内容，跳过发送邮件。")
        return

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    new_count = sum(1 for item in review_list if item['stage'] == 0)
    review_count = len(review_list) - new_count

    html_content = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; color: #333;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">📅 日语记忆曲线复习表 ({today_str})</h2>
        <p>今日任务：<b>{len(review_list)}</b> 个单词 (🆕 新词: {new_count} / 🔄 复习: {review_count})</p>
    """

    for item in review_list:
        word = item['word']
        stage = item['stage']
        db_raw_info = item['db_raw_info'] # 获取数据库原始数据
        
        # 熟练度颜色条
        stage_color = "#2ecc71" if stage > 5 else "#1abc9c" if stage > 3 else "#f1c40f" if stage > 1 else "#e74c3c"
        if stage == 0:
            stage_display = '<span style="background-color:#e74c3c; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em; margin-left:5px;">NEW</span>'
        else:
            stage_display = f'<span style="display:inline-block;width:10px;height:10px;background-color:{stage_color};border-radius:50%; margin-left:5px;" title="熟练度等级: {stage}"></span>'

        # 调用 API 生成内容
        details = fetch_word_details_deepseek(word, db_raw_info)
        
        readings = " / ".join(details.get("readings", []))
        pos = details.get("pos", "暂无词性")
        variations = details.get("variations", [])
        variations_str = "、".join(variations) if variations else "无常见变形"

        # 标签 HTML 生成
        tags_html = ""
        jlpt_list = details.get("jlpt", [])
        for lvl in jlpt_list:
            lvl_display = lvl.replace("jlpt-", "").upper()
            tags_html += f'<span style="background-color:#3498db; color:white; padding:2px 6px; border-radius:4px; font-size:0.7em; margin-right:5px;">{lvl_display}</span>'

        if details.get("is_common"):
            tags_html += '<span style="background-color:#27ae60; color:white; padding:2px 6px; border-radius:4px; font-size:0.7em; margin-right:5px;">常用</span>'

        html_content += f"""
        <div style="border:1px solid #e0e0e0; border-radius:8px; padding:10px; margin-bottom:15px; background-color:#fafafa;">
            <div style="display:flex; align-items:center; margin-bottom:5px;">
                <h3 style="margin:0; color:#2c3e50; margin-right:10px;">
                    {word}
                </h3>
                {stage_display}
                <div style="margin-left:auto;">{tags_html}</div>
            </div>
            
            <p style="margin:2px 0; color:#555;"><b>读音:</b> <span style="color:#d35400; font-family:'Hiragino Sans', sans-serif;">{readings}</span></p>
            <p style="margin:2px 0; color:#555;"><b>词性:</b> <span style="background-color:#e8f4f8; padding:2px 5px; border-radius:3px; color:#2980b9; font-size:0.9em;">{pos}</span></p>
            <p style="margin:2px 0; color:#555;"><b>变形:</b> <span style="color:#7f8c8d; font-size:0.9em;">{variations_str}</span></p>
        """

        for m in details.get("meanings", []):
            html_content += f"""
            <div style="margin:5px 0; padding:5px; background-color:#fff; border-left:4px solid #3498db; border-radius:4px;">
                <p style="margin:2px 0;"><b>释义:</b> {m.get('meaning','')}</p>
                <p style="margin:2px 0;"><b>例句(日):</b> {m.get('example_jp','')}</p>
                <p style="margin:2px 0; color:#888;"><b>例句(中):</b> {m.get('example_cn','')}</p>
            </div>
            """

        html_content += "</div>"

    html_content += "<p style='text-align:center; color:#999; font-size:12px;'>Generated by DeepSeek AI (Ref: SQLite)</p></div>"

    message = MIMEText(html_content, 'html', 'utf-8')
    message['From'] = formataddr(("日语单词助手", SENDER_EMAIL))
    message['To'] = RECEIVER_EMAIL
    message['Subject'] = f'【记忆曲线】{today_str} 任务: {new_count}新词 + {review_count}复习'

    try:
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        smtp_obj.login(SENDER_EMAIL, SENDER_PASSWORD)
        smtp_obj.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        smtp_obj.quit()
        print("📧 邮件发送成功！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# ---------- 主流程 (数据库版) ----------
def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ 未找到数据库文件: {DB_PATH}")
        return

    today = datetime.date.today().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 获取今日复习 (Stage > 0 且 时间到)
    # 注意：表名已修改为 vocab_progress
    cursor.execute("""
        SELECT * FROM vocab_progress 
        WHERE stage > 0 AND next_review <= ? AND next_review != '' 
        ORDER BY next_review ASC
    """, (today,))
    due_reviews = [dict(row) for row in cursor.fetchall()]

    # 2. 获取新词 (Stage = 0)
    # 注意：表名已修改为 vocab_progress
    cursor.execute("SELECT * FROM vocab_progress WHERE stage = 0 LIMIT ?", (NEW_WORDS_PER_DAY,))
    new_words = [dict(row) for row in cursor.fetchall()]
    
    conn.close()

    review_queue = new_words + due_reviews

    print(f"📊 今日任务总计: {len(review_queue)} 词")
    print(f"   🔹 新词: {len(new_words)} (目标: {NEW_WORDS_PER_DAY})")
    print(f"   🔸 复习: {len(due_reviews)}")

    if not review_queue:
        print("🎉 今日没有需要复习的单词，且词库已空。")
        return

    email_data_list = []
    
    # 用于批量更新数据库的列表
    updates = []

    for item in review_queue:
        word = item['word']
        
        # 如果是新词，设置 first_seen
        first_seen = item['first_seen']
        if not first_seen:
            first_seen = today
        
        # 准备传给邮件函数的数据
        email_data = {
            "word": word,
            "stage": item['stage'],
            "db_raw_info": item  # 将整行数据传给 DeepSeek 函数做参考
        }
        email_data_list.append(email_data)

        # 算法更新
        current_stage = item['stage']
        days_delta = calculate_next_review_date(current_stage)
        next_date = datetime.date.today() + datetime.timedelta(days=days_delta)
        
        # 记录更新操作
        updates.append({
            "stage": current_stage + 1,
            "first_seen": first_seen,
            "last_review": today,
            "next_review": next_date.isoformat(),
            "word": word
        })

    # 发送邮件
    send_email(email_data_list)

    # 批量更新数据库 (使用 vocab_progress 表名)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.executemany("""
            UPDATE vocab_progress 
            SET stage = :stage, first_seen = :first_seen, 
                last_review = :last_review, next_review = :next_review
            WHERE word = :word
        """, updates)
        conn.commit()
        print(f"✅ 数据库已更新 {len(updates)} 条记录。")
    except Exception as e:
        print(f"❌ 数据库更新失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()