import os
import json
from datetime import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright

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
    # --- [Step 1] 네이버 API 데이터 수집 (Playwright 완벽 우회 버전) ---
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1920, "height": 1080}
        )

        # 봇 탐지 솔루션을 우회하기 위해 브라우저 내부 속성 변조
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
            """
        )

        page = context.new_page()

        print("1. 네이버 부동산 실제 지도 페이지 진입 및 완전 로딩 대기...")
        try:
            # 단순 메인 페이지가 아닌 실제 맵(지도) 서비스 페이지로 진입하여 유효 토큰을 온전히 확보합니다.
            page.goto("https://naver.com", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)  # 페이지 안정화를 위한 여유 시간 추가
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
                result = page.evaluate(
                    """
                    async ({url, payload}) => {
                      try {
                        const response = await fetch(url, {
                          method: "POST",
                          headers: {
                            "accept": "application/json, text/plain, */*",
                            "accept-language": "ko,en-US;q=0.9,en;q=0.8",
                            "content-type": "application/json",
                            "sec-fetch-dest": "empty",
                            "sec-fetch-mode": "cors",
                            "sec-fetch-site": "same-origin"
                          },
                          body: JSON.stringify(payload)
                        });

                        const text = await response.text();
                        let json = null;
                        try { json = JSON.parse(text); } catch (e) {}

                        return { status: response.status, rawText: text, json: json };
                      } catch (err) {
                        return { status: 0, error: err.toString() };
                      }
                    }
                    """,
                    {"url": API_URL, "payload": api_payload},
                )

                # 파이썬 딕셔너리 안전 검사 및 조건문 들여쓰기 완벽 수정
                if result and result.get("status") == 200 and result.get("json"):
                    complex_data = find_complex(result["json"], target_num)
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
                    err_msg = result.get('error', f"상태 코드: {result.get('status')}") if result else "결과 없음"
                    print(f"   [실패] 데이터 반환 문제 ({err_msg})")
                    if result and "rawText" in result and len(result["rawText"]) < 200:
                        print(f"   [서버 응답 내용]: {result['rawText']}")
            except Exception as e:
                print(f"   [에러] 예외 발생: {e}")

            print("-" * 40)

        browser.close()

    if not collected_results:
        print("❌ 수집된 데이터가 없어 구글 시트 업데이트를 건너뜜.")
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

        if os.path.exists(key_json_path):
            os.remove(key_json_path)

        print("\n🎉 모든 작업이 성공적으로 완료되었습니다!")

    except Exception as sheet_error:
        print(f"❌ 구글 시트 기록 중 에러 발생: {sheet_error}")


if __name__ == "__main__":
    main()
