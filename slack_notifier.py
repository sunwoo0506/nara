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
