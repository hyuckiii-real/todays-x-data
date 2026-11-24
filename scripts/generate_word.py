import asyncio
import json
import os
import time
import re
import unicodedata
from datetime import datetime, timezone, timedelta
import edge_tts
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
    quiz_distractors: list[str]

class DailyWordItem(BaseModel):
    title: str
    subtitle: str
    summary: str
    category: str
    payload: WordPayload

# 2. 경로 및 상수 설정
KST = timezone(timedelta(hours=9))
today_str = datetime.now(KST).strftime("%Y-%m-%d")

DATA_FILE = "data/daily_words.json"
AUDIO_DIR = "audio"
RAW_BASE_URL = "https://raw.githubusercontent.com/hyuckiii-real/todays-x-data/main/audio"
VOICE = "en-US-AriaNeural"  # 미국 원어민 여성 성우 음성

os.makedirs("data", exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

# 3. 원어민 MP3 생성 비동기 함수
async def generate_mp3(text: str, filepath: str):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filepath)

async def ensure_audio_for_entry(entry: dict):
    word_id = entry["id"]
    payload = entry.setdefault("payload", {})
    
    # 단어 오디오 생성
    word_filename = f"{word_id}_word.mp3"
    word_filepath = os.path.join(AUDIO_DIR, word_filename)
    if not os.path.exists(word_filepath):
        await generate_mp3(entry["title"], word_filepath)
        print(f"  -> 단어 오디오 생성: {word_filename}", flush=True)
    payload["word_audio_url"] = f"{RAW_BASE_URL}/{word_filename}"

    # 예문 오디오 생성
    for idx, ex in enumerate(payload.get("examples", [])):
        ex_filename = f"{word_id}_ex{idx}.mp3"
        ex_filepath = os.path.join(AUDIO_DIR, ex_filename)
        if not os.path.exists(ex_filepath):
            await generate_mp3(ex["en"], ex_filepath)
            print(f"  -> 예문 오디오 생성: {ex_filename}", flush=True)
        ex["audio_url"] = f"{RAW_BASE_URL}/{ex_filename}"

# 4. 기존 데이터 로드
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
else:
    db = {"app_type": "english_word", "updated_at": "", "items": []}

def normalize_word(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()

# 5. 오늘 날짜 단어가 없으면 신규 생성
if not any(item["date"] == today_str for item in db["items"]):
    existing_words = [item["title"] for item in db["items"] if item.get("title")]
    used_words = {normalize_word(w) for w in existing_words}
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(timeout=45000)
    )

    available_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" in name and "embedding" not in name and "imagen" not in name and "veo" not in name:
                available_models.append(name)
    except Exception as e:
        print(f"모델 목록 조회 실패: {e}", flush=True)

    priority_models = [m for m in available_models if "flash" in m] + [m for m in available_models if "pro" in m]
    if not priority_models:
        priority_models = ["gemini-3.8-flash"]

    prompt = f"""
    한국인 성인 학습자를 위한 '오늘의 영단어' 1개를 선정해 주세요.
    - 난이도: 토익 750~900점 수준 또는 실생활/비즈니스에서 유용하지만 헷갈리기 쉬운 세련된 어휘
    - 제외할 단어(이미 출제됨): {', '.join(existing_words)}
    - quiz_distractors에는 정답(summary)과 품사는 비슷하지만 뜻이 완전히 다른 한국어 오답 보기 3개를 작성하세요.
    """

    response = None
    for attempt in range(1, 4):
        for model_name in priority_models[:4]:
            try:
                print(f"[시도 {attempt}/3 - {model_name}] 호출 시작...", flush=True)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=DailyWordItem,
                        temperature=0.7,
                    ),
                )
                candidate = json.loads(response.text)
                if not candidate.get("title") or normalize_word(candidate["title"]) in used_words:
                    print(f"[{model_name}] 중복 단어 생성: {candidate.get('title')}. 재시도합니다.", flush=True)
                    response = None
                    continue
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
    print(f"[{today_str}] 신규 단어 생성 완료: {new_entry['title']}", flush=True)
else:
    print(f"[{today_str}] 이미 오늘의 단어가 존재합니다. 누락된 오디오만 점검합니다.", flush=True)

# 6. 전체 아이템에 대해 원어민 오디오 생성 및 URL 매핑
async def process_all():
    for entry in db["items"]:
        await ensure_audio_for_entry(entry)

asyncio.run(process_all())

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print("JSON 및 원어민 오디오 업데이트 완료!", flush=True)
