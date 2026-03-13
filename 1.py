import argparse
import json

import requests

from notices import get_kw_notices


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(description="광운대학교 공지사항 조회")
    parser.add_argument(
        "-k",
        "--keyword",
        default="",
        help="제목/카테고리 검색어 (예: 국제학생, 장학)",
    )
    parser.add_argument(
        "--date-from",
        default="",
        help="작성일 시작일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date-to",
        default="",
        help="작성일 종료일 (YYYY-MM-DD)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # 사용자가 전달한 검색어를 읽어 필터 조회에 사용합니다.
    args = parse_args()
    try:
        result = get_kw_notices(
            keyword=args.keyword,
            date_from=args.date_from,
            date_to=args.date_to,
        )
    except ValueError as exc:
        raise SystemExit(f"입력값 오류: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise SystemExit(f"공지사항을 가져오지 못했습니다: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
