import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

kst = ZoneInfo("Asia/Seoul")
today_str = datetime.now(kst).strftime("%Y-%m-%d")

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

host = "".join(["gene", "rative", "language", ".", "google", "apis", ".", "com"])
target_models = ["gemini-3.8-flash", "gemini-3.7-flash"]
raw_text = None

# 타임아웃을 90초로 확장하고 최대 3회 재시도
for model in target_models:
    url = f"https://{host}/v1beta/models/{model}:generateContent"
    for attempt in range(3):
        try:
            print(f"[{model}] 호출 시도 {attempt + 1}/3...")
            resp = requests.post(
                url,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=90
            )
            if resp.status_code == 200:
                res_json = resp.json()
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"호출 성공 모델: {model}")
                break
            elif resp.status_code in [503, 429]:
                print(f"일시적 부하 발생 ({resp.status_code}), 5초 대기...")
                time.sleep(5)
            else:
                print(f"실패 코드 {resp.status_code}: {resp.text}")
                break
        except requests.exceptions.Timeout:
            print(f"[{model}] 타임아웃 발생, 재시도 대기...")
            time.sleep(3)
        except Exception as e:
            print(f"통신 에러: {e}")
            break
            
    if raw_text:
        break

if not raw_text:
    raise RuntimeError("모든 시도 실패. 잠시 후 다시 실행해 주세요.")

clean_text = raw_text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
