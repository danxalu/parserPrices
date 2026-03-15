# parserPrices
The parser of prices of goods on Ozon

В папке `developer` две части:

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
python parser/main.py
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
