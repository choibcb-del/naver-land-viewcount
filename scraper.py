import json
from playwright.sync_api import sync_playwright

API_URL = "https://fin.land.naver.com/front-api/v1/complex/complexClusters"

# 보내주신 최신 Copy as fetch의 body 데이터
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
        "hasArticle": False,
    },
    "boundingBox": {
        "left": 127.08735311730976,
        "right": 127.0894130835772,
        "top": 37.60024396982949,
        "bottom": 37.598777071015576,
    },
    "precision": 18.858996210416944,
    "userChannelType": "PC",
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
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = context.new_page()

        print("1. 네이버 부동산 기본 세션 진입 중...")
        try:
            # [수정] 지도 레이어 로딩이 없는 아주 가벼운 기본 주소로 진입하여 쿠키/세션만 구워냅니다.
            # wait_until도 가장 가벼운 "commit"을 주어 에러를 원천 차단합니다.
            base_url = "https://fin.land.naver.com/"
            page.goto(base_url, wait_until="commit", timeout=20000)
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"진입 경고 (속행): {e}")

        print("2. 최신 Fetch 헤더 및 페이로드로 API 요청 전송 중...")
        try:
            result = page.evaluate(
                """
                async ({url, payload}) => {
                  const response = await fetch(url, {
                    method: "POST",
                    headers: {
                      "accept": "application/json, text/plain, */*",
                      "accept-language": "ko,en;q=0.9,en-US;q=0.8",
                      "content-type": "application/json",
                      "sec-fetch-dest": "empty",
                      "sec-fetch-mode": "cors",
                      "sec-fetch-site": "same-origin"
                    },
                    referrer: "https://fin.land.naver.com/map",
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
                {"url": API_URL, "payload": API_BODY},
            )

            print(f"STATUS: {result['status']}")

            if result["status"] == 200 and result["json"]:
                target_num = 3469  # 상봉우정
                complex_data = find_complex(result["json"], target_num)

                if complex_data:
                    print(f"[성공] 단지 발견: complexNumber={target_num}")
                    print(
                        f"단지명: {complex_data.get('complexName', '이름없음')}"
                    )
                    # 실제 변수명이 보려는 인원수 혹은 조회수 데이터인지 체크해 줍니다.
                    print(
                        f"viewCount (보는 중): {complex_data.get('viewCount', '정보 없음')}"
                    )
                else:
                    print(
                        f"[실패] 응답은 성공했으나 데이터 내부에서 단지 번호 {target_num}를 찾지 못했습니다."
                    )
                    print(
                        "현재 받아온 전체 JSON 데이터 키 구조:",
                        list(result["json"].keys()),
                    )
            else:
                print(
                    "[실패] API 응답코드가 200이 아니거나 올바른 데이터가 아닙니다."
                )
                print(result["rawText"][:300])

        except Exception as evaluate_error:
            print(f"❌ 데이터 추출 단계 최종 에러 발생: {evaluate_error}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
