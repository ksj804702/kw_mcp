import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Comment, NavigableString


NOTICE_URL = "https://www.kw.ac.kr/ko/life/notice.jsp"
BASE_URL = "https://www.kw.ac.kr"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
DATE_PATTERN = re.compile(r"작성일\s+(\d{4}-\d{2}-\d{2})")
WHITESPACE_RE = re.compile(r"\s+")
CALENDAR_AJAX_URL = "https://www.kw.ac.kr/KWBoard/list5_detail.jsp"


def _normalize_notice_url(notice_url: str) -> str:
    """상대/절대 URL을 광운대 공지 절대 URL로 정규화합니다."""
    normalized = (notice_url or "").strip()
    if not normalized:
        raise ValueError("notice_url은 비어 있을 수 없습니다.")

    if normalized.startswith("/"):
        normalized = BASE_URL + normalized

    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("notice_url은 절대 URL 또는 '/'로 시작하는 상대 URL이어야 합니다.")
    if "kw.ac.kr" not in parsed.netloc:
        raise ValueError("광운대학교(kw.ac.kr) 도메인 URL만 허용됩니다.")

    return normalized


def _extract_clean_text(content_tag: BeautifulSoup) -> str:
    """복잡한 HTML 본문을 읽기 쉬운 일반 텍스트로 정리합니다."""
    lines = []
    for raw_line in content_tag.get_text("\n", strip=True).splitlines():
        line = WHITESPACE_RE.sub(" ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def get_kw_notices(
    search_key: int = 1,
    search_val: str | None = None,
) -> list[dict]:
    """광운대학교 공지사항 목록을 수집해 반환합니다.

    Args:
        search_key: 사이트 검색 기준.
            1=제목, 2=내용, 3=제목+내용, 4=작성자
        search_val: 사이트 검색어(searchVal). None 또는 빈 문자열이면 전체 검색.

    Returns:
        각 공지에 대해 category, title, date, url 키를 가진 딕셔너리 목록.
    """
    # 검색어는 사이트 검색 파라미터로 전달되므로 공백 정리만 수행합니다.
    normalized_search_val = (search_val or "").strip()
    if search_key not in {1, 2, 3, 4}:
        raise ValueError("search_key는 1, 2, 3, 4 중 하나여야 합니다.")

    # 공지 목록 URL 쿼리 파라미터를 구성합니다.
    # 사이트 내부 검색과 동일한 방식으로 searchKey/searchVal을 전달합니다.
    query_params = {
        "searchKey": str(search_key),
        "searchVal": normalized_search_val,
        "srCategoryId": "",
        "mode": "list",
    }

    # 공지 목록 페이지 HTML을 요청합니다.
    response = requests.get(
        NOTICE_URL,
        params=query_params,
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
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
            notices.append(
                {
                    "category": category,
                    "title": title,
                    "date": notice_date_text,
                    "url": link,
                }
            )

    return notices


def get_kw_notice_content(notice_url: str) -> dict:
    """공지 상세 URL로 게시글 제목/작성일/본문을 반환합니다.

    Args:
        notice_url: 공지 상세 페이지 URL.
            예) https://www.kw.ac.kr/ko/life/notice.jsp?BoardMode=view&DUID=52089...

    Returns:
        url, title, date, content_text 키를 가진 딕셔너리.
    """
    normalized_url = _normalize_notice_url(notice_url)

    response = requests.get(normalized_url, headers=DEFAULT_HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 제목은 페이지 상단 제목 영역에서 우선 추출하고, 실패 시 og:title을 사용합니다.
    title = ""
    title_tag = soup.select_one(".board-view-box .board-view-head h3")
    if title_tag:
        title = title_tag.get_text(" ", strip=True)
    if not title:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            title = (og_title.get("content") or "").strip()

    # 작성일은 본문 상단 정보 영역에서 동일한 정규식으로 추출합니다.
    notice_date_text = ""
    info_tag = soup.select_one(".board-view-box .board-view-head .info")
    if info_tag:
        date_match = DATE_PATTERN.search(info_tag.get_text(" ", strip=True))
        if date_match:
            notice_date_text = date_match.group(1)

    # 사용자가 전달한 샘플과 동일하게 li.contents 내부를 본문으로 사용합니다.
    content_tag = soup.select_one("li.contents")
    if content_tag is None:
        raise ValueError("게시글 본문(li.contents)을 찾지 못했습니다.")

    content_text = _extract_clean_text(content_tag)

    return {
        "url": normalized_url,
        "title": title,
        "date": notice_date_text,
        "content_text": content_text,
    }


def get_kw_academic_calendar(year: str = "", month: str = "") -> dict:
    """광운대학교 학사일정 페이지에서 일정 영역만 추출해 반환합니다.

    Returns:
        url, year, schedules 키를 가진 딕셔너리.
        schedules는 월("02" 등)을 키로 갖고,
        값은 period/event 항목 목록인 딕셔너리입니다.
        서버에서 내려온 원본 학사일정(예: 10~09 순환) 구조를 그대로 반영합니다.
    """
    calendar_url = "https://www.kw.ac.kr/ko/life/bachelor_calendar.jsp"

    # month 입력은 3/03 모두 허용하고 내부적으로 2자리 월 문자열로 통일합니다.
    normalized_month = ""
    if (month or "").strip():
        raw_month = (month or "").strip()
        if not raw_month.isdigit():
            raise ValueError("month는 1~12 숫자여야 합니다.")
        month_number = int(raw_month)
        if month_number < 1 or month_number > 12:
            raise ValueError("month는 1~12 범위여야 합니다.")
        normalized_month = f"{month_number:02d}"

    normalized_year = (year or "").strip()
    year_match = re.search(r"(\d{4})", normalized_year)
    if year_match:
        normalized_year = year_match.group(1)

    payload = {
        "sy": normalized_year,
        "sm": normalized_month,
    }
    response = requests.post(
        CALENDAR_AJAX_URL,
        data=payload,
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    calendar_box = soup.select_one(".schedule-this-year")
    if calendar_box is None:
        calendar_box = soup

    schedule_root = calendar_box.select_one(".schedule-list-box.schedule-this-yearlist")
    if schedule_root is None:
        schedule_root = calendar_box.select_one(".schedule-list-box")
    if schedule_root is None:
        schedule_root = calendar_box

    parsed_year = ""
    year_title = calendar_box.select_one(".schedule-title h3")
    if year_title is None:
        year_title = soup.select_one("h3")
    if year_title:
        parsed_year_match = re.search(r"(\d{4})", year_title.get_text(" ", strip=True))
        if parsed_year_match:
            parsed_year = parsed_year_match.group(1)

    schedules: dict[str, list[dict]] = {}
    month_boxes = schedule_root.select(".month_box")
    if month_boxes:
        for month_box in month_boxes:
            month_text = month_box.select_one(".month span")
            month_key = month_text.get_text(strip=True) if month_text else ""
            if not month_key:
                continue

            if month_key not in schedules:
                schedules[month_key] = []

            for item in month_box.select(".list ul li"):
                period_tag = item.select_one("strong")
                event_tag = item.select_one("p")
                period = period_tag.get_text(" ", strip=True) if period_tag else ""
                event = event_tag.get_text(" ", strip=True) if event_tag else ""
                if period and event:
                    schedules[month_key].append(
                        {
                            "period": period,
                            "event": event,
                        }
                    )
    else:
        # 월간 뷰 fallback: month_box 없이 li가 내려오는 경우를 지원합니다.
        fallback_items = []
        for item in schedule_root.select("li"):
            period_tag = item.select_one("strong")
            event_tag = item.select_one("p")
            period = period_tag.get_text(" ", strip=True) if period_tag else ""
            event = event_tag.get_text(" ", strip=True) if event_tag else ""
            if period and event:
                fallback_items.append(
                    {
                        "period": period,
                        "event": event,
                    }
                )

        if fallback_items and normalized_month:
            schedules[normalized_month] = fallback_items
        elif not fallback_items:
            raise ValueError("학사일정 목록 영역(.schedule-list-box/.month_box)을 찾지 못했습니다.")

    # month 키에서 숫자가 아닌 모든 문자(\D)를 강제로 제거한 후 오름차순 정렬합니다.
    # (눈에 보이지 않는 특수 공백 문자가 섞여 있어도 완벽하게 숫자로 변환해 줍니다)
    sorted_schedules = dict(
        sorted(
            schedules.items(),
            key=lambda item: int(re.sub(r'\D', '', str(item[0]))) if re.sub(r'\D', '', str(item[0])) else 99
        )
    )

    return {
        "url": calendar_url,
        "year": normalized_year or parsed_year,
        "schedules": sorted_schedules,
    }