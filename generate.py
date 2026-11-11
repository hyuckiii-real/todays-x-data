import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

# KST(한국 표준시) 오늘 날짜 구하기
kst = ZoneInfo("Asia/Seoul")
today_str = datetime.now(kst).strftime("%Y-%m-%d")

# 기존 히스토리 불러오기 (중복 방지용)
archive = []
if os.path.exists("archive.json"):
    try:
        with open("archive.json", "r", encoding="utf-8") as f:
            archive = json.load(f)
    except Exception:
        archive = []

past_words = [item.get("word", "").lower() for item in archive if isinstance(item, dict)]

# 구글 Gemini 클라이언트 설정 (최신 SDK)
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수한 JSON 형식으로만 응답해줘.
마크다운(```json) 없이 순수 JSON 텍스트만 출력해야 해.

조건:
1. 제외할 단어 리스트: {past_words[-100:]}
2. 날짜: {today_str}

JSON 형식 규격:
{{
  "date": "{today_str}",
  "word": "단어",
  "phonetic": "/발음기호/",
  "part_of_speech": "품사 (예: noun, verb, idiom)",
  "meaning": "한국어 핵심 뜻",
  "example_en": "자연스러운 영어 예문 1문장",
  "example_ko": "예문의 자연스러운 한국어 번역"
}}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
)

# 불필요한 마크다운 태그 제거 후 JSON 파싱
clean_text = response.text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

# today.json 덮어쓰기
with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# archive.json 누적 업데이트
archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 성공적으로 생성됨: {data.get('word')}")
