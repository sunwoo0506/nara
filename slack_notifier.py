import sys
import requests

BATCH_SIZE = 20
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


def send_slack_notification(webhook_url: str, bids: list[dict], today_str: str) -> None:
    """매칭 공고를 Slack으로 전송. 20건 초과 시 분할 전송."""
    total = len(bids)

    for i in range(0, total, BATCH_SIZE):
        batch = bids[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        header = f"🔔 나라장터 입찰공고 알림 [{today_str}]"
        if total_batches > 1:
            header += f" ({batch_num}/{total_batches})"

        bid_texts = "\n\n".join(format_bid(b) for b in batch)
        footer = f"총 {total}건 새 공고 매칭"

        text = f"{header}\n\n{bid_texts}\n\n{footer}"

        resp = requests.post(webhook_url, json={"text": text}, timeout=10)

        if resp.status_code != 200:
            print(f"[ERROR] Slack 전송 실패: HTTP {resp.status_code}", flush=True)
            sys.exit(1)
