# 나라장터 Slack Slash Command + 결과 10건 제한 — 설계 문서

**날짜:** 2026-03-24
**상태:** 승인됨

---

## 개요

기존 스케줄 알림(매일 10시)에 더해, Slack slash command `/나라장터 [키워드]`로 언제든 원하는 키워드로 나라장터 입찰공고를 즉시 검색할 수 있도록 한다. 결과는 최신순 상위 10건만 표시하고, 초과 시 나라장터 전체 보기 링크를 제공한다.

---

## 요구사항

- `/나라장터 소프트웨어 유지보수` 입력 → 해당 키워드로 나라장터 검색 → Slack으로 결과 전송
- 키워드 AND 조건: 스페이스로 구분된 키워드가 모두 공고명에 포함되어야 매칭
- 검색 결과는 공고일시(`bidNtceDt`) 기준 최신순 정렬, 최대 10건 표시
- 10건 초과 시 하단에 나라장터 전체 보기 링크 표시
- 스케줄 실행(매일 10시)은 기존대로 `keywords.txt` 키워드 사용
- 신규 외부 서비스: Cloudflare Worker 1개 (무료, 관리 최소화)

---

## 아키텍처

```
[Slack] /나라장터 소프트웨어 유지보수
        ↓
[Cloudflare Worker]
 - Slack Signing Secret 검증 (HMAC-SHA256)
 - "🔍 검색 중..." 즉시 응답 (3초 제한 충족)
 - GitHub API → workflow_dispatch 트리거 (keywords 파라미터 전달)
        ↓
[GitHub Actions: check_bids.yml]
 - SEARCH_KEYWORDS 환경변수 있으면 → 수동 모드
 - 없으면 (스케줄 실행) → 스케줄 모드
        ↓
[checker.py]
 - 수동 모드: SEARCH_KEYWORDS 파싱, seen 목록 읽기/쓰기 생략
 - 스케줄 모드: keywords.txt 사용, seen 목록 관리
 - G2B API 호출 → 키워드 매칭 → bidNtceDt 최신순 정렬 → 상위 10건
        ↓
[slack_notifier.py]
 - 헤더: 수동=🔍, 스케줄=🔔
 - 10건 표시, 초과분 있으면 "나라장터에서 전체 보기" 링크
 - 0건이면 "매칭된 공고가 없습니다" 전송 (수동 모드만)
```

---

## 구성 요소별 상세 설계

### 1. Cloudflare Worker (`cloudflare-worker/worker.js`)

**처리 흐름:**
1. Slack POST 수신 (`application/x-www-form-urlencoded`)
2. `X-Slack-Signature` 헤더로 HMAC-SHA256 검증
3. `text` 필드에서 키워드 추출 후 공백 제거
4. 키워드 없으면 즉시 반환: `"❌ 키워드를 입력해주세요. 예: /검색 소프트웨어 유지보수"`
5. 즉시 응답 (HTTP 200): `"🔍 검색 중... 잠시 후 결과를 전송합니다."`
6. `waitUntil`로 비동기 GitHub API 호출:
   ```
   POST https://api.github.com/repos/sunwoo0506/nara/actions/workflows/check_bids.yml/dispatches
   Headers: Authorization: Bearer {GH_PAT}
   Body: { "ref": "master", "inputs": { "keywords": "소프트웨어 유지보수" } }
   ```
7. GitHub API 실패 시: Worker 로그에만 기록, Slack에 별도 알림 없음

**환경변수 (Cloudflare Worker Secrets):**

| 변수명 | 설명 |
|--------|------|
| `SLACK_SIGNING_SECRET` | Slack App → Basic Information → Signing Secret |
| `GH_PAT` | GitHub Fine-grained PAT (저장소 Actions: write 권한) |

---

### 2. GitHub Actions (`check_bids.yml`) 변경

```yaml
on:
  schedule:
    - cron: '0 1 * * *'
  workflow_dispatch:
    inputs:
      keywords:
        description: '검색 키워드 (스페이스 구분, AND 조건)'
        required: false
        default: ''

jobs:
  check-bids:
    ...
    steps:
      ...
      - name: Run checker
        run: python checker.py
        env:
          G2B_API_KEY: ${{ secrets.G2B_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          SEARCH_KEYWORDS: ${{ github.event.inputs.keywords }}
```

스케줄 실행 시 `SEARCH_KEYWORDS`는 빈 문자열 → checker.py가 스케줄 모드로 동작.

---

### 3. `checker.py` 변경

**수동/스케줄 분기:**
```python
search_keywords_env = os.environ.get("SEARCH_KEYWORDS", "").strip()
if search_keywords_env:
    keywords = [k for k in search_keywords_env.split() if k]
    if not keywords:
        # 공백만 있는 경우 (Worker에서 걸러지지만 방어 처리)
        print("[ERROR] 키워드가 없습니다.", flush=True)
        sys.exit(1)
    triggered_by = "manual"
else:
    keywords = load_keywords(keywords_path)
    triggered_by = "scheduled"
```

**수동 모드 흐름:**
```python
if triggered_by == "manual":
    # seen 목록 읽기/쓰기 없음 — 매번 전체 결과 반환
    matched = [b for b in bids if matches_all_keywords(b.get("bidNtceNm", ""), keywords)]
    matched.sort(key=lambda b: b.get("bidNtceDt", ""), reverse=True)
    display_bids = matched[:10]
    total_matched = len(matched)
    for b in display_bids:
        b["deadline"] = parse_deadline(b.get("bidClseDt", ""))
    send_slack_notification(slack_url, display_bids, today_display,
                            triggered_by="manual", total_matched=total_matched)
    return
```

