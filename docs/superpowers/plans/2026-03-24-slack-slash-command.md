# Slack Slash Command + 10건 제한 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/검색 [키워드]` slash command로 나라장터를 즉시 검색하고, 스케줄/수동 모두 최신순 10건 + 나라장터 더 보기 링크로 결과를 전송한다.

**Architecture:** Cloudflare Worker가 Slack 이벤트를 받아 GitHub Actions workflow_dispatch를 트리거한다. checker.py는 `SEARCH_KEYWORDS` 환경변수 유무로 수동/스케줄 모드를 분기하며, 수동 모드는 seen 목록을 건드리지 않는다. 결과 정렬과 10건 제한은 checker.py에서, 포맷과 전송은 slack_notifier.py에서 담당한다.

**Tech Stack:** Python 3.11, requests, pytest, unittest.mock, GitHub Actions, Cloudflare Workers (JavaScript)

---

## 파일 구조

| 파일 | 변경 | 역할 |
|------|------|------|
| `slack_notifier.py` | 수정 | 시그니처 변경, 배치 로직 제거, 헤더 분기, 10건+더보기, 0건 처리 |
| `checker.py` | 수정 | 수동/스케줄 분기, bidNtceDt 정렬, 10건 슬라이싱, seen 분기 |
| `.github/workflows/check_bids.yml` | 수정 | workflow_dispatch inputs 추가, SEARCH_KEYWORDS 주입 |
| `cloudflare-worker/worker.js` | 신규 | Slack 서명 검증, 즉시 응답, GitHub API 트리거 |
| `tests/test_slack_notifier.py` | 수정 | 배치 테스트 제거, 새 시그니처·헤더·더보기·0건 테스트 추가 |
| `tests/test_checker.py` | 수정 | make_bid에 bidNtceDt 추가, 수동 모드 테스트 추가 |

---

## Task 1: slack_notifier.py — 시그니처 변경 + 10건 + 더보기

**Files:**
- Modify: `slack_notifier.py`
- Modify: `tests/test_slack_notifier.py`

- [ ] **Step 1: 기존 배치 테스트를 새 동작에 맞게 교체**

`tests/test_slack_notifier.py`를 아래 내용으로 전면 교체한다:

```python
from unittest.mock import patch, MagicMock
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


def test_send_slack_notification_single_message():
    """3건이면 POST 1회."""
    bids = [make_bid(str(i)) for i in range(3)]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification("https://hooks.slack.com/fake", bids, "2026-03-24")
    assert mock_post.call_count == 1


def test_send_slack_notification_scheduled_header():
    """스케줄 모드 헤더에 🔔 포함."""
    bids = [make_bid()]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", bids, "2026-03-24",
            triggered_by="scheduled", total_matched=1
        )
    text = mock_post.call_args[1]["json"]["text"]
    assert "🔔" in text
    assert "2026-03-24" in text


def test_send_slack_notification_manual_header():
    """수동 모드 헤더에 🔍 포함."""
    bids = [make_bid()]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", bids, "2026-03-24",
            triggered_by="manual", total_matched=1
        )
    text = mock_post.call_args[1]["json"]["text"]
    assert "🔍" in text


def test_send_slack_notification_see_more_link_when_over_10():
    """total_matched=15이면 '전체 보기' 링크 포함."""
    bids = [make_bid(str(i)) for i in range(10)]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", bids, "2026-03-24",
            triggered_by="manual", total_matched=15
        )
    text = mock_post.call_args[1]["json"]["text"]
    assert "15" in text
    assert "g2b.go.kr" in text


def test_send_slack_notification_no_see_more_when_exact():
    """total_matched=3이면 '전체 보기' 링크 없음."""
    bids = [make_bid(str(i)) for i in range(3)]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", bids, "2026-03-24",
            triggered_by="manual", total_matched=3
        )
    text = mock_post.call_args[1]["json"]["text"]
    assert "전체 보기" not in text


def test_send_slack_notification_empty_bids():
    """bids가 빈 리스트면 '매칭된 공고가 없습니다' 전송."""
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", [], "2026-03-24",
            triggered_by="manual", total_matched=0
        )
    assert mock_post.call_count == 1
    text = mock_post.call_args[1]["json"]["text"]
    assert "없습니다" in text


def test_send_slack_notification_raises_on_failure():
    bids = [make_bid()]
    mock_resp = MagicMock(status_code=500)
    with patch("slack_notifier.requests.post", return_value=mock_resp):
        with pytest.raises(SystemExit):
            send_slack_notification("https://hooks.slack.com/fake", bids, "2026-03-24")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
PYTHONIOENCODING=utf-8 "/c/Users/user1/.local/bin/uv.exe" run --with pytest --with requests python -m pytest tests/test_slack_notifier.py -v
```

