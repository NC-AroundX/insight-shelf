# -*- coding: utf-8 -*-
"""2단계: Gemini API로 선별 → 영상 심층분석 → 주간 뉴스레터(markdown) 생성.
무료 티어 전용 설계: 페이스 조절 + 시간 예산제 + 주/예비 모델 자동 교체(fallback)."""
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

VIDEO_TIME_BUDGET = 15 * 60   # 영상 분석 전체 상한 15분
VIDEO_GAP = 70                # 영상 사이 대기 (분당 한도 리셋 주기)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _call_one_model(model, api_key, parts, generation_config=None, retries=2, timeout=300):
    url = f"{API_BASE}/{model}:generateContent"
    body = {"contents": [{"parts": parts}]}
    if generation_config:
        body["generationConfig"] = generation_config
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, params={"key": api_key}, json=body, timeout=timeout)
            if r.status_code in (429, 503):
                wait = 70 if r.status_code == 429 else 30
                print(f"  [{model}] 한도/혼잡({r.status_code}) → {wait}초 대기 후 재시도")
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
                time.sleep(15)
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(10)
    raise RuntimeError(f"{model} 실패: {last_err}")


def call_gemini(cfg, api_key, parts, generation_config=None, retries=2):
    """주 모델 실패 시 예비 모델로 자동 교체하여 호출."""
    models = [cfg["model"], cfg.get("fallback_model", "gemini-3.1-flash-lite")]
    last_err = None
    for m in models:
        try:
            return _call_one_model(m, api_key, parts, generation_config, retries)
        except Exception as exc:
            last_err = exc
            print(f"  {exc} → 예비 모델로 교체 시도" if m == models[0] else f"  {exc}")
    raise RuntimeError(f"모든 모델 실패: {last_err}")


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
    text = call_gemini(cfg, api_key, [{"text": prompt}])
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
    # 영상은 처음부터 경량 모델 사용 (무료 한도 절약), 재시도 1회로 짧게
    video_model = cfg.get("video_model", "gemini-3.1-flash-lite")
    try:
        return _call_one_model(video_model, api_key, parts,
                               {"mediaResolution": "MEDIA_RESOLUTION_LOW"}, retries=1)
    except Exception:
        return _call_one_model(video_model, api_key, parts, retries=1)


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
    return call_gemini(cfg, api_key, [{"text": prompt}],
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
    video_notes, skipped = [], 0
    video_start = time.time()
    deep_list = selection.get("deep_videos", [])[: cfg["max_deep_videos"]]
    for i, vid in enumerate(deep_list):
        item = by_id.get(vid)
        if not item or item["kind"] != "youtube":
            continue
        if time.time() - video_start > VIDEO_TIME_BUDGET:
            skipped = len(deep_list) - i
            print(f"시간 예산 초과 → 남은 영상 {skipped}편 건너뜀 (브리핑은 계속 진행)")
            break
        print(f"영상 분석: {item['title'][:50]}…")
        try:
            note = stage2_video(cfg, api_key, item)
            video_notes.append({"title": item["title"], "source": item["source"],
                                "link": item["link"], "note": note})
        except Exception as exc:
            skipped += 1
            print(f"  실패(건너뜀): {exc}", file=sys.stderr)
        if i < len(deep_list) - 1:
            print(f"  분당 한도 리셋 대기 {VIDEO_GAP}초…")
            time.sleep(VIDEO_GAP)

    print("뉴스레터 작성…")
    body = stage3_newsletter(cfg, api_key, items, selection, video_notes, feed_status)

    dead = [s for s in feed_status if not s.get("ok")]
    footer_lines = ["", "---", ""]
    if skipped:
        footer_lines.append(f"> ℹ️ 무료 사용량 한도로 이번 주 심층 영상 {skipped}편은 "
                            f"제목·설명 기반으로만 반영되었습니다. (분석 성공 {len(video_notes)}편)")
    if dead:
        names = ", ".join(f"{s['name']}{'(선택적)' if s.get('optional') else ''}" for s in dead)
        footer_lines.append(f"> ⚠️ 이번 주 수집 실패 피드: {names}")
    if not dead and not skipped:
        footer_lines.append("> ✅ 모든 소스 정상 수집·분석됨")
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
