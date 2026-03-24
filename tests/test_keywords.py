import os
import tempfile
import pytest
from keywords import load_keywords, matches_all_keywords


def write_keywords_file(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    f.write(content)
    f.close()
    return f.name


def test_load_keywords_basic():
    path = write_keywords_file("제주\nAI\n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_skips_comments_and_blank():
    path = write_keywords_file("# 주석\n제주\n\nAI\n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_strips_whitespace():
    path = write_keywords_file("  제주  \n  AI  \n")
    try:
        result = load_keywords(path)
        assert result == ["제주", "AI"]
    finally:
        os.unlink(path)


def test_load_keywords_raises_if_file_missing():
    with pytest.raises(SystemExit):
        load_keywords("/nonexistent/keywords.txt")


def test_load_keywords_raises_if_empty():
    path = write_keywords_file("# 주석만 있음\n\n")
    try:
        with pytest.raises(SystemExit):
            load_keywords(path)
    finally:
        os.unlink(path)


def test_matches_all_keywords_true():
    assert matches_all_keywords("제주 AI 시스템 구축", ["제주", "AI"]) is True


def test_matches_all_keywords_false_missing_one():
    assert matches_all_keywords("AI 시스템 구축", ["제주", "AI"]) is False


def test_matches_all_keywords_case_insensitive():
    assert matches_all_keywords("제주 ai 시스템", ["제주", "AI"]) is True


def test_matches_all_keywords_single_keyword():
    assert matches_all_keywords("소프트웨어 유지보수", ["소프트웨어"]) is True
