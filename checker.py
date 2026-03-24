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