기대 결과: 대부분 FAIL (시그니처 불일치, 배치 테스트 제거)

- [ ] **Step 3: slack_notifier.py 전면 교체**

```python
import sys
import requests

DISPLAY_LIMIT = 10
G2B_HOME = "https://www.g2b.go.kr"
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


def send_slack_notification(
    webhook_url: str,
    bids: list[dict],
    today_str: str,
    triggered_by: str = "scheduled",
    total_matched: int = 0,
) -> None:
    """매칭 공고를 Slack으로 전송. bids는 이미 최대 10건으로 잘려서 전달됨."""
    header = (
        f"🔔 나라장터 입찰공고 알림 [{today_str}]"
        if triggered_by == "scheduled"
        else f"🔍 나라장터 검색 결과 [{today_str}]"
    )

    if not bids:
        text = f"{header}\n\n매칭된 공고가 없습니다."
    else:
        bid_texts = "\n\n".join(format_bid(b) for b in bids)
        if total_matched > DISPLAY_LIMIT:
            footer = (
                f"📋 총 {total_matched}건 매칭 (상위 {DISPLAY_LIMIT}건 표시)"
                f" · <{G2B_HOME}|나라장터에서 전체 보기>"
            )
        else:
            footer = f"총 {total_matched}건 매칭"
        text = f"{header}\n\n{bid_texts}\n\n{footer}"

    resp = requests.post(webhook_url, json={"text": text}, timeout=10)
    if resp.status_code != 200:
        print(f"[ERROR] Slack 전송 실패: HTTP {resp.status_code}", flush=True)
        sys.exit(1)
```

- [ ] **Step 4: 테스트 실행 — 전체 통과 확인**

```bash
PYTHONIOENCODING=utf-8 "/c/Users/user1/.local/bin/uv.exe" run --with pytest --with requests python -m pytest tests/test_slack_notifier.py -v
```

기대 결과: 8개 PASS

- [ ] **Step 5: 커밋**

```bash
git add slack_notifier.py tests/test_slack_notifier.py
git commit -m "feat: update slack_notifier - 10건 제한, 헤더 분기, 더보기 링크"
```

---

## Task 2: checker.py — 수동/스케줄 분기 + 정렬 + 10건

**Files:**
- Modify: `checker.py`
- Modify: `tests/test_checker.py`

- [ ] **Step 1: test_checker.py에 make_bid에 bidNtceDt 추가 + 수동 모드 테스트 추가**

`tests/test_checker.py` 전면 교체:

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


def make_bid(no, name, deadline="20260407180000", ntce_dt="2026-03-24 10:00:00"):
    return {
        "bidNtceNo": no,
        "bidNtceNm": name,
        "ntceInsttNm": "기관",
        "bidMethdNm": "일반경쟁",
        "bidClseDt": deadline,
        "bidNtceDt": ntce_dt,
    }


# ── 스케줄 모드 테스트 ────────────────────────────────────────────

