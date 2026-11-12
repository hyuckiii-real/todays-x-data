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

host = "".join(["gene", "rative", "language", ".", "google", "apis", ".", "com"])

# 1. 현재 무료 키에서 실제 호출 가능한 generateContent 모델 목록 조회
available_models = []
try:
    list_url = f"https://{host}/v1beta/models"
    res = requests.get(list_url, params={"key": api_key}, timeout=15)
    if res.status_code == 200:
        for m in res.json().get("models", []):
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                # 이미지, 임베딩, 비디오 전용 모델 제외
                if not any(x in name for x in ["imagen", "veo", "embedding", "aqa"]):
                    available_models.append(name)
        print(f"계정 지원 모델 목록: {available_models}")
except Exception as e:
    print(f"목록 조회 실패: {e}")

# 트래픽이 적고 빠른 경량 모델(lite, gemma 등)을 우선순위로 정렬
priority_keywords = ["lite", "gemma", "3.7-flash", "3.8-flash", "flash"]
sorted_models = []
for kw in priority_keywords:
    for m in available_models:
        if kw in m and m not in sorted_models:
            sorted_models.append(m)

# 나머지 사용 가능 모델 추가
for m in available_models:
    if m not in sorted_models:
        sorted_models.append(m)

if not sorted_models:
    sorted_models = ["gemini-3.8-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"]

prompt_text = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 순수한 JSON 형식으로만 응답해줘.
코드블록(```json 등)은 일체 쓰지 말고 순수 JSON 텍스트만 출력해.

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
    "contents": [{"parts": [{"text": prompt_text}]}]
}

raw_text = None

# 2. 경량 모델부터 순차 호출 (과부하 503 회피)
for model in sorted_models:
    url = f"https://{host}/v1beta/models/{model}:generateContent"
    print(f"[{model}] 호출 시도...")
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
            print(f"호출 성공 모델: {model}")
            break
        else:
            print(f"[{model}] 실패 ({resp.status_code}) -> 다음 모델로 즉시 전환")
            time.sleep(2)
    except Exception as e:
        print(f"[{model}] 지연/에러 -> 다음 모델로 즉시 전환: {e}")

if not raw_text:
    raise RuntimeError("모든 지원 모델 호출에 실패했습니다.")

# 응답 텍스트에서 순수 JSON 객체만 추출
clean_text = raw_text.replace("```json", "").replace("```", "").strip()
start_idx = clean_text.find("{")
end_idx = clean_text.rfind("}")
if start_idx != -1 and end_idx != -1:
    clean_text = clean_text[start_idx:end_idx + 1]

data = json.loads(clean_text)

with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
