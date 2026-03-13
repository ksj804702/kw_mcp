import re
from datetime import date

import requests
from bs4 import BeautifulSoup, Comment, NavigableString


NOTICE_URL = (
    "https://www.kw.ac.kr/ko/life/notice.jsp"
    "?srCategoryId=&mode=list&searchKey=1&searchVal="
)
BASE_URL = "https://www.kw.ac.kr"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
DATE_PATTERN = re.compile(r"작성일\s+(\d{4}-\d{2}-\d{2})")


def _parse_iso_date(value: str | None, arg_name: str) -> date | None:
    """YYYY-MM-DD 문자열을 date 객체로 변환합니다."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{arg_name}는 YYYY-MM-DD 형식이어야 합니다: {value}") from exc


def get_kw_notices(
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """광운대학교 공지사항 목록을 수집해 반환합니다.

    Args:
        keyword: 제목/카테고리에 포함되어야 하는 검색어(대소문자 무시).
            None 또는 빈 문자열이면 전체 공지사항을 반환합니다.
        date_from: 작성일 시작일(YYYY-MM-DD). 해당 날짜 이상만 포함합니다.
        date_to: 작성일 종료일(YYYY-MM-DD). 해당 날짜 이하만 포함합니다.

    Returns:
        각 공지에 대해 category, title, date, url 키를 가진 딕셔너리 목록.
    """
    # 공백 검색어는 "필터 없음"으로 처리합니다.
    normalized_keyword = (keyword or "").strip().lower()
    parsed_date_from = _parse_iso_date(date_from, "date_from")
    parsed_date_to = _parse_iso_date(date_to, "date_to")

    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise ValueError("date_from은 date_to보다 늦을 수 없습니다.")

    # 공지 목록 페이지 HTML을 요청합니다.
    response = requests.get(NOTICE_URL, headers=DEFAULT_HEADERS, timeout=10)
    response.raise_for_status()

    # 응답 HTML을 파싱해 공지 데이터를 추출합니다.
    soup = BeautifulSoup(response.text, "html.parser")
    notices = []

    # 실제 공지 상세 페이지로 이동하는 링크만 대상으로 순회합니다.
    for a_tag in soup.select('a[href*="BoardMode=view"]'):
        # 카테고리([국제학생] 등)는 strong.category에서 추출합니다.
        category_tag = a_tag.select_one(".category")
        category = category_tag.get_text(strip=True) if category_tag else ""

        # 제목은 a 태그의 "직접 텍스트"만 합칩니다.
        # 이렇게 하면 아이콘 설명, 주석, 하위 태그 텍스트가 섞이지 않습니다.
        title = " ".join(
            child.strip()
            for child in a_tag.children
            if isinstance(child, NavigableString)
            and not isinstance(child, Comment)
            and child.strip()
        )

        # 링크가 상대 경로면 절대 경로로 바꿉니다.
        link = a_tag.get("href", "")
        if link.startswith("/"):
            link = BASE_URL + link

        # 작성일은 같은 공지 블록의 info 영역에서 정규식으로 추출합니다.
        info_tag = a_tag.find_next_sibling("p", class_="info")
        notice_date_text = ""
        if info_tag:
            date_match = DATE_PATTERN.search(info_tag.get_text(" ", strip=True))
            if date_match:
                notice_date_text = date_match.group(1)

        # 필수값이 있는 항목만 유효 공지로 판단합니다.
        if title and link:
            # 검색어가 있으면 제목/카테고리에 검색어가 포함된 항목만 남깁니다.
            if normalized_keyword:
                haystack = f"{category} {title}".lower()
                if normalized_keyword not in haystack:
                    continue

            # 작성일이 존재하면 작성일 범위 필터를 적용합니다.
            if parsed_date_from or parsed_date_to:
                if not notice_date_text:
                    continue
                parsed_notice_date = date.fromisoformat(notice_date_text)
                if parsed_date_from and parsed_notice_date < parsed_date_from:
                    continue
                if parsed_date_to and parsed_notice_date > parsed_date_to:
                    continue

            notices.append(
                {
                    "category": category,
                    "title": title,
                    "date": notice_date_text,
                    "url": link,
                }
            )

    return notices