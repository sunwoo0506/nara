# 나라장터 입찰공고 Slack 알림 시스템 — 설계 문서

**날짜:** 2026-03-24
**상태:** 승인됨

---

## 개요

나라장터(g2b.go.kr)에 올라오는 입찰공고 중 사용자가 지정한 키워드와 매칭되는 공고가 있을 때 Slack으로 알림을 전송하는 자동화 시스템.

---

## 요구사항

- 매일 오전 10시(KST)에 자동 실행
- 사용자가 지정한 키워드와 매칭되는 입찰공고만 알림 전송 (AND 조건: 모든 키워드가 매칭되면 알림)
- 이미 알림 보낸 공고는 재전송하지 않음 (중복 방지)
- 마감된 공고는 추적 목록에서 자동 제거
- 완전 무료 인프라 사용
- 키워드는 GitHub에서 파일 수정으로 관리

---

## 아키텍처

### 구성 요소

| 구성 요소 | 역할 |
|-----------|------|
| GitHub Actions | 스케줄 실행 (매일 10시 KST) |
| Python 스크립트 | 메인 로직 |
| 나라장터 Open API | 입찰공고 데이터 소스 |
| `keywords.txt` | 키워드 목록 저장 |
| GitHub Issue | 알림 전송된 공고번호 추적 (중복 방지 DB) |
| Slack Incoming Webhook | 알림 전송 |

### 실행 흐름

```
GitHub Actions (매일 10시 KST = UTC 01:00)
        ↓
checker.py 실행
        ↓
1. keywords.txt 읽기 (없거나 비어있으면 경고 후 종료)
        ↓
2. 나라장터 Open API 호출 (당일 등록 입찰공고 전체 페이지 조회)
        ↓
3. 키워드 매칭 필터링 (공고명 기준, 대소문자 무시, AND 조건)
        ↓
4. GitHub Issue에서 기존 seen 목록 읽기
        ↓
5. 마감일이 오늘 이전인 공고를 seen 목록에서 제거
        ↓
6. 새 공고(seen에 없는 것)만 추출
        ↓
7. 새 공고 있으면 → Slack으로 알림 전송
        ↓
8. seen 목록에 새 공고 추가 후 GitHub Issue 업데이트
```

---

## 저장소 구조

```
/
├── .github/
│   └── workflows/
│       └── check_bids.yml      # GitHub Actions 워크플로우
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-03-24-g2b-slack-alert-design.md
├── checker.py                  # 메인 실행 스크립트
├── keywords.txt                # 키워드 목록 (한 줄에 하나)
└── README.md
```

---

## 상세 설계

### keywords.txt 형식

```
소프트웨어
유지보수
시스템 구축
IT 서비스
```

- 한 줄에 키워드 하나
- `#`으로 시작하는 줄은 주석으로 무시
- 공고명(`bidNtceNm`)에 키워드가 포함되면 매칭 (대소문자 무시)
- AND 조건: 모든 키워드가 공고명에 포함되어야 매칭 (예: `제주`, `AI` → "제주 AI 시스템 구축"은 매칭, "AI 시스템 구축"은 미매칭)
- `keywords.txt`가 없거나 유효 키워드가 0개이면 오류 메시지 출력 후 스크립트 종료

---

### 나라장터 Open API

**엔드포인트:**
```
GET https://apis.data.go.kr/1230000/ad/BidPublicInfoService
```
(data.go.kr 개발계정 기준 실제 End Point — 운영계정 전환 시 URL이 변경될 수 있음)

**요청 파라미터:**

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `serviceKey` | API 인증키 (URL 인코딩) | `G2B_API_KEY` 환경변수에서 주입 |
| `pageNo` | 페이지 번호 | `1` |
| `numOfRows` | 페이지당 결과 수 | `100` |
| `type` | 응답 형식 | `json` |
| `inqryBgnDt` | 조회 시작일시 (yyyyMMddHHmm) | `202603240000` |
| `inqryEndDt` | 조회 종료일시 (yyyyMMddHHmm) | `202603242359` |

