# 나라장터 입찰공고 Slack 알림 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 나라장터 Open API에서 매일 입찰공고를 조회해 키워드 AND 매칭 공고를 Slack으로 알림 전송하는 GitHub Actions 기반 자동화 시스템을 구축한다.

**Architecture:** `checker.py`가 진입점으로 4개의 전용 모듈(keywords, g2b_api, github_issue, slack_notifier)을 조합해 실행한다. GitHub Actions가 매일 UTC 01:00(KST 10:00)에 트리거하고, GitHub Issue를 중복 방지 DB로 사용한다.

**Tech Stack:** Python 3.11, requests, pytest, unittest.mock, GitHub Actions

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `checker.py` | 메인 진입점 — 모듈 조합 및 실행 흐름 |
| `keywords.py` | keywords.txt 로드 및 AND 조건 매칭 |
| `g2b_api.py` | 나라장터 Open API 호출 및 페이지네이션 |
| `github_issue.py` | GitHub Issue 기반 seen 목록 읽기/쓰기 |
| `slack_notifier.py` | Slack Incoming Webhook 메시지 전송 |
| `keywords.txt` | 키워드 목록 (사용자 편집) |
| `.github/workflows/check_bids.yml` | GitHub Actions 스케줄 워크플로우 |
| `tests/test_keywords.py` | keywords 모듈 테스트 |
| `tests/test_g2b_api.py` | g2b_api 모듈 테스트 |
| `tests/test_github_issue.py` | github_issue 모듈 테스트 |
| `tests/test_slack_notifier.py` | slack_notifier 모듈 테스트 |
| `tests/test_checker.py` | checker 통합 테스트 |

---

## Task 1: 프로젝트 초기 구조 생성

**Files:**
- Create: `keywords.txt`
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: keywords.txt 생성**

```
# 알림 받고 싶은 키워드를 한 줄에 하나씩 입력하세요
# #으로 시작하는 줄은 주석으로 무시됩니다
제주
AI
```

- [ ] **Step 2: requirements.txt 생성**

```
requests==2.31.0
pytest==8.1.0
```

- [ ] **Step 3: tests 디렉토리 초기화**

```bash
mkdir tests
touch tests/__init__.py
```

- [ ] **Step 4: 커밋**

```bash
git init
git add keywords.txt requirements.txt tests/__init__.py
git commit -m "chore: init project structure"
```

---

## Task 2: keywords 모듈

**Files:**
- Create: `keywords.py`
- Create: `tests/test_keywords.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_keywords.py`:
```python
import os
import tempfile
import pytest
from keywords import load_keywords, matches_all_keywords


def write_keywords_file(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


def test_load_keywords_basic():
    path = write_keywords_file("제주\nAI\n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_skips_comments_and_blank():
    path = write_keywords_file("# 주석\n제주\n\nAI\n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_strips_whitespace():
    path = write_keywords_file("  제주  \n  AI  \n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_raises_if_file_missing():
    with pytest.raises(SystemExit):
        load_keywords("/nonexistent/keywords.txt")


def test_load_keywords_raises_if_empty():
    path = write_keywords_file("# 주석만 있음\n\n")
    try:
        with pytest.raises(SystemExit):
            load_keywords(path)
    finally:
        os.unlink(path)


def test_matches_all_keywords_true():
    assert matches_all_keywords("제주 AI 시스템 구축", ["제주", "AI"]) is True


def test_matches_all_keywords_false_missing_one():
    assert matches_all_keywords("AI 시스템 구축", ["제주", "AI"]) is False


def test_matches_all_keywords_case_insensitive():
    assert matches_all_keywords("제주 ai 시스템", ["제주", "AI"]) is True


def test_matches_all_keywords_single_keyword():
    assert matches_all_keywords("소프트웨어 유지보수", ["소프트웨어"]) is True
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_keywords.py -v
```
Expected: `ModuleNotFoundError: No module named 'keywords'`

- [ ] **Step 3: keywords.py 구현**

