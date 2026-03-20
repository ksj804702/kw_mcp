import base64
import json
from datetime import datetime
import xml.etree.ElementTree as ET

import requests


USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 16; 2412DPC0AG Build/BP2A.250605.031.A3)"


def _encode_student_id(student_id: str) -> str:
    real_id_bytes = base64.b64encode(student_id.encode("utf-8"))
    return real_id_bytes.decode("utf-8")


def fetch_study_room_status(room_type: str = "6", search_date: str = "") -> str:
    """광운대학교 중앙도서관 그룹스터디룸 예약 현황을 조회합니다."""
    if not search_date:
        search_date = datetime.now().strftime("%Y%m%d")

    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_Study_Room_Map.php"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "room_seat_no": room_type,
        "search_date": search_date,
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        item = root.find("item")
        if item is None:
            return "스터디룸 데이터를 찾을 수 없습니다."

        rooms = {}
        for i in range(20):
            name_elem = item.find(f"room_name_{i}")
            if name_elem is not None and name_elem.text and name_elem.text.strip():
                rooms[i] = {"room_name": name_elem.text.strip(), "schedule": []}

        if not rooms:
            return f"{search_date} 일자의 {room_type}인실 데이터가 없습니다."

        for time_list in item.findall("time_list"):
            time_period_elem = time_list.find("time_period")
            if time_period_elem is None or not time_period_elem.text:
                continue

            raw_time = time_period_elem.text.strip()
            if len(raw_time) == 8:
                formatted_time = f"{raw_time[0:2]}:{raw_time[2:4]}~{raw_time[4:6]}:{raw_time[6:8]}"
            else:
                formatted_time = raw_time

            for idx in rooms.keys():
                status_elem = time_list.find(f"time_period_arr_{idx}")
                status_val = status_elem.text.strip() if status_elem is not None and status_elem.text else ""

                if status_val == "0":
                    status_str = "예약가능"
                elif status_val == "":
                    status_str = "마감(시간지남/불가)"
                else:
                    status_str = "예약됨"

                rooms[idx]["schedule"].append(
                    {
                        "time": formatted_time,
                        "status": status_str,
                    }
                )

        result = {
            "date": search_date,
            "room_type": f"{room_type}인실",
            "rooms": list(rooms.values()),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"스터디룸 정보를 불러오는데 실패했습니다: {e}"


def fetch_library_seats() -> str:
    """광운대학교 중앙도서관 각 열람실별 실시간 잔여 좌석 현황을 조회합니다."""
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_seat_status_list.php"
    headers = {
        "User-Agent": USER_AGENT,
    }
    payload = {
        "lib_gb": "L",
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        root = ET.fromstring(response.text)

        seat_info = []
        for item in root.findall("item"):
            room_name_elem = item.find("room_name")
            room_name = room_name_elem.text.strip() if room_name_elem is not None and room_name_elem.text else "알수없음"

            total_seat_elem = item.find("total_seat")
            total_seat = int(total_seat_elem.text.strip()) if total_seat_elem is not None and total_seat_elem.text else 0

            use_seat_elem = item.find("use_seat")
            use_seat = int(use_seat_elem.text.strip()) if use_seat_elem is not None and use_seat_elem.text else 0

            remain_seat_elem = item.find("remain_seat")
            remain_seat = int(remain_seat_elem.text.strip()) if remain_seat_elem is not None and remain_seat_elem.text else 0

            use_rate_elem = item.find("use_rate")
            use_rate = float(use_rate_elem.text.strip()) if use_rate_elem is not None and use_rate_elem.text else 0.0

            if total_seat > 0:
                seat_info.append(
                    {
                        "room_name": room_name,
                        "total_seat": total_seat,
                        "use_seat": use_seat,
                        "remain_seat": remain_seat,
                        "use_rate_percent": use_rate,
                    }
                )

        return json.dumps(seat_info, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"도서관 좌석 정보를 불러오는데 실패했습니다: {e}"


def reserve_study_room_action(
    room_no: str,
    search_date: str,
    start_time: str,
    end_time: str,
    student_arr: str,
) -> str:
    """광운대학교 중앙도서관 그룹스터디룸 예약을 실행합니다."""
    url = "https://mobileid.kw.ac.kr/mobile/MA/Xml_Study_Room_Reserve.php"
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "room_no": room_no,
        "search_date": search_date,
        "student_arr": student_arr,
        "start_time": start_time,
        "end_time": end_time,
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        item = root.find("item")
        if item is None:
            return "❌ 예약 서버 응답을 파싱할 수 없습니다."

        result_code_elem = item.find("result_code")
        result_msg_elem = item.find("result_msg")

        result_code = result_code_elem.text.strip() if result_code_elem is not None and result_code_elem.text else "-1"
        result_msg = result_msg_elem.text.strip() if result_msg_elem is not None and result_msg_elem.text else "알 수 없는 오류"

        if result_code == "0":
            room_elem = item.find("res_room_info")
            time_elem = item.find("res_use_time")
            res_room = room_elem.text.strip() if room_elem is not None and room_elem.text else ""
            res_time = time_elem.text.strip() if time_elem is not None and time_elem.text else ""
            return f"✅ 예약 성공! [{res_room}] {res_time} ({result_msg})"

        return f"❌ 예약 실패: {result_msg}"
    except Exception as e:
        return f"❌ 예약 요청 중 오류가 발생했습니다: {e}"


def cancel_study_room_action(reserve_no: str, student_id: str) -> str:
    """광운대학교 중앙도서관 그룹스터디룸 예약을 취소합니다."""
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_Study_Room_Cancel.php"
    real_id = _encode_student_id(student_id)

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "reserve_no": reserve_no,
        "real_id": real_id,
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        item = root.find("item")
        if item is None:
            return "❌ 취소 서버 응답을 파싱할 수 없습니다."

        result_code_elem = item.find("result_code")
        result_msg_elem = item.find("result_msg")

        result_code = result_code_elem.text.strip() if result_code_elem is not None and result_code_elem.text else "-1"
        result_msg = result_msg_elem.text.strip() if result_msg_elem is not None and result_msg_elem.text else "알 수 없는 오류"

        if result_code == "0":
            return f"✅ {result_msg}"
        return f"❌ 예약 취소 실패: {result_msg}"
    except Exception as e:
        return f"❌ 예약 취소 요청 중 오류가 발생했습니다: {e}"


def fetch_my_seat_status(student_id: str) -> str:
    """열람실 좌석/그룹스터디룸 예약 또는 발권 현황을 조회합니다."""
    url = "https://mobileid.kw.ac.kr/mobile/MA/xml_mySeat_Status_list.php"
    real_id = _encode_student_id(student_id)

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "real_id": real_id,
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        item = root.find("item")
        if item is None:
            return "❌ 서버 응답을 파싱할 수 없습니다."

        result_code = item.findtext("result_code", default="").strip()
        if result_code != "0":
            return "❌ 조회 실패 (학번 또는 서버 상태를 확인하세요)"

        study_reserve_no = item.findtext("study_reserve_no", default="").strip()
        seat_room_name = item.findtext("seat_room_name", default="").strip()

        if study_reserve_no:
            result = {
                "type": "그룹스터디룸",
                "room_name": item.findtext("study_sroom_name", default="").strip(),
                "date": item.findtext("study_reserve_date", default="").strip(),
                "time": item.findtext("study_use_time", default="").strip(),
                "status": item.findtext("study_reserve_stat", default="").strip(),
                "reserve_no": study_reserve_no,
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        if seat_room_name:
            result = {
                "type": "일반열람실",
                "room_name": seat_room_name,
                "seat_no": item.findtext("seat_seat_no", default="").strip(),
                "start_time": item.findtext("seat_start_time", default="").strip(),
                "end_time": item.findtext("seat_end_time", default="").strip(),
            }
            return json.dumps(result, ensure_ascii=False, indent=2)

        return "현재 예약되거나 발권된 좌석이 없습니다."
    except Exception as e:
        return f"❌ 조회 요청 중 오류가 발생했습니다: {e}"
