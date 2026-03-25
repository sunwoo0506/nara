import sys
import urllib.parse
from datetime import datetime
import requests

G2B_ENDPOINT = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServc"


def parse_deadline(value: str | None) -> str:
    """bidClseDt(yyyyMMddHHmmss)를 YYYY-MM-DD 문자열로 변환. 빈값이면 '9999-12-31'."""
    if not value:
        return "9999-12-31"
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except ValueError:
        return "9999-12-31"


def _extract_items(body: dict) -> list:
    """응답 body에서 item 목록 추출. 단일 dict이면 리스트로 감쌈."""
    items_field = body.get("items")
    if not items_field or items_field == "":
        return []
    # items 자체가 list인 경우 (결과가 여러 건일 때 API가 직접 list 반환)
    if isinstance(items_field, list):
        return items_field
    item = items_field.get("item", [])
    if isinstance(item, dict):
        return [item]
    return item if item else []


def fetch_bids(api_key: str, begin_date: str, end_date: str) -> list[dict]:
    """입찰공고를 페이지네이션하여 반환. begin_date/end_date: 'YYYYMMDD'"""
    all_bids = []
    page = 1
    num_of_rows = 100

    begin_dt = begin_date + "0000"
    end_dt = end_date + "2359"

    # 키가 이미 URL인코딩된 상태로 저장된 경우를 대비해 디코딩 후 requests에 위임
    decoded_key = urllib.parse.unquote(api_key)

    while True:
        params = {
            "serviceKey": decoded_key,
            "pageNo": page,
            "numOfRows": num_of_rows,
            "type": "json",
            "inqryDiv": "1",
            "inqryBgnDt": begin_dt,
            "inqryEndDt": end_dt,
        }

        resp = requests.get(G2B_ENDPOINT, params=params, timeout=30)

        if resp.status_code != 200:
            print(f"[ERROR] 나라장터 API 호출 실패: HTTP {resp.status_code}", flush=True)
            print(f"[DEBUG] URL: {resp.url[:300]}", flush=True)
            print(f"[DEBUG] Response: {resp.text[:1000]}", flush=True)
            sys.exit(1)

        raw = resp.json()
        if "response" not in raw:
            print(f"[ERROR] 예상치 못한 API 응답 구조: {str(raw)[:500]}", flush=True)
            sys.exit(1)

        body = raw["response"]["body"]
        total_count = int(body.get("totalCount", 0))
        items = _extract_items(body)
        all_bids.extend(items)

        if page * num_of_rows >= total_count:
            break
        page += 1

    return all_bids
