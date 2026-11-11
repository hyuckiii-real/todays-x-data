import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import google.generativeai as genai

# KST 기준 날짜
kst = ZoneInfo("Asia/Seoul")
today_str = datetime.now(kst).strftime("%Y-%m-%d")

# 기존 히스토리 불러오기
archive = []
if os.path.exists("archive.json"):
    try:
        with open("archive.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

past_words = [item.get("word", "").lower() for item in archive if isinstance(item, dict)]

# Gemini 설정
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

prompt = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수 JSON 텍스트로만 응답해줘.
마크다운 태그(```json 등)는 일체 포함하지 마.

제외할 최근 단어: {past_words[-100:]}
날짜: {today_str}

형식:
{{
  "date": "{today_str}",
  "word": "단어",
  "phonetic": "/발음기호/",
  "part_of_speech": "품사",
  "meaning": "한국어 뜻",
  "example_en": "영어 예문 1개",
  "example_ko": "예문의 한국어 해석"
}}
"""

response = model.generate_content(prompt)
clean_text = response.text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

# today.json 저장
with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# archive.json 누적
archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
