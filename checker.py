import os
import sys
from datetime import date, timedelta

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
    begin_date = (today - timedelta(days=30)).strftime("%Y%m%d")

    # ── 모드 감지 ────────────────────────────────────────────────
    search_keywords_env = os.environ.get("SEARCH_KEYWORDS", "").strip()
    if search_keywords_env:
        keywords = [k for k in search_keywords_env.split() if k]
        if not keywords:  # 방어 처리: Worker에서 이미 차단하지만 만약을 대비
            print("[ERROR] SEARCH_KEYWORDS에 유효한 키워드가 없습니다.", flush=True)
            sys.exit(1)
        triggered_by = "manual"
    else:
        keywords = load_keywords(keywords_path)
        triggered_by = "scheduled"

    # ── G2B API 조회 + 마감 미경과 필터 + 키워드 매칭 ───────────
    bids = fetch_bids(api_key, begin_date, today_str)
    today_dt = today_str + "000000"
    active_bids = [b for b in bids if b.get("bidClseDt", "99991231235959") >= today_dt]
    matched = [b for b in active_bids if matches_all_keywords(b.get("bidNtceNm", ""), keywords)]

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
