from playwright.sync_api import sync_playwright
import json

API_URL = "https://fin.land.naver.com/front-api/v1/complex/complexClusters"

# 보내주신 최신 Copy as fetch의 body를 파싱해서 그대로 사용
API_BODY = {
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
        "hasArticle": False
    },
    "boundingBox": {
        "left": 127.08735311730976,
        "right": 127.0894130835772,
        "top": 37.60024396982949,
        "bottom": 37.598777071015576
    },
    "precision": 18.858996210416944,
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
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        page = context.new_page()
        
        print("1. 네이버 부동산 지도 페이지로 정밀 세션 진입 중...")
        try:
            # 보내주신 실제 Referrer의 지도 URL로 직접 진입하여 완벽한 세션 환경 구축
            target_map_url = "https://fin.land.naver.com/map?layer=NobwRAlgJmBcYAsD2BbApmANGAzmghgE4DGCACkfijnCAL50C6QA&center=3zmiiP-2ANqRH&zoom=18.858996210416944"
            page.goto(target_map_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"진입 경고 (속행): {e}")

        print("2. 최신 Fetch 헤더 및 페이로드로 API 요청 전송 중...")
        result = page.evaluate(
            """
            async ({url, payload}) => {
              const response = await fetch(url, {
                method: "POST",
                headers: {
                  "accept": "application/json, text/plain, */*",
                  "accept-language": "ko,en;q=0.9,en-US;q=0.8",
                  "baggage": "sentry-environment=real,sentry-release=property-web%402026.08.05,sentry-public_key=ec5063b7741b4a9282a85c1e2f27ab09,sentry-trace_id=c0199be52fa64945be84d7a462bc9e12",
                  "content-type": "application/json",
                  "priority": "u=1, i",
                  "sec-fetch-dest": "empty",
                  "sec-fetch-mode": "cors",
                  "sec-fetch-site": "same-origin",
                  "sentry-trace": "c0199be52fa64945be84d7a462bc9e12-8d30ad718415b46d"
                },
                referrer: "https://fin.land.naver.com/map?layer=NobwRAlgJmBcYAsD2BbApmANGAzmghgE4DGCACkfijnCAL50C6QA&center=3zmiiP-2ANqRH&zoom=18.858996210416944",
                body: JSON.stringify(payload),
                credentials: "include"
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
            {"url": API_URL, "payload": API_BODY}
        )

        print(f"STATUS: {result['status']}")

        if result['status'] == 200 and result['json']:
            target_num = 3469  # 상봉우정
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
