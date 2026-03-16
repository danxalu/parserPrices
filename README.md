# parserPrices
The parser of prices of goods on Ozon

Перед чтением инструкицй, перейдите в папку `developer`. Здесь есть 2 части:

- `parser/` — код парсинга (сбор цен/данных по товарам).
- `monitoring/` — мониторинг (дашборды/метрики/инфраструктура мониторинга).

> Парсер использует локально запущенный Google Chrome в режиме **Remote Debugging**.

---

## Требования

- Python 3.10+
- Google Chrome (локально)
- Docker — если используешь `monitoring/`

---

## Быстрый старт

## Конфиг `search_configs.yaml`

Парсер читает список запросов и их фильтры из файла `search_configs.yaml`.  
Каждый элемент `queries` — это **один запрос** и **его фильтры**: фильтры применяются только к своему запросу и подставляются в URL поиска Ozon.

### Пример `search_configs.yaml`
```
victoria_url: "http://localhost:8428/api/v1/import/prometheus"
interval_hours: 3
page_count: 5

queries:
  - query: "iphone 17 pro max 256gb"
    filters:
      volumememoryphone: "100956393"
      smartphonecondition: "101845557"
      sort: "popular"
```

### 1) Клонирование

```bash
git clone https://github.com/danxalu/parserPrices.git
cd parserPrices
```

### 2) Виртуальное окружение и зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r parser/requirements.txt
```

---

## Запуск Google Chrome

Парсер подключается к Chrome по порту Remote Debugging.

Ниже команды **для macOS** (путь к Chrome у тебя может отличаться; на Windows/Linux он будет другим):

### Профиль 1 (порт 9222)

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome_profile_1
```

### Профиль 2 (порт 9223)

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9223 \
  --user-data-dir=/tmp/chrome_profile_2
```

#### Примечания
- Если Chrome установлен нестандартно — поправь путь к бинарнику.
- На Windows обычно используется `chrome.exe`, на Linux — `google-chrome` / `chromium` (зависит от дистрибутива).

---

## Запуск парсера

```bash
python parser/parser_main.py
```

---

## Мониторинг

В `monitoring/` лежит инфраструктура мониторинга (часто это Docker Compose + Grafana/Prometheus/и т.п.).

Запуск:

```bash
cd monitoring
docker compose up -d
```

Остановка:

```bash
docker compose down
```

## Основные функции парсера

### `extract_sku(href: str) -> str | None`
Извлекает SKU из URL товара Ozon.

Пример:

```python
extract_sku("https://www.ozon.ru/product/iphone-17-pro-max-2835198401/")
# -> "2835198401"
```

### `parse_price(price_text: str) -> int`
Очищает цену от пробелов, валюты и посторонних символов.

Примеры:

```python
parse_price("119 734 ₽")   # 119734
parse_price("~ 99 990 ₽ *")  # 99990
parse_price("нет в наличии")  # 0
```

### `auto_scroll(page, count_scroll=20)`
Прокручивает страницу поиска вниз несколько раз, чтобы Ozon подгрузил карточки.

### `extract_custom_fee(page) -> int`
Пытается найти на странице товара блок с текстом `пошлина` и вернуть сумму пошлины. Если блок или цена не найдены, возвращает `0`.

### `collect_prices(search_cfg: dict) -> dict`
Главная функция парсинга.

Что делает:

- формирует url поискового запроса;
- подключается к двум браузерам через Playwright CDP;
- работает с поисковой страницей и страницей товара;
- собирает SKU, цену и пошлину;
- возвращает словарь вида:

```python
{
    "2835198401": {
        "query": "iphone",
        "sku": "2835198401",
        "price": 121234,
    }
}
```

### `push_to_victoria(metrics: dict)`
Преобразует словарь метрик в Prometheus text exposition format и отправляет данные в VictoriaMetrics.

Формат строки:

```text
ozon_price{query="iphone",sku="123"} 100000
```

### `main()`
Бесконечный цикл приложения:

- проходит по всем запросам из `SEARCH_QUERIES`;
- собирает метрики;
- отправляет их в VictoriaMetrics;
- спит `INTERVAL_HOURS` часов.

## Настройки

В `parser_main.py` используются такие параметры:

- `VICTORIA_URL` — адрес VictoriaMetrics для импорта метрик;
- `INTERVAL_HOURS` — интервал между циклами парсинга;
- `SEARCH_QUERIES` — список поисковых запросов;
- `PAGE_COUNT` — число страниц поиска, которые нужно обойти.

Пример текущих значений в коде: `VICTORIA_URL = "http://localhost:8428/api/v1/import/prometheus"`, `INTERVAL_HOURS = 3`, `PAGE_COUNT = 1`. Эти константы заданы прямо в файле `parser_main.py`. fileciteturn11file0

## Как запустить тесты

Все тесты лежат в `test_parser.py`. Там есть:

- unit-тесты для `extract_sku()` и `parse_price()`;
- тесты отправки метрик в VictoriaMetrics через мок `requests.post`;
- негативные тесты для `extract_custom_fee()`;
- тесты для `collect_prices()` с моками Playwright. fileciteturn11file1

### Запуск всех тестов

```bash
pytest -v
```

### Запуск одного теста

```bash
pytest -v test_parser.py::test_parse_price_with_currency
```

### Запуск только группы тестов по шаблону

```bash
pytest -v -k parse_price
```

### Запуск с coverage

Если установлен `pytest-cov`:

```bash
pip install pytest-cov
pytest --cov=parser_main --cov-report=term-missing -v
```

## Что проверяют тесты

### Unit-тесты

Проверяют:

- корректное извлечение SKU из валидных URL;
- обработку URL с query-параметрами;
- возврат `None` для невалидных ссылок;
- корректный парсинг цены из разных форматов строки. fileciteturn11file1

### Тесты VictoriaMetrics

Проверяют:

- что `push_to_victoria()` формирует правильную строку метрики;
- что `requests.post()` вызывается;
- что несколько SKU превращаются в несколько строк;
- что для пустого словаря отправляется пустая строка. fileciteturn11file1

### Негативные тесты

Проверяют:

- отсутствие блока пошлины;
- отсутствие цены внутри блока пошлины;
- ошибку подключения к браузеру;
- пустые результаты поиска. fileciteturn11file1

## Полезные команды для разработки

Проверить только проблемные тесты:

```bash
pytest -v -k "empty_search_results or collect_prices_success or push_metrics_error"
```

Остановиться на первой ошибке:

```bash
pytest -x -v
```

Показать print и логи в консоли:

```bash
pytest -v -s
```

## Особенности текущей реализации

### 1. Бесконечный цикл в `main()`
Скрипт работает бесконечно и спит между итерациями. Для локальной отладки обычно удобнее вызывать `collect_prices()` отдельно.

### 2. Жёстко прописанные адреса браузеров
CDP-адреса `9222` и `9223` захардкожены в коде. Для продакшена лучше вынести их в переменные окружения или конфиг.

### 3. Жёстко прописанные параметры поиска
Список запросов и число страниц заданы константами в модуле. Это удобно для простого запуска, но неудобно для масштабирования.

## Пример локального сценария работы

1. Поднять VictoriaMetrics.
2. Подготовить два браузера с CDP на `9222` и `9223`.
3. Установить зависимости и выполнить `playwright install`.
4. Запустить тесты:

```bash
pytest -v
```

5. Запустить парсер:

```bash
python parser_main.py
```