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
    resp = requests.get(url, params={"labels": "seen-bids", "state": "open"}, headers=_headers(token), timeout=30)

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
        timeout=30,
    )
    if create_resp.status_code != 201:
        print(f"[ERROR] GitHub Issue 생성 실패: HTTP {create_resp.status_code}", flush=True)
        sys.exit(1)

    return create_resp.json()["number"], []


def update_seen_list(repo: str, token: str, issue_number: int, seen: list[dict]) -> None:
    """seen 목록을 GitHub Issue 본문에 저장."""
    url = f"{GITHUB_API}/repos/{repo}/issues/{issue_number}"
    body = json.dumps({"seen": seen}, ensure_ascii=False)
    resp = requests.patch(url, json={"body": body}, headers=_headers(token), timeout=30)

    if resp.status_code != 200:
        print(f"[ERROR] GitHub Issue 업데이트 실패: HTTP {resp.status_code}", flush=True)
        sys.exit(1)
