from fastmcp import FastMCP

from notices import get_kw_notices as fetch_kw_notices
from notices import get_kw_notice_content as fetch_kw_notice_content
from notices import get_kw_academic_calendar as fetch_kw_academic_calendar
from cafeteria import get_kw_student_meal as fetch_kw_student_meal
import xml.etree.ElementTree as ET
import requests
import json
from datetime import datetime 
import base64

mcp = FastMCP("KW University Notices")


@mcp.tool()
def get_kw_notices(
    search_key: int = 1,
    search_val: str = "",
) -> list[dict]:
    """광운대학교 공지사항 목록을 반환합니다.

    Args:
        search_key: 사이트 검색 기준(1=제목, 2=내용, 3=제목+내용, 4=작성자).
        search_val: 사이트 검색어(searchVal).
    """
    # MCP 클라이언트에서 전달된 검색 조건을 수집 함수에 그대로 위임합니다.
    return fetch_kw_notices(
        search_key=search_key,
        search_val=search_val,
    )


@mcp.tool()
def get_kw_notice_content(notice_url: str) -> dict:
    """공지 상세 URL을 받아 게시글 제목/작성일/본문을 반환합니다.

    Args:
        notice_url: 공지 상세 URL(절대 URL 또는 '/'로 시작하는 상대 URL).
    """
    return fetch_kw_notice_content(notice_url)


@mcp.tool()
def get_kw_academic_calendar(year: str = "", month: str = "") -> dict:
    """광운대학교 학사일정 데이터만 반환합니다."""
    
    # 1. 원본 데이터를 받아옵니다.
    data = fetch_kw_academic_calendar(year=year, month=month)
    
    if "schedules" in data:
        schedules = data["schedules"]
        
        # 2. 파이썬에서 완벽하게 월 순서(1~12)로 오름차순 정렬합니다.
        sorted_items = sorted(
            schedules.items(),
            key=lambda x: int(''.join(filter(str.isdigit, str(x[0])))) if ''.join(filter(str.isdigit, str(x[0]))) else 99
        )
        
        # 3. 핵심(해킹): JS가 순서를 못 바꾸게 키값 뒤에 '월'을 붙여줍니다!
        # {"02": [...]} -> {"02월": [...]} 로 변환
        final_schedules = {f"{k}월" if not str(k).endswith('월') else k: v for k, v in sorted_items}
        
        data["schedules"] = final_schedules
        
    return data


@mcp.tool()
def get_kw_student_meal(meal_type: str = "") -> dict:
    """광운대학교 학생식당 주간 식단을 조회합니다.

    Args:
        meal_type: 식사 구분("아침", "점심"). 비우면 전체 반환.
    """
    return fetch_kw_student_meal(meal_type=meal_type)