`keywords.py`:
```python
import sys


def load_keywords(path: str) -> list[str]:
    """keywords.txt에서 유효 키워드 목록을 반환. 없거나 비어있으면 exit(1)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[ERROR] keywords 파일을 찾을 수 없습니다: {path}", flush=True)
        sys.exit(1)

    keywords = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

    if not keywords:
        print("[ERROR] keywords.txt에 유효한 키워드가 없습니다.", flush=True)
        sys.exit(1)

    return keywords


def matches_all_keywords(title: str, keywords: list[str]) -> bool:
    """공고명에 모든 키워드가 포함되면 True (대소문자 무시)."""
    title_lower = title.lower()
    return all(kw.lower() in title_lower for kw in keywords)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_keywords.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add keywords.py tests/test_keywords.py
git commit -m "feat: add keywords loader and AND matcher"
```

---

## Task 3: g2b_api 모듈

**Files:**
- Create: `g2b_api.py`
- Create: `tests/test_g2b_api.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_g2b_api.py`:
```python
from unittest.mock import patch, MagicMock
from datetime import date
import pytest
from g2b_api import fetch_bids, parse_deadline, G2B_ENDPOINT


def make_item(bid_no="20260324001", name="제주 AI 시스템", deadline="20260407180000"):
    return {
        "bidNtceNo": bid_no,
        "bidNtceNm": name,
        "ntceInsttNm": "행정안전부",
        "bidMethdNm": "일반경쟁",
        "bidClseDt": deadline,
    }


def make_api_response(items, total_count=None):
    if isinstance(items, list):
        item_data = items
    else:
        item_data = items
    count = total_count if total_count is not None else (len(items) if isinstance(items, list) else 1)
    return {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "totalCount": count,
                "pageNo": 1,
                "numOfRows": 100,
                "items": {"item": item_data},
            },
        }
    }


def test_fetch_bids_returns_list():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = make_api_response([make_item()])

    with patch("g2b_api.requests.get", return_value=mock_resp):
        bids = fetch_bids("FAKE_KEY", "20260324")

    assert isinstance(bids, list)
    assert len(bids) == 1
    assert bids[0]["bidNtceNo"] == "20260324001"


def test_fetch_bids_single_item_as_dict():
    """API가 단일 건일 때 item을 dict로 반환하는 케이스."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = make_api_response(make_item(), total_count=1)

    with patch("g2b_api.requests.get", return_value=mock_resp):
        bids = fetch_bids("FAKE_KEY", "20260324")

    assert len(bids) == 1


def test_fetch_bids_pagination():
    """totalCount > numOfRows 이면 두 번 호출."""
    page1 = make_api_response([make_item("001")], total_count=101)
    page2 = make_api_response([make_item("002")], total_count=101)

    mock_resp1 = MagicMock(status_code=200)
    mock_resp1.json.return_value = page1
    mock_resp2 = MagicMock(status_code=200)
    mock_resp2.json.return_value = page2

    with patch("g2b_api.requests.get", side_effect=[mock_resp1, mock_resp2]):
        bids = fetch_bids("FAKE_KEY", "20260324")

    assert len(bids) == 2


def test_fetch_bids_raises_on_api_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("g2b_api.requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            fetch_bids("FAKE_KEY", "20260324")


def test_fetch_bids_empty_result():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": {
            "header": {"resultCode": "00"},
            "body": {"totalCount": 0, "pageNo": 1, "numOfRows": 100, "items": ""},
        }
    }

    with patch("g2b_api.requests.get", return_value=mock_resp):
        bids = fetch_bids("FAKE_KEY", "20260324")

    assert bids == []


def test_parse_deadline_normal():
    assert parse_deadline("20260407180000") == "2026-04-07"


def test_parse_deadline_empty():
    assert parse_deadline("") == "9999-12-31"


def test_parse_deadline_none():
    assert parse_deadline(None) == "9999-12-31"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_g2b_api.py -v
```
Expected: `ModuleNotFoundError: No module named 'g2b_api'`

- [ ] **Step 3: g2b_api.py 구현**

