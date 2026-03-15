import pytest
from unittest.mock import patch, MagicMock

from __main__ import (
    extract_sku,
    parse_price,
    extract_custom_fee,
    push_to_victoria,
    collect_prices
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

@patch("requests.post")
def test_metric_format(mock_post):

    mock_post.return_value.status_code = 204

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000
        }
    }

    push_to_victoria(metrics)

    expected = 'ozon_price{query="iphone",sku="123"} 100000'

    args, kwargs = mock_post.call_args
    assert expected in kwargs["data"]


@patch("requests.post")
def test_push_metrics_success(mock_post):

    mock_post.return_value.status_code = 204

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000
        }
    }

    push_to_victoria(metrics)

    mock_post.assert_called_once()


@patch("requests.post")
def test_push_metrics_error(mock_post):

    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "server error"

    metrics = {
        "123": {
            "query": "iphone",
            "sku": "123",
            "price": 100000
        }
    }

    push_to_victoria(metrics)

    mock_post.assert_called_once()


@patch("requests.post")
def test_multiple_sku_metrics(mock_post):

    mock_post.return_value.status_code = 204

    metrics = {
        "111": {"query": "iphone", "sku": "111", "price": 100000},
        "222": {"query": "iphone", "sku": "222", "price": 110000},
        "333": {"query": "iphone", "sku": "333", "price": 120000}
    }

    push_to_victoria(metrics)

    args, kwargs = mock_post.call_args
    data = kwargs["data"]

    assert data.count("ozon_price") == 3


@patch("requests.post")
def test_empty_metrics(mock_post):

    metrics = {}

    push_to_victoria(metrics)

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


@patch("playwright.sync_api.sync_playwright")
def test_browser_connection_error(mock_playwright):

    mock_playwright.side_effect = Exception("Connection failed")

    with pytest.raises(Exception):
        collect_prices("iphone")


@patch("playwright.sync_api.sync_playwright")
def test_empty_search_results(mock_playwright):

    browser_mock = MagicMock()
    context_mock = MagicMock()
    page_mock = MagicMock()

    page_mock.query_selector_all.return_value = []

    context_mock.pages = [page_mock]
    browser_mock.contexts = [context_mock]

    playwright_mock = MagicMock()
    playwright_mock.chromium.connect_over_cdp.return_value = browser_mock

    mock_playwright.return_value.__enter__.return_value = playwright_mock

    result = collect_prices("iphone")

    assert result == {}


@patch("playwright.sync_api.sync_playwright")
def test_dom_structure_changed(mock_playwright):

    browser_mock = MagicMock()
    context_mock = MagicMock()
    page_mock = MagicMock()

    tile_mock = MagicMock()
    tile_mock.query_selector.return_value = None

    page_mock.query_selector_all.return_value = [tile_mock]

    context_mock.pages = [page_mock]
    browser_mock.contexts = [context_mock]

    playwright_mock = MagicMock()
    playwright_mock.chromium.connect_over_cdp.return_value = browser_mock

    mock_playwright.return_value.__enter__.return_value = playwright_mock

    result = collect_prices("iphone")

    assert isinstance(result, dict)