import os
import json
import time
import re
import unicodedata
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
    except Exception as exc:
        raise RuntimeError("archive.json 읽기 실패: 이전 단어 기록을 보호하기 위해 생성 중단") from exc

def normalize_word(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).casefold()).strip()

if any(isinstance(item, dict) and item.get("date") == today_str for item in archive):
    print(f"[{today_str}] 오늘 단어가 이미 있어 재생성하지 않습니다.")
    raise SystemExit(0)

past_words = [item.get("word", "") for item in archive if isinstance(item, dict)]
used_words = {normalize_word(w) for w in past_words if w}

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경변수가 누락되었습니다.")

prompt_text = f"""
유용한 영어 단어나 숙어 1개를 선정해서 반드시 유효한 순수 JSON 형식으로만 응답해줘.
값(문자열) 내부에는 큰따옴표(")와 줄바꿈을 절대 쓰지 말고, 작은따옴표(')만 사용해.

제외 단어: {past_words}
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
target_models = [
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-flash-latest"
]

data = None

for model in target_models:
    url = f"https://{host}/v1beta/models/{model}:generateContent"
    for attempt in range(1, 3):
        try:
            print(f"[{model}] 호출 시도 {attempt}/2...")
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
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if json_match:
                    clean_text = json_match.group(0)
                # 줄바꿈 제어문자 제거 후 파싱
                clean_text = re.sub(r'[\r\n]+', ' ', clean_text)
                parsed = json.loads(clean_text)
                if all(k in parsed for k in ["word", "meaning", "example_en", "example_ko"]):
                    if not parsed["word"] or normalize_word(parsed["word"]) in used_words:
                        print(f"중복 또는 빈 단어 생성: {parsed.get('word')}. 다른 후보 요청")
                        continue
                    parsed["date"] = today_str
                    data = parsed
                    print(f"호출 및 JSON 파싱 성공: {model}")
                    break
            elif resp.status_code in [429, 503]:
                print(f"[{model}] 일시적 부하({resp.status_code}), 4초 후 재시도...")
                time.sleep(4)
            else:
                print(f"[{model}] 응답 코드 {resp.status_code}")
                break
        except Exception as e:
            print(f"[{model}] 오류 발생({e}), 재시도 또는 다음 모델 전환...")
            time.sleep(2)

    if data:
        break

if not data:
    raise RuntimeError("유효한 JSON 데이터 생성에 실패했습니다.")

with open("today.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

archive.append(data)
with open("archive.json", "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False, indent=2)

print(f"[{today_str}] 생성 완료: {data.get('word')}")
