import requests
from bs4 import BeautifulSoup
import json

def get_kw_notices():
    # 광운대학교 공지사항 URL (실제 URL 구조에 맞게 수정 필요)
    url = "https://www.kw.ac.kr/ko/life/notice.jsp?srCategoryId=&mode=list&searchKey=1&searchVal="
    
    # 봇 차단을 막기 위해 일반 브라우저에서 접속한 척 위장(User-Agent)합니다.
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status() # 통신 에러 발생 시 프로그램 중단
    
    soup = BeautifulSoup(response.text, 'html.parser')
    notices = []
    
    # [주의] 아래 태그와 클래스명은 예시입니다. F12를 눌러 실제 구조에 맞게 변경해야 합니다.
    # 보통 게시판의 각 줄(row)을 감싸는 태그를 먼저 모두 찾습니다.
    board_rows = soup.select('.board-list-box li') 
    
    for row in board_rows:
        title_tag = row.select_one('.board-text a') # 제목과 링크가 있는 a 태그
        date_tag = row.select_one('.info-date')     # 작성일이 있는 태그
        
        if title_tag and date_tag:
            title = title_tag.text.strip()
            # 링크가 '/ko/life/...' 처럼 상대경로로 되어 있다면 앞부분을 붙여줍니다.
            link = title_tag['href']
            if link.startswith('/'):
                link = "https://www.kw.ac.kr" + link
                
            date = date_tag.text.strip()
            
            notices.append({
                "title": title,
                "date": date,
                "url": link
            })
            
    return notices

# 스크립트 실행 테스트
if __name__ == "__main__":
    result = get_kw_notices()
    # 결과를 한글 깨짐 없이 예쁜 JSON 형태로 터미널에 출력합니다.
    print(json.dumps(result, ensure_ascii=False, indent=2))