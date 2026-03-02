#!/bin/bash

# чистим возможные старые локи
rm -rf /chrome-profile-1
rm -rf /chrome-profile-2

mkdir -p /chrome-profile-1
mkdir -p /chrome-profile-2

chromium \
  --headless=new \
  --remote-debugging-port=9222 \
  --disable-features=UseDBus \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --user-data-dir=/chrome-profile-1 \
  --remote-allow-origins=* &

chromium \
  --headless=new \
  --remote-debugging-port=9223 \
  --disable-features=UseDBus \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --user-data-dir=/chrome-profile-2 \
  --remote-allow-origins=* &

sleep 5

python3 __main__.py
