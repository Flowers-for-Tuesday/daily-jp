import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

def get_ai_content():
    """调用 DeepSeek API 生成日语学习内容"""
    api_key = os.getenv("DEEPSEEK_APIKEY")
    url = "https://api.deepseek.com/v1/chat/completions"

    # --- 新增：从 topic.txt 读取第一行 ---
    topic_file = "read/topic.txt"
    if not os.path.exists(topic_file):
        print("❌ 找不到 topic.txt")
        return None

    with open(topic_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("⚠️ topic.txt 为空，没有更多话题可用。")
        return None

    # 取第一行作为今日话题
    selected_topic = lines[0].strip()

    # 删除第一行并写回
    with open(topic_file, "w", encoding="utf-8") as f:
        f.writelines(lines[1:])

    print(f"🎯 本次选定话题: {selected_topic}")
    # --- 新增部分结束 ---

    system_prompt = f"""
    你是一位专业的日语老师。请生成一封适合 N4-N3 水平日语学习者的“每日日语阅读”邮件内容。
    
    今天的指定话题是：【{selected_topic}】。
    请务必围绕这个话题编写内容，不要偏题。

    要求：
    1. 结构：
       - title: 日语标题（请包含话题相关的趣味性）。
       - body: 800字左右的日语短文，汉字必须标注假名（格式：漢字(かんじ)）。
       - translation: 中文翻译。
       - vocab: 5-10个与【{selected_topic}】相关的核心词汇解释。
       - grammar: 3-5个短文中出现的 N4/N3 核心语法点讲解。
    2. 输出格式：直接返回可以在邮件中显示的 HTML 代码（不需要 ```html 包裹），
       使用内联 CSS 美化，风格简洁清新，适合手机阅读。
       把主要内容放在一个 max-width: 800px 的 div 容器中。
       请使用柔和的背景色，给单词和语法部分加上醒目的小标题样式。
    """

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "DailyJapaneseReader/1.0"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请生成关于'{selected_topic}'的阅读材料。"}
                ],
                "temperature": 1.0
            }
        )

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            print("❌ DeepSeek API 错误：", data["error"])
            return None

        return data['choices'][0]['message']['content']

    except Exception as e:
        print(f"❌ AI 生成失败: {e}")
        return None


# 下面保持 send_email 和 main 函数不变...

def send_email(html_content):
    """发送 HTML 邮件（修复版）"""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    receiver = os.getenv("RECEIVER_EMAIL")
    smtp_server = os.getenv("SMTP_SERVER")

    # 构建邮件
    subject = f"📅 每日日语阅读提升 - {datetime.now().strftime('%Y-%m-%d')}"
    message = MIMEText(html_content, 'html', 'utf-8')
    
    # --- 关键修改开始 ---
    # 使用 formataddr 确保符合 RFC 标准，解决 550 错误
    # formataddr 会自动处理中文编码，并保持 <email> 部分不被编码
    message['From'] = formataddr(("日语阅读助手", sender))
    message['To'] = formataddr(("日语学习者", receiver))
    # --- 关键修改结束 ---
    
    message['Subject'] = Header(subject, 'utf-8')

    try:
        server = smtplib.SMTP_SSL(smtp_server, 465) 
        server.login(sender, password)
        server.sendmail(sender, [receiver], message.as_string())
        server.quit()
        print(f"✅ 邮件已成功发送给 {receiver}")
    except smtplib.SMTPException as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    print("🤖 正在请求 DeepSeek 生成日语教材...")
    content = get_ai_content()
    
    if content:
        print("📝 内容生成完毕，正在发送邮件...")
        send_email(content)
    else:
        print("⚠️ 无法获取内容，程序终止。")