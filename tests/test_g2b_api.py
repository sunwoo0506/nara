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
    count = total_count if total_count is not None else (len(items) if isinstance(items, list) else 1)
    return {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "totalCount": count,
                "pageNo": 1,
                "numOfRows": 100,
                "items": {"item": items},
            },
        }
    }


def test_fetch_bids_returns_list():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = make_api_response([make_item()])

    with patch("g2b_api.requests.get", return_value=mock_resp):
        bids = fetch_bids("FAKE_KEY", "20260224", "20260324")

    assert isinstance(bids, list)
    assert len(bids) == 1
    assert bids[0]["bidNtceNo"] == "20260324001"


def test_fetch_bids_single_item_as_dict():
    """API가 단일 건일 때 item을 dict로 반환하는 케이스."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = make_api_response(make_item(), total_count=1)

    with patch("g2b_api.requests.get", return_value=mock_resp):
        bids = fetch_bids("FAKE_KEY", "20260224", "20260324")

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
        bids = fetch_bids("FAKE_KEY", "20260224", "20260324")

    assert len(bids) == 2


def test_fetch_bids_raises_on_api_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("g2b_api.requests.get", return_value=mock_resp):
        with pytest.raises(SystemExit):
            fetch_bids("FAKE_KEY", "20260224", "20260324")


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
        bids = fetch_bids("FAKE_KEY", "20260224", "20260324")

    assert bids == []


def test_parse_deadline_normal():
    assert parse_deadline("20260407180000") == "2026-04-07"


def test_parse_deadline_empty():
    assert parse_deadline("") == "9999-12-31"


def test_parse_deadline_none():
    assert parse_deadline(None) == "9999-12-31"