`g2b_api.py`:
```python
import sys
from datetime import datetime
import requests

G2B_ENDPOINT = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"


def parse_deadline(value: str | None) -> str:
    """bidClseDt(yyyyMMddHHmmss)를 YYYY-MM-DD 문자열로 변환. 빈값이면 '9999-12-31'."""
    if not value:
        return "9999-12-31"
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")
    except ValueError:
        return "9999-12-31"


def _extract_items(body: dict) -> list:
    """응답 body에서 item 목록 추출. 단일 dict이면 리스트로 감쌈."""
    items_field = body.get("items")
    if not items_field or items_field == "":
        return []
    item = items_field.get("item", [])
    if isinstance(item, dict):
        return [item]
    return item if item else []


def fetch_bids(api_key: str, date_str: str) -> list[dict]:
    """당일 입찰공고 전체를 페이지네이션하여 반환. date_str: 'YYYYMMDD'"""
    all_bids = []
    page = 1
    num_of_rows = 100

    begin_dt = date_str + "0000"
    end_dt = date_str + "2359"

    while True:
        params = {
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": num_of_rows,
            "type": "json",
            "inqryBgnDt": begin_dt,
            "inqryEndDt": end_dt,
        }

        resp = requests.get(G2B_ENDPOINT, params=params, timeout=30)

        if resp.status_code != 200:
            print(f"[ERROR] 나라장터 API 호출 실패: HTTP {resp.status_code}", flush=True)
            sys.exit(1)

        body = resp.json()["response"]["body"]
        total_count = int(body.get("totalCount", 0))
        items = _extract_items(body)
        all_bids.extend(items)

        if page * num_of_rows >= total_count:
            break
        page += 1

    return all_bids
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_g2b_api.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add g2b_api.py tests/test_g2b_api.py
git commit -m "feat: add G2B API client with pagination"
```

---

## Task 4: github_issue 모듈

**Files:**
- Create: `github_issue.py`
- Create: `tests/test_github_issue.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_github_issue.py`:
```python
import json
from unittest.mock import patch, MagicMock
from datetime import date
import pytest
from github_issue import get_seen_list, update_seen_list, _purge_expired


REPO = "myuser/myrepo"
TOKEN = "ghp_fake"


def make_issue_response(body_json: dict, issue_number=1):
    return {"number": issue_number, "body": json.dumps(body_json)}


def test_get_seen_list_existing_issue():
    data = {"seen": [{"id": "001", "deadline": "2099-12-31"}]}
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [make_issue_response(data)]

    with patch("github_issue.requests.get", return_value=mock_resp):
        issue_number, seen = get_seen_list(REPO, TOKEN)

    assert issue_number == 1
    assert seen == [{"id": "001", "deadline": "2099-12-31"}]


def test_get_seen_list_creates_new_issue_when_none():
    list_resp = MagicMock(status_code=200)
    list_resp.json.return_value = []

    create_resp = MagicMock(status_code=201)
    create_resp.json.return_value = {"number": 5, "body": '{"seen": []}'}

    with patch("github_issue.requests.get", return_value=list_resp), \
         patch("github_issue.requests.post", return_value=create_resp):
        issue_number, seen = get_seen_list(REPO, TOKEN)

    assert issue_number == 5
    assert seen == []


def test_get_seen_list_raises_on_api_error():
    mock_resp = MagicMock(status_code=403)
    with patch("github_issue.requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            get_seen_list(REPO, TOKEN)


def test_update_seen_list_success():
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {}

    with patch("github_issue.requests.patch", return_value=mock_resp):
        update_seen_list(REPO, TOKEN, 1, [{"id": "001", "deadline": "2099-12-31"}])


def test_update_seen_list_raises_on_failure():
    mock_resp = MagicMock(status_code=500)
    with patch("github_issue.requests.patch", return_value=mock_resp):
        with pytest.raises(SystemExit):
            update_seen_list(REPO, TOKEN, 1, [])


def test_purge_expired_removes_past():
    today = date(2026, 3, 24)
    seen = [
        {"id": "001", "deadline": "2026-03-23"},  # 어제 → 제거
        {"id": "002", "deadline": "2026-03-24"},  # 오늘 → 유지
        {"id": "003", "deadline": "2026-04-01"},  # 미래 → 유지
    ]
    result = _purge_expired(seen, today)
    assert [s["id"] for s in result] == ["002", "003"]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_github_issue.py -v
```
Expected: `ModuleNotFoundError: No module named 'github_issue'`

- [ ] **Step 3: github_issue.py 구현**

