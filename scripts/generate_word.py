import json
import os
import time
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from pydantic import BaseModel

# 1. 응답 JSON 스키마 강제 (Pydantic)
class ExampleSentence(BaseModel):
    en: str
    ko: str

class WordPayload(BaseModel):
    part_of_speech: str
    examples: list[ExampleSentence]
    synonyms: list[str]
    quiz_distractors: list[str]  # 4지선다용 오답 뜻 3개

class DailyWordItem(BaseModel):
    title: str          # 영단어
    subtitle: str       # 발음기호
    summary: str        # 핵심 뜻 (한국어)
    category: str       # 비즈니스 / 일상 / 뉴스 등
    payload: WordPayload

# 2. 한국 시간(KST) 기준 오늘 날짜 계산
KST = timezone(timedelta(hours=9))
today_str = datetime.now(KST).strftime("%Y-%m-%d")

DATA_FILE = "data/daily_words.json"
os.makedirs("data", exist_ok=True)

# 3. 기존 데이터 로드 (중복 방지용)
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
else:
    db = {"app_type": "english_word", "updated_at": "", "items": []}

if any(item["date"] == today_str for item in db["items"]):
    print(f"[{today_str}] 이미 오늘의 단어가 생성되어 있습니다.", flush=True)
    exit(0)

existing_words = [item["title"] for item in db["items"]]

# 4. Gemini API 호출 (30초 타임아웃 + 503 과부하 대비 5회 재시도)
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=30000)
)

prompt = f"""
한국인 성인 학습자를 위한 '오늘의 영단어' 1개를 선정해 주세요.
- 난이도: 토익 750~900점 수준 또는 실생활/비즈니스에서 유용하지만 헷갈리기 쉬운 세련된 어휘
- 제외할 단어(이미 출제됨): {', '.join(existing_words[-100:])}
- quiz_distractors에는 정답(summary)과 품사는 비슷하지만 뜻이 완전히 다른 한국어 오답 보기 3개를 작성하세요.
"""

models_to_try = ["gemini-3.8-flash", "gemini-3.8-pro"]
response = None

for attempt in range(1, 6):
    for model_name in models_to_try:
        try:
            print(f"[시도 {attempt}/5 - {model_name}] 모델 호출 시작...", flush=True)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DailyWordItem,
                    temperature=0.7,
                ),
            )
            print(f"[{model_name}] 모델 호출 성공!", flush=True)
            break
        except Exception as e:
            print(f"[{model_name}] 실패: {e}", flush=True)
            time.sleep(3)
    if response:
        break

if not response:
    raise RuntimeError("모든 모델 호출 시도가 실패했습니다.")

generated = json.loads(response.text)

# 5. 공통 규격으로 데이터 조립 및 저장
new_entry = {
    "id": len(db["items"]) + 1,
    "date": today_str,
    "category": generated["category"],
    "title": generated["title"],
    "subtitle": generated["subtitle"],
    "summary": generated["summary"],
    "payload": generated["payload"],
}

db["items"].insert(0, new_entry)
db["updated_at"] = today_str

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 신규 단어 생성 완료: {new_entry['title']}", flush=True)
