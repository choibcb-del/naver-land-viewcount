import os
import json
from datetime import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests

# ==========================================
# 1. 설정값 (Constants)
# ==========================================
API_URL = "https://naver.com"
SPREADSHEET_NAME = "네이버부동산_뷰카운터"  # 구글 시트 파일 이름
SHEET_TAB_NAME = "DATA"                     # 구글 시트 탭 이름

TARGET_COMPLEXES = [
    {
        "name": "신당현대",
        "id": 797,
        "payload": {
            "filter": {
                "tradeTypes": ["A1", "B1"],
                "realEstateTypes": ["A01", "A04", "B01"],
                "roomCount": [],
                "bathRoomCount": [],
                "optionTypes": [],
                "oneRoomShapeTypes": [],
                "moveInTypes": [],
                "filtersExclusiveSpace": False,
                "floorTypes": [],
                "directionTypes": [],
                "hasArticlePhoto": False,
                "isAuthorizedByOwner": False,
                "parkingTypes": [],
                "entranceTypes": [],
                "hasArticle": False,
            },
            "boundingBox": {
                "left": 127.02099123923551,
                "right": 127.02283919886935,
                "top": 37.56069520010895,
                "bottom": 37.559652957889085,
            },
            "precision": 18.824369570126738,
            "userChannelType": "PC",
        }
    },
    {
        "name": "중화한신",
        "id": 824,
        "payload": {
            "filter": {
                "tradeTypes": ["A1", "B1"],
                "realEstateTypes": ["A01", "A04", "B01"],
                "roomCount": [],
                "bathRoomCount": [],
                "optionTypes": [],
                "oneRoomShapeTypes": [],
                "moveInTypes": [],
                "filtersExclusiveSpace": False,
                "floorTypes": [],
                "directionTypes": [],
                "hasArticlePhoto": False,
                "isAuthorizedByOwner": False,
                "parkingTypes": [],
                "entranceTypes": [],
                "hasArticle": False,
            },
            "boundingBox": {
                "left": 127.08211015510489,
                "right": 127.08296315895547,
                "top": 37.5974907670075,
                "bottom": 37.597009915573636,
            },
            "precision": 19.939678652914548,
            "userChannelType": "PC",
        }
    },
    {
        "name": "상봉우정",
        "id": 3469,
        "payload": {
            "filter": {
                "tradeTypes": ["A1", "B1"],
                "realEstateTypes": ["A01", "A04", "B01"],
                "roomCount": [],
                "bathRoomCount": [],
                "optionTypes": [],
                "oneRoomShapeTypes": [],
                "moveInTypes": [],
                "filtersExclusiveSpace": False,
                "floorTypes": [],
                "directionTypes": [],
                "hasArticlePhoto": False,
                "isAuthorizedByOwner": False,
                "parkingTypes": [],
                "entranceTypes": [],
                "hasArticle": False,
            },
            "boundingBox": {
                "left": 127.08837032558625,
                "right": 127.0900657371709,
                "top": 37.60007215171801,
                "bottom": 37.59911645215416,
            },
            "precision": 18.948667263440065,
            "userChannelType": "PC",
        }
    },
    {
        "name": "행당신동아",
        "id": 332,
        "payload": {
            "filter": {
                "tradeTypes": ["A1", "B1"],
                "realEstateTypes": ["A01", "A04", "B01"],
                "roomCount": [],
                "bathRoomCount": [],
                "optionTypes": [],
                "oneRoomShapeTypes": [],
                "moveInTypes": [],
                "filtersExclusiveSpace": False,
                "floorTypes": [],
                "directionTypes": [],
                "hasArticlePhoto": False,
                "isAuthorizedByOwner": False,
                "parkingTypes": [],
                "entranceTypes": [],
                "hasArticle": False,
            },
            "boundingBox": {
                "left": 127.0316359362094,
                "right": 127.03447352540286,
                "top": 37.554961001158745,
                "bottom": 37.553360482467,
            },
            "precision": 18.205637072432747,
            "userChannelType": "PC",
        }
    }
]

# ==========================================
# 2. 보조 도구 함수 (Helper Functions)
# ==========================================
def find_complex(obj, target_complex_number):
    if isinstance(obj, dict):
        if "complexNumber" in obj:
            try:
                if int(obj["complexNumber"]) == int(target_complex_number):
                    return obj
            except (TypeError, ValueError):
                pass
        for value in obj.values():
            result = find_complex(value, target_complex_number)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = find_complex(item, target_complex_number)
            if result is not None:
                return result
    return None