**응답 구조 (JSON):**
```json
{
  "response": {
    "header": {"resultCode": "00", "resultMsg": "OK"},
    "body": {
      "totalCount": 150,
      "pageNo": 1,
      "numOfRows": 100,
      "items": {
        "item": [
          {
            "bidNtceNo": "20260324001",
            "bidNtceNm": "소프트웨어 유지보수 용역",
            "ntceInsttNm": "행정안전부",
            "bidMethdNm": "일반경쟁",
            "bidClseDt": "20260407180000",
            "bidNtceDt": "20260324100000"
          }
        ]
      }
    }
  }
}
```

**페이지네이션:** `totalCount`가 `numOfRows`보다 크면 `pageNo`를 증가시켜 전체 결과를 가져옴

**단일 건 응답 주의:** API는 결과가 1건일 때 `items.item`을 배열이 아닌 객체로 반환하는 경우가 있음. 구현 시 `isinstance(items, list)` 체크 후 단일 객체이면 리스트로 감싸서 처리

**`bidClseDt` 파싱:** `"20260407180000"` (yyyyMMddHHmmss) 형식 → `datetime.strptime(val, "%Y%m%d%H%M%S").date()` 로 파싱 후 `YYYY-MM-DD` 문자열로 저장

**`bidClseDt` null/빈값 처리:** 마감일 미지정 공고의 경우 `bidClseDt`가 비어 있을 수 있음 → `deadline`을 `"9999-12-31"`로 저장하여 만료 처리 제외 (영구 추적)

**공고 상세 URL 구성:**
```
https://www.g2b.go.kr/pt/menu/selectSubFrame.do?bidNtceNo={bidNtceNo}
```

---

### GitHub Issue (중복 방지 DB)

- **라벨:** `seen-bids`
- 저장소 내 `seen-bids` 라벨이 붙은 open 상태의 Issue 1개를 고정으로 사용
- Issue 본문(body)에 JSON 형식으로 공고 추적 목록 저장

**Issue 조회 방법:**
```
GET /repos/{owner}/{repo}/issues?labels=seen-bids&state=open
```
- 결과가 없으면(첫 실행 또는 실수로 삭제된 경우) 자동으로 새 Issue 생성
- 결과가 있으면 첫 번째 Issue를 사용
- **주의:** `seen-bids` 라벨 Issue가 2개 이상 존재하면 첫 번째만 사용되고 나머지는 무시됨 → 수동으로 중복 Issue를 닫아야 함

**본문 형식:**
```json
{
  "seen": [
    {"id": "20260324001", "deadline": "2026-04-07"},
    {"id": "20260324002", "deadline": "2026-04-14"}
  ]
}
```

- `id`: API 응답의 `bidNtceNo` 값 그대로 저장
- `deadline`: `bidClseDt`를 파싱한 `YYYY-MM-DD` 형식

**정리 조건:** `deadline < 오늘 날짜`인 항목은 실행 시 자동 제거 (오늘 마감 공고는 유지)

**Issue 업데이트:**
```
PATCH /repos/{owner}/{repo}/issues/{issue_number}
Body: {"body": "<updated JSON>"}
```

**인증:** GitHub Actions 내장 `GITHUB_TOKEN` 사용 (`secrets.GITHUB_TOKEN` — 별도 PAT 발급 불필요)

---

### GitHub Actions 워크플로우

```yaml
name: 나라장터 입찰공고 알림

on:
  schedule:
    - cron: '0 1 * * *'   # UTC 01:00 = KST 10:00 (한국은 UTC+9, DST 없음)
  workflow_dispatch:        # 수동 실행 (테스트용)

jobs:
  check-bids:
    runs-on: ubuntu-latest
    permissions:
      issues: write         # GITHUB_TOKEN에 Issues 쓰기 권한 부여
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests
      - run: python checker.py
        env:
          G2B_API_KEY: ${{ secrets.G2B_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}   # GitHub Actions 기본 제공 변수이나 명시적 주입으로 로컬 테스트 시 override 가능
```

