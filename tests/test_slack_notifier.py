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
