import re
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP

mcp = FastMCP("KW University Notices")

# 제목에서 제거할 불필요한 텍스트 패턴 목록
_TITLE_NOISE_PATTERNS = [
    r"비밀글일 경우 비밀글 아이콘 표시",
    r"뉴아이콘 첨부",
    r"새글",
    r"new",
]
_TITLE_NOISE_RE = re.compile(
    "|".join(_TITLE_NOISE_PATTERNS), re.IGNORECASE
)


def _clean_title(raw: str) -> str:
    """불필요한 아이콘 설명 텍스트를 제목에서 제거합니다."""
    cleaned = _TITLE_NOISE_RE.sub("", raw)
    return " ".join(cleaned.split())


@mcp.tool()
def get_kw_notices() -> list[dict]:
    """광운대학교 공지사항 목록을 가져옵니다.

    Returns:
        공지사항 목록. 각 항목은 title, date, url 키를 가집니다.
    """
    url = (
        "https://www.kw.ac.kr/ko/life/notice.jsp"
        "?srCategoryId=&mode=list&searchKey=1&searchVal="
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("광운대학교 서버 요청 시간이 초과되었습니다.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("광운대학교 서버에 연결할 수 없습니다.")
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"HTTP 오류가 발생했습니다: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"요청 중 오류가 발생했습니다: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    notices = []

    board_rows = soup.select(".board-list-box li")

    for row in board_rows:
        title_tag = row.select_one(".board-text a")
        date_tag = row.select_one(".info-date")

        if title_tag and date_tag:
            title = _clean_title(title_tag.text)
            link = title_tag.get("href", "")
            if link.startswith("/"):
                link = "https://www.kw.ac.kr" + link
            date = date_tag.text.strip()

            if title and link:
                notices.append({"title": title, "date": date, "url": link})

    return notices


if __name__ == "__main__":
    mcp.run()
