# -*- coding: utf-8 -*-
"""3단계: 이번 주 브리핑을 '인사이트 서가' 디자인의 HTML 이메일로 발송한다.

- 수신자: MAIL_TO에 쉼표로 여러 명 지정 가능, 전원 숨은참조(BCC) 처리
- 브리핑 하단의 시스템 자가진단 문구(수집 실패 등)는 이메일에서 자동 제거
  (서가 웹페이지에는 그대로 남아 운영자가 확인 가능)
- 푸터에 AI 생성 자료 고지 문구 포함

필요한 시크릿: SMTP_USER, SMTP_PASS, MAIL_TO
선택: SMTP_HOST(기본 smtp.gmail.com), SMTP_PORT(기본 465), SITE_URL(서가 주소)
"""
import glob
import json
import os
import re
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "archive")

# ── 디자인 토큰 (서가 웹페이지와 동일 계열) ──────────────────────────
PAPER = "#F1F2EF"
CARD = "#FBFBF9"
INK = "#191B1C"
MUTED = "#6B6F6D"
TEAL = "#0F5D56"
AMBER = "#C77E1F"
LINE = "#DCDED9"
SERIF = "'Noto Serif KR','Nanum Myeongjo',Batang,serif"
SANS = ("-apple-system,'Apple SD Gothic Neo','Malgun Gothic',"
        "'Segoe UI',Roboto,sans-serif")

AI_NOTICE = ("이 브리핑은 AI가 공개 콘텐츠를 자동 수집·요약해 생성한 자료로, "
             "사실관계 오류나 원문과 다른 해석이 포함될 수 있습니다. "
             "중요한 의사결정이나 인용 전에는 심사숙고해서 사용하시기 바랍니다.")


def latest_brief():
    metas = sorted(glob.glob(os.path.join(ARCHIVE, "*.meta.json")))
    if not metas:
        print("오류: 발송할 브리핑이 없습니다.", file=sys.stderr)
        sys.exit(1)
    with open(metas[-1], encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(ARCHIVE, f"{meta['slug']}.md"), encoding="utf-8") as f:
        body = f.read()
    return meta, body


def strip_system_footer(body_md):
    """브리핑 끝의 시스템 자가진단 블록(--- 이후의 > 안내문들)을 이메일용으로 제거."""
    lines = body_md.rstrip().split("\n")
    i = len(lines) - 1
    while i >= 0 and (lines[i].strip() == "" or lines[i].lstrip().startswith(">")):
        i -= 1
    if i >= 0 and lines[i].strip() == "---":
        i -= 1
    return "\n".join(lines[: i + 1]).rstrip()


def style_html(html_body):
    """markdown 변환 결과의 각 태그에 이메일 안전 인라인 스타일을 주입."""
    rules = [
        (r"<h2>", f'<h2 style="font-family:{SERIF};font-size:20px;font-weight:700;'
                  f'color:{INK};margin:34px 0 12px;padding-top:22px;'
                  f'border-top:1px solid {LINE};letter-spacing:-0.3px">'),
        (r"<h3>", f'<h3 style="font-family:{SANS};font-size:16px;font-weight:700;'
                  f'color:{TEAL};margin:22px 0 8px">'),
        (r"<p>", f'<p style="font-family:{SANS};font-size:15px;line-height:1.8;'
                 f'color:{INK};margin:0 0 14px">'),
        (r"<ul>", '<ul style="margin:0 0 16px;padding-left:20px">'),
        (r"<ol>", '<ol style="margin:0 0 16px;padding-left:20px">'),
        (r"<li>", f'<li style="font-family:{SANS};font-size:15px;line-height:1.8;'
                  f'color:{INK};margin:0 0 10px">'),
        (r"<a ", f'<a style="color:{TEAL};font-weight:600" '),
        (r"<strong>", f'<strong style="color:{INK}">'),
        (r"<blockquote>", f'<blockquote style="margin:20px 0;padding:12px 16px;'
                          f'background:{PAPER};border-left:3px solid {AMBER};'
                          f'font-family:{SANS};font-size:13px;color:{MUTED}">'),
        (r"<hr\s*/?>", f'<hr style="border:none;border-top:1px solid {LINE};margin:28px 0">'),
    ]
    for pat, rep in rules:
        html_body = re.sub(pat, rep, html_body)
    return html_body


def build_email_html(meta, body_md, site_url):
    content = style_html(markdown.markdown(body_md, extensions=["extra"]))
    site_btn = ""
    if site_url:
        site_btn = f"""
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:32px auto 0">
          <tr><td style="background:{TEAL};border-radius:4px">
            <a href="{site_url}" style="display:inline-block;padding:12px 28px;
               font-family:{SANS};font-size:14px;font-weight:700;color:#ffffff;
               text-decoration:none">→ 인사이트 서가에서 전체 아카이브 보기</a>
          </td></tr>
        </table>"""
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{PAPER}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:{PAPER};padding:24px 12px">
<tr><td align="center">
  <table role="presentation" width="640" cellpadding="0" cellspacing="0"
         style="max-width:640px;width:100%">
    <!-- 헤더 -->
    <tr><td style="padding:8px 8px 18px">
      <div style="font-family:{SANS};font-size:11px;font-weight:700;
                  letter-spacing:3px;color:{TEAL};text-transform:uppercase">
        Weekly Insight Brief</div>
      <div style="font-family:{SERIF};font-size:26px;font-weight:700;
                  color:{INK};margin-top:6px;letter-spacing:-0.5px">
        {meta['title']}</div>
      <div style="font-family:{SANS};font-size:13px;color:{MUTED};margin-top:6px">
        {meta['date']} · 선별 {meta.get('item_count', 0)}건 ·
        심층 영상 {meta.get('deep_video_count', 0)}편</div>
    </td></tr>
    <!-- 본문 카드 -->
    <tr><td style="background:{CARD};border:1px solid {LINE};
                   border-top:4px solid {TEAL};padding:30px 28px">
      {content}
      {site_btn}
    </td></tr>
    <!-- 푸터 -->
    <tr><td style="padding:18px 8px;text-align:center">
      <div style="font-family:{SANS};font-size:12px;color:{MUTED}">
        인사이트 서가 · 매주 월요일 아침 자동 발행</div>
      <div style="font-family:{SANS};font-size:11px;line-height:1.7;color:{MUTED};
                  margin-top:10px;max-width:520px;margin-left:auto;margin-right:auto">
        {AI_NOTICE}</div>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def main():
    user = os.environ.get("SMTP_USER")
    pw = os.environ.get("SMTP_PASS")
    to = os.environ.get("MAIL_TO")
    if not all([user, pw, to]):
        print("오류: SMTP_USER / SMTP_PASS / MAIL_TO 시크릿이 필요합니다.", file=sys.stderr)
        sys.exit(1)
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    site = os.environ.get("SITE_URL", "")

    meta, body_md = latest_brief()
    body_md = strip_system_footer(body_md)  # 이메일에서는 자가진단 문구 제거
    html = build_email_html(meta, body_md, site)

    recipients = [a.strip() for a in to.split(",") if a.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[인사이트 브리핑] {meta['title']}"
    msg["From"] = user
    msg["To"] = user  # 표시상 받는사람은 발신자 본인 → 실제 수신자들은 숨은참조 처리
    plain_footer = f"\n\n---\n{AI_NOTICE}"
    msg.attach(MIMEText(body_md + plain_footer, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=ctx) as server:
        server.login(user, pw)
        server.sendmail(user, recipients, msg.as_string())
    print(f"발송 완료 → {len(recipients)}명")


if __name__ == "__main__":
    main()
