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
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            extra_http_headers={
                "Referer": "https://fin.land.naver.com/map",
                "Origin": "https://fin.land.naver.com"
            }
        )
        page = context.new_page()
        
        print("1. 빈 세션 페이지 초기화 중...")
        # 직접 네이버에 접속하는 대신 빈 페이지를 띄워 차단(Connection Reset)을 회피합니다.
        page.goto("about:blank")

        print("2. 세션 권한으로 API 직접 POST 요청 전송 중...")
        result = page.evaluate(
            """
            async ({url, payload}) => {
              const response = await fetch(url, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Accept": "application/json, text/plain, */*"
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
