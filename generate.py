import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# KST 오늘 날짜 구하기
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

# 503 과부하 회피용 다중 백업 모델군 (우선순위 순서대로 시도)
target_models = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

raw_text = None

for model in target_models:
    url = f"https://{host}/v1beta/models/{model}:generateContent"
    print(f"[{model}] 호출 시도 중...")
    
    # 모델당 최대 2회 시도
    for attempt in range(1, 3):
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=25
            )
            if resp.status_code == 200:
                res_json = resp.json()
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"호출 성공: {model}")
                break
            elif resp.status_code in [429, 503]:
                print(f"[{model}] 과부하({resp.status_code}). 3초 후 재시도 또는 다음 모델로 전환...")
                time.sleep(3)
            elif resp.status_code == 404:
                # 계정에서 지원하지 않는 구형 모델은 즉시 다음 모델로 패스
                print(f"[{model}] 미지원 모델 (404), 다음 모델 탐색.")
                break
            else:
                print(f"[{model}] 응답 코드 {resp.status_code}: {resp.text}")
                break
        except requests.exceptions.Timeout:
            print(f"[{model}] 타임아웃, 다음 시도 진행...")
            time.sleep(2)
        except Exception as e:
            print(f"[{model}] 통신 오류: {e}")
            break

    if raw_text:
        break

if not raw_text:
    raise RuntimeError("모든 백업 모델 호출에 실패했습니다. 잠시 후 다시 실행해 주세요.")

# 마크다운 코드블록이나 불필요한 줄바꿈 제거
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
