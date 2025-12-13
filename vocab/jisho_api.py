import requests

def jisho_api(word: str):
    """
    调用 Jisho API 并返回简化信息。
    
    返回字典字段：
    {
        'word': str,           # 单词的汉字形（如果没有，则用假名）
        'reading': str,        # 单词的假名读音
        'definitions': list,   # 英文释义列表
        'part_of_speech': list,# 词性信息列表
        'is_common': bool,     # 是否为常用词
        'jlpt': list           # JLPT 等级列表
    }
    """
    url = f"https://jisho.org/api/v1/search/words?keyword={word}"
    response = requests.get(url)
    data = response.json()

    if not data.get("data"):
        return {"error": "No results found."}

    entry = data["data"][0]

    # --- Japanese form & reading ---
    japanese = entry.get("japanese", [])
    if japanese:
        word_form = japanese[0].get("word", "") or japanese[0].get("reading", "")
        reading = japanese[0].get("reading", "")
    else:
        word_form = ""
        reading = ""

    # --- 词义和词性 ---
    senses = entry.get("senses", [])
    if senses:
        sense = senses[0]
        definitions = sense.get("english_definitions", [])
        parts_of_speech = sense.get("parts_of_speech", [])
    else:
        definitions = []
        parts_of_speech = []

    simplified = {
        "word": word_form,
        "reading": reading,
        "definitions": definitions,
        "part_of_speech": parts_of_speech,
        "is_common": entry.get("is_common", None),
        "jlpt": entry.get("jlpt", []),
    }

    return simplified

# --- 使用示例 ---
if __name__ == "__main__":
    result = jisho_api("夜")
    print(result)
    # 输出示例结果
    """
    {
        'word': '夜',
        'reading': 'よる',
        'definitions': ['night', 'evening'],
        'part_of_speech': ['Noun', 'Adverb (fukushi)'],
        'is_common': True,
        'jlpt': ['jlpt-n3', 'jlpt-n5']
    }
    """
