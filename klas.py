import json
import os
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime  
from pathlib import Path
from playwright.sync_api import BrowserContext
from pdfminer.high_level import extract_text
from bs4 import BeautifulSoup

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
                    task_no = task.get("taskNo")
                    subject_work_str += f"  📝 [과제] {title} (마감: {deadline}) [단축코드: subj={subj_code}, task={task_no}\n"
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

# 다운로드 폴더 설정
DOWNLOAD_DIR = Path("C:\\Users\\김성준\\klas_downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# --- [내부 유틸 함수] requests 쿠키를 Playwright에 넣기 ---
def _get_playwright_context_with_cookies(p: sync_playwright) -> BrowserContext:
    """공유 agent_session의 쿠키를 이식받은 가상 브라우저 컨텍스트를 반환합니다."""
    # headless=True로 해야 백그라운드에서 조용히 돕니다.
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True) # 다운로드 허용 필수!

    # requests.Session 주머니에서 쿠키 꺼내기
    requests_cookies = agent_session.cookies.get_dict()
    
    # Playwright 포맷으로 변환해서 넣기
    playwright_cookies = []
    for name, value in requests_cookies.items():
        # KLAS는 보통 mobileid.kw.ac.kr 나 klas.kw.ac.kr 도메인을 씁니다.
        # 안전하게 전체 도메인에 대해 세팅합니다.
        playwright_cookies.append({
            'name': name,
            'value': value,
            'url': 'https://klas.kw.ac.kr' 
        })
    
    context.add_cookies(playwright_cookies)
    return context

# --- 과제 게시글 본문 및 첨부파일 목록 긁기 ---
def fetch_assignment_post_body(subj_code: str, year: str, semester: str, task_no: int) -> str:
    """
    KLAS API를 직접 찔러 과제 상세 내용과 첨부파일 여부를 가져옵니다.
    로봇(Playwright) 렌더링 없이 0.1초 만에 본문을 긁어옵니다.
    """
    global is_logged_in
    if not is_logged_in: return "❌ KLAS 로그인 필요"

    url = "https://klas.kw.ac.kr/std/lis/evltn/TaskStdView.do"
    
    # 찾아주신 Payload 구조 완벽 반영!
    # 이전 목록(TaskStdList)에서 받은 task_no가 여기서 ordseq, weeklySeq로 쓰입니다.
    payload = {
        "pageInit": True,
        "selectYearhakgi": f"{year},{semester}",
        "selectSubj": subj_code,
        "selectChangeYn": "Y",
        "ordseq": str(task_no),
        "weeklySeq": str(task_no),
        "weeklySubSeq": "1"
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        # 공유 중인 쿠키 세션으로 다이렉트 API 호출
        response = agent_session.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        rpt = data.get("rpt", {})
        if not rpt:
            return "❌ 과제 상세 내용을 불러올 수 없습니다."
            
        title = rpt.get("title", "제목 없음")
        html_content = rpt.get("contents", "")
        
        # BeautifulSoup을 써서 지저분한 <p>, <br> 태그를 깔끔한 줄바꿈 텍스트로 변환!
        clean_text = BeautifulSoup(html_content, "html.parser").get_text(separator="\n", strip=True)
        
        # 제출 제한 및 첨부파일 정보 수집
        file_type = rpt.get("submitfiletype", "제한 없음")
        real_file = rpt.get("realfile")
        atch_file_id = rpt.get("atchFileId")
        
        # 클로드가 읽기 좋게 예쁜 마크다운 문자열로 조립
        result = f"📖 [과제 상세] {title}\n"
        result += "=" * 40 + "\n"
        result += f"{clean_text}\n"
        result += "=" * 40 + "\n"
        result += f"📌 제출 파일 형식: {file_type}\n"
        
        if real_file:
            result += f"📎 첨부파일: {real_file} (첨부파일 ID: {atch_file_id})\n"
        else:
            result += "📎 첨부파일: 없음\n"
            
        return result

    except Exception as e:
        return f"❌ 상세 조회 중 오류 발생: {str(e)}"

def perform_assignment_download(subj_code: str, year: str, semester: str, task_no: int, file_name: str) -> str:
    """
    Playwright를 이용해 상세 페이지에 접속, 특정 첨부파일 다운로드 버튼을 클릭합니다.
    """
    global is_logged_in
    if not is_logged_in: return "❌ KLAS 로그인 필요"

    try:
        with sync_playwright() as p:
            context = _get_playwright_context_with_cookies(p)
            page = context.new_page()
            
            # 1. 상세 페이지 이동 로직 (위의 fetch 함수와 동일)
            # ... 생략 ...
            
            # 2. 다운로드 이벤트 대기 설정 (🌟핵심!)
            with page.expect_download() as download_info:
                # 3. file_name을 포함하는 텍스트 링크를 찾아서 클릭! (닌자 클릭)
                # selector 패턴: text="파일명.pdf" 를 포함하는 <a> 태그
                page.locator(f"a:has-text('{file_name}')").click()
                
            download = download_info.value
            
            # 4. downloads/ 폴더에 실제 파일 이름으로 저장
            save_path = DOWNLOAD_DIR / download.suggested_filename
            download.save_as(save_path)
            
            context.close()
            return str(save_path) # 저장된 로컬 파일 경로 반환

    except Exception as e:
        return f"❌ 다운로드 오류: {str(e)}"

# --- [신규 기능 3] PDF 텍스트 추출 툴 ---
def extract_text_from_pdf(file_path: str) -> str:
    """로컬에 저장된 PDF 파일에서 텍스트를 추출하여 클로드에게 던집니다."""
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".pdf":
        return "❌ 오류: PDF 파일이 아니거나 존재하지 않습니다."
        
    try:
        # pdfminer가 PDF 전체를 텍스트로 싹 다 긁어줍니다!
        text = extract_text(path)
        # LLM context 제한이 있을 수 있으므로 너무 길면 자르는 로직을 두는 게 좋습니다.
        return text[:10000] # 일단 만 자만 자름
    except Exception as e:
        return f"❌ PDF 분석 실패: {str(e)}"   