def get_previous_view_count(sheet, complex_number):
    data = sheet.get_all_values()
    if len(data) <= 1:
        return None
    
    for row in reversed(data[1:]):
        if len(row) > 3 and str(row[3]) == str(complex_number):
            try:
                return int(row[5])
            except ValueError:
                pass
    return None

# ==========================================
# 3. 핵심 실행 함수 (Main Function)
# ==========================================
def main():
    # --- [Step 1] 네이버 세션 생성 및 안전한 헤더 설정 ---
    session = requests.Session()
    
    # 실제 일반 브라우저처럼 보이게 만드는 필수 헤더 정보
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
        "Origin": "https://fin.land.naver.com",
        "Referer": "https://naver.com",
    }
    session.headers.update(headers)

    print("1. 네이버 부동산 기본 세션 초기화 완료 (메인 페이지 우회 진입)")
    try:
        # 가볍게 메인 홈을 먼저 들러 쿠키 값을 백그라운드에서 자동 수집합니다.
        session.get("https://fin.land.naver.com/", timeout=15)
    except Exception as e:
        print(f"진입 경고 (속행): {e}")

    print("2. 4개 타겟 단지 순회 및 데이터 수집 시작...\n" + "="*40)
    collected_results = []

    for target in TARGET_COMPLEXES:
        target_name = target["name"]
        target_num = target["id"]
        api_payload = target["payload"]

        print(f"🔍 조회 중: {target_name} (ID: {target_num})")

        try:
            # 브라우저를 켜지 않고 API에 직접 데이터를 쏘아 응답을 받아옵니다.
            response = session.post(API_URL, json=api_payload, timeout=15)

            if response.status_code == 200:
                json_data = response.json()
                complex_data = find_complex(json_data, target_num)
                
                if complex_data:
                    complex_name = complex_data.get('complexName', target_name)
                    view_count = complex_data.get('viewCount')
                    if view_count is not None:
                        print(f"   [성공] 단지명: {complex_name} | viewCount: {view_count}")
                        collected_results.append({
                            "id": target_num,
                            "name": complex_name,
                            "viewCount": int(view_count)
                        })
                    else:
                        print(f"   [경고] viewCount 필드가 없습니다.")
                else:
                    print(f"   [경고] 영역 내에서 단지 번호 {target_num}를 찾지 못함.")
            else:
                print(f"   [실패] API 응답 오류 (Status: {response.status_code})")
        except Exception as e:
            print(f"   [에러] 예외 발생: {e}")

        print("-" * 40)

    if not collected_results:
        print("❌ 수집된 데이터가 없어 구글 시트 업데이트를 건너뜁니다.")
        return

    # --- [Step 2] 구글 시트 연동 및 기록 ---
    print("\n3. 구글 시트 연동 및 데이터 기록 중...")
    try:
        key_json_path = "credentials.json"
        key_content = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
        if not key_content:
            raise ValueError("GCP_SERVICE_ACCOUNT_KEY 환경 변수가 설정되지 않았습니다.")
        
        with open(key_json_path, "w", encoding="utf-8") as f:
            f.write(key_content)

        scope = [
            "https://google.com",
            "https://googleapis.com"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_json_path, scope)
        client = gspread.authorize(creds)

        spreadsheet = client.open(SPREADSHEET_NAME)
        sheet = spreadsheet.worksheet(SHEET_TAB_NAME)

        kst = pytz.timezone("Asia/Seoul")
        now = datetime.now(kst)
        collected_at = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        for item in collected_results:
            complex_num = item["id"]
            complex_name = item["name"]
            view_count = item["viewCount"]

            prev_view = get_previous_view_count(sheet, complex_num)
            
            delta = ""
            if prev_view is not None:
                delta = view_count - prev_view

            sheet.append_row([
                collected_at,
                date_str,
                time_str,
                complex_num,
                complex_name,
                view_count,
                prev_view if prev_view is not None else "",
                delta
            ])

            print(f"   [시트 기록 완료] {complex_name} (현재: {view_count}, 직전: {prev_view}, 증가량: {delta})")

        # 임시 인증 json 파일이 남아있다면 안전하게 삭제합니다
        if os.path.exists(key_json_path):
            os.remove(key_json_path)

        print("\n🎉 모든 작업이 성공적으로 완료되었습니다!")

    except Exception as sheet_error:
        print(f"❌ 구글 시트 기록 중 에러 발생: {sheet_error}")


if __name__ == "__main__":
    main()
