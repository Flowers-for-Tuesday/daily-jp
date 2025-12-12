import requests

def jisho_api(word: str):
    """
    Call Jisho API and return simplified useful information
    from the first search result, including see_also.

    Output dictionary fields:

    {
        'word': str,           # 单词的汉字形（如果有），如没有则用假名
        'reading': str,        # 单词的假名读音
        'definitions': list,   # 英文释义列表
        'part_of_speech': list,# 词性信息（如 Ichidan verb, Intransitive verb）
        'see_also': list,      # 相关词、近义词或对比词（如果有）
        'is_common': bool,     # 是否为常用词
        'jlpt': list           # JLPT 等级（如 jlpt-n5）
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
        # word_form: 汉字形式，如果没有则用 reading
        word_form = japanese[0].get("word", "") or japanese[0].get("reading", "")
        # reading: 假名读音
        reading = japanese[0].get("reading", "")
    else:
        word_form = ""
        reading = ""

    # --- First sense ---
    senses = entry.get("senses", [])
    if senses:
        sense = senses[0]
        # definitions: 英文释义列表
        definitions = sense.get("english_definitions", [])
        # parts_of_speech: 词性信息列表
        parts_of_speech = sense.get("parts_of_speech", [])
        # see_also: 相关词列表
        see_also = sense.get("see_also", [])
    else:
        definitions = []
        parts_of_speech = []
        see_also = []

    # --- Build simplified output ---
    simplified = {
        "word": word_form,
        "reading": reading,
        "definitions": definitions,
        "part_of_speech": parts_of_speech,
        "see_also": see_also,
        "is_common": entry.get("is_common", None),
        "jlpt": entry.get("jlpt", []),
    }

    return simplified

# --- 使用示例 ---
result = jisho_api("けど")
print(result)
