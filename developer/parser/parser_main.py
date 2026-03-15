import logging
import os
import random
import re
import sys
import time
from urllib.parse import quote

import requests
from playwright.sync_api import sync_playwright

os.environ["NODE_OPTIONS"] = "--no-deprecation"

log = logging.getLogger(__name__)


VICTORIA_URL = "http://localhost:8428/api/v1/import/prometheus"
INTERVAL_HOURS = 3
SEARCH_QUERIES = ["iphone 17 pro max 256gb"]
PAGE_COUNT = 5


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s [%(process)d] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# выполнить команду playwright install


def extract_sku(href: str) -> str | None:
    """
    Извлекаем артикул из ссылки:
    ...-2835198401/?...
    """
    match = re.search(r"-(\d+)/", href)
    return match.group(1) if match else None



def parse_price(price_text: str) -> int:
    """
    '119 734 ₽' -> 119734
    """
    digits = re.sub(r"[\D]", "", price_text)
    return int(digits) if digits else 0



def auto_scroll(page, count_scroll: int = 20):
    previous_height = 0
    count = 0

    while count < count_scroll:
        current_height = page.evaluate("document.body.scrollHeight")

        if current_height == previous_height:
            break

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(random.randint(800, 1200))

        previous_height = current_height
        count += 1



def extract_custom_fee(page):
    try:
        fee_block = page.locator("span:has-text('пошлина')").first
        if not fee_block or not fee_block.count():
            return 0

        price_span = fee_block.locator("span:has-text('₽')").first
        if not price_span or not price_span.count():
            return 0

        text = price_span.inner_text()
        digits = re.sub(r"[\D]", "", text)
        return int(digits) if digits else 0
    except Exception:
        return 0



def collect_prices(query: str):
    encoded_query = quote(query)
    url = (
        "https://www.ozon.ru/search/?volumememoryphone=100956393"
        f"&smartphonecondition=101845557&text={encoded_query}&page={{}}"
    )

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        log.info("localhost:9222 connected")

        browser2 = p.chromium.connect_over_cdp("http://localhost:9223")
        context2 = browser2.contexts[0]
        log.info("localhost:9223 connected")

        if not context.pages or not context2.pages:
            return results

        search_page = context.pages[0]
        product_page = context2.pages[0]

        try:
            for page_number in range(1, PAGE_COUNT + 1):
                search_page.goto(
                    url.format(page_number),
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                search_page.wait_for_timeout(random.randint(1500, 3000))

                auto_scroll(search_page, random.randint(7, 9))
                search_page.wait_for_timeout(random.randint(1500, 3000))

                tiles = search_page.query_selector_all("div[data-index]")

                if tiles:
                    log.info("Found %s tiles", len(tiles))
                else:
                    log.error("No tiles found")
                    log.info(search_page.content())
                    continue

                for tile in tiles:
                    try:
                        link = tile.query_selector("a.tile-clickable-element")
                        price_span = tile.query_selector("span[class*='tsHeadline']")

                        if not link or not price_span:
                            continue

                        href = link.get_attribute("href")
                        sku = extract_sku(href)
                        price = parse_price(price_span.inner_text())

                        if not sku:
                            continue

                        product_url = f"https://www.ozon.ru/product/{sku}"
                        product_page.goto(
                            product_url,
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )
                        product_page.wait_for_timeout(random.randint(2800, 3200))

                        custom_fee = extract_custom_fee(product_page)
                        final_price = int(price) + int(custom_fee)

                        results[sku] = {
                            "query": query,
                            "sku": sku,
                            "price": final_price,
                        }
                    except Exception:
                        continue
        finally:
            context.close()
            context2.close()
            browser.close()
            browser2.close()

    return results



def push_to_victoria(metrics: dict):
    lines = []
    for sku, item in metrics.items():
        line = f'ozon_price{{query="{item["query"]}",sku="{sku}"}} {item["price"]}'
        lines.append(line)

    data = "\n".join(lines)
    response = requests.post(VICTORIA_URL, data=data)

    if response.status_code != 204:
        log.error("Ошибка отправки: %s", response.text)
        return False

    return True



def main():
    while True:
        all_metrics = {}

        for query in SEARCH_QUERIES:
            log.info("Парсим: %s", query)
            metrics = collect_prices(query)
            all_metrics.update(metrics)

        if all_metrics:
            push_to_victoria(all_metrics)
            log.info("Отправлено %s метрик", len(all_metrics))

        log.info("Спим %s часов", INTERVAL_HOURS)
        time.sleep(INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    setup_logging()
    log.info("Application started")
    main()