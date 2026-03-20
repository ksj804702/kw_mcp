from fastmcp import FastMCP

from cafeteria import get_kw_student_meal as fetch_kw_student_meal
from klas import fetch_klas_timetable
from klas import perform_klas_login
from klas import fetch_uncompleted_work
from klas import fetch_assignment_post_body
from klas import perform_assignment_download
from klas import extract_text_from_pdf
from library import cancel_study_room_action
from library import fetch_library_seats
from library import fetch_my_seat_status
from library import fetch_study_room_status
from library import reserve_study_room_action
from notices import get_kw_academic_calendar_for_mcp as fetch_kw_academic_calendar
from notices import get_kw_notice_content as fetch_kw_notice_content
from notices import get_kw_notices as fetch_kw_notices

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
    return fetch_kw_academic_calendar(year=year, month=month)


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
    return fetch_study_room_status(room_type=room_type, search_date=search_date)
    
@mcp.tool()
def get_library_seats() -> str:
    """광운대학교 중앙도서관의 각 열람실별 실시간 잔여 좌석 현황을 조회합니다."""
    return fetch_library_seats()
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
    return reserve_study_room_action(
        room_no=room_no,
        search_date=search_date,
        start_time=start_time,
        end_time=end_time,
        student_arr=student_arr,
    )
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
    return cancel_study_room_action(reserve_no=reserve_no, student_id=student_id)
@mcp.tool()
def get_my_seat_status(student_id: str) -> str:
    """
    광운대학교 중앙도서관 일반 열람실 좌석 및 그룹스터디룸 나의 예약/발권 현황을 조회합니다.
    예약을 취소하기 위해 reserve_no가 필요할 때 이 도구를 먼저 사용하세요.
    
    Args:
        student_id: 조회할 학생의 학번
    """
    return fetch_my_seat_status(student_id=student_id)
@mcp.tool()
def login_klas(student_id: str, password: str) -> str:
    """
    광운대학교 종합정보시스템(KLAS)에 자동 로그인하여 세션을 유지합니다.
    이 로그인 이후 시간표, 과제 등의 로그인 필수 데이터를 조회할 수 있습니다.
    
    Args:
        student_id: 학번
        password: KLAS 비밀번호
    """
    return perform_klas_login(student_id=student_id, password=password)


@mcp.tool()
def get_klas_timetable(year: str = "2026", semester: str = "1") -> str:
    """
    KLAS 로그인 후 시간표를 조회합니다.
    반드시 login_klas을 먼저 호출해서 로그인을 완료해야 합니다.
    
    Args:
        year: 학년도 (기본값 "2026")
        semester: 학기 ("1" 또는 "2", 기본값 "1")
    """
    return fetch_klas_timetable(year=year, semester=semester)

@mcp.tool()
def get_klas_todo(year: str = "2026", semester: str = "1") -> str:
    """
    [경고] 반드시 login_klas 도구를 먼저 사용한 후 호출하세요.
    수강 중인 모든 과목을 스캔하여 '제출하지 않은 과제(미제출)'와 '다 듣지 않은 온라인 강의(미수강)' 목록을 모두 찾아줍니다.
    """
    return fetch_uncompleted_work(year, semester)
@mcp.tool()
def get_klas_todo_detail(subj_code: str, year: str, semester: str, task_no: int) -> str:
    """
    [경고] login_klas 사용 후 호출하세요. get_klas_todo에서 확인한 subj_code, task_no 등을 
    입력하여 해당 과제의 상세 게시글 본문과 첨부파일 목록을 긁어옵니다.
    """
    # ⚠️ 위 klas.py 코드에서 드롭다운 조작 로직이 생략되어 dummy 데이터를 반환합니다.
    # 실제 구현 시 가장 많은 reverse engineering이 필요한 부분입니다.
    return fetch_assignment_post_body(subj_code, year, semester, task_no)

@mcp.tool()
def download_klas_file(subj_code: str, year: str, semester: str, task_no: int, file_name: str) -> str:
    """
    [경고] login_klas 사용 후 호출하세요. 과제 상세 페이지에서 특정 첨부파일을 
    'downloads/' 폴더로 다운로드하고 로컬 파일 경로를 반환합니다.
    """
    return perform_assignment_download(subj_code, year, semester, task_no, file_name)

@mcp.tool()
def analyze_pdf_file(file_path: str) -> str:
    """
    download_klas_file로 다운로드한 PDF 파일의 경로를 입력받아 내부 텍스트를 싹 다 긁어서 보여줍니다.
    """
    return extract_text_from_pdf(file_path)
if __name__ == "__main__":
    mcp.run()