`github_issue.py`:
```python
import json
import sys
from datetime import date
import requests

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _purge_expired(seen: list[dict], today: date) -> list[dict]:
    """마감일이 오늘보다 이전인 항목 제거."""
    return [s for s in seen if s["deadline"] >= today.isoformat()]


def get_seen_list(repo: str, token: str) -> tuple[int, list[dict]]:
    """seen-bids 라벨 Issue에서 seen 목록 반환. 없으면 새 Issue 생성."""
    url = f"{GITHUB_API}/repos/{repo}/issues"
    resp = requests.get(url, params={"labels": "seen-bids", "state": "open"}, headers=_headers(token))

    if resp.status_code != 200:
        print(f"[ERROR] GitHub Issues 조회 실패: HTTP {resp.status_code}", flush=True)
        sys.exit(1)

    issues = resp.json()

    if issues:
        issue = issues[0]
        try:
            seen = json.loads(issue["body"]).get("seen", [])
        except (json.JSONDecodeError, TypeError):
            seen = []
        return issue["number"], seen

    # Issue가 없으면 새로 생성
    create_resp = requests.post(
        url,
        json={"title": "나라장터 알림 seen 목록", "body": '{"seen": []}', "labels": ["seen-bids"]},
        headers=_headers(token),
    )
    if create_resp.status_code != 201:
        print(f"[ERROR] GitHub Issue 생성 실패: HTTP {create_resp.status_code}", flush=True)
        sys.exit(1)

    return create_resp.json()["number"], []


def update_seen_list(repo: str, token: str, issue_number: int, seen: list[dict]) -> None:
    """seen 목록을 GitHub Issue 본문에 저장."""
    url = f"{GITHUB_API}/repos/{repo}/issues/{issue_number}"
    body = json.dumps({"seen": seen}, ensure_ascii=False)
    resp = requests.patch(url, json={"body": body}, headers=_headers(token))

    if resp.status_code != 200:
        print(f"[ERROR] GitHub Issue 업데이트 실패: HTTP {resp.status_code}", flush=True)
        sys.exit(1)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_github_issue.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add github_issue.py tests/test_github_issue.py
git commit -m "feat: add GitHub Issue seen-list client"
```

---

## Task 5: slack_notifier 모듈

**Files:**
- Create: `slack_notifier.py`
- Create: `tests/test_slack_notifier.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_slack_notifier.py`:
```python
from unittest.mock import patch, MagicMock, call
import pytest
from slack_notifier import format_bid, send_slack_notification


def make_bid(no="20260324001", name="제주 AI 시스템 구축", org="행정안전부",
             method="일반경쟁", deadline="2026-04-07"):
    return {
        "bidNtceNo": no,
        "bidNtceNm": name,
        "ntceInsttNm": org,
        "bidMethdNm": method,
        "deadline": deadline,
    }


def test_format_bid_contains_key_fields():
    text = format_bid(make_bid())
    assert "20260324001" in text
    assert "제주 AI 시스템 구축" in text
    assert "행정안전부" in text
    assert "2026-04-07" in text
    assert "g2b.go.kr" in text


def test_send_slack_notification_single_batch():
    bids = [make_bid(str(i)) for i in range(3)]
    mock_resp = MagicMock(status_code=200)

    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification("https://hooks.slack.com/fake", bids, "2026-03-24")

    assert mock_post.call_count == 1


def test_send_slack_notification_splits_over_20():
    """21건이면 2번 전송."""
    bids = [make_bid(str(i)) for i in range(21)]
    mock_resp = MagicMock(status_code=200)

    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification("https://hooks.slack.com/fake", bids, "2026-03-24")

    assert mock_post.call_count == 2


def test_send_slack_notification_raises_on_failure():
    bids = [make_bid()]
    mock_resp = MagicMock(status_code=500)

    with patch("slack_notifier.requests.post", return_value=mock_resp):
        with pytest.raises(SystemExit):
            send_slack_notification("https://hooks.slack.com/fake", bids, "2026-03-24")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_slack_notifier.py -v
```
Expected: `ModuleNotFoundError: No module named 'slack_notifier'`

- [ ] **Step 3: slack_notifier.py 구현**

