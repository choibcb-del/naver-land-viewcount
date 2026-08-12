from playwright.sync_api import sync_playwright

API_URL = "https://fin.land.naver.com/front-api/v1/complex/complexClusters"

payload = {
  "filter": {
    "tradeTypes": ["A1"],
    "realEstateTypes": ["A01"],
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
    "hasArticle": False
  },
  "boundingBox": {
    "left": 127.08829528276294,
    "right": 127.08999069434759,
    "top": 37.60008756612412,
    "bottom": 37.59913186675824
  },
  "precision": 18.948667263440065,
  "userChannelType": "PC"
}

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

def main():
    with sync_playwright() as p:
        # 자동화 탐지(navigator.webdriver)를 완전히 숨기는 옵션 적용
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1920, "height": 1080}
        )
        
        # 봇 탐지 우회 스크립트 주입
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        page = context.new_page()
        
        print("1. 네이버 부동산 메인 세션 초기화 접속 중...")
        try:
            # 연결 리셋을 피하기 위해 네이버 부동산 메인으로 부드럽게 진입
            page.goto("https://land.naver.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000) # 세션 쿠키 발급 대기
        except Exception as e:
            print(f"메인 접속 경고 (속행): {e}")

        print("2. API 도메인 세션으로 이동 및 API POST 요청 전송 중...")
        # API가 요구하는 출처(Origin) 세션을 맞추기 위해 지도 페이지로 이동 후 fetch 수행
        try:
            page.goto("https://fin.land.naver.com/map", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"지도 페이지 접속 경고 (속행): {e}")

        result = page.evaluate(
            """
            async ({url, payload}) => {
              const response = await fetch(url, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Accept": "application/json, text/plain, */*",
                  "Referer": "https://fin.land.naver.com/map"
                },
                credentials: "include",
                body: JSON.stringify(payload)
              });

              const text = await response.text();
              let json = null;
              try {
                  json = JSON.parse(text);
              } catch (e) {}

              return {
                status: response.status,
                json: json,
                rawText: text
              };
            }
            """,
            {"url": API_URL, "payload": payload}
        )

        print(f"STATUS: {result['status']}")

        if result['status'] == 200 and result['json']:
            target_num = 3469
            complex_data = find_complex(result['json'], target_num)
            
            if complex_data:
                print(f"[성공] 단지 발견: complexNumber={target_num}")
                print(f"단지명: {complex_data.get('complexName', '이름없음')}")
                print(f"viewCount: {complex_data.get('viewCount', '조회수 정보 없음')}")
            else:
                print(f"[실패] 응답은 200이지만 JSON 내부에서 complexNumber {target_num}을 찾지 못했습니다.")
        else:
            print("[실패] API 호출이 정상 Status 200을 반환하지 않았거나 JSON 파싱에 실패했습니다.")
            print(result['rawText'][:300])

        browser.close()

if __name__ == "__main__":
    main()