def test_run_sends_notification_for_matching_new_bids(monkeypatch):
    kw_path = write_keywords("제주\nAI\n")
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")
    monkeypatch.delenv("SEARCH_KEYWORDS", raising=False)

    bids = [make_bid("001", "제주 AI 시스템 구축"), make_bid("002", "서울 시스템")]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "get_seen_list", return_value=(1, [])), \
         patch.object(checker, "update_seen_list") as mock_update, \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run(keywords_path=kw_path)

    assert mock_slack.call_count == 1
    sent_bids = mock_slack.call_args[0][1]
    assert len(sent_bids) == 1
    assert sent_bids[0]["bidNtceNo"] == "001"

    updated_seen = mock_update.call_args[0][3]
    assert any(s["id"] == "001" for s in updated_seen)
    os.unlink(kw_path)


def test_run_skips_already_seen_bids(monkeypatch):
    kw_path = write_keywords("제주\nAI\n")
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")
    monkeypatch.delenv("SEARCH_KEYWORDS", raising=False)

    bids = [make_bid("001", "제주 AI 시스템")]
    existing_seen = [{"id": "001", "deadline": "2026-04-07"}]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "get_seen_list", return_value=(1, existing_seen)), \
         patch.object(checker, "update_seen_list"), \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run(keywords_path=kw_path)

    mock_slack.assert_not_called()
    os.unlink(kw_path)


def test_run_exits_if_env_missing(monkeypatch):
    monkeypatch.delenv("G2B_API_KEY", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("SEARCH_KEYWORDS", raising=False)

    import checker
    with pytest.raises(SystemExit):
        checker.run()


def test_run_scheduled_registers_all_new_bids_in_seen(monkeypatch):
    """11건 매칭 시 display는 10건이지만 seen에는 11건 모두 등록."""
    kw_path = write_keywords("AI\n")
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")
    monkeypatch.delenv("SEARCH_KEYWORDS", raising=False)

    bids = [make_bid(str(i), f"AI 시스템 {i}", ntce_dt=f"2026-03-24 {10+i:02d}:00:00")
            for i in range(11)]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "get_seen_list", return_value=(1, [])), \
         patch.object(checker, "update_seen_list") as mock_update, \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run(keywords_path=kw_path)

    sent_bids = mock_slack.call_args[0][1]
    assert len(sent_bids) == 10  # display 10건
    updated_seen = mock_update.call_args[0][3]
    assert len(updated_seen) == 11  # seen에 11건 모두 등록
    os.unlink(kw_path)


# ── 수동 모드 테스트 ────────────────────────────────────────────

def test_run_manual_mode_uses_env_keywords(monkeypatch):
    """SEARCH_KEYWORDS 있으면 파일 대신 env 키워드 사용."""
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("SEARCH_KEYWORDS", "AI 시스템")

    bids = [
        make_bid("001", "AI 시스템 구축"),
        make_bid("002", "일반 공사"),
    ]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run()

    assert mock_slack.call_count == 1
    sent_bids = mock_slack.call_args[0][1]
    assert len(sent_bids) == 1
    assert sent_bids[0]["bidNtceNo"] == "001"


def test_run_manual_mode_skips_seen_list(monkeypatch):
    """수동 모드는 get_seen_list를 호출하지 않는다."""
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("SEARCH_KEYWORDS", "AI")

    bids = [make_bid("001", "AI 시스템")]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "get_seen_list") as mock_seen, \
         patch.object(checker, "update_seen_list") as mock_update, \
         patch.object(checker, "send_slack_notification"), \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run()

    mock_seen.assert_not_called()
    mock_update.assert_not_called()


def test_run_manual_mode_sorts_by_date_newest_first(monkeypatch):
    """수동 모드는 bidNtceDt 기준 최신순 정렬."""
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("SEARCH_KEYWORDS", "AI")

    bids = [
        make_bid("001", "AI 구축", ntce_dt="2026-03-24 08:00:00"),
        make_bid("002", "AI 운영", ntce_dt="2026-03-24 10:00:00"),
        make_bid("003", "AI 유지", ntce_dt="2026-03-24 09:00:00"),
    ]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run()

    sent_bids = mock_slack.call_args[0][1]
    assert sent_bids[0]["bidNtceNo"] == "002"  # 가장 최신
    assert sent_bids[1]["bidNtceNo"] == "003"
    assert sent_bids[2]["bidNtceNo"] == "001"


