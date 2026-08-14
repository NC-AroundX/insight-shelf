# 인사이트 서가 (Insight Shelf)

매주 월요일 오전 9시(KST), 구독 유튜브 채널 + AI 공식 블로그 + 테크 미디어를 자동 수집·분석해
**주간 인사이트 브리핑**을 만들어 ① 이메일로 발송하고 ② 웹/모바일 '서가' 페이지에 아카이빙합니다.

- 수집: 유튜브 채널 RSS 7개 + 기사 RSS 5개 (`config/sources.json`)
- 분석: Google Gemini API — 1차 선별(제목·설명) → 2차 영상 심층분석(최대 4편, 저해상도) → 뉴스레터 작성
- 배포: GitHub Pages (모바일 대응) + 이메일

---

## 최초 설치 (약 20~30분, 한 번만)

### 1. Gemini API 키 발급 (5분)
1. https://aistudio.google.com 접속 → 구글 계정 로그인
2. 좌측 **Get API key** → **Create API key** → 키 복사해서 메모장에 임시 보관
   (이 키는 Gemini 앱 유료 구독과 별개의 종량제이며, 무료 티어가 있습니다)

### 2. Gmail 앱 비밀번호 발급 (5분) — 이메일 발송용
1. 구글 계정 → 보안 → **2단계 인증**이 켜져 있어야 합니다
2. https://myaccount.google.com/apppasswords → 앱 이름 아무거나(예: insight-shelf) → 생성
3. 표시되는 16자리 비밀번호 복사 (이게 `SMTP_PASS`가 됩니다)

### 3. GitHub 저장소 만들기 (5분)
1. https://github.com 가입/로그인 → 우측 상단 **+** → **New repository**
2. 이름: `insight-shelf`, **Public** 선택 (Pages 무료 사용 조건) → Create
3. **uploading an existing file** 링크 클릭 → 이 압축을 푼 **폴더 안의 내용 전체**를 드래그해서 업로드 → Commit
   - 주의: `insight-shelf` 폴더째가 아니라 폴더 **안의** 파일들을 올려야 합니다
   - `.github` 폴더가 안 보이면(숨김 파일) 압축 해제 프로그램에서 숨김 표시를 켜세요

### 4. 시크릿 등록 (5분)
저장소 → **Settings → Secrets and variables → Actions** → **New repository secret**으로 4개 등록:

| 이름 | 값 |
|---|---|
| `GEMINI_API_KEY` | 1번에서 발급한 키 |
| `SMTP_USER` | 본인 Gmail 주소 |
| `SMTP_PASS` | 2번의 16자리 앱 비밀번호 |
| `MAIL_TO` | 브리핑 받을 이메일 주소 |

같은 화면의 **Variables** 탭에서 변수 1개 (선택, 메일 하단 서가 링크용):
`SITE_URL` = `https://본인아이디.github.io/insight-shelf/`

### 5. GitHub Pages 켜기 (2분)
저장소 → **Settings → Pages** → Source: **Deploy from a branch** →
Branch: `main`, 폴더: **/docs** → Save.
1~2분 후 `https://본인아이디.github.io/insight-shelf/` 에서 서가가 열립니다.
(처음엔 디자인 확인용 샘플 브리핑 1건이 꽂혀 있습니다)

### 6. 첫 테스트 실행 (필수)
저장소 → **Actions** 탭 → 좌측 `weekly-brief` → **Run workflow**
- 처음엔 "skip_email" 체크해서 이메일 없이 돌려보고, 성공하면 체크 해제하고 한 번 더
- 5~15분 소요. 성공하면 서가에 실제 브리핑이 추가되고 샘플과 함께 표시됩니다
- 샘플 삭제: 저장소에서 `archive/2026-W33.md` 와 `archive/2026-W33.meta.json` 삭제 → 다음 실행 때 서가에서 사라짐

이후로는 **매주 월요일 오전 9시(±10~30분, GitHub 스케줄러 특성)** 자동 실행됩니다.

---

## 운영 중 자주 하는 일

**소스 추가/삭제**: `config/sources.json` 을 GitHub 웹에서 직접 편집 (연필 아이콘).
유튜브 채널 RSS 주소는 `https://www.youtube.com/feeds/videos.xml?channel_id=채널ID` 형식.
채널 ID는 채널 페이지 → 더보기 → 채널 공유 → 채널 ID 복사.

**관심사 조정**: 같은 파일의 `interests` 문장을 수정하면 선별 기준이 바뀝니다.

**비용 조절**: `max_deep_videos` (심층 분석 영상 수, 기본 4) 를 줄이면 토큰 사용이 크게 줍니다.

**실패 확인**: 월요일에 메일이 안 왔다면 → Actions 탭에서 빨간 X 클릭 → 로그 확인.
각 단계(수집/분석/발송/빌드)별로 어디서 멈췄는지 표시됩니다.

---

## 알아두면 좋은 설계 사항

- **피드 자가진단**: 매 브리핑 하단에 수집 실패한 소스가 자동 보고됩니다. Anthropic 피드는
  비공식 미러라 끊길 수 있는데, 끊겨도 전체 파이프라인은 계속 돌고 하단에만 표시됩니다.
- **비용 안전장치**: 영상 전체가 아니라 1차 선별을 통과한 영상만, 최대 4편, 저해상도로 분석합니다.
- **오류 시 중단 원칙**: 영상 분석이 연속 2회 실패하면 남은 분석을 중단하고 브리핑에 명시합니다.
  필수 피드 절반 이상이 죽으면 부실한 브리핑을 만드는 대신 실행 자체를 실패시킵니다.
- **모델 교체**: `config/sources.json` 의 `model` 값을 바꾸면 됩니다 (예: 상위 모델로).

## 폴더 구조

```
config/sources.json   수집 소스·설정
scripts/collect.py    RSS 수집 + 피드 상태 점검
scripts/analyze.py    Gemini 선별·심층분석·뉴스레터 작성
scripts/send_email.py 이메일 발송
scripts/build_site.py 서가 사이트 빌드 (docs/)
archive/              브리핑 원본 아카이브 (markdown)
docs/                 GitHub Pages로 서빙되는 서가 사이트
.github/workflows/    매주 월요일 자동 실행 스케줄
```
