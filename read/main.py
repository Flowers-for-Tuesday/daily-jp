import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime
from dotenv import load_dotenv

# =========================
# 可配置参数
# =========================
JLPT_LEVEL = "N4"
template_file = "read/template_reference.html"
# 加载 .env 环境变量
load_dotenv()


def get_html_template():
    """读取HTML模板文件"""
    with open(template_file, "r", encoding="utf-8") as f:
        return f.read()


def get_ai_content():
    """调用 DeepSeek API 生成日语学习内容"""
    api_key = os.getenv("DEEPSEEK_APIKEY")
    url = "https://api.deepseek.com/v1/chat/completions"

    # 从 topic.txt 读取第一行
    topic_file = "read/topic.txt"
    with open(topic_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    selected_topic = lines[0].strip()

    # 删除第一行并写回
    with open(topic_file, "w", encoding="utf-8") as f:
        f.writelines(lines[1:])

    print(f"🎯 本次选定话题: {selected_topic}")

    html_template = get_html_template()

    system_prompt = f"""
你是一位专业的日语教师，专攻JLPT {JLPT_LEVEL}水平教学。请生成一封适合{JLPT_LEVEL}水平日语学习者的"每日日语阅读"邮件内容。

【今日话题】
{selected_topic}

【生成要求】
1. 文章内容：
   - 标题：与话题相关的正式、有深度的日语标题
   - 正文：500-800字的日语文章，{JLPT_LEVEL}阅读难度
   - 文章需要有逻辑性，包含观点、分析或说明

2. 中文翻译：
   - 提供准确、通顺的中文翻译

3. {JLPT_LEVEL}模拟试题（4问）：
   - 问题1: 文章主旨题
   - 问题2: 细节理解题
   - 问题3: 词义推断题
   - 问题4: 观点态度题
   - 每题提供4个选项（日文），并附解析和答案

4. 学习要点：
   - 8-12个{JLPT_LEVEL}核心词汇（表格形式，包含单词、读音、中文意思）
   - 4-6个{JLPT_LEVEL}核心语法点（包含接续、用法、例句）

【HTML格式要求】
请严格遵循以下HTML模板的结构、样式和格式。请直接生成完整的HTML代码，不需要额外的解释。

{html_template}

【重要提示】
1. 用今天的实际日期替换模板中的时间
2. 保持模板的CSS样式不变
3. 根据实际内容调整各部分
4. 确保所有内容都围绕话题【{selected_topic}】展开
"""

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
                {
                    "role": "user",
                    "content": f"请严格按照模板格式，生成关于「{selected_topic}」的{JLPT_LEVEL}水平日语阅读材料。"
                }
            ],
            "temperature": 0.7,
            "max_tokens": 8000
        },
        timeout=180
    )

    response.raise_for_status()
    data = response.json()

    content = data['choices'][0]['message']['content']

    if not content.strip().startswith('<!DOCTYPE html>'):
        content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{JLPT_LEVEL}日语阅读练习</title>
</head>
<body>
{content}
</body>
</html>"""

    return content


def send_email(html_content):
    """发送 HTML 邮件"""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    receiver = os.getenv("RECEIVER_EMAIL")
    smtp_server = os.getenv("SMTP_SERVER")

    subject = f"📚 {JLPT_LEVEL}日语阅读训练 - {datetime.now().strftime('%Y-%m-%d')}"
    message = MIMEText(html_content, 'html', 'utf-8')

    message['From'] = formataddr(("日语阅读助手", sender))
    message['To'] = formataddr(("日语学习者", receiver))
    message['Subject'] = Header(subject, 'utf-8')

    server = smtplib.SMTP_SSL(smtp_server, 465)
    server.login(sender, password)
    server.sendmail(sender, [receiver], message.as_string())
    server.quit()

    print(f"✅ 邮件已成功发送给 {receiver}")


def main():
    print(f"🤖 正在生成 {JLPT_LEVEL} 日语阅读材料...")
    content = get_ai_content()

    print("📝 内容生成完毕，正在发送邮件...")
    send_email(content)

    print("🎉 任务完成！")


if __name__ == "__main__":
    main()
