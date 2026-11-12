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

host = "".join(["gene", "rative", "language", ".", "google", "apis", ".", "com"])
raw_text = None

# 1단계: 503 회피용 최신 Interactions API 우선 호출 시도
print("1단계: Interactions API 호출 시도...")
interaction_url = f"https://{host}/v1beta/interactions"
interaction_payload = {
    "model": "gemini-3.8-flash",
    "input": prompt_text,
    "generation_config": {
        "response_mime_type": "application/json"
    }
}

try:
    resp = requests.post(
        interaction_url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json=interaction_payload,
        timeout=30
    )
    if resp.status_code == 200:
        res_json = resp.json()
        # Interactions 규격 응답 파싱
        if "candidates" in res_json:
            raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
        elif "output" in res_json:
            raw_text = res_json["output"]
        print("Interactions API 호출 성공!")
except Exception as e:
    print(f"Interactions API 경유 실패, 기존 generateContent 파이프라인으로 전환: {e}")

# 2단계: 실패 시 사용 가능한 실존 모델 목록 순차 호출 (재시도 간격 10초)
if not raw_text:
    print("2단계: generateContent 모델별 순차 호출 시작...")
    active_models = ["gemini-3.8-flash", "gemini-3.7-flash"]
    generate_payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    for model in active_models:
        url = f"https://{host}/v1beta/models/{model}:generateContent"
        for attempt in range(1, 4):
            try:
                print(f"[{model}] 호출 시도 {attempt}/3...")
                resp = requests.post(
                    url,
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json=generate_payload,
                    timeout=30
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"호출 성공: {model}")
                    break
                elif resp.status_code in [429, 503]:
                    wait_sec = attempt * 8
                    print(f"[{model}] 일시적 과부하 ({resp.status_code}). {wait_sec}초 대기...")
                    time.sleep(wait_sec)
                else:
                    print(f"[{model}] 응답 코드 {resp.status_code}: {resp.text}")
                    break
            except Exception as e:
                print(f"[{model}] 통신 오류: {e}")
                time.sleep(3)

        if raw_text:
            break

if not raw_text:
    raise RuntimeError("모든 API 및 모델 호출 실패. 구글 AI Studio 상태를 확인해주세요.")

clean_text = raw_text.replace("```json", "").replace("```", "").strip()
data = json.loads(clean_text)

with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
