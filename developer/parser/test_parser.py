import pytest
from unittest.mock import MagicMock, patch

from parser_main import (
    collect_prices,
    extract_custom_fee,
    extract_sku,
    parse_price,
    push_to_victoria,
)


# =========================================================
# UNIT TESTS
# =========================================================


def test_extract_sku_valid_url():
    url = "https://www.ozon.ru/product/iphone-17-pro-max-2835198401/"
    assert extract_sku(url) == "2835198401"



def test_extract_sku_with_params():
    url = "https://www.ozon.ru/product/iphone-17-2835198401/?at=abc"
    assert extract_sku(url) == "2835198401"



def test_extract_sku_invalid_url():
    url = "https://www.ozon.ru/product/test"
    assert extract_sku(url) is None



def test_parse_price_with_currency():
    assert parse_price("119 734 ₽") == 119734



def test_parse_price_without_currency():
    assert parse_price("85000") == 85000



def test_parse_price_with_extra_symbols():
    assert parse_price("~ 99 990 ₽ *") == 99990



def test_parse_price_no_digits():
    assert parse_price("нет в наличии") == 0



def test_parse_price_empty_string():
    assert parse_price("") == 0


# =========================================================
# INTEGRATION TESTS
# =========================================================


@patch("parser_main.requests.post")
def test_metric_format(mock_post):
    mock_post.return_value.status_code = 204

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000,
        }
    }

    push_to_victoria(metrics)

    expected = 'ozon_price{query="iphone",sku="123"} 100000'
    args, kwargs = mock_post.call_args
    assert expected in kwargs["data"]


@patch("parser_main.requests.post")
def test_push_metrics_success(mock_post):
    mock_post.return_value.status_code = 204

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000,
        }
    }

    result = push_to_victoria(metrics)

    assert result is True
    mock_post.assert_called_once()


@patch("parser_main.requests.post")
def test_push_metrics_error(mock_post):
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "server error"

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000,
        }
    }

    result = push_to_victoria(metrics)

    assert result is False
    mock_post.assert_called_once()


@patch("parser_main.requests.post")
def test_multiple_sku_metrics(mock_post):
    mock_post.return_value.status_code = 204

    metrics = {
        "111": {"query": "iphone", "sku": "111", "price": 100000},
        "222": {"query": "iphone", "sku": "222", "price": 110000},
        "333": {"query": "iphone", "sku": "333", "price": 120000},
    }

    push_to_victoria(metrics)

    args, kwargs = mock_post.call_args
    data = kwargs["data"]
    assert data.count("ozon_price") == 3


@patch("parser_main.requests.post")
def test_empty_metrics(mock_post):
    mock_post.return_value.status_code = 204

    push_to_victoria({})

    args, kwargs = mock_post.call_args
    assert kwargs["data"] == ""


# =========================================================
# NEGATIVE TESTS
# =========================================================


def test_extract_custom_fee_no_fee_block():
    page = MagicMock()

    locator_mock = MagicMock()
    locator_mock.count.return_value = 0

    page.locator.return_value.first = locator_mock

    result = extract_custom_fee(page)
    assert result == 0



def test_extract_custom_fee_no_price_span():
    page = MagicMock()

    fee_block = MagicMock()
    fee_block.count.return_value = 1

    price_span = MagicMock()
    price_span.count.return_value = 0

    fee_block.locator.return_value.first = price_span
    page.locator.return_value.first = fee_block

    result = extract_custom_fee(page)
    assert result == 0


@patch("parser_main.sync_playwright")
def test_browser_connection_error(mock_sync_playwright):
    mock_sync_playwright.side_effect = Exception("Connection failed")

    with pytest.raises(Exception):
        collect_prices("iphone")



def _make_scroll_evaluate():
    state = {"calls": 0}

    def side_effect(script):
        if script == "document.body.scrollHeight":
            state["calls"] += 1
            return 1000 if state["calls"] == 1 else 1000
        return None

    return side_effect


@patch("parser_main.PAGE_COUNT", 1)
@patch("parser_main.sync_playwright")
def test_empty_search_results(mock_sync_playwright):
    browser_mock_1 = MagicMock()
    browser_mock_2 = MagicMock()
    context_mock_1 = MagicMock()
    context_mock_2 = MagicMock()
    search_page_mock = MagicMock()
    product_page_mock = MagicMock()

    search_page_mock.goto.return_value = None
    search_page_mock.wait_for_timeout.return_value = None
    search_page_mock.query_selector_all.return_value = []
    search_page_mock.content.return_value = "<html></html>"
    search_page_mock.evaluate.side_effect = _make_scroll_evaluate()

    product_page_mock.goto.return_value = None
    product_page_mock.wait_for_timeout.return_value = None

    context_mock_1.pages = [search_page_mock]
    context_mock_2.pages = [product_page_mock]
    browser_mock_1.contexts = [context_mock_1]
    browser_mock_2.contexts = [context_mock_2]

    playwright_mock = MagicMock()
    playwright_mock.chromium.connect_over_cdp.side_effect = [browser_mock_1, browser_mock_2]
    mock_sync_playwright.return_value.__enter__.return_value = playwright_mock

    result = collect_prices("iphone")

    assert result == {}
    search_page_mock.query_selector_all.assert_called_once_with("div[data-index]")


@patch("parser_main.PAGE_COUNT", 1)
@patch("parser_main.extract_custom_fee", return_value=1500)
@patch("parser_main.sync_playwright")
def test_collect_prices_success(mock_sync_playwright, mock_extract_custom_fee):
    browser_mock_1 = MagicMock()
    browser_mock_2 = MagicMock()
    context_mock_1 = MagicMock()
    context_mock_2 = MagicMock()
    search_page_mock = MagicMock()
    product_page_mock = MagicMock()
    tile_mock = MagicMock()
    link_mock = MagicMock()
    price_span_mock = MagicMock()

    link_mock.get_attribute.return_value = "https://www.ozon.ru/product/iphone-17-2835198401/"
    price_span_mock.inner_text.return_value = "119 734 ₽"

    tile_mock.query_selector.side_effect = lambda selector: {
        "a.tile-clickable-element": link_mock,
        "span[class*='tsHeadline']": price_span_mock,
    }.get(selector)

    search_page_mock.goto.return_value = None
    search_page_mock.wait_for_timeout.return_value = None
    search_page_mock.evaluate.side_effect = _make_scroll_evaluate()
    search_page_mock.query_selector_all.return_value = [tile_mock]

    product_page_mock.goto.return_value = None
    product_page_mock.wait_for_timeout.return_value = None

    context_mock_1.pages = [search_page_mock]
    context_mock_2.pages = [product_page_mock]
    browser_mock_1.contexts = [context_mock_1]
    browser_mock_2.contexts = [context_mock_2]

    playwright_mock = MagicMock()
    playwright_mock.chromium.connect_over_cdp.side_effect = [browser_mock_1, browser_mock_2]
    mock_sync_playwright.return_value.__enter__.return_value = playwright_mock

    result = collect_prices("iphone")

    assert result == {
        "2835198401": {
            "query": "iphone",
            "sku": "2835198401",
            "price": 121234,
        }
    }
    product_page_mock.goto.assert_called_once()
    mock_extract_custom_fee.assert_called_once_with(product_page_mock)
