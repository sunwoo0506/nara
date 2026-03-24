import sys
from datetime import datetime
import requests

G2B_ENDPOINT = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"


def parse_deadline(value: str | None) -> str:
    """bidClseDt(yyyyMMddHHmmss)를 YYYY-MM-DD 문자열로 변환. 빈값이면 '9999-12-31'."""
    if not value:
        return "9999-12-31"
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").strftime("%Y-%m-%d")
    except ValueError:
        return "9999-12-31"


def _extract_items(body: dict) -> list:
    """응답 body에서 item 목록 추출. 단일 dict이면 리스트로 감쌈."""
    items_field = body.get("items")
    if not items_field or items_field == "":
        return []
    item = items_field.get("item", [])
    if isinstance(item, dict):
        return [item]
    return item if item else []


def fetch_bids(api_key: str, date_str: str) -> list[dict]:
    """당일 입찰공고 전체를 페이지네이션하여 반환. date_str: 'YYYYMMDD'"""
    all_bids = []
    page = 1
    num_of_rows = 100

    begin_dt = date_str + "0000"
    end_dt = date_str + "2359"

    while True:
        # serviceKey는 requests가 재인코딩하지 않도록 URL에 직접 포함
        import urllib.parse
        query = urllib.parse.urlencode({
            "pageNo": page,
            "numOfRows": num_of_rows,
            "type": "json",
            "inqryBgnDt": begin_dt,
            "inqryEndDt": end_dt,
        })
        url = f"{G2B_ENDPOINT}?serviceKey={api_key}&{query}"

        resp = requests.get(url, timeout=30)

        if resp.status_code != 200:
            print(f"[ERROR] 나라장터 API 호출 실패: HTTP {resp.status_code}", flush=True)
            print(f"[DEBUG] URL: {url[:200]}", flush=True)
            print(f"[DEBUG] Response: {resp.text[:500]}", flush=True)
            sys.exit(1)

        body = resp.json()["response"]["body"]
        total_count = int(body.get("totalCount", 0))
        items = _extract_items(body)
        all_bids.extend(items)

        if page * num_of_rows >= total_count:
            break
        page += 1

    return all_bids
