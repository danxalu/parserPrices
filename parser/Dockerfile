FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем Chromium + Python + зависимости
RUN apt-get update && apt-get install -y \
    chromium \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    libxrandr2 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    libxdamage1 \
    libpangocairo-1.0-0 \
    libcups2 \
    libatk1.0-0 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Создаём виртуальное окружение (чтобы не ломался PEP 668)
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

CMD ["./start.sh"]