`slack_notifier.py`:
```python
import sys
import requests

BATCH_SIZE = 20
G2B_URL = "https://www.g2b.go.kr/pt/menu/selectSubFrame.do?bidNtceNo={bid_no}"


def format_bid(bid: dict) -> str:
    url = G2B_URL.format(bid_no=bid["bidNtceNo"])
    return (
        f"📌 {bid['bidNtceNm']} ({bid['ntceInsttNm']})\n"
        f"   • 공고번호: {bid['bidNtceNo']}\n"
        f"   • 입찰방식: {bid['bidMethdNm']}\n"
        f"   • 마감일: {bid['deadline']}\n"
        f"   • 🔗 <{url}|공고 바로가기>"
    )


def send_slack_notification(webhook_url: str, bids: list[dict], today_str: str) -> None:
    """매칭 공고를 Slack으로 전송. 20건 초과 시 분할 전송."""
    total = len(bids)

    for i in range(0, total, BATCH_SIZE):
        batch = bids[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        header = f"🔔 나라장터 입찰공고 알림 [{today_str}]"
        if total_batches > 1:
            header += f" ({batch_num}/{total_batches})"

        bid_texts = "\n\n".join(format_bid(b) for b in batch)
        footer = f"총 {total}건 새 공고 매칭"

        text = f"{header}\n\n{bid_texts}\n\n{footer}"

        resp = requests.post(webhook_url, json={"text": text}, timeout=10)

        if resp.status_code != 200:
            print(f"[ERROR] Slack 전송 실패: HTTP {resp.status_code}", flush=True)
            sys.exit(1)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_slack_notifier.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add slack_notifier.py tests/test_slack_notifier.py
git commit -m "feat: add Slack notifier with batch split"
```

---

## Task 6: checker.py 메인 로직

**Files:**
- Create: `checker.py`
- Create: `tests/test_checker.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_checker.py`:
```python
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import date
import pytest


def write_keywords(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


def make_bid(no, name, deadline="20260407180000"):
    return {
        "bidNtceNo": no,
        "bidNtceNm": name,
        "ntceInsttNm": "기관",
        "bidMethdNm": "일반경쟁",
        "bidClseDt": deadline,
    }


def test_run_sends_notification_for_matching_new_bids(monkeypatch):
    kw_path = write_keywords("제주\nAI\n")

    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")

    bids = [make_bid("001", "제주 AI 시스템 구축"), make_bid("002", "서울 시스템")]

    with patch("checker.fetch_bids", return_value=bids), \
         patch("checker.get_seen_list", return_value=(1, [])), \
         patch("checker.update_seen_list") as mock_update, \
         patch("checker.send_slack_notification") as mock_slack, \
         patch("checker.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)

        from checker import run
        run(keywords_path=kw_path)

    # "001"만 매칭 ("제주" AND "AI"), "002"는 미매칭
    assert mock_slack.call_count == 1
    sent_bids = mock_slack.call_args[0][1]
    assert len(sent_bids) == 1
    assert sent_bids[0]["bidNtceNo"] == "001"

    # seen 목록에 "001" 추가됨
    updated_seen = mock_update.call_args[0][3]
    assert any(s["id"] == "001" for s in updated_seen)

    os.unlink(kw_path)


def test_run_skips_already_seen_bids(monkeypatch):
    kw_path = write_keywords("제주\nAI\n")

    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")

    bids = [make_bid("001", "제주 AI 시스템")]
    existing_seen = [{"id": "001", "deadline": "2026-04-07"}]

    with patch("checker.fetch_bids", return_value=bids), \
         patch("checker.get_seen_list", return_value=(1, existing_seen)), \
         patch("checker.update_seen_list"), \
         patch("checker.send_slack_notification") as mock_slack, \
         patch("checker.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)

        from checker import run
        run(keywords_path=kw_path)

    mock_slack.assert_not_called()
    os.unlink(kw_path)


def test_run_exits_if_env_missing(monkeypatch):
    monkeypatch.delenv("G2B_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit):
        from checker import run
        run()
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_checker.py -v
```
Expected: `ModuleNotFoundError: No module named 'checker'`

- [ ] **Step 3: checker.py 구현**

