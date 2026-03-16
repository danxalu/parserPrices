import logging
import sys
import random
import re
import time
import requests
import yaml
from urllib.parse import quote, urlencode
import os

os.environ["NODE_OPTIONS"] = "--no-deprecation"
from playwright.sync_api import sync_playwright


log = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s [%(process)d] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def load_search_configs_from_yaml(yaml_path: str):
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    settings = {
        "interval_hours": int(cfg.get("interval_hours", 3)),
        "page_count": int(cfg.get("page_count", 5)),
        "victoria_url": cfg.get("victoria_url", "http://localhost:8428/api/v1/import/prometheus"),
    }

    search_configs = []
    for item in (cfg.get("queries") or []):
        q = (item.get("query") or "").strip()
        if not q:
            continue
        filters = item.get("filters") or {}
        filters = {str(k): str(v) for k, v in filters.items()}
        search_configs.append({"query": q, "filters": filters})

    return search_configs, settings


CONFIG_YAML_SEARCH_PATH = "search_config.yaml"
SEARCH_CONFIGS, settings = load_search_configs_from_yaml(CONFIG_YAML_SEARCH_PATH)
VICTORIA_URL = settings["victoria_url"]
INTERVAL_HOURS = settings["interval_hours"]
PAGE_COUNT = settings["page_count"]


def extract_sku(href: str) -> str:
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


def extract_custom_fee(page) -> int:
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


def build_search_url(query: str, filters: dict, page_number: int) -> str:
    """
    Строит URL поиска для конкретного запроса и его фильтров.
    """
    encoded_query = query

    params = dict(filters or {})
    params["text"] = encoded_query
    params["page"] = str(page_number)

    qs = urlencode(params, doseq=True)
    return f"https://www.ozon.ru/search/?{qs}"


def collect_prices(search_cfg: dict) -> dict:
    query = search_cfg["query"]
    filters = search_cfg.get("filters", {})

    results = dict()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        log.info("localhost:9222 connected")

        browser2 = p.chromium.connect_over_cdp("http://localhost:9223")
        context2 = browser2.contexts[0]
        log.info("localhost:9223 connected")

        search_page = context.pages[0]
        product_page = context2.pages[0]

        try:
            for page_number in range(1, PAGE_COUNT + 1):
                url = build_search_url(query, filters, page_number)

                search_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                search_page.wait_for_timeout(random.randint(1500, 3000))

                auto_scroll(search_page, random.randint(7, 9))
                search_page.wait_for_timeout(random.randint(1500, 3000))

                tiles = search_page.query_selector_all("div[data-index]")

                if tiles:
                    log.info(f"[{query}] Found {len(tiles)} tiles (page={page_number})")
                else:
                    log.error(f"[{query}] No tiles found (page={page_number})")
                    log.info(search_page.content())

                for tile in tiles:
                    try:
                        link = tile.query_selector("a.tile-clickable-element")
                        price_span = tile.query_selector("span[class*='tsHeadline']")

                        if not link or not price_span:
                            continue

                        href = link.get_attribute("href")
                        sku = extract_sku(href)  # sku = артикул
                        price = parse_price(price_span.inner_text())

                        if not sku:
                            continue

                        product_url = f"https://www.ozon.ru/product/{sku}"
                        product_page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
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
        line = (
            f'ozon_price{{query="{item["query"]}",sku="{sku}"}} '
            f'{item["price"]}'
        )
        lines.append(line)

    data = "\n".join(lines)
    response = requests.post(VICTORIA_URL, data=data)

    if response.status_code != 204:
        log.error("Ошибка отправки: %s", response.text)


def main():
    while True:
        all_metrics = dict()

        for cfg in SEARCH_CONFIGS:
            log.info(f"Парсим: {cfg['query']}")
            metrics = collect_prices(cfg)
            all_metrics.update(metrics)

        if all_metrics:
            push_to_victoria(all_metrics)
            log.info(f"Отправлено {len(all_metrics)} метрик")

        log.info(f"Спим {INTERVAL_HOURS} часов")
        time.sleep(INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    setup_logging()
    log.info("Application started")
    main()