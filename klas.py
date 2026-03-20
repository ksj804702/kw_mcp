import json

from playwright.sync_api import sync_playwright


def login_klas_action(student_id: str, password: str) -> str:
    """광운대학교 KLAS 로그인 후 세션 쿠키를 반환합니다."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
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
                browser.close()
                return json.dumps(
                    {
                        "status": "success",
                        "message": "✅ KLAS 로그인 성공! 세션 쿠키를 확보했습니다.",
                        "cookies": cookies,
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            browser.close()
            return "❌ 로그인 실패: 아이디/비밀번호를 확인하세요."
    except Exception as e:
        return f"❌ KLAS 로그인 중 치명적 오류 발생: {str(e)}"
