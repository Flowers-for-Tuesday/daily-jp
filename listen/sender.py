import os
import glob
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from openai import OpenAI
from dotenv import load_dotenv

# ================= 🚀 配置加载 =================
load_dotenv() 

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_APIKEY")

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
AUDIO_DIR = "audio"

if not all([SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL, DEEPSEEK_API_KEY]):
    print("❌ 错误：重要的环境变量未加载。请检查 .env 文件。")
    exit(1)


# ================= 功能函数 =================

def get_file_pair():
    """在 audio 文件夹中查找配对的 mp3 和 txt 文件"""
    wav_files = glob.glob(os.path.join(AUDIO_DIR, "*.mp3")) # 注意这里是查找 mp3
    txt_files = glob.glob(os.path.join(AUDIO_DIR, "*.txt"))

    if not wav_files:
        raise FileNotFoundError("在 audio 文件夹中未找到音频文件。")
    
    wav_path = wav_files[0]
    # 尝试找同名的txt，找不到就找第一个txt
    base_name = os.path.splitext(os.path.basename(wav_path))[0]
    possible_txt_path = os.path.join(AUDIO_DIR, f"{base_name}.txt")
    
    if os.path.exists(possible_txt_path):
        txt_path = possible_txt_path
    elif txt_files:
        txt_path = txt_files[0]
    else:
        raise FileNotFoundError("未找到文本文件。")

    print(f"📂 找到文件:\n - 音频: {wav_path}\n - 文本: {txt_path}")
    return wav_path, txt_path

def get_ai_response(content):
    """
    调用 DeepSeek API:
    1. 生成摘要
    2. 【新增】为日语原文添加标点并智能分段
    3. 生成中文翻译
    """
    print("🤖 正在请求 DeepSeek API 进行重写、分段和翻译...")
    
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    # 修改后的 Prompt，核心在于要求 AI 进行"文本整形"
    prompt = f"""
    请阅读以下日语文本（原文可能是语音转文字，缺少标点且未分段），请完成三个任务：

    1. 【摘要】：提供一个非常简短的中文概括（不超过 15 个字），用于邮件标题。
    2. 【日语重写】：
       - 为原文添加正确的标点符号（。、？！等）。
       - 根据语义逻辑进行**智能分段**（在段落之间插入空行），使其易于朗读和阅读。
    3. 【中文翻译】：
       - 将重写后的日语翻译成自然流畅的中文。
       - **中文翻译的段落结构必须与重写后的日语完全对应**（日语分几段，中文就分几段）。

    请严格按照以下格式返回结果（不要包含多余的寒暄）：
    
    [SUMMARY]
    (这里写概括)
    [JAPANESE]
    (这里写添加标点并分段后的日语原文)
    [TRANSLATION]
    (这里写对应的中文翻译)

    待处理的日语原文：
    {content}
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个专业的日语语言学专家和翻译家。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3 # 保持较低温度以确保格式稳定
    )

    result_text = response.choices[0].message.content
    
    # 解析返回的三部分内容
    try:
        # 1. 提取翻译部分（在最后）
        parts_trans = result_text.split("[TRANSLATION]")
        translation_part = parts_trans[1].strip()
        
        # 2. 提取剩余部分中的摘要和日语
        parts_meta = parts_trans[0].split("[JAPANESE]")
        formatted_japanese = parts_meta[1].strip()
        
        # 3. 提取摘要
        summary_part = parts_meta[0].replace("[SUMMARY]", "").strip()
        
        return summary_part, formatted_japanese, translation_part
        
    except IndexError:
        print("⚠️ 解析 AI 响应失败，将使用原始文本。")
        return "今日日语听力", content, result_text


def send_email(subject_summary, formatted_japanese, translation_text, audio_path):
    """发送带附件的 HTML 邮件"""
    print("📧 正在构建并发送邮件...")

    msg = MIMEMultipart()
    msg['From'] = formataddr(("日语学习助手", SENDER_EMAIL))
    msg['To'] = RECEIVER_EMAIL
    
    subject = f"今日听力：{subject_summary}"
    msg['Subject'] = subject

    # 将换行符转换为 HTML 的 <br> 标签，以保留分段效果
    html_japanese = formatted_japanese.replace('\n', '<br>')
    html_translation = translation_text.replace('\n', '<br>')

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: "Hiragino Sans", "Microsoft YaHei", Arial, sans-serif; line-height: 1.8; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            .section {{ margin-bottom: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
            h2 {{ color: #2980b9; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; font-size: 18px; }}
            /* 重点：保留空白和换行，或者使用替换后的 br */
            .content-text {{ font-size: 16px; color: #444; }}
            .japanese {{ font-family: "Yu Mincho", "MS Mincho", serif; }} /* 日语使用衬线体更有质感 */
            .footer {{ margin-top: 30px; font-size: 12px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <p>👋 你好！这是为你整理的今日日语听力材料（已智能分段）。</p>
            
            <div class="section">
                <h2>📖 日语原文 (精校版)</h2>
                <div class="content-text japanese">{html_japanese}</div>
            </div>

            <div class="section">
                <h2>🇨🇳 中文翻译</h2>
                <div class="content-text">{html_translation}</div>
            </div>
            
            <p>🎧 <strong>音频文件已包含在附件中，请查收。</strong></p>
            
            <div class="footer">由 Python 自动生成 | DeepSeek 智能排版</div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    # 添加音频附件
    try:
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
            filename = os.path.basename(audio_path)
            attachment = MIMEApplication(audio_data, Name=filename)
            attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(attachment)
    except FileNotFoundError:
        print(f"⚠️ 警告: 未找到音频文件 {audio_path}")
        
    try:
        smtp_obj = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15)
        smtp_obj.login(SENDER_EMAIL, SENDER_PASSWORD)
        smtp_obj.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], msg.as_string())
        smtp_obj.quit()
        print("✅ 邮件发送成功！")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
    return False

def delete_pair_files(audio_path, txt_path):
    """邮件成功发送后自动删除对应的 mp3 和 txt 文件"""
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"🗑 已删除音频文件: {audio_path}")

        if os.path.exists(txt_path):
            os.remove(txt_path)
            print(f"🗑 已删除文本文件: {txt_path}")
    except Exception as e:
        print(f"⚠️ 删除文件失败: {e}")

# ================= 主程序 =================

def main():
    try:
        # 1. 获取文件路径
        wav_path, txt_path = get_file_pair()
        
        # 2. 读取原始的、无标点的文本
        with open(txt_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
            
        # 3. AI 处理：获取摘要、格式化后的日语、翻译
        # 注意：这里接收三个返回值
        summary, formatted_japanese, translation = get_ai_response(raw_text)
        
        print(f"📝 生成摘要: {summary}")
        
        # 4. 发送邮件
        success = send_email(summary, formatted_japanese, translation, wav_path)

        # 5. 邮件发送成功 → 删除对应文件
        if success:
            delete_pair_files(wav_path, txt_path)
        
    except FileNotFoundError as e:
        print(f"\n❌ 文件错误: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ 程序运行出错: {e}")

if __name__ == "__main__":
    main()