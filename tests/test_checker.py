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

    import checker
    with patch.object(checker, "fetch_bids", return_value=bids), \
         patch.object(checker, "get_seen_list", return_value=(1, [])), \
         patch.object(checker, "update_seen_list") as mock_update, \
         patch.object(checker, "send_slack_notification") as mock_slack, \
         patch.object(checker, "date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 24)
        mock_date.side_effect = lambda *a, **k: date(*a, **k)
        checker.run(keywords_path=kw_path)

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

    import checker
    with pytest.raises(SystemExit):
        checker.run()
