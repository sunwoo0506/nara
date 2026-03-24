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
    assert mock_slack.call_args[1].get("triggered_by") == "scheduled"

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
    assert len(sent_bids) == 10
    updated_seen = mock_update.call_args[0][3]
    assert len(updated_seen) == 11
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
    assert mock_slack.call_args[1].get("triggered_by") == "manual"


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
    assert sent_bids[0]["bidNtceNo"] == "002"
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
