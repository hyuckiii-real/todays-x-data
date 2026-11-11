import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

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

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

prompt_text = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수 JSON 텍스트로만 응답해줘.
코드블록(```json 등)은 일체 포함하지 마.

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

payload = {
    "contents": [{"parts": [{"text": prompt_text}]}],
    "generationConfig": {
        "response_mime_type": "application/json"
    }
}

models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
raw_text = ""

for model_name in models_to_try:
    endpoint = "[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/)" + model_name + ":generateContent"
    try:
        resp = requests.post(
            endpoint,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            res_data = resp.json()
            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"성공 모델: {model_name}")
            break
        else:
            print(f"모델 {model_name} 실패 (상태코드 {resp.status_code}): {resp.text}")
    except Exception as err:
        print(f"모델 {model_name} 통신 에러: {err}")
        continue

if not raw_text:
    raise RuntimeError("모든 모델 호출에 실패했습니다. API 키 권한 또는 설정을 확인해주세요.")

clean_text = raw_text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

# today.json 저장
with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# archive.json 누적
archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