def test_run_manual_mode_limits_to_10(monkeypatch):
    """수동 모드는 최대 10건만 전달."""
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("SEARCH_KEYWORDS", "AI")

    bids = [make_bid(str(i), f"AI 시스템 {i}") for i in range(15)]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run()

    sent_bids = mock_slack.call_args[0][1]
    assert len(sent_bids) == 10

    # total_matched kwarg로 전체 건수 전달 확인
    kwargs = mock_slack.call_args[1]
    assert kwargs.get("total_matched") == 15


def test_run_manual_mode_no_results(monkeypatch):
    """수동 모드 0건이면 빈 리스트로 Slack 호출."""
    monkeypatch.setenv("G2B_API_KEY", "FAKE")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    monkeypatch.setenv("SEARCH_KEYWORDS", "존재하지않는키워드xyz")

    bids = [make_bid("001", "AI 시스템")]

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run()

    assert mock_slack.call_count == 1
    sent_bids = mock_slack.call_args[0][1]
    assert sent_bids == []
```

- [ ] **Step 2: 테스트 실행 — 새 테스트 실패 확인**

```bash
PYTHONIOENCODING=utf-8 "/c/Users/user1/.local/bin/uv.exe" run --with pytest --with requests python -m pytest tests/test_checker.py -v
```

기대 결과: 수동 모드 테스트 FAIL, 기존 3개 PASS

- [ ] **Step 3: checker.py 전면 교체**

```python
import os
import sys
from datetime import date

from g2b_api import fetch_bids, parse_deadline
from github_issue import get_seen_list, update_seen_list, _purge_expired
from keywords import load_keywords, matches_all_keywords
from slack_notifier import send_slack_notification

DISPLAY_LIMIT = 10


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"[ERROR] 환경변수 {name}이 설정되지 않았습니다.", flush=True)
        sys.exit(1)
    return value


