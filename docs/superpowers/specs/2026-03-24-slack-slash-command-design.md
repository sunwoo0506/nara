# 나라장터 Slack Slash Command + 결과 10건 제한 — 설계 문서

**날짜:** 2026-03-24
**상태:** 승인됨

---

## 개요

기존 스케줄 알림(매일 10시)에 더해, Slack slash command `/검색 [키워드]`로 언제든 원하는 키워드로 나라장터 입찰공고를 즉시 검색할 수 있도록 한다. 결과는 최신순 상위 10건만 표시하고, 초과 시 나라장터 전체 보기 링크를 제공한다.

---

## 요구사항

- `/검색 소프트웨어 유지보수` 입력 → 해당 키워드로 나라장터 검색 → Slack으로 결과 전송
- 키워드 AND 조건: 스페이스로 구분된 키워드가 모두 공고명에 포함되어야 매칭
- 검색 결과는 공고일시(`bidNtceDt`) 기준 최신순 정렬, 최대 10건 표시
- 10건 초과 시 하단에 나라장터 전체 보기 링크 표시
- 스케줄 실행(매일 10시)은 기존대로 `keywords.txt` 키워드 사용
- 신규 외부 서비스: Cloudflare Worker 1개 (무료, 관리 최소화)

---

## 아키텍처

```
[Slack] /검색 소프트웨어 유지보수
        ↓
[Cloudflare Worker]
 - Slack Signing Secret 검증
 - "🔍 검색 중..." 즉시 응답 (3초 제한 충족)
 - GitHub API → workflow_dispatch 트리거 (keywords 파라미터 전달)
        ↓
[GitHub Actions: check_bids.yml]
 - SEARCH_KEYWORDS 환경변수 있으면 → 해당 키워드 사용
 - 없으면 (스케줄 실행) → keywords.txt 사용
        ↓
[checker.py → g2b_api.py]
 - G2B API 호출 및 키워드 매칭
 - 결과 bidNtceDt 기준 최신순 정렬 → 상위 10건 추출
        ↓
[slack_notifier.py]
 - 10건 표시
 - 초과분 있으면 "나라장터에서 전체 보기" 링크 추가
 - 결과를 기존 SLACK_WEBHOOK_URL로 전송
```

---

## 구성 요소별 상세 설계

### 1. Cloudflare Worker (`cloudflare-worker/worker.js`)

**역할:** Slack slash command 수신 → GitHub Actions 트리거

**처리 흐름:**
1. Slack이 POST 전송 (`application/x-www-form-urlencoded`)
2. `X-Slack-Signature` 헤더로 Slack Signing Secret 검증 (HMAC-SHA256)
3. `text` 필드에서 키워드 추출
4. 키워드 없으면 `"❌ 키워드를 입력해주세요. 예: /검색 소프트웨어 유지보수"` 반환
5. 즉시 `"🔍 검색 중... 잠시 후 결과를 전송합니다."` 응답 (HTTP 200)
6. `waitUntil`로 비동기 GitHub API 호출:
   ```
   POST https://api.github.com/repos/sunwoo0506/nara/actions/workflows/check_bids.yml/dispatches
   Body: { "ref": "master", "inputs": { "keywords": "소프트웨어 유지보수" } }
   ```

**환경변수 (Cloudflare Worker Secrets):**

| 변수명 | 설명 |
|--------|------|
| `SLACK_SIGNING_SECRET` | Slack App 설정 페이지 → Basic Information → Signing Secret |
| `GH_PAT` | GitHub Fine-grained PAT (저장소 Actions: write 권한) |

---

### 2. GitHub Actions (`check_bids.yml`) 변경

**추가 트리거:**
```yaml
workflow_dispatch:
  inputs:
    keywords:
      description: '검색 키워드 (스페이스 구분, AND 조건)'
      required: false
      default: ''
```

**환경변수 주입 추가:**
```yaml
env:
  SEARCH_KEYWORDS: ${{ github.event.inputs.keywords }}
```

기존 스케줄 실행 시 `SEARCH_KEYWORDS`는 빈 문자열 → checker.py가 keywords.txt 사용.

---

### 3. `checker.py` 변경

**키워드 소스 분기:**
```python
search_keywords_env = os.environ.get("SEARCH_KEYWORDS", "").strip()
if search_keywords_env:
    keywords = [k for k in search_keywords_env.split() if k]
    triggered_by = "manual"
else:
    keywords = load_keywords(keywords_path)
    triggered_by = "scheduled"
```