**스케줄 모드 흐름 (기존 로직 유지):**
```python
# 기존: matched → seen 필터 → new_bids
matched = [b for b in bids if matches_all_keywords(b.get("bidNtceNm", ""), keywords)]
issue_number, seen = get_seen_list(gh_repo, gh_token)
seen = _purge_expired(seen, today)
seen_ids = {s["id"] for s in seen}
new_bids = [b for b in matched if b["bidNtceNo"] not in seen_ids]

# 최신순 정렬 → 상위 10건
new_bids.sort(key=lambda b: b.get("bidNtceDt", ""), reverse=True)
display_bids = new_bids[:10]
total_matched = len(new_bids)

if not new_bids:
    print(f"[INFO] 새 매칭 공고 없음", flush=True)
    update_seen_list(gh_repo, gh_token, issue_number, seen)
    return

for b in display_bids:
    b["deadline"] = parse_deadline(b.get("bidClseDt", ""))

send_slack_notification(slack_url, display_bids, today_display,
                        triggered_by="scheduled", total_matched=total_matched)

# seen 목록: display_bids가 아닌 new_bids 전체를 등록 (10건 초과분도 중복 방지)
for b in new_bids:
    seen.append({"id": b["bidNtceNo"], "deadline": parse_deadline(b.get("bidClseDt", ""))})
update_seen_list(gh_repo, gh_token, issue_number, seen)
```

> **seen 목록 등록 범위:** 표시된 10건뿐 아니라 매칭된 `new_bids` 전체를 seen에 등록한다. 그렇지 않으면 11번째 이후 공고가 다음 날도 "새 공고"로 반복 알림된다.

---

### 4. `slack_notifier.py` 변경

**시그니처:**
```python
def send_slack_notification(
    webhook_url: str,
    bids: list[dict],
    today_str: str,
    triggered_by: str = "scheduled",
    total_matched: int = 0
) -> None:
```

**메시지 구성:**
```python
DISPLAY_LIMIT = 10
G2B_HOME = "https://www.g2b.go.kr"

header = "🔔 나라장터 입찰공고 알림" if triggered_by == "scheduled" else "🔍 나라장터 검색 결과"
header += f" [{today_str}]"

if not bids:
    # 수동 모드 0건 처리 (스케줄은 checker.py에서 early return으로 여기 미도달)
    text = f"{header}\n\n매칭된 공고가 없습니다."
else:
    bid_texts = "\n\n".join(format_bid(b) for b in bids)  # bids는 이미 최대 10건
    if total_matched > DISPLAY_LIMIT:
        footer = f"📋 총 {total_matched}건 매칭 (상위 {DISPLAY_LIMIT}건 표시) · <{G2B_HOME}|나라장터에서 전체 보기>"
    else:
        footer = f"총 {total_matched}건 매칭"
    text = f"{header}\n\n{bid_texts}\n\n{footer}"

resp = requests.post(webhook_url, json={"text": text}, timeout=10)
if resp.status_code != 200:
    print(f"[ERROR] Slack 전송 실패: HTTP {resp.status_code}", flush=True)
    sys.exit(1)
```

- 기존 20건 배치 분할 로직(`BATCH_SIZE`, `for i in range(0, total, BATCH_SIZE)`) 제거
- 슬라이싱은 checker.py에서 완료 후 전달받으므로 notifier는 단순 포맷/전송만 담당

---

## 신규 Secrets / 환경변수

| 위치 | 이름 | 설명 |
|------|------|------|
| GitHub Secrets | 기존 유지 | G2B_API_KEY, SLACK_WEBHOOK_URL, GITHUB_TOKEN |
| Cloudflare Worker Secrets | `SLACK_SIGNING_SECRET` | Slack App Signing Secret |
| Cloudflare Worker Secrets | `GH_PAT` | GitHub Fine-grained PAT (Actions: write) |

---

## 초기 설정 절차

1. **GitHub Fine-grained PAT 발급** — Settings → Developer settings → Fine-grained tokens → `sunwoo0506/nara`, 권한: Actions (write)
2. **Cloudflare Worker 배포** — 대시보드에서 `worker.js` 붙여넣기 → Secrets 2개 등록 → Worker URL 확인
3. **Slack App slash command 등록** — Slack App → Slash Commands → `/나라장터` → Request URL에 Worker URL 입력
4. **테스트** — Slack DM에서 `/검색 소프트웨어` 입력 → "검색 중..." 확인 → 결과 수신 확인

---

## 오류 처리

| 상황 | 처리 |
|------|------|
| `/나라장터` 키워드 없음 | Worker가 Slack에 즉시 안내 메시지 반환 |
| GitHub API 호출 실패 | Worker 로그에 기록, Slack에 알림 없음 |
| G2B API 오류 | exit(1) → Actions 실패로 표시 |
| 수동 검색 매칭 0건 | "매칭된 공고가 없습니다" Slack 전송 |
| 스케줄 실행 매칭 0건 | 기존대로 early return (Slack 전송 없음) |
| 키워드 공백만 입력 | Worker에서 차단, checker.py에서도 exit(1) 방어 처리 |

---

## 변경 파일 요약

| 파일 | 변경 종류 | 주요 내용 |
|------|-----------|-----------|
| `cloudflare-worker/worker.js` | 신규 | Slack 검증, 즉시 응답, workflow_dispatch 트리거 |
| `.github/workflows/check_bids.yml` | 수정 | workflow_dispatch inputs, SEARCH_KEYWORDS 주입 |
| `checker.py` | 수정 | 수동/스케줄 분기, 정렬, 10건 제한, seen 목록 분기 |
| `slack_notifier.py` | 수정 | 시그니처 변경, 헤더 분기, 배치 로직 제거, 0건 처리 |
