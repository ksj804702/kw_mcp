import argparse
import json

import requests

from notices import get_kw_notices


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(description="광운대학교 공지사항 조회")
    parser.add_argument(
        "--search-key",
        type=int,
        default=1,
        help="검색 기준 (1=제목, 2=내용, 3=제목+내용, 4=작성자)",
    )
    parser.add_argument(
        "--search-val",
        default="",
        help="사이트 검색어 (searchVal)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    # 사용자가 전달한 사이트 검색 조건과 날짜 조건으로 조회합니다.
    args = parse_args()
    try:
        result = get_kw_notices(
            search_key=args.search_key,
            search_val=args.search_val,
        )
    except ValueError as exc:
        raise SystemExit(f"입력값 오류: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise SystemExit(f"공지사항을 가져오지 못했습니다: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