**결과 정렬 (최신순 상위 10건):**
```python
matched.sort(key=lambda b: b.get("bidNtceDt", ""), reverse=True)
new_bids = [b for b in matched if b["bidNtceNo"] not in seen_ids][:10]
```

- `triggered_by`를 `send_slack_notification`에 전달하여 메시지 헤더 구분

**수동 실행 시 seen 목록 업데이트 안 함:**
- 수동 검색은 중복 방지 DB(`seen-bids` Issue)를 읽지도 쓰지도 않음
- 스케줄 실행만 seen 목록 관리

---

### 4. `slack_notifier.py` 변경

**메시지 헤더 구분:**
- 스케줄: `🔔 나라장터 입찰공고 알림 [YYYY-MM-DD]`
- 수동: `🔍 나라장터 검색 결과 [YYYY-MM-DD]`

**10건 제한 + 더 보기 링크:**
```python
DISPLAY_LIMIT = 10
G2B_HOME = "https://www.g2b.go.kr"

def send_slack_notification(webhook_url, bids, today_str, triggered_by="scheduled"):
    total_matched = len(bids)          # 전체 매칭 수 (10건 초과 가능)
    display_bids = bids[:DISPLAY_LIMIT]

    header = "🔔 나라장터 입찰공고 알림" if triggered_by == "scheduled" else "🔍 나라장터 검색 결과"
    header += f" [{today_str}]"

    bid_texts = "\n\n".join(format_bid(b) for b in display_bids)

    if total_matched > DISPLAY_LIMIT:
        footer = f"📋 총 {total_matched}건 매칭 (상위 {DISPLAY_LIMIT}건 표시) · <{G2B_HOME}|나라장터에서 전체 보기>"
    else:
        footer = f"총 {total_matched}건 매칭"

    text = f"{header}\n\n{bid_texts}\n\n{footer}"
    # 기존 requests.post 유지
```

- 기존 20건 배치 분할 로직 제거 (10건으로 제한하므로 불필요)

---

## 신규 GitHub Secrets / 환경변수

| 위치 | 이름 | 설명 |
|------|------|------|
| GitHub Secrets | 변경 없음 | 기존 G2B_API_KEY, SLACK_WEBHOOK_URL, GITHUB_TOKEN 유지 |
| Cloudflare Worker Secrets | `SLACK_SIGNING_SECRET` | Slack App Signing Secret |
| Cloudflare Worker Secrets | `GH_PAT` | GitHub Fine-grained PAT (Actions write) |

---

## 초기 설정 절차

1. **Slack App 설정** — Slack App → Slash Commands → `/검색` 추가 → Request URL에 Worker URL 입력
2. **GitHub Fine-grained PAT 발급** — GitHub Settings → Developer settings → Fine-grained tokens → `sunwoo0506/nara` Actions: write
3. **Cloudflare Worker 배포** — Cloudflare 대시보드에서 `worker.js` 붙여넣기 → Secrets 2개 등록
4. **Slack App에 Worker URL 등록** — `/검색` slash command Request URL 업데이트
5. **테스트** — Slack DM에서 `/검색 소프트웨어` 입력

---

## 오류 처리

| 상황 | 처리 |
|------|------|
| `/검색` 키워드 없음 | Worker가 Slack에 즉시 안내 메시지 반환 |
| GitHub API 호출 실패 | Worker 로그에 기록 (Slack에는 영향 없음, 재시도 없음) |
| G2B API 오류 | 기존대로 exit(1) → Actions 실패로 표시 |
| 매칭 결과 0건 | "매칭된 공고가 없습니다" 메시지 Slack 전송 |
| 수동 실행 키워드 공백 토큰 | split()으로 처리되어 자동 제거 |

---

## 변경 파일 요약

| 파일 | 변경 종류 |
|------|-----------|
| `cloudflare-worker/worker.js` | 신규 |
| `.github/workflows/check_bids.yml` | workflow_dispatch 입력 추가, SEARCH_KEYWORDS 주입 |
| `checker.py` | 키워드 소스 분기, 결과 정렬·10건 제한, triggered_by 전달 |
| `slack_notifier.py` | 헤더 구분, 10건 제한, 더 보기 링크, 배치 로직 제거 |