`checker.py`:
```python
import os
import sys
from datetime import date

from g2b_api import fetch_bids, parse_deadline
from github_issue import get_seen_list, update_seen_list, _purge_expired
from keywords import load_keywords, matches_all_keywords
from slack_notifier import send_slack_notification


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"[ERROR] 환경변수 {name}이 설정되지 않았습니다.", flush=True)
        sys.exit(1)
    return value


def run(keywords_path: str = "keywords.txt") -> None:
    api_key = _require_env("G2B_API_KEY")
    slack_url = _require_env("SLACK_WEBHOOK_URL")
    gh_token = _require_env("GITHUB_TOKEN")
    gh_repo = _require_env("GITHUB_REPOSITORY")

    keywords = load_keywords(keywords_path)
    today = date.today()
    today_str = today.strftime("%Y%m%d")
    today_display = today.isoformat()

    # 입찰공고 조회
    bids = fetch_bids(api_key, today_str)

    # 키워드 AND 매칭
    matched = [b for b in bids if matches_all_keywords(b.get("bidNtceNm", ""), keywords)]

    # seen 목록 로드 및 만료 제거
    issue_number, seen = get_seen_list(gh_repo, gh_token)
    seen = _purge_expired(seen, today)

    seen_ids = {s["id"] for s in seen}
    new_bids = [b for b in matched if b["bidNtceNo"] not in seen_ids]

    if not new_bids:
        print(f"[INFO] 새 매칭 공고 없음 (전체 {len(bids)}건 조회, {len(matched)}건 매칭)", flush=True)
        update_seen_list(gh_repo, gh_token, issue_number, seen)
        return

    # deadline 필드 추가 (slack_notifier용)
    for b in new_bids:
        b["deadline"] = parse_deadline(b.get("bidClseDt", ""))

    # Slack 전송
    send_slack_notification(slack_url, new_bids, today_display)
    print(f"[INFO] Slack 알림 전송 완료: {len(new_bids)}건", flush=True)

    # seen 목록 업데이트
    for b in new_bids:
        seen.append({"id": b["bidNtceNo"], "deadline": b["deadline"]})

    update_seen_list(gh_repo, gh_token, issue_number, seen)


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add checker.py tests/test_checker.py
git commit -m "feat: add main checker orchestration"
```

---

## Task 7: GitHub Actions 워크플로우

**Files:**
- Create: `.github/workflows/check_bids.yml`

- [ ] **Step 1: 워크플로우 디렉토리 생성**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: check_bids.yml 작성**

`.github/workflows/check_bids.yml`:
```yaml
name: 나라장터 입찰공고 알림

on:
  schedule:
    - cron: '0 1 * * *'   # UTC 01:00 = KST 10:00 (한국 UTC+9, DST 없음)
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

      - name: 의존성 설치
        run: pip install requests

      - name: 입찰공고 확인 및 알림 전송
        run: python checker.py
        env:
          G2B_API_KEY: ${{ secrets.G2B_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}   # 로컬 테스트 시 override 가능
```

- [ ] **Step 3: README.md 작성**

`README.md`:
```markdown
# 나라장터 입찰공고 Slack 알림

나라장터(g2b.go.kr) 입찰공고 중 지정한 키워드(AND 조건)와 매칭되는 공고를 매일 오전 10시 Slack으로 알림.

## 설정

1. 저장소 Settings → Secrets → `G2B_API_KEY`, `SLACK_WEBHOOK_URL` 등록
2. Issues → Labels → `seen-bids` 라벨 생성
3. `keywords.txt` 수정 후 커밋

## 키워드 변경

`keywords.txt` 파일을 직접 수정하세요. 한 줄에 하나, `#`은 주석.
모든 키워드가 공고명에 포함된 경우에만 알림 전송됩니다.

## 수동 실행

Actions 탭 → 나라장터 입찰공고 알림 → Run workflow
```

- [ ] **Step 4: 최종 커밋**

```bash
git add .github/workflows/check_bids.yml README.md
git commit -m "feat: add GitHub Actions workflow and README"
```

---

## Task 8: GitHub 저장소에 푸시 및 최종 확인

- [ ] **Step 1: GitHub에 새 저장소 생성**

GitHub.com → New repository → 이름 지정 (예: `g2b-slack-alert`) → Create

- [ ] **Step 2: 원격 저장소 연결 및 푸시**

```bash
git remote add origin https://github.com/<YOUR_USERNAME>/g2b-slack-alert.git
git branch -M main
git push -u origin main
```

- [ ] **Step 3: GitHub Secrets 등록**

저장소 → Settings → Secrets and variables → Actions → New repository secret:
- `G2B_API_KEY`: data.go.kr에서 발급받은 인증키
- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL

- [ ] **Step 4: `seen-bids` 라벨 생성**

저장소 → Issues → Labels → New label → Name: `seen-bids` → Create label

- [ ] **Step 5: 수동 실행으로 동작 확인**

저장소 → Actions → 나라장터 입찰공고 알림 → Run workflow → Run workflow 클릭

실행 로그에서 다음 중 하나 확인:
- `[INFO] 새 매칭 공고 없음 (전체 N건 조회...)` — 정상 (매칭 없음)
- `[INFO] Slack 알림 전송 완료: N건` — 매칭 공고 있고 Slack 전송됨
- Issues 탭에서 `seen-bids` 라벨 Issue 자동 생성 확인
