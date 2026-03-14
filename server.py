from fastmcp import FastMCP

from notices import get_kw_notices as fetch_kw_notices
import xml.etree.ElementTree as ET
import requests
import json

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

@mcp.tool()
def get_library_seats() -> str:
    """광운대학교 중앙도서관의 각 열람실별 실시간 잔여 좌석 현황을 조회합니다."""
    
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_seat_status_list.php" 
    
    # 1. 헤더 설정 (앱에서 보낸 것과 똑같이 위장)
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)'
    }
    
    # 2. 방금 찾아낸 핵심 파라미터 (Body 데이터)
    payload = {
        "lib_gb": "L"
    }
    
    try:
        # 3. 핵심 포인트: get이 아니라 post로 요청하고 data에 payload를 넣습니다!
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        # XML 데이터 파싱
        root = ET.fromstring(response.text)
        
        seat_info = []
        for item in root.findall('item'):
            # 데이터가 비어있을 경우(None)를 대비한 안전한 텍스트 추출
            room_name_elem = item.find('room_name')
            room_name = room_name_elem.text.strip() if room_name_elem is not None and room_name_elem.text else "알수없음"
            
            total_seat_elem = item.find('total_seat')
            total_seat = int(total_seat_elem.text.strip()) if total_seat_elem is not None and total_seat_elem.text else 0
            
            use_seat_elem = item.find('use_seat')
            use_seat = int(use_seat_elem.text.strip()) if use_seat_elem is not None and use_seat_elem.text else 0
            
            remain_seat_elem = item.find('remain_seat')
            remain_seat = int(remain_seat_elem.text.strip()) if remain_seat_elem is not None and remain_seat_elem.text else 0
            
            use_rate_elem = item.find('use_rate')
            use_rate = float(use_rate_elem.text.strip()) if use_rate_elem is not None and use_rate_elem.text else 0.0
            
            # 의미 없는 데이터(총 좌석이 0인 곳 등)는 제외하고 추가
            if total_seat > 0:
                seat_info.append({
                    "room_name": room_name,
                    "total_seat": total_seat,
                    "use_seat": use_seat,
                    "remain_seat": remain_seat,
                    "use_rate_percent": use_rate
                })
            
        return json.dumps(seat_info, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"도서관 좌석 정보를 불러오는데 실패했습니다: {e}"

if __name__ == "__main__":
    mcp.run()
