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
SPREADSHEET_NAME = "네이버부동산_뷰카운터"
SHEET_TAB_NAME = "DATA"

TARGET_COMPLEXES = [
    {"name": "신당현대", "id": 797},
    {"name": "중화한신", "id": 824},
    {"name": "상봉우정", "id": 3469},
    {"name": "행당신동아", "id": 332}
]

# ==========================================
# 2. 보조 도구 함수 (Helper Functions)
# ==========================================
def find_view_count_deep(obj):
    """JSON 데이터를 이 잡듯 뒤져서 대소문자 상관없이 viewcount 관련 숫자를 파내어 반환합니다."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() == "viewcount" and value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    pass
            res = find_view_count_deep(value)
            if res is not None:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_view_count_deep(item)
            if res is not None:
                return res
    return None


def get_previous_view_count(sheet, complex_number):
    try:
        data = sheet.get_all_values()
        if len(data) <= 1:
            return None
        for row in reversed(data[1:]):
            if len(row) > 3 and str(row[3]) == str(complex_number):
                try:
                    return int(row[5])  # F열 (6번째 열)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return None

# ==========================================
# 3. 핵심 실행 함수 (Main Function)
# ==========================================
def main():
    # --- [Step 1] 네이버 API 데이터 수집 (CORS 우회 네트워크 버전) ---
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        page = context.new_page()

        print("1. 네이버 부동산 정식 세션 연결 및 보안 쿠키 수집 중...")
        try:
            # 먼저 실제 웹 페이지를 정식으로 열어 브라우저 컨텍스트 내부에 쿠키와 세션을 확실하게 적재합니다.
            page.goto("https://fin.land.naver.com/", wait_until="commit", timeout=40000)
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"진입 경고 (속행): {e}")

        print("2. 4개 타겟 단지 네트워크 우회 조회 및 조회수 수집 시작...\n" + "="*40)
        collected_results = []

        for target in TARGET_COMPLEXES:
            target_name = target["name"]
            target_num = target["id"]
            
            # 단지 정보를 관리하는 정확한 상세 API 엔드포인트 경로
            direct_api_url = f"https://naver.com{target_num}"
            print(f"🔍 조회 중: {target_name} (ID: {target_num})")

            try:
                # [핵심 변경] 브라우저 내부 자바스크립트(fetch) 대신 Playwright 자체 네트워크 시스템으로 직통 GET 요청
                response = context.request.get(
                    direct_api_url,
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
                        "Referer": "https://fin.land.naver.com/",
                        "Origin": "https://fin.land.naver.com"
                    }
                )

                if response.status == 200:
                    json_data = response.json()
                    view_count = find_view_count_deep(json_data)
                    
                    if view_count is not None:
                        print(f"   [성공] 단지명: {target_name} | viewCount: {view_count}")
                        collected_results.append({
                            "id": target_num,
                            "name": target_name,
                            "viewCount": int(view_count)
                        })
                    else:
                        print(f"   [경고] 응답 성공(200)했으나 데이터 구조 내부에 viewCount 필드가 존재하지 않습니다.")
                        print(f"   [서버 응답 요약]: {response.text()[:200]}")
                else:
                    print(f"   [실패] 네이버 서버 응답 거부 (상태 코드: {response.status})")
            except Exception as e:
                print(f"   [에러] 네트워크 예외 발생: {e}")

            print("-" * 40)

        browser.close()

    if not collected_results:
        print("❌ 최종 추출된 조회수 데이터가 하나도 없어 구글 시트 업데이트를 건너뜁니다.")
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

        print("\n🎉 모든 아파트 단지의 데이터 기록이 성공적으로 완료되었습니다!")

    except Exception as sheet_error:
        print(f"❌ 구글 시트 기록 중 에러 발생: {sheet_error}")


if __name__ == "__main__":
    main()
