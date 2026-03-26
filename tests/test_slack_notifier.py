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


def test_send_slack_notification_always_has_g2b_link():
    """건수와 무관하게 항상 g2b.go.kr 링크가 포함된다."""
    bids = [make_bid(str(i)) for i in range(3)]
    mock_resp = MagicMock(status_code=200)
    with patch("slack_notifier.requests.post", return_value=mock_resp) as mock_post:
        send_slack_notification(
            "https://hooks.slack.com/fake", bids, "2026-03-24",
            triggered_by="manual", total_matched=3
        )
    text = mock_post.call_args[1]["json"]["text"]
    assert "g2b.go.kr" in text


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
