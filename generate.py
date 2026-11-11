import os
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# KST 오늘 날짜 구하기
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

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 누락되었습니다.")

prompt_text = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수한 JSON 형식으로만 응답해줘.
코드블록(```json 등)은 일체 쓰지 말고 순수 텍스트만 출력해.

제외 단어: {past_words[-100:]}
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

# 브라우저의 도메인 자동 하이퍼링크 변환을 원천 봉쇄하는 조각 조립
host = "".join(["gene", "rative", "language", ".", "google", "apis", ".", "com"])

# 회원님 계정의 ListModels 결과에서 확인된 실제 지원 모델
models = ["gemini-3.7-flash", "gemini-3.8-flash"]
raw_text = None

for m in models:
    url = f"https://{host}/v1beta/models/{m}:generateContent"
    try:
        resp = requests.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            res_json = resp.json()
            raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            print(f"호출 성공 모델: {m}")
            break
        else:
            print(f"모델 {m} 응답 코드: {resp.status_code}, 상세: {resp.text}")
    except Exception as e:
        print(f"모델 {m} 통신 에러: {e}")

if not raw_text:
    raise RuntimeError("모델 호출 실패. 키 또는 권한을 확인하세요.")

clean_text = raw_text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

# today.json 저장
with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# archive.json 누적 저장
archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
