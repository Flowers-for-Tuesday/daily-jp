import torch
from transformers import pipeline
import time
import os

def main():
    model_path = "listen/whisper-large-v3"   # 本地模型
    audio_dir = "listen/audio"               # 音频文件夹

    # === 1. 修改此处：寻找 audio/ 中的 MP3 文件 (也可以兼容 WAV) ===
    # 定义支持的格式
    valid_extensions = (".mp3")
    
    # 获取文件夹内所有文件
    all_files = os.listdir(audio_dir)
    
    # 筛选出音频文件
    audio_files = [f for f in all_files if f.lower().endswith(valid_extensions)]

    if len(audio_files) == 0:
        print(f"❌ 错误：audio 文件夹中没有找到音频文件 ({valid_extensions})！")
        return

    # 默认取第一个文件
    target_file = audio_files[0]
    audio_path = os.path.join(audio_dir, target_file)
    print(f"📂 找到音频文件：{audio_path}")

    # 输出文件名（自动替换后缀为 .txt）
    output_txt = os.path.join(audio_dir, os.path.splitext(target_file)[0] + ".txt")

    # === 2. 自动检测设备 ===
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    print(f"[1/3] 加载模型 (Device: {device}, Dtype: {torch_dtype})...")

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_path,
        tokenizer=model_path,
        chunk_length_s=30,
        device=device,
        torch_dtype=torch_dtype,
    )

    # === 3. 开始转写 ===
    print("[2/3] 开始转写…")
    start_time = time.time()

    # pipeline 会自动处理 MP3 解码，无需额外代码
    result = pipe(
        audio_path,
        batch_size=8,
        return_timestamps=False,
        generate_kwargs={"language": "japanese", "task": "transcribe"}
    )

    end_time = time.time()
    print(f"⏱️ 转写耗时: {end_time - start_time:.2f} 秒")

    final_text = result["text"]

    print("\n[3/3] 识别结果预览：")
    print(final_text[:500] + "..." if len(final_text) > 500 else final_text)

    # === 4. 保存 ===
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(final_text)

    print(f"\n🎉 已保存到：{output_txt}")

if __name__ == "__main__":
    main()