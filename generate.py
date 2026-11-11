import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

# KST 오늘 날짜
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

# 최신 GenAI 클라이언트
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# 1. 현재 계정/키에서 실제 사용 가능한 generateContent 지원 모델 찾기
available_model = None
try:
    for m in client.models.list():
        # generateContent를 지원하는 모델 검색
        actions = getattr(m, 'supported_actions', []) or getattr(m, 'supported_generation_methods', [])
        if "generateContent" in actions or "generate_content" in actions:
            # flash 계열 우선 선택
            model_name = m.name.replace("models/", "")
            if "flash" in model_name:
                available_model = model_name
                break
            if not available_model:
                available_model = model_name
except Exception as e:
    print(f"모델 목록 조회 실패: {e}")

# 목록 조회 실패 시 기본 추천 모델 사용
if not available_model:
    available_model = "gemini-2.5-flash"

print(f"선택된 모델: {available_model}")

prompt = f"""
유용한 영어 단어나 숙어 1개를 골라 순수한 JSON 형식으로만 응답해줘.
코드블록(```) 등은 일체 포함하지 마.

제외 단어: {past_words[-100:]}
날짜: {today_str}

형식:
{{
  "date": "{today_str}",
  "word": "단어",
  "phonetic": "/발음기호/",
  "part_of_speech": "품사",
  "meaning": "한국어 뜻",
  "example_en": "영어 예문",
  "example_ko": "한국어 해석"
}}
"""

response = client.models.generate_content(
    model=available_model,
    contents=prompt,
)

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
