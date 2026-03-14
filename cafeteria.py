import re

import requests
from bs4 import BeautifulSoup


FACILITY11_URL = "https://www.kw.ac.kr/ko/life/facility11.jsp"
DEFAULT_SECTION_NAME = "함지마루"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
PERIOD_RE = re.compile(r"조회기간\s*:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})")


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def _extract_lines(pre_tag) -> list[str]:
    if pre_tag is None:
        return []
    lines = [line.strip() for line in pre_tag.get_text("\n", strip=False).splitlines()]
    return [line for line in lines if line]


def _is_breakfast_menu(title: str) -> bool:
    normalized = _normalize_text(title)
    return "천원의 아침" in normalized or "아침" in normalized


def _is_lunch_menu(title: str) -> bool:
    normalized = _normalize_text(title)
    return "자율중식" in normalized or "푸드코트" in normalized


def _find_target_section(soup: BeautifulSoup, section_name: str):
    normalized_name = _normalize_text(section_name)

    for section in soup.select("section.h3_contents-block"):
        h3 = section.select_one("h3")
        if h3 and normalized_name in _normalize_text(h3.get_text(" ", strip=True)):
            return section

    # fallback: 페이지 구조가 바뀌어 section 태그가 없더라도 h3 기준으로 탐색
    for h3 in soup.select("h3"):
        if normalized_name in _normalize_text(h3.get_text(" ", strip=True)):
            return h3.find_parent()

    return None


def get_kw_student_meal(meal_type: str = "", url: str = FACILITY11_URL) -> dict:
    """광운대학교 학생식당(예: 함지마루) 주간 식단을 반환합니다.

    Args:
        meal_type: 식사 구분("아침", "점심"). 비우면 전체 반환.
        url: 식단 페이지 URL.
    """
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    section = _find_target_section(soup, DEFAULT_SECTION_NAME)
    if section is None:
        raise ValueError(f"'{DEFAULT_SECTION_NAME}' 섹션을 찾지 못했습니다.")

    section_title_tag = section.select_one("h3")
    table = section.select_one("table.tbl-list")
    if table is None:
        raise ValueError("식단 테이블(table.tbl-list)을 찾지 못했습니다.")

    period_text = ""
    period_start = ""
    period_end = ""
    h4_tag = section.select_one("h4")
    if h4_tag:
        period_text = _normalize_text(h4_tag.get_text(" ", strip=True))
        match = PERIOD_RE.search(period_text)
        if match:
            period_start = match.group(1)
            period_end = match.group(2)

    day_headers = []
    header_cells = table.select("thead tr th")
    for th in header_cells[1:]:
        day_name_tag = th.select_one(".nowDay")
        day_date_tag = th.select_one(".nowDate")
        day_headers.append(
            {
                "day": _normalize_text(day_name_tag.get_text(" ", strip=True)) if day_name_tag else "",
                "date": _normalize_text(day_date_tag.get_text(" ", strip=True)) if day_date_tag else "",
            }
        )

    menus = []
    for row in table.select("tbody.dietData tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        info_cell = cells[0]
        title = ""
        price = ""
        sale_time = ""

        diet_title_tag = info_cell.select_one(".dietTitle")
        if diet_title_tag:
            title = _normalize_text(diet_title_tag.get_text(" ", strip=True))

        price_tag = info_cell.select_one(".dietPrice")
        if price_tag:
            price = _normalize_text(price_tag.get_text(" ", strip=True))

        time_tag = info_cell.select_one(".dietTime")
        if time_tag:
            sale_time = _normalize_text(time_tag.get_text(" ", strip=True))

        daily_menus = []
        for idx, menu_cell in enumerate(cells[1:]):
            pre_tag = menu_cell.select_one("pre")
            day_info = day_headers[idx] if idx < len(day_headers) else {"day": "", "date": ""}
            daily_menus.append(
                {
                    "day": day_info.get("day", ""),
                    "date": day_info.get("date", ""),
                    "items": _extract_lines(pre_tag),
                }
            )

        menus.append(
            {
                "title": title,
                "price": price,
                "sale_time": sale_time,
                "daily_menus": daily_menus,
            }
        )

    normalized_meal_type = _normalize_text(meal_type)
    if normalized_meal_type:
        if normalized_meal_type == "아침":
            menus = [menu for menu in menus if _is_breakfast_menu(menu.get("title", ""))]
        elif normalized_meal_type == "점심":
            menus = [menu for menu in menus if _is_lunch_menu(menu.get("title", ""))]
        else:
            raise ValueError("meal_type은 '아침', '점심' 또는 빈 문자열이어야 합니다.")

    return {
        "url": url,
        "section_name": _normalize_text(section_title_tag.get_text(" ", strip=True)) if section_title_tag else DEFAULT_SECTION_NAME,
        "meal_type": normalized_meal_type,
        "period": {
            "text": period_text,
            "start_date": period_start,
            "end_date": period_end,
        },
        "days": day_headers,
        "menus": menus,
    }