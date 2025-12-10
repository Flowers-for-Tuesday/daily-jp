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
NEW_WORDS_PER_DAY = int(os.getenv("NEW_WORDS_PER_DAY", 20)) 
MAX_STAGES = int(os.getenv("MAX_REVIEWS", 8))

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
    
    # 【修改点 2】优化 Prompt，加入声调标记要求
    prompt = f"""
    请作为日语老师，分析日语单词: 「{word}」。
    请返回严格的 JSON 格式，包含以下字段：
    - word: 日语原词
    - readings: [字符串数组], 请在平假名读音后严格标注声调数字(0为平板, 1为头高等)。格式如: "がくせい [0]", "あめ [1]"
    - pos: 字符串，详细的词性分类 (例如: "五段动词·他动词" 或 "な形容词")
    - variations: [字符串数组]，列出该词常见的3-4个变形或搭配。
      (如果是动词/形容词，请列出如 ["ます形: xxx", "て形: xxx"]；如果是名词，列出常用搭配)
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
        return {
            "word": word,
            "readings": ["查询失败"],
            "pos": "未知",
            "variations": [],
            "meanings": [{"meaning": "API调用失败", "example_jp": "", "example_cn": ""}]
        }

# ---------- 发送邮件 ----------
def send_email(review_list):
    if not review_list:
        print("📭 今日无复习内容，跳过发送邮件。")
        return

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    # 统计新词和旧词数量用于标题
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
        stage_color = "#2ecc71" if stage > 5 else "#1abc9c" if stage > 3 else "#f1c40f" if stage > 1 else "#e74c3c"
        
        # 新词给一个特殊的标记颜色
        if stage == 0:
            stage_display = '<span style="background-color:#e74c3c; color:white; padding:2px 6px; border-radius:4px; font-size:0.8em; margin-left:5px;">NEW</span>'
        else:
            stage_display = f'<span style="display:inline-block;width:10px;height:10px;background-color:{stage_color};border-radius:50%; margin-left:5px;" title="熟练度等级: {stage}"></span>'

        details = fetch_word_details_deepseek(word)
        readings = " / ".join(details.get("readings", []))
        
        pos = details.get("pos", "暂无词性")
        variations = details.get("variations", [])
        variations_str = "、".join(variations) if variations else "无常见变形"

        html_content += f"""
        <div style="border:1px solid #e0e0e0; border-radius:8px; padding:10px; margin-bottom:15px; background-color:#fafafa;">
            <h3 style="margin:0 0 5px 0; color:#2c3e50;">
                {word} {stage_display}
            </h3>
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

    html_content += "<p style='text-align:center; color:#999; font-size:12px;'>Generated by DeepSeek AI | Spaced Repetition System</p></div>"

    message = MIMEText(html_content, 'html', 'utf-8')
    message['From'] = formataddr(("日语记忆助手", SENDER_EMAIL))
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

# ---------- 主流程 (已修改) ----------
def main():
    vocab_list = load_vocab()
    progress = load_progress()
    today = datetime.date.today().isoformat()
    
    review_queue = [] # 最终的复习队列
    due_reviews = []  # 到期复习的旧词
    new_words = []    # 今日新词

    # 1. 筛选已到期的旧词 (全部收录，不做数量限制，保证复习效果)
    for word, info in progress.items():
        if "stage" not in info: info["stage"] = info.get("count", 0)
        # 只要日期到了且没完成所有阶段，就必须复习
        if info['next_review'] <= today and info['stage'] < MAX_STAGES:
            due_reviews.append(word)
    
    # 对旧词按日期排序
    due_reviews.sort(key=lambda w: progress[w]['next_review'])

    # 2. 补充固定数量的新词 (保证每天都有新输入)
    # 【修改点 3】 这里的逻辑改为：不管有多少旧词，雷打不动加 NEW_WORDS_PER_DAY 个新词
    for word in vocab_list:
        if len(new_words) >= NEW_WORDS_PER_DAY:
            break
        if word not in progress:
            new_words.append(word)

    # 合并列表：先展示新词(可选)，再展示旧词，或者混合
    # 这里我们把新词放前面，因为新词需要更多精力
    review_queue = new_words + due_reviews

    print(f"📊 今日任务总计: {len(review_queue)} 词")
    print(f"   🔹 新词: {len(new_words)} (目标: {NEW_WORDS_PER_DAY})")
    print(f"   🔸 复习: {len(due_reviews)}")

    if not review_queue:
        print("🎉 今日没有需要复习的单词，且词库已空。")
        return

    email_data_list = []

    # 处理队列
    for word in review_queue:
        # 如果是新词，初始化进度
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