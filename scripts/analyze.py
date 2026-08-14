# -*- coding: utf-8 -*-
"""2단계: Gemini API로 선별 → 영상 심층분석 → 주간 뉴스레터(markdown) 생성."""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")
ARCHIVE = os.path.join(ROOT, "archive")
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
KST = timezone(timedelta(hours=9))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def call_gemini(model, api_key, parts, generation_config=None, retries=4, timeout=300):
    """Gemini 호출. 429/503(일시 혼잡)은 점점 길게 기다리며 재시도."""
    url = f"{API_BASE}/{model}:generateContent"
    body = {"contents": [{"parts": parts}]}
    if generation_config:
        body["generationConfig"] = generation_config
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, params={"key": api_key}, json=body, timeout=timeout)
            if r.status_code in (429, 503):
                wait = 30 * (attempt + 1)  # 30s, 60s, 90s...
                print(f"  일시 혼잡({r.status_code}) → {wait}초 대기 후 재시도")
                time.sleep(wait)
                last_err = RuntimeError(f"{r.status_code} busy")
                continue
            r.raise_for_status()
            data = r.json()
            text = "".join(
                p.get("text", "")
                for p in data["candidates"][0]["content"]["parts"]
            ).strip()
            if not text:
                raise RuntimeError("빈 응답")
            return text
        except requests.exceptions.RequestException as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(15 * (attempt + 1))
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(10)
    raise RuntimeError(f"Gemini 호출 실패: {last_err}")


def parse_json_response(text):
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


def stage1_select(cfg, api_key, items):
    listing = "\n".join(
        f"[{it['id']}] ({'영상' if it['kind'] == 'youtube' else '기사'} / {it['source']}) "
        f"{it['title']} — {it['summary'][:200]}"
        for it in items
    )
    prompt = f"""당신은 주간 인사이트 브리핑의 편집장이다. 수신자의 관심사는 다음과 같다:
{cfg['interests']}

아래는 지난 한 주간 수집된 콘텐츠 목록이다. 관심사와 무관한 항목(연예, 단순 사건사고, 스포츠 등)은 과감히 제외하라.

{listing}

다음 JSON만 출력하라 (다른 텍스트, 마크다운 펜스 금지):
{{
  "selected": [브리핑에 포함할 항목 id 목록 (최대 25개)],
  "deep_videos": [심층 분석할 가치가 가장 높은 '영상' 항목 id 목록 (최대 {cfg['max_deep_videos']}개, 관심사 적합도 순)],
  "week_theme": "이번 주 콘텐츠를 관통하는 흐름 한 문장"
}}"""
    text = call_gemini(cfg["model"], api_key, [{"text": prompt}])
    return parse_json_response(text)


def stage2_video(cfg, api_key, item):
    prompt = (
        "이 영상을 분석해 다음을 한국어로 작성하라:\n"
        "1) 핵심 주장 요약 (3~5문장)\n"
        "2) 강연자가 인용할 만한 구체적 수치·사례 (있는 경우만, 출처 시점 명시)\n"
        "3) AI 트렌드/경제/국제정세 강연 또는 AI 생산성 컨설팅 관점에서의 시사점 1~2개\n"
        "과장 없이, 영상에 실제로 나온 내용만 다뤄라."
    )
    parts = [
        {"fileData": {"fileUri": item["link"]}},
        {"text": prompt},
    ]
    try:
        return call_gemini(cfg["model"], api_key, parts,
                           generation_config={"mediaResolution": "MEDIA_RESOLUTION_LOW"})
    except Exception:
        return call_gemini(cfg["model"], api_key, parts)


