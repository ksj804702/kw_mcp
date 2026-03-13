from fastmcp import FastMCP

from notices import get_kw_notices as fetch_kw_notices

mcp = FastMCP("KW University Notices")


@mcp.tool()
def get_kw_notices(
    keyword: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict]:
    """광운대학교 공지사항 목록을 반환합니다.

    Args:
        keyword: 제목/카테고리 필터용 검색어.
            빈 문자열이면 전체 공지사항을 반환합니다.
        date_from: 작성일 시작일(YYYY-MM-DD).
        date_to: 작성일 종료일(YYYY-MM-DD).
    """
    # MCP 클라이언트에서 전달된 keyword를 그대로 수집 함수에 위임합니다.
    return fetch_kw_notices(
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )


if __name__ == "__main__":
    mcp.run()
