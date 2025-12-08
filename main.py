import os
import json
import smtplib
import datetime
import requests
import random
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
DAILY_REVIEW_COUNT = int(os.getenv("DAILY_REVIEW_COUNT", 20))
MAX_STAGES = int(os.getenv("MAX_REVIEWS", 7))

FILES = {
    "vocab": "vocab.txt",
    "json": "progress.json"
}

# ---------- 遗忘曲线计算下一次复习 ----------
def calculate_next_review_date(current_stage):
    intervals = [1, 2, 4, 7, 15, 30, 60, 90, 180]
    base_interval = intervals[current_stage] if current_stage < len(intervals) else intervals[-1]
    fuzz = random.randint(-max(1, int(base_interval * 0.15)), max(1, int(base_interval * 0.15))) if base_interval > 4 else 0
    return max(1, base_interval + fuzz)

# ---------- 词库与进度 ----------
def load_vocab():
    if not os.path.exists(FILES["vocab"]):
        print("❌ 未找到 vocab.txt")
        return []
    with open(FILES["vocab"], "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def load_progress():
    if not os.path.exists(FILES["json"]):
        return {}
    with open(FILES["json"], "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_progress(data):
    with open(FILES["json"], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- 调用 DeepSeek API 获取单词详情 (已修改) ----------
def fetch_word_details_deepseek(word):
    print(f"🤖 正在向 DeepSeek 查询单词: {word} ...")
    
    url = "https://api.deepseek.com/chat/completions"
    
    # 修改了 Prompt，增加了 pos 和 variations 字段的要求
    prompt = f"""
    请作为日语老师，分析日语单词: 「{word}」。
    请返回严格的 JSON 格式，包含以下字段：
    - word: 原词
    - readings: [平假名读音1, 平假名读音2,...]
    - pos: 字符串，详细的词性分类 (例如: "五段动词·他动词" 或 "な形容词" 或 "副词")
    - variations: [字符串数组]，列出该词常见的3-4个变形或搭配。
      (如果是动词/形容词，请列出如 ["ます形: xxx", "て形: xxx", "ない形: xxx"]；如果是名词没有变形，请列出常用搭配或"无")
    - meanings: [
        {{ "meaning": 中文释义1, "example_jp": 日语例句1, "example_cn": 中文例句1 }},
        {{ "meaning": 中文释义2, "example_jp": 日语例句2, "example_cn": 中文例句2 }}
      ]
    """
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that outputs JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 1.0,
        "response_format": {"type": "json_object"}
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"❌ 获取 {word} 详情失败: {e}")
        # 返回结构包含新字段的默认值
        return {
            "word": word,
            "readings": ["查询失败"],
            "pos": "未知",
            "variations": [],
            "meanings": [{"meaning": "API调用失败", "example_jp": "", "example_cn": ""}]
        }

# ---------- 发送邮件 (已修改) ----------
def send_email(review_list):
    if not review_list:
        print("📭 今日无复习内容，跳过发送邮件。")
        return

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # 邮件开头
    html_content = f"""
    <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; color: #333;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">📅 日语记忆曲线复习表 ({today_str})</h2>
        <p>根据<b>艾宾浩斯遗忘曲线</b>，今日为您安排了 <b>{len(review_list)}</b> 个单词。</p>
    """

    for item in review_list:
        word = item['word']
        stage = item['stage']
        stage_color = "#2ecc71" if stage > 5 else "#1abc9c" if stage > 3 else "#f1c40f" if stage > 1 else "#e74c3c"

        details = fetch_word_details_deepseek(word)
        readings = " / ".join(details.get("readings", []))
        
        # 获取新字段，如果不存在则给默认值
        pos = details.get("pos", "暂无词性")
        variations = details.get("variations", [])
        variations_str = "、".join(variations) if variations else "无常见变形"

        # 单词卡片样式 (增加了词性和变形的显示)
        html_content += f"""
        <div style="border:1px solid #e0e0e0; border-radius:8px; padding:10px; margin-bottom:15px; background-color:#fafafa;">
            <h3 style="margin:0 0 5px 0; color:#2c3e50;">
                {word} 
                <span style="display:inline-block;width:10px;height:10px;background-color:{stage_color};border-radius:50%; margin-left:5px;" title="熟练度等级: {stage}"></span>
            </h3>
            <p style="margin:2px 0; color:#555;"><b>读音:</b> {readings}</p>
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

    html_content += "<p style='text-align:center; color:#999; font-size:12px;'>Generated by DeepSeek AI | Spaced Repetition System</p></div>"

    # 发送邮件
    message = MIMEText(html_content, 'html', 'utf-8')
    message['From'] = formataddr(("日语记忆助手", SENDER_EMAIL))
    message['To'] = RECEIVER_EMAIL
    message['Subject'] = f'【记忆曲线】{today_str} 今日复习任务 ({len(review_list)}词)'

    try:
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        smtp_obj.login(SENDER_EMAIL, SENDER_PASSWORD)
        smtp_obj.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        smtp_obj.quit()
        print("📧 邮件发送成功！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# ---------- 主流程 ----------
def main():
    vocab_list = load_vocab()
    progress = load_progress()
    today = datetime.date.today().isoformat()
    
    review_queue = []

    # 筛选已到期的旧词
    for word, info in progress.items():
        if "stage" not in info: info["stage"] = info.get("count",0)
        if info['next_review'] <= today and info['stage'] < MAX_STAGES:
            review_queue.append(word)
    
    review_queue.sort(key=lambda w: progress[w]['next_review'])

    # 补充新词
    for word in vocab_list:
        if len(review_queue) >= DAILY_REVIEW_COUNT:
            break
        if word not in progress:
            review_queue.append(word)

    print(f"📊 今日任务: {len(review_queue)} 个单词 (复习+新词)")
    if not review_queue:
        print("🎉 今日没有需要复习的单词。")
        return

    email_data_list = []

    for word in review_queue:
        if word not in progress:
            progress[word] = {
                "stage": 0,
                "next_review": today,
                "first_seen": today
            }

        item_data = {
            "word": word,
            "stage": progress[word]["stage"]
        }
        email_data_list.append(item_data)

        # 更新复习状态
        current_stage = progress[word]["stage"]
        days_delta = calculate_next_review_date(current_stage)
        next_date = datetime.date.today() + datetime.timedelta(days=days_delta)

        progress[word]["stage"] += 1
        progress[word]["next_review"] = next_date.isoformat()
        progress[word]["last_review"] = today

    send_email(email_data_list)
    save_progress(progress)
    print("✅ 进度已更新。")

if __name__ == "__main__":
    main()