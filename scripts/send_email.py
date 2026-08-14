# -*- coding: utf-8 -*-
"""3단계: 이번 주 브리핑을 이메일로 발송한다.

필요한 시크릿(환경변수):
  SMTP_USER - 발신 계정 (예: Gmail 주소)
  SMTP_PASS - 앱 비밀번호 (Gmail: 2단계 인증 후 '앱 비밀번호' 발급)
  MAIL_TO   - 수신 주소
선택:
  SMTP_HOST (기본 smtp.gmail.com), SMTP_PORT (기본 465), SITE_URL (서가 주소, 메일 하단 링크)
"""
import glob
import json
import os
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "archive")


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
    html_body = markdown.markdown(body_md, extensions=["extra"])
    site_link = (f'<p style="margin-top:24px"><a href="{site}" '
                 f'style="color:#0F5D56">→ 전체 아카이브 보러 가기</a></p>') if site else ""
    html = f"""<html><body style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
max-width:640px;margin:0 auto;padding:24px;color:#191B1C;line-height:1.7">
<p style="font-size:12px;letter-spacing:.12em;color:#0F5D56;font-weight:700">주간 인사이트 브리핑</p>
<h1 style="font-size:22px;margin:4px 0 20px">{meta['title']}</h1>
{html_body}
{site_link}
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[인사이트 브리핑] {meta['title']}"
    msg["From"] = user
    msg["To"] = to
    msg.attach(MIMEText(body_md, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=ctx) as server:
        server.login(user, pw)
        server.sendmail(user, [to], msg.as_string())
    print(f"발송 완료 → {to}")


if __name__ == "__main__":
    main()
