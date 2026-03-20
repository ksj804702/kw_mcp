import json

import requests
from playwright.sync_api import sync_playwright
from datetime import datetime  

# 🌟 KLAS 전용 공용 쿠키 주머니 (이 파일 안의 모든 함수가 공유합니다)
agent_session = requests.Session()
is_logged_in = False


def perform_klas_login(student_id: str, password: str) -> str:
    """KLAS 자동 로그인 (server.py에서 호출할 순수 함수)"""
    global is_logged_in

    # 이미 로그인되어 있으면 스킵
    if is_logged_in:
        return "✅ 이미 KLAS에 로그인되어 있습니다."

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # 백그라운드 실행
            context = browser.new_context()
            page = context.new_page()

            page.on("dialog", lambda dialog: dialog.accept())
            page.goto("https://klas.kw.ac.kr/")
            page.locator("#loginId").fill(student_id)
            page.locator("#loginPwd").fill(password)
            page.locator("button[type='submit']").click()

            page.wait_for_load_state("networkidle")

            if "login" not in page.url.lower():
                cookies = context.cookies()

                # 🔥 [핵심] Playwright가 얻은 쿠키를 파이썬 requests 세션에 저장
                for cookie in cookies:
                    agent_session.cookies.set(
                        cookie["name"], cookie["value"], domain=cookie["domain"]
                    )

                is_logged_in = True
                browser.close()
                return "✅ KLAS 로그인 성공! 세션이 유지됩니다."
            else:
                browser.close()
                return "❌ 로그인 실패 (아이디/비번 확인)"
    except Exception as e:
        return f"❌ 로그인 오류: {str(e)}"


def fetch_klas_timetable(year: str = "2026", semester: str = "1") -> str:
    """시간표 조회 (server.py에서 호출할 순수 함수)"""
    global is_logged_in

    if not is_logged_in:
        return "❌ 오류: KLAS에 먼저 로그인해야 시간표를 볼 수 있습니다."

    url = "https://klas.kw.ac.kr/std/cps/atnlc/TimetableStdList.do"
    payload = {
        "searchYear": year,
        "searchHakgi": semester,
        "searchPgmNo": "2003041",
        "atnlcYearList": [],
        "list": [],
        "timeTableList": [],
    }
    headers = {"Content-Type": "application/json"}

    try:
        # 공유 중인 agent_session을 사용해 요청 (쿠키 자동 포함)
        response = agent_session.post(url, json=payload, headers=headers)
        response.raise_for_status()

        timetable_data = response.json()
        result_text = f"📅 {year}학년도 {semester}학기 시간표\n"
        days = {"1": "월", "2": "화", "3": "수", "4": "목", "5": "금"}

        for row in timetable_data:
            time_period = row.get("wtTime")
            if str(row.get("wtHasSchedule")) == "N":
                continue

            for day_num, day_str in days.items():
                if row.get(f"wtSubjNm_{day_num}"):
                    subject = row.get(f"wtSubjNm_{day_num}")
                    room = row.get(f"wtLocHname_{day_num}", "미정")
                    prof = row.get(f"wtProfNm_{day_num}", "미정")
                    result_text += f"[{day_str}] {time_period}교시: {subject} ({prof} 교수, {room})\n"

        return result_text
    except Exception as e:
        return f"❌ 시간표 조회 중 오류 발생: {str(e)}"
    
def fetch_uncompleted_work(year: str = "2026", semester: str = "1") -> str:
    """수강 중인 모든 과목을 스캔하여 '미제출 과제'와 '미수강 인강'을 모아서 반환합니다."""
    global is_logged_in
    if not is_logged_in:
        return "❌ 오류: KLAS에 먼저 로그인해야 과제와 강의를 볼 수 있습니다."

    # 현재 시각 구하기 (기한 비교용)
    now = datetime.now()

    # 1단계: 시간표 API로 내 '수강 과목 코드' 목록 수집
    timetable_url = "https://klas.kw.ac.kr/std/cps/atnlc/TimetableStdList.do"
    tt_payload = {
        "searchYear": year, "searchHakgi": semester, "searchPgmNo": "2003041",
        "atnlcYearList": [], "list": [], "timeTableList": []
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        tt_response = agent_session.post(timetable_url, json=tt_payload, headers=headers)
        tt_response.raise_for_status()
        timetable_data = tt_response.json()
        
        my_subjects = {}
        for row in timetable_data:
            for i in range(1, 6): 
                subj_code = row.get(f"wtSubj_{i}")
                subj_name = row.get(f"wtSubjNm_{i}")
                if subj_code and subj_name:
                    my_subjects[subj_code] = subj_name
                    
        # 2단계: 수집한 과목 코드로 과제 & 인강 API 순회
        task_url = "https://klas.kw.ac.kr/std/lis/evltn/TaskStdList.do"
        vod_url = "https://klas.kw.ac.kr/std/lis/evltn/SelectOnlineCntntsStdList.do"
        
        result_text = "🚨 [미완료된 과제 및 온라인 강의 알림]\n\n"
        has_work = False
        
        for subj_code, subj_name in my_subjects.items():
            subject_work_str = "" # 각 과목별로 할 일을 모을 임시 문자열
            
            # --- (A) 과제 조회 ---
            payload = {
                "selectYearhakgi": f"{year},{semester}",
                "selectSubj": subj_code,
                "selectChangeYn": "Y"
            }
            task_response = agent_session.post(task_url, json=payload, headers=headers)
            tasks = task_response.json()
            
            for task in tasks:
                if task.get("submityn") == "N" and task.get("indate") == "Y":
                    title = task.get("title")
                    deadline = task.get("expiredate")
                    subject_work_str += f"  📝 [과제] {title} (마감: {deadline})\n"
                    has_work = True

            # --- (B) 인강(VOD) 조회 ---
            vod_response = agent_session.post(vod_url, json=payload, headers=headers)
            vods = vod_response.json()
            
            for vod in vods:
                prog = vod.get("prog", 0)
                end_date_str = vod.get("endDate") # "2026-03-25 23:59"
                
                # 문자열 날짜를 datetime 객체로 변환하여 현재 시각과 비교
                try:
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
                    is_active = now <= end_date
                except:
                    is_active = True # 날짜 파싱 실패 시 일단 보여줌

                # 진도율이 100%가 아니고, 아직 수강 기간이 안 끝났다면!
                if prog < 100 and is_active:
                    title = vod.get("moduletitle")
                    subject_work_str += f"  ▶️ [인강] {title} (진도율: {prog}%, 마감: {end_date_str})\n"
                    has_work = True
                    
            # 해당 과목에 할 일이 하나라도 있으면 결과 텍스트에 추가
            if subject_work_str:
                result_text += f"📚 [{subj_name}]\n{subject_work_str}\n"
                    
        if not has_work:
            return "🎉 축하합니다! 모든 과제와 온라인 강의를 완료하셨습니다. 편안하게 쉬세요!"
            
        return result_text

    except Exception as e:
        return f"❌ 과제/강의 조회 중 오류 발생: {str(e)}"    