def run(keywords_path: str = "keywords.txt") -> None:
    api_key = _require_env("G2B_API_KEY")
    slack_url = _require_env("SLACK_WEBHOOK_URL")

    today = date.today()
    today_str = today.strftime("%Y%m%d")
    today_display = today.isoformat()

    # ── 모드 감지 ────────────────────────────────────────────────
    search_keywords_env = os.environ.get("SEARCH_KEYWORDS", "").strip()
    if search_keywords_env:
        keywords = [k for k in search_keywords_env.split() if k]
        if not keywords:
            print("[ERROR] SEARCH_KEYWORDS에 유효한 키워드가 없습니다.", flush=True)
            sys.exit(1)
        triggered_by = "manual"
    else:
        keywords = load_keywords(keywords_path)
        triggered_by = "scheduled"

    # ── G2B API 조회 + 키워드 매칭 ──────────────────────────────
    bids = fetch_bids(api_key, today_str)
    matched = [b for b in bids if matches_all_keywords(b.get("bidNtceNm", ""), keywords)]

    # ── 수동 모드 ────────────────────────────────────────────────
    if triggered_by == "manual":
        matched.sort(key=lambda b: b.get("bidNtceDt", ""), reverse=True)
        display_bids = matched[:DISPLAY_LIMIT]
        total_matched = len(matched)

        for b in display_bids:
            b["deadline"] = parse_deadline(b.get("bidClseDt", ""))

        send_slack_notification(
            slack_url, display_bids, today_display,
            triggered_by="manual", total_matched=total_matched,
        )
        print(f"[INFO] 수동 검색 완료: {total_matched}건 매칭, {len(display_bids)}건 전송", flush=True)
        return

    # ── 스케줄 모드 ──────────────────────────────────────────────
    gh_token = _require_env("GITHUB_TOKEN")
    gh_repo = _require_env("GITHUB_REPOSITORY")

    issue_number, seen = get_seen_list(gh_repo, gh_token)
    seen = _purge_expired(seen, today)

    seen_ids = {s["id"] for s in seen}
    new_bids = [b for b in matched if b["bidNtceNo"] not in seen_ids]

    if not new_bids:
        print(f"[INFO] 새 매칭 공고 없음 (전체 {len(bids)}건 조회, {len(matched)}건 매칭)", flush=True)
        update_seen_list(gh_repo, gh_token, issue_number, seen)
        return

    # 최신순 정렬 → 상위 10건 display
    new_bids.sort(key=lambda b: b.get("bidNtceDt", ""), reverse=True)
    display_bids = new_bids[:DISPLAY_LIMIT]
    total_matched = len(new_bids)

    for b in new_bids:  # display 아닌 전체에 deadline 추가 (seen 등록용)
        b["deadline"] = parse_deadline(b.get("bidClseDt", ""))

    send_slack_notification(
        slack_url, display_bids, today_display,
        triggered_by="scheduled", total_matched=total_matched,
    )
    print(f"[INFO] Slack 알림 전송 완료: {total_matched}건 매칭, {len(display_bids)}건 표시", flush=True)

    # seen 목록: 표시 10건이 아닌 new_bids 전체 등록 (11번째 이후 중복 방지)
    for b in new_bids:
        seen.append({"id": b["bidNtceNo"], "deadline": b["deadline"]})

    update_seen_list(gh_repo, gh_token, issue_number, seen)


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 전체 테스트 실행 — 통과 확인**

```bash
PYTHONIOENCODING=utf-8 "/c/Users/user1/.local/bin/uv.exe" run --with pytest --with requests python -m pytest tests/ -v
```