def stage3_newsletter(cfg, api_key, items, selection, video_notes, feed_status):
    sel_ids = set(selection.get("selected", []))
    selected = [it for it in items if it["id"] in sel_ids]
    articles = [it for it in selected if it["kind"] == "article"]
    videos = [it for it in selected if it["kind"] == "youtube"]

    def block(its):
        return "\n".join(f"- ({it['source']}) {it['title']} — {it['summary'][:250]} [링크: {it['link']}]" for it in its)

    notes_block = "\n\n".join(
        f"### 영상: {n['title']} ({n['source']})\n링크: {n['link']}\n{n['note']}" for n in video_notes
    ) or "(이번 주 심층 분석 영상 없음)"

    prompt = f"""당신은 '주간 인사이트 브리핑'의 편집장이다. 수신자 정보:
{cfg['interests']}

이번 주 흐름: {selection.get('week_theme', '')}

[선별된 기사]
{block(articles) or '(없음)'}

[선별된 영상 (제목/설명 기반)]
{block(videos) or '(없음)'}

[심층 분석 노트]
{notes_block}

위 재료로 한국어 뉴스레터를 markdown으로 작성하라. 구조는 정확히 다음을 따르라:

## 이번 주 핵심 3가지
(가장 중요한 흐름 3개, 각 2~3문장. 왜 중요한지 포함)

## AI 트렌드 · 경제 · 국제정세
(관련 항목 종합. 개별 나열이 아니라 흐름으로 엮을 것. 출처는 문장 끝에 (소스명, [링크](url)) 형식)

## AI 툴 · 신기술
(새로 나온 툴/기능/업데이트. 생산성·업무 활용 관점의 코멘트 포함)

## 심층 노트
(심층 분석 노트를 다듬어 배치. 없으면 이 섹션 생략)

## 핵심 인사이트 종합요약
(이번 주 재료에서 뽑은, 강연 슬라이드나 컨설팅 대화에 바로 쓸 수 있는 인사이트 2~3개. 각 한 문장)

규칙: 재료에 없는 사실을 만들어내지 마라. 확실하지 않은 것은 쓰지 마라. 링크는 재료에 있는 것만 사용하라. 제목(h1)은 쓰지 마라."""
    return call_gemini(cfg["model"], api_key, [{"text": prompt}],
                       generation_config={"temperature": 0.4})


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("오류: GEMINI_API_KEY 환경변수(시크릿)가 없습니다.", file=sys.stderr)
        sys.exit(1)

    cfg = load_json(os.path.join(ROOT, "config", "sources.json"))
    items = load_json(os.path.join(WORK, "items.json"))
    feed_status = load_json(os.path.join(WORK, "feed_status.json"))
    items = items[: cfg.get("max_items_stage1", 80)]

    print(f"1차 선별 시작 (후보 {len(items)}건)…")
    selection = stage1_select(cfg, api_key, items)
    print(f"선별 결과: 포함 {len(selection.get('selected', []))}건, "
          f"심층 영상 {len(selection.get('deep_videos', []))}건")

    by_id = {it["id"]: it for it in items}
    video_notes, consecutive_fail, aborted = [], 0, False
    for vid in selection.get("deep_videos", [])[: cfg["max_deep_videos"]]:
        item = by_id.get(vid)
        if not item or item["kind"] != "youtube":
            continue
        print(f"영상 분석: {item['title'][:50]}…")
        try:
            note = stage2_video(cfg, api_key, item)
            video_notes.append({"title": item["title"], "source": item["source"],
                                "link": item["link"], "note": note})
            consecutive_fail = 0
        except Exception as exc:
            consecutive_fail += 1
            print(f"  실패: {exc}", file=sys.stderr)
            if consecutive_fail >= 2:
                aborted = True
                print("  연속 2회 실패 → 남은 영상 분석 중단 (근본 원인 확인 필요)", file=sys.stderr)
                break
        time.sleep(10)  # 영상 사이 간격을 두어 혼잡 회피

    print("뉴스레터 작성…")
    body = stage3_newsletter(cfg, api_key, items, selection, video_notes, feed_status)

    dead = [s for s in feed_status if not s.get("ok")]
    footer_lines = ["", "---", ""]
    if aborted:
        footer_lines.append("> ⚠️ 영상 심층 분석이 연속 실패하여 일부만 포함되었습니다. "
                            "유튜브 URL 처리 기능의 변경 여부 확인이 필요합니다.")
    if dead:
        names = ", ".join(f"{s['name']}{'(선택적)' if s.get('optional') else ''}" for s in dead)
        footer_lines.append(f"> ⚠️ 이번 주 수집 실패 피드: {names}")
    if not dead and not aborted:
        footer_lines.append("> ✅ 모든 소스 정상 수집됨")
    body += "\n".join(footer_lines)

    now = datetime.now(KST)
    iso = now.isocalendar()
    slug = f"{iso.year}-W{iso.week:02d}"
    title = f"{now.year}년 {now.month}월 {((now.day - 1) // 7) + 1}주차 AI 인사이트 브리핑"

    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(body)
    meta = {
        "slug": slug, "title": title, "date": now.strftime("%Y-%m-%d"),
        "week_theme": selection.get("week_theme", ""),
        "deep_video_count": len(video_notes),
        "item_count": len(selection.get("selected", [])),
    }
    with open(os.path.join(ARCHIVE, f"{slug}.meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"완료: archive/{slug}.md")


if __name__ == "__main__":
    main()
