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
