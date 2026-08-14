# -*- coding: utf-8 -*-
"""4단계: archive/ 의 브리핑들을 '인사이트 서가' 정적 사이트로 빌드한다 (docs/ 출력, GitHub Pages 용)."""
import glob
import html
import json
import os

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "archive")
DOCS = os.path.join(ROOT, "docs")

CSS = """
:root{--paper:#F1F2EF;--ink:#191B1C;--muted:#6B6F6D;--teal:#0F5D56;--teal-deep:#0A423D;
--amber:#C77E1F;--line:#DCDED9;--card:#FBFBF9}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
line-height:1.75;font-size:16px;-webkit-font-smoothing:antialiased}
.wrap{max-width:720px;margin:0 auto;padding:0 20px 96px}
header.site{padding:56px 0 8px}
.eyebrow{font-size:12px;letter-spacing:.22em;color:var(--teal);font-weight:700;text-transform:uppercase}
h1.site-title{font-family:"Noto Serif KR",serif;font-weight:700;font-size:clamp(30px,6vw,44px);
margin:6px 0 10px;letter-spacing:-.01em}
.site-sub{color:var(--muted);font-size:15px;margin:0 0 40px;max-width:46ch}
/* 서가: 책등 카드 */
.shelf{display:flex;flex-direction:column}
a.spine{display:flex;text-decoration:none;color:inherit;background:var(--card);
border:1px solid var(--line);border-left:none;margin-bottom:14px;min-height:104px;
transition:transform .18s ease,box-shadow .18s ease}
a.spine:hover{transform:translateX(4px);box-shadow:0 6px 20px rgba(15,93,86,.10)}
a.spine:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
.spine-bar{flex:0 0 46px;background:var(--teal);color:#fff;display:flex;align-items:center;
justify-content:center}
.shelf .spine:nth-child(3n+2) .spine-bar{background:var(--teal-deep)}
.shelf .spine:nth-child(3n) .spine-bar{background:var(--amber)}
.spine-week{writing-mode:vertical-rl;font-size:12px;font-weight:700;letter-spacing:.18em}
.spine-body{padding:16px 20px;flex:1;min-width:0}
.spine-title{font-family:"Noto Serif KR",serif;font-weight:600;font-size:18px;margin:0 0 4px}
.spine-theme{color:var(--muted);font-size:14px;margin:0;display:-webkit-box;
-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.spine-meta{font-size:12px;color:var(--muted);margin-top:8px;letter-spacing:.04em}
.shelf-base{height:6px;background:var(--ink);border-radius:1px;margin-top:6px;opacity:.85}
.empty{border:1px dashed var(--line);padding:48px 24px;text-align:center;color:var(--muted);
background:var(--card)}
/* 브리핑 본문 */
article.brief{background:var(--card);border:1px solid var(--line);padding:36px 32px;margin-top:24px}
.brief h2{font-family:"Noto Serif KR",serif;font-size:21px;margin:36px 0 12px;
padding-top:20px;border-top:1px solid var(--line);letter-spacing:-.01em}
.brief h2:first-child{margin-top:0;border-top:none;padding-top:0}
.brief a{color:var(--teal);text-decoration-thickness:1px;text-underline-offset:3px}
.brief blockquote{margin:20px 0;padding:12px 18px;background:var(--paper);
border-left:3px solid var(--amber);color:var(--muted);font-size:14px}
.brief li{margin:6px 0}
.back{display:inline-block;margin:40px 0 0;color:var(--muted);text-decoration:none;font-size:14px}
.back:hover{color:var(--teal)}
.brief-head{padding-top:48px}
.brief-title{font-family:"Noto Serif KR",serif;font-size:clamp(26px,5vw,36px);font-weight:700;
margin:6px 0 4px;letter-spacing:-.01em}
.brief-date{color:var(--muted);font-size:14px}
@media (max-width:480px){article.brief{padding:28px 20px}.spine-bar{flex-basis:40px}}
@media (prefers-reduced-motion:reduce){a.spine{transition:none}a.spine:hover{transform:none}}
"""

HEAD = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" as="style" crossorigin
 href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>{css}</style></head><body><div class="wrap">"""

FOOT = "</div></body></html>"


def load_briefs():
    briefs = []
    for meta_path in sorted(glob.glob(os.path.join(ARCHIVE, "*.meta.json")), reverse=True):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        md_path = os.path.join(ARCHIVE, f"{meta['slug']}.md")
        if os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as f:
                meta["body_md"] = f.read()
            briefs.append(meta)
    return briefs


def build_index(briefs):
    parts = [HEAD.format(title="인사이트 서가", css=CSS)]
    parts.append('<header class="site"><p class="eyebrow">Weekly Insight Archive</p>'
                 '<h1 class="site-title">인사이트 서가</h1>'
                 '<p class="site-sub">AI 트렌드 · 경제 · 국제정세 · AI 툴 — 매주 월요일 아침, '
                 '한 주의 흐름을 한 권으로.</p></header>')
    if not briefs:
        parts.append('<div class="empty">아직 서가가 비어 있습니다.<br>'
                     '첫 브리핑이 도착하면 여기에 꽂힙니다.</div>')
    else:
        parts.append('<div class="shelf">')
        for b in briefs:
            week = html.escape(b["slug"].split("-")[-1])
            parts.append(
                f'<a class="spine" href="briefs/{b["slug"]}.html">'
                f'<div class="spine-bar"><span class="spine-week">{week} · {b["slug"][:4]}</span></div>'
                f'<div class="spine-body"><p class="spine-title">{html.escape(b["title"])}</p>'
                f'<p class="spine-theme">{html.escape(b.get("week_theme", ""))}</p>'
                f'<p class="spine-meta">{b["date"]} · 선별 {b.get("item_count", 0)}건 · '
                f'심층 영상 {b.get("deep_video_count", 0)}편</p></div></a>')
        parts.append('</div><div class="shelf-base"></div>')
    parts.append(FOOT)
    return "".join(parts)


def build_brief_page(b):
    body_html = markdown.markdown(b["body_md"], extensions=["extra"])
    return "".join([
        HEAD.format(title=html.escape(b["title"]) + " — 인사이트 서가", css=CSS),
        '<div class="brief-head"><p class="eyebrow">Weekly Insight Brief</p>',
        f'<h1 class="brief-title">{html.escape(b["title"])}</h1>',
        f'<p class="brief-date">{b["date"]}</p></div>',
        f'<article class="brief">{body_html}</article>',
        '<a class="back" href="../index.html">← 서가로 돌아가기</a>',
        FOOT,
    ])


def main():
    briefs = load_briefs()
    os.makedirs(os.path.join(DOCS, "briefs"), exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(build_index(briefs))
    for b in briefs:
        with open(os.path.join(DOCS, "briefs", f"{b['slug']}.html"), "w", encoding="utf-8") as f:
            f.write(build_brief_page(b))
    # Jekyll 처리 비활성화 (언더스코어 파일 이슈 예방)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"사이트 빌드 완료: 브리핑 {len(briefs)}건")


if __name__ == "__main__":
    main()
