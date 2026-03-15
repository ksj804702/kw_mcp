from fastapi import FastAPI
from fastapi.responses import JSONResponse
import json

# 1. 아까 빼먹은 핵심 도구들까지 전부 다 수입해옵니다!
from server import (
    get_library_seats, 
    get_study_room_status, 
    get_kw_academic_calendar,
    get_kw_notices,          # 추가됨
    get_kw_notice_content,   # 추가됨
    get_kw_student_meal      # 추가됨
)

app = FastAPI(
    title="광운대학교 비공식 API 서버",
    description="안드로이드 앱 통신을 위한 캠퍼스 통합 API",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {"message": "광운대 API 서버가 정상 작동 중입니다! 🚀"}

@app.get("/api/library/seats")
def get_seats():
    """중앙도서관 열람실 실시간 좌석 현황을 반환합니다."""
    # 우리가 만든 함수는 JSON '문자열'을 반환하므로, 
    # FastAPI가 예쁘게 처리할 수 있도록 파이썬 딕셔너리로 다시 변환해줍니다.
    raw_data = get_library_seats()
    data = json.loads(raw_data) 
    return JSONResponse(content=data)

@app.get("/api/library/studyroom")
def get_studyroom(room_type: str = "6", search_date: str = ""):
    """그룹스터디룸 예약 현황을 반환합니다."""
    raw_data = get_study_room_status(room_type=room_type, search_date=search_date)
    # 에러 메시지가 문자열로 올 경우를 대비한 예외 처리
    try:
        data = json.loads(raw_data)
        return JSONResponse(content=data)
    except:
        return {"error": raw_data}

@app.get("/api/calendar")
def get_calendar(year: str = "", month: str = ""):
    """광운대학교 학사일정을 반환합니다."""
    # 달력은 이미 dict 형태로 반환하도록 고쳤었죠!
    data = get_kw_academic_calendar(year=year, month=month)
    return JSONResponse(content=data)

@app.get("/api/notices")
def get_notices(search_key: int = 1, search_val: str = ""):
    """
    광운대학교 공지사항 목록을 검색합니다.
    - search_key: 1=제목, 2=내용, 3=제목+내용, 4=작성자
    """
    # 파이썬 리스트/딕셔너리 형태로 바로 반환되는 함수들이므로 그대로 JSONResponse에 꽂습니다.
    data = get_kw_notices(search_key=search_key, search_val=search_val)
    return JSONResponse(content=data)

@app.get("/api/notices/detail")
def get_notice_detail(notice_url: str):
    """
    특정 공지사항의 본문 텍스트를 추출합니다.
    - notice_url: 공지사항 상세 URL 파라미터
    """
    data = get_kw_notice_content(notice_url=notice_url)
    return JSONResponse(content=data)

@app.get("/api/meals")
def get_meals(meal_type: str = ""):
    """
    광운대학교 학생식당 식단을 조회합니다.
    - meal_type: "아침" 또는 "점심" (비우면 전체)
    """
    data = get_kw_student_meal(meal_type=meal_type)
    
    # 만약 학식 데이터가 JSON 문자열(String)로 반환되게 짜두셨다면 딕셔너리로 변환
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"error": "학식 데이터를 파싱할 수 없습니다.", "raw_data": data}
            
    return JSONResponse(content=data)