---

### GitHub Secrets

| Secret 이름 | 설명 |
|-------------|------|
| `G2B_API_KEY` | 나라장터 Open API 인증키 (data.go.kr에서 발급) |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

`GITHUB_TOKEN`은 GitHub Actions에서 자동 제공 — 별도 발급 불필요

---

### 오류 처리 정책

| 상황 | 처리 방법 |
|------|-----------|
| `keywords.txt` 없음 또는 비어있음 | 오류 메시지 출력 후 exit(1) — Actions 실패로 표시 |
| `G2B_API_KEY` 미설정 | 오류 메시지 출력 후 exit(1) |
| `SLACK_WEBHOOK_URL` 미설정 | 오류 메시지 출력 후 exit(1) |
| API 호출 실패 (비200 응답) | 오류 메시지 출력 후 exit(1) — 다음 날 재시도 |
| Slack 전송 실패 | 오류 메시지 출력 후 exit(1) — Issue 업데이트 하지 않아 다음 날 재전송 시도 |
| GitHub Issue 업데이트 실패 | 오류 메시지 출력 후 exit(1) — Slack은 이미 전송됐으므로 다음 날 중복 가능성 있지만 허용 |
| API 결과 0건 | 정상 종료 (알림 없음) |
| 키워드 매칭 0건 | 정상 종료 (알림 없음) |

---

### Slack 알림 포맷

매칭된 공고가 있을 때만 전송. 없으면 전송하지 않음.

```
🔔 나라장터 입찰공고 알림 [2026-03-24]

📌 소프트웨어 유지보수 용역 (행정안전부)
   • 공고번호: 20260324001
   • 입찰방식: 일반경쟁
   • 마감일: 2026-04-07
   • 매칭 키워드: 소프트웨어, 유지보수
   • 🔗 공고 바로가기

📌 시스템 구축 사업 (국토교통부)
   • 공고번호: 20260324002
   • 입찰방식: 제한경쟁
   • 마감일: 2026-04-14
   • 매칭 키워드: 시스템 구축
   • 🔗 공고 바로가기

총 2건 새 공고 매칭
```

- AND 조건이므로 매칭 시 `keywords.txt`의 모든 키워드가 매칭된 것 — 별도 키워드 표시 없이 공고 정보만 표시
- `공고 바로가기` 링크: `https://www.g2b.go.kr/pt/menu/selectSubFrame.do?bidNtceNo={bidNtceNo}`
- **메시지 분할:** 매칭 공고가 20건을 초과할 경우 20건씩 분할하여 여러 메시지로 전송

---

## 초기 설정 절차

1. **GitHub 저장소 생성** — public 또는 private (public은 Actions 무제한 무료, private은 월 2,000분 무료)
2. **나라장터 Open API 키 발급** — data.go.kr 회원가입 → "나라장터 입찰공고정보 서비스" 신청 (활용목적: 기타)
3. **Slack Incoming Webhook URL 발급** — Slack 채널 설정에서 Incoming Webhook 추가
4. **GitHub Secrets 등록** — 저장소 Settings → Secrets and variables → Actions → `G2B_API_KEY`, `SLACK_WEBHOOK_URL` 등록
5. **`seen-bids` 라벨 생성** — 저장소 Issues → Labels → New label → 이름: `seen-bids`
6. **`keywords.txt` 작성** — 원하는 키워드 입력 후 커밋
7. **수동 실행 테스트** — GitHub Actions → check_bids.yml → Run workflow

---

## 제약 및 한계

- **GitHub Actions 무료 플랜:** public 저장소 무제한, private 저장소 월 2,000분 제공 (일 1회 실행 시 충분)
- **나라장터 Open API:** 일 트래픽 제한 있음 (개인 사용에는 충분)
- **키워드 변경:** GitHub 웹사이트에서 `keywords.txt` 직접 수정 필요
- **실행 시간 약간의 지연 가능:** GitHub Actions 스케줄은 부하 시 최대 몇 분 지연될 수 있음
