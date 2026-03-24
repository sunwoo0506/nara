import sys


def load_keywords(path: str) -> list[str]:
    """keywords.txt에서 유효 키워드 목록을 반환. 없거나 비어있으면 exit(1)."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"[ERROR] keywords 파일을 찾을 수 없습니다: {path}", flush=True)
        sys.exit(1)

    keywords = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

    if not keywords:
        print("[ERROR] keywords.txt에 유효한 키워드가 없습니다.", flush=True)
        sys.exit(1)

    return keywords


def matches_all_keywords(title: str, keywords: list[str]) -> bool:
    """공고명에 모든 키워드가 포함되면 True (대소문자 무시)."""
    title_lower = title.lower()
    return all(kw.lower() in title_lower for kw in keywords)