@mcp.tool()
def get_study_room_status(room_type: str = "6", search_date: str = "") -> str:
    """광운대학교 중앙도서관 그룹스터디룸(집현실 등) 예약 현황을 조회합니다.
    
    Args:
        room_type: 스터디룸 종류 ('4a', '4b', '6', '10' 중 하나). 기본값은 '6'.
        search_date: 조회할 날짜 (YYYYMMDD 형식). 비워두면 오늘 날짜로 자동 조회합니다.
    """
    # 날짜 입력이 없으면 오늘 날짜로 자동 세팅
    if not search_date:
        search_date = datetime.now().strftime("%Y%m%d")
        
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_Study_Room_Map.php"
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    payload = {
        "room_seat_no": room_type,
        "search_date": search_date
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        item = root.find('item')
        if item is None:
            return "스터디룸 데이터를 찾을 수 없습니다."
            
        # 1. 방 이름 맵핑 추출 (room_name_0, room_name_1 ...)
        rooms = {}
        for i in range(20): # 넉넉하게 20번 인덱스까지 검사
            name_elem = item.find(f'room_name_{i}')
            if name_elem is not None and name_elem.text and name_elem.text.strip():
                # CDATA로 묶인 방 이름을 가져옵니다.
                rooms[i] = {"room_name": name_elem.text.strip(), "schedule": []}
                
        if not rooms:
            return f"{search_date} 일자의 {room_type}인실 데이터가 없습니다."
            
        # 2. 시간대별 상태 추출
        for time_list in item.findall('time_list'):
            time_period_elem = time_list.find('time_period')
            if time_period_elem is None or not time_period_elem.text:
                continue
                
            raw_time = time_period_elem.text.strip()
            # "09000955" 같은 문자열을 "09:00~09:55"로 예쁘게 포맷팅
            if len(raw_time) == 8:
                formatted_time = f"{raw_time[0:2]}:{raw_time[2:4]}~{raw_time[4:6]}:{raw_time[6:8]}"
            else:
                formatted_time = raw_time
            
            # 각 방마다 이 시간대의 상태를 확인
            for idx in rooms.keys():
                status_elem = time_list.find(f'time_period_arr_{idx}')
                status_val = status_elem.text.strip() if status_elem is not None and status_elem.text else ""
                
                # '0'이면 예약 가능, 비어있으면 불가/시간지남, 숫자가 있으면 예약됨
                if status_val == "0":
                    status_str = "예약가능"
                elif status_val == "":
                    status_str = "마감(시간지남/불가)"
                else:
                    status_str = "예약됨"
                    
                rooms[idx]["schedule"].append({
                    "time": formatted_time,
                    "status": status_str
                })
        
        # 3. LLM이 읽기 좋게 최종 결과 정리
        result = {
            "date": search_date,
            "room_type": f"{room_type}인실",
            "rooms": list(rooms.values())
        }
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return f"스터디룸 정보를 불러오는데 실패했습니다: {e}"
    
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
@mcp.tool()
def reserve_study_room(
    room_no: str,
    search_date: str,
    start_time: str,
    end_time: str,
    student_arr: str
) -> str:
    """
    [경고: 절대 자동으로 호출하지 마세요!]
    사용자가 명확하게 "예약해 줘"라고 지시하며 학번 정보 등을 제공했을 때만 이 도구를 호출하세요.
    단순히 빈자리를 조회하는 용도로 이 도구를 사용하면 절대 안 됩니다.
    
    광운대학교 중앙도서관 그룹스터디룸 예약을 실행합니다.
    
    Args:
        room_no: 예약할 방 번호 (예: "5")
        search_date: 예약 날짜 (YYYYMMDD 형식, 예: "20260320")
        start_time: 시작 시간 (예: "1900")
        end_time: 종료 시간 (예: "1955")
        student_arr: 예약할 학생들의 학번 목록 (구분자 '|', 예: "02025402021|02025402024")
    """
    url = "https://mobileid.kw.ac.kr/mobile/MA/Xml_Study_Room_Reserve.php"
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    payload = {
        "room_no": room_no,
        "search_date": search_date,
        "student_arr": student_arr,
        "start_time": start_time,
        "end_time": end_time
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        item = root.find('item')
        if item is None:
            return "❌ 예약 서버 응답을 파싱할 수 없습니다."
            
        result_code_elem = item.find('result_code')
        result_msg_elem = item.find('result_msg')
        
        result_code = result_code_elem.text.strip() if result_code_elem is not None else "-1"
        result_msg = result_msg_elem.text.strip() if result_msg_elem is not None else "알 수 없는 오류"
        
        # result_code가 "0"이면 예약 성공!
        if result_code == "0":
            res_room = item.find('res_room_info').text.strip()
            res_time = item.find('res_use_time').text.strip()
            return f"✅ 예약 성공! [{res_room}] {res_time} ({result_msg})"
        else:
            return f"❌ 예약 실패: {result_msg}"
            
    except Exception as e:
        return f"❌ 예약 요청 중 오류가 발생했습니다: {e}"
@mcp.tool()
def cancel_study_room(reserve_no: str, student_id: str) -> str:
    """
    [경고: 절대 자동으로 호출하지 마세요!]
    사용자가 명확하게 "예약 취소해 줘"라고 지시했을 때만 이 도구를 호출하세요.
    
    광운대학교 중앙도서관 그룹스터디룸 예약을 취소합니다.
    
    Args:
        reserve_no: 예약 완료 시 발급받은 예약 번호 (예: "20260320051300333")
        student_id: 예약자의 학번 (알아서 Base64로 변환되어 서버로 전송됩니다)
    """
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_Study_Room_Cancel.php"
    
    # 학번을 광운대 서버가 요구하는 Base64 형태(real_id)로 자동 인코딩
    real_id_bytes = base64.b64encode(student_id.encode('utf-8'))
    real_id = real_id_bytes.decode('utf-8')
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    payload = {
        "reserve_no": reserve_no,
        "real_id": real_id
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        item = root.find('item')
        if item is None:
            return "❌ 취소 서버 응답을 파싱할 수 없습니다."
            
        result_code_elem = item.find('result_code')
        result_msg_elem = item.find('result_msg')
        
        result_code = result_code_elem.text.strip() if result_code_elem is not None else "-1"
        result_msg = result_msg_elem.text.strip() if result_msg_elem is not None else "알 수 없는 오류"
        
        if result_code == "0":
            return f"✅ {result_msg}"
        else:
            return f"❌ 예약 취소 실패: {result_msg}"
            
    except Exception as e:
        return f"❌ 예약 취소 요청 중 오류가 발생했습니다: {e}"
@mcp.tool()
def get_my_seat_status(student_id: str) -> str:
    """
    광운대학교 중앙도서관 일반 열람실 좌석 및 그룹스터디룸 나의 예약/발권 현황을 조회합니다.
    예약을 취소하기 위해 reserve_no가 필요할 때 이 도구를 먼저 사용하세요.
    
    Args:
        student_id: 조회할 학생의 학번
    """
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_mySeat_Status_list.php"
    
    # 학번 Base64 인코딩
    real_id_bytes = base64.b64encode(student_id.encode('utf-8'))
    real_id = real_id_bytes.decode('utf-8')
    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    payload = {
        "real_id": real_id
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        item = root.find('item')
        
        if item is None:
            return "❌ 서버 응답을 파싱할 수 없습니다."
            
        result_code = item.findtext('result_code', default="").strip()
        
        if result_code != "0":
            return "❌ 조회 실패 (학번 또는 서버 상태를 확인하세요)"

        # 1. 스터디룸 예약 번호가 있는지 먼저 확인
        study_reserve_no = item.findtext('study_reserve_no', default="").strip()
        
        # 2. 일반 열람실 발권 정보가 있는지 확인
        seat_room_name = item.findtext('seat_room_name', default="").strip()
        
        if study_reserve_no:
            # 스터디룸 예약이 있는 경우
            result = {
                "type": "그룹스터디룸",
                "room_name": item.findtext('study_sroom_name', default="").strip(),
                "date": item.findtext('study_reserve_date', default="").strip(),
                "time": item.findtext('study_use_time', default="").strip(),
                "status": item.findtext('study_reserve_stat', default="").strip(),
                "reserve_no": study_reserve_no
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        elif seat_room_name:
            # 일반 열람실 발권이 있는 경우
            result = {
                "type": "일반열람실",
                "room_name": seat_room_name,
                "seat_no": item.findtext('seat_seat_no', default="").strip(),
                "start_time": item.findtext('seat_start_time', default="").strip(),
                "end_time": item.findtext('seat_end_time', default="").strip()
            }
            return json.dumps(result, ensure_ascii=False, indent=2)
            
        else:
            return "현재 예약되거나 발권된 좌석이 없습니다."
            
    except Exception as e:
        return f"❌ 조회 요청 중 오류가 발생했습니다: {e}"
if __name__ == "__main__":
    mcp.run()
