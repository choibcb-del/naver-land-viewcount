import json
from playwright.sync_api import sync_playwright

API_URL = "https://fin.land.naver.com/front-api/v1/complex/complexClusters"

# 1. 추적할 단지 목록 정의 (상봉우정 외에 추가할 단지들을 이 리스트에 계속 확장하면 됩니다)
TARGET_COMPLEXES = [
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
                "left": 127.08735311730976,
                "right": 127.0894130835772,
                "top": 37.60024396982949,
                "bottom": 37.598777071015576,
            },
            "precision": 18.858996210416944,
            "userChannelType": "PC",
        }
    },
    # 예시: 두 번째 단지를 추가하고 싶다면 아래와 같이 템플릿을 복사해서 채워넣으세요!
    # {
    #     "name": "추적할다른단지이름",
    #     "id": 0000,
    #     "payload": { ... (해당 위치의 boundingBox 및 설정) ... }
    # }
]


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
            base_url = "https://fin.land.naver.com/"
            page.goto(base_url, wait_until="commit", timeout=20000)
            page.wait_for_timeout(1500)
        except Exception as e:
            print(f"진입 경고 (속행): {e}")

        print("2. 타겟 단지 목록 순회 및 데이터 수집 시작...\n" + "="*40)

        results_summary = []

        for target in TARGET_COMPLEXES:
            target_name = target["name"]
            target_num = target["id"]
            api_payload = target["payload"]

            print(f"🔍 조회 중인 단지: {target_name} (ID: {target_num})")

            try:
                # 브라우저 세션 내부에서 각 단지 페이로드를 담아 fetch 실행
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
                    {"url": API_URL, "payload": api_payload},
                )

                if result["status"] == 200 and result["json"]:
                    complex_data = find_complex(result["json"], target_num)

                    if complex_data:
                        complex_name = complex_data.get('complexName', target_name)
                        view_count = complex_data.get('viewCount', '정보 없음')
                        print(f"   [성공] 단지명: {complex_name} | viewCount(보는 중): {view_count}")
                        
                        results_summary.append({
                            "name": complex_name,
                            "id": target_num,
                            "viewCount": view_count,
                            "status": "SUCCESS"
                        })
                    else:
                        print(f"   [경고] 응답 200이나, 해당 바운딩박스/구역 내에서 단지 번호 {target_num}를 찾지 못함.")
                        results_summary.append({
                            "name": target_name,
                            "id": target_num,
                            "viewCount": "N/A",
                            "status": "NOT_FOUND_IN_RESPONSE"
                        })
                else:
                    print(f"   [실패] API 응답 오류 (Status: {result['status']})")
                    results_summary.append({
                        "name": target_name,
                        "id": target_num,
                        "viewCount": "N/A",
                        "status": f"HTTP_{result['status']}"
                    })

            except Exception as evaluate_error:
                print(f"   [에러] 예외 발생: {evaluate_error}")
                results_summary.append({
                    "name": target_name,
                    "id": target_num,
                    "viewCount": "N/A",
                    "status": "ERROR"
                })

            print("-" * 40)

        browser.close()

        # 최종 요약 출력
        print("\n📊 [최종 수집 결과 요약]")
        for item in results_summary:
            print(f"- 단지명: {item['name']} (ID: {item['id']}) | 조회수(viewCount): {item['viewCount']} | 상태: {item['status']}")


if __name__ == "__main__":
    main()
