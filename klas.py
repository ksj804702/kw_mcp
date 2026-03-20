import json

import requests
from playwright.sync_api import sync_playwright

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
