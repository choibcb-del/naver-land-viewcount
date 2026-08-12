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

# 아파트 단지 기본 ID 목록 (디렉트 조회용으로 가볍게 압축)
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
            # 네이버가 viewCount 또는 viewcount 등 어떻게 보냈어도 매칭되도록 대소문자 통합 검사
            if key.lower() == "viewcount" and value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    pass
            
            # 더 깊은 곳 탐색
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
                    return int(row[5]) # F열 (6번째 열)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return None

# ==========================================
# 3. 핵심 실행 함수 (Main Function)
# ==========================================
def main():
    # --- [Step 1] 네이버 API 데이터 수집 ---
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security"
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => []});
            """
        )

        page = context.new_page()

        print("1. 네이버 부동산 웹 세션 초기화 진입...")
        try:
            # 기본 지도를 정식으로 띄워 네이버가 로봇이 아니라고 믿게 만듭니다.
            page.goto("https://naver.com", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"진입 경고 (속행): {e}")

        print("2. 4개 타겟 단지 데이터 정밀 추적 시작...\n" + "="*40)
        collected_results = []

        for target in TARGET_COMPLEXES:
            target_name = target["name"]
            target_num = target["id"]
            
            # 네이버 부동산 프론트엔드가 상세창을 열 때 쏘는 진짜 직통 상세정보 API 엔드포인트 주소입니다.
            direct_api_url = f"https://naver.com{target_num}"
            print(f"🔍 조회 중: {target_name} (ID: {target_num})")

            try:
                result = page.evaluate(
                    """
                    async (url) => {
                      try {
                        const response = await fetch(url, {
                          method: "GET",
                          headers: {
                            "accept": "application/json, text/plain, */*",
                            "accept-language": "ko,en-US;q=0.9,en;q=0.8",
                            "sec-fetch-dest": "empty",
                            "sec-fetch-mode": "cors",
                            "sec-fetch-site": "same-origin"
                          }
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
                    direct_api_url
                )

                if result and result.get("status") == 200:
                    json_data = result.get("json")
                    view_count = find_view_count_deep(json_data)
                    
                    if view_count is not None:
                        print(f"   [성공] 단지명: {target_name} | viewCount: {view_count}")
                        collected_results.append({
                            "id": target_num,
                            "name": target_name,
                            "viewCount": int(view_count)
                        })
                    else:
                        print(f"   [경고] 200 OK 응답을 받았으나 내부에서 viewCount 숫자를 찾지 못했습니다.")
                        # 에러 분석용: 서버가 보낸 원본 텍스트의 앞부분 일부를 로그로 노출시킵니다.
                        raw_text = result.get("rawText", "")
                        print(f"   [서버 실제 응답 요약]: {raw_text[:200]}")
                else:
                    err_msg = result.get('error', f"상태 코드: {result.get('status')}") if result else "응답 없음"
                    print(f"   [실패] 네이버 응답 차단 또는 실패 ({err_msg})")
            except Exception as e:
                print(f"   [에러] 예외 발생: {e}")

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
