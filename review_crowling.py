import sys
import asyncio
import pandas as pd
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ✅ Windows 환경에서 UTF-8로 출력되도록 설정
sys.stdout.reconfigure(encoding="utf-8")

star_folder = "review\star"
summery_folder = "review\summery"
best_review_folder = "review\best"

# ✅ 크롤링할 제품 URL (쿠팡 제품 리뷰 페이지 URL 입력)
PRODUCT_URL = "https://www.coupang.com/vp/products/123456789?itemId=987654321"

# ✅ 크롤링할 페이지 수
MAX_PAGES = 5

def get_page_source(page, url):
    """ ✅ HTML을 가져오는 함수 """
    page.goto(url)
    page.wait_for_selector(".sdp-review__article__list__review")  # ✅ 리뷰가 로드될 때까지 대기
    return page.content()  # ✅ HTML 소스 반환

def extract_reviews_from_html(html):
    """ ✅ HTML에서 리뷰 내용만 추출하는 함수 """
    soup = BeautifulSoup(html, "html.parser")
    review_elements = soup.select(".sdp-review__article__list__review__content")

    reviews = [review.get_text(strip=True) for review in review_elements]
    return reviews

def scrape_coupang_reviews():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # ✅ Headless 모드 실행 (UI 없이 실행)
        page = browser.new_page()

        all_reviews = []
        current_page = 1

        while current_page <= MAX_PAGES:
            print(f"🔹 {current_page}페이지 HTML 가져오는 중...")

            # ✅ 1️⃣ HTML 소스를 먼저 가져오기
            html = get_page_source(page, PRODUCT_URL)

            # ✅ 2️⃣ HTML에서 리뷰 추출 (동기 방식)
            reviews = extract_reviews_from_html(html)
            all_reviews.extend(reviews)

            print(f"✅ {current_page}페이지에서 {len(reviews)}개의 리뷰 수집 완료!")

            # ✅ 3️⃣ 다음 페이지로 이동
            try:
                next_button = page.query_selector(".sdp-review__article__page__next")
                if next_button:
                    next_button.click()
                    time.sleep(3)  # ✅ 페이지 로딩 대기 (비동기 대비 안정적)
                    current_page += 1
                else:
                    print("🚫 다음 페이지 버튼 없음. 마지막 페이지일 가능성이 높음.")
                    break
            except Exception as e:
                print("🚫 다음 페이지 버튼을 찾을 수 없습니다.")
                break

        browser.close()

        # ✅ 크롤링 완료 후 데이터 저장
        df = pd.DataFrame(all_reviews, columns=["리뷰 내용"])
        df.to_csv("coupang_reviews_sync.csv", index=False, encoding="utf-8-sig")
        print(f"✅ 총 {len(all_reviews)}개의 리뷰를 수집했습니다. CSV 파일 저장 완료: coupang_reviews_sync.csv")

# ✅ 실행
scrape_coupang_reviews()