기대 결과: 전체 PASS (기존 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add checker.py tests/test_checker.py
git commit -m "feat: add manual/scheduled mode branching, sort + 10건 limit"
```

---

## Task 3: check_bids.yml — workflow_dispatch inputs 추가

**Files:**
- Modify: `.github/workflows/check_bids.yml`

테스트 없음 — GitHub Actions에서 직접 확인.

- [ ] **Step 1: 워크플로우 파일 수정**

`.github/workflows/check_bids.yml`을 아래로 교체:

```yaml
name: G2B Bid Alert

on:
  schedule:
    - cron: '0 1 * * *'   # UTC 01:00 = KST 10:00 (한국 UTC+9, DST 없음)
  workflow_dispatch:
    inputs:
      keywords:
        description: '검색 키워드 (스페이스 구분, AND 조건). 예: 소프트웨어 유지보수'
        required: false
        default: ''

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

      - name: Install dependencies
        run: pip install requests

      - name: Run checker
        run: python checker.py
        env:
          G2B_API_KEY: ${{ secrets.G2B_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          SEARCH_KEYWORDS: ${{ github.event.inputs.keywords }}
```

- [ ] **Step 2: 커밋 + 푸시**

```bash
git add .github/workflows/check_bids.yml
git commit -m "feat: add workflow_dispatch keywords input + SEARCH_KEYWORDS env"
git push
```

- [ ] **Step 3: GitHub Actions에서 수동 테스트**

GitHub → Actions → G2B Bid Alert → Run workflow → keywords 입력란에 `소프트웨어` 입력 → Run workflow

기대 결과: 스케줄 모드가 아닌 수동 모드로 실행, Slack에 🔍 헤더로 결과 수신

---

## Task 4: Cloudflare Worker 생성 + 배포

**Files:**
- Create: `cloudflare-worker/worker.js`

자동화 테스트 없음 — Cloudflare Worker는 별도 런타임. 배포 후 Slack에서 직접 테스트.

- [ ] **Step 1: worker.js 파일 생성**

`cloudflare-worker/worker.js`:

```javascript
export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const rawBody = await request.text();
    const timestamp = request.headers.get("X-Slack-Request-Timestamp") ?? "";
    const slackSig = request.headers.get("X-Slack-Signature") ?? "";

    // 리플레이 공격 방지: 5분 초과 요청 거부
    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - parseInt(timestamp)) > 300) {
      return new Response("Unauthorized", { status: 401 });
    }

    // HMAC-SHA256 서명 검증
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(env.SLACK_SIGNING_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const sigBytes = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(`v0:${timestamp}:${rawBody}`)
    );
    const computed =
      "v0=" +
      Array.from(new Uint8Array(sigBytes))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

    if (computed !== slackSig) {
      return new Response("Unauthorized", { status: 401 });
    }

    // 슬래시 커맨드 본문 파싱
    const params = new URLSearchParams(rawBody);
    const keywords = (params.get("text") ?? "").trim();

    if (!keywords) {
      return Response.json({
        response_type: "ephemeral",
        text: "❌ 키워드를 입력해주세요. 예: `/검색 소프트웨어 유지보수`",
      });
    }

    // GitHub Actions workflow_dispatch 트리거 (백그라운드)
    ctx.waitUntil(
      fetch(
        "https://api.github.com/repos/sunwoo0506/nara/actions/workflows/check_bids.yml/dispatches",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.GH_PAT}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "nara-slack-bot",
          },
          body: JSON.stringify({ ref: "master", inputs: { keywords } }),
        }
      ).then(async (r) => {
        if (!r.ok) {
          console.error(`GitHub API ${r.status}: ${await r.text()}`);
        }
      })
    );

    return Response.json({
      response_type: "in_channel",
      text: `🔍 \`${keywords}\` 검색 중... 잠시 후 결과를 전송합니다.`,
    });
  },
};
```

- [ ] **Step 2: 커밋**

```bash
git add cloudflare-worker/worker.js
git commit -m "feat: add Cloudflare Worker for Slack slash command"
git push
```

- [ ] **Step 3: Cloudflare Worker 배포**

1. [dash.cloudflare.com](https://dash.cloudflare.com) 로그인
2. Workers & Pages → Create → Hello World (새 Worker 생성)
3. Worker 이름 지정 (예: `nara-slack-bot`)
4. 에디터에서 `worker.js` 내용으로 교체 → Deploy
5. Worker URL 복사 (예: `https://nara-slack-bot.{account}.workers.dev`)
6. Settings → Variables → Add Secret:
   - `SLACK_SIGNING_SECRET`: Slack App → Basic Information → Signing Secret
   - `GH_PAT`: GitHub Fine-grained PAT (Actions: write 권한)

- [ ] **Step 4: GitHub Fine-grained PAT 발급**

1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Generate new token
3. Repository access: `sunwoo0506/nara`
4. Permissions → Actions: Read and write
5. 발급된 토큰을 Cloudflare Worker Secret `GH_PAT`에 등록

- [ ] **Step 5: Slack App slash command 등록**

1. [api.slack.com/apps](https://api.slack.com/apps) → 해당 앱 선택
2. Slash Commands → Create New Command
   - Command: `/검색`
   - Request URL: `https://nara-slack-bot.{account}.workers.dev`
   - Short Description: `나라장터 입찰공고 검색`
   - Usage Hint: `소프트웨어 유지보수`
3. Save → 앱 재설치 (Install App → Reinstall)

- [ ] **Step 6: End-to-end 테스트**

Slack DM에서 `/검색 소프트웨어` 입력

기대 결과:
1. 즉시 `🔍 소프트웨어 검색 중... 잠시 후 결과를 전송합니다.` 수신
2. 30~60초 후 Slack에 `🔍 나라장터 검색 결과` 헤더로 공고 목록 수신
3. 최대 10건, 10건 초과 시 `나라장터에서 전체 보기` 링크 포함
