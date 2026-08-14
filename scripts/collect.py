# -*- coding: utf-8 -*-
"""1단계: 모든 소스(RSS)에서 최근 항목을 수집하고 피드 상태를 점검한다.

출력:
  work/items.json   - 수집된 항목 목록
  work/feed_status.json - 각 피드의 생존/실패 상태 (브리핑 하단에 보고됨)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")


def load_config():
    with open(os.path.join(ROOT, "config", "sources.json"), encoding="utf-8") as f:
        return json.load(f)


def entry_datetime(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None


def clean_text(s, limit=600):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def collect_feed(source, kind, cutoff):
    """단일 피드 수집. 반환: (items, status_dict)"""
    items = []
    try:
        parsed = feedparser.parse(source["feed"], request_headers={"User-Agent": "Mozilla/5.0 insight-shelf/1.0"})
        if parsed.bozo and not parsed.entries:
            raise RuntimeError(str(getattr(parsed, "bozo_exception", "parse error")))
        for e in parsed.entries:
            dt = entry_datetime(e)
            if dt is None or dt < cutoff:
                continue
            link = e.get("link", "")
            summary = e.get("summary", "") or e.get("description", "")
            # 유튜브 피드는 media:description 에 상세 설명이 있음
            if kind == "youtube":
                media = e.get("media_description") or ""
                if media:
                    summary = media
            items.append({
                "source": source["name"],
                "kind": kind,
                "title": clean_text(e.get("title", ""), 200),
                "summary": clean_text(summary, 600),
                "link": link,
                "published": dt.isoformat(),
            })
        status = {"name": source["name"], "ok": True, "count": len(items)}
    except Exception as exc:  # 피드 하나가 죽어도 전체는 계속
        status = {"name": source["name"], "ok": False,
                  "optional": bool(source.get("optional")), "error": str(exc)[:200]}
    return items, status


def main():
    cfg = load_config()
    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.get("lookback_days", 8))
    all_items, statuses = [], []

    for kind, key in (("youtube", "youtube"), ("article", "articles")):
        for src in cfg.get(key, []):
            items, status = collect_feed(src, kind, cutoff)
            all_items.extend(items)
            statuses.append(status)
            print(f"[{'OK' if status.get('ok') else 'FAIL'}] {src['name']}: "
                  f"{status.get('count', 0)}건" if status.get("ok")
                  else f"[FAIL] {src['name']}: {status.get('error')}")

    # 최신순 정렬 후 id 부여
    all_items.sort(key=lambda x: x["published"], reverse=True)
    for i, item in enumerate(all_items):
        item["id"] = i

    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "items.json"), "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    with open(os.path.join(WORK, "feed_status.json"), "w", encoding="utf-8") as f:
        json.dump(statuses, f, ensure_ascii=False, indent=2)

    dead_required = [s for s in statuses if not s.get("ok") and not s.get("optional")]
    print(f"\n수집 완료: 총 {len(all_items)}건, 피드 {len(statuses)}개 중 실패 {sum(1 for s in statuses if not s.get('ok'))}개")

    if not all_items:
        print("오류: 수집된 항목이 0건입니다. 네트워크 또는 피드 전체 장애 가능성.", file=sys.stderr)
        sys.exit(1)
    # 필수 피드가 절반 이상 죽었으면 실패 처리 (조용히 부실한 브리핑을 만들지 않음)
    required_total = sum(1 for s in statuses if not s.get("optional"))
    if required_total and len(dead_required) >= required_total / 2:
        print("오류: 필수 피드 절반 이상이 실패했습니다. 원인 확인이 필요합니다.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
