import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai

# KST 기준 오늘 날짜
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

# 구글 공식 최신 GenAI 클라이언트
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

prompt = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수한 JSON 형식으로만 응답해줘.
마크다운 코드블록(```json 등)은 일체 쓰지 말고 순수 텍스트만 출력해.

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

# 지원되는 최신 모델 순차 시도 (첫 번째 에러 안내 모델 포함)
candidate_models = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash-latest"]
response = None

for m in candidate_models:
    try:
        response = client.models.generate_content(
            model=m,
            contents=prompt,
        )
        if response and response.text:
            print(f"사용된 모델: {m}")
            break
    except Exception as e:
        print(f"모델 {m} 시도 실패, 다음 모델 확인 중: {e}")
        continue

if not response or not response.text:
    raise RuntimeError("사용 가능한 Gemini 모델을 찾을 수 없습니다.")

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
