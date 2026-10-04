FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
 && curl -fsSL -o /tmp/x.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip \
 && unzip -o /tmp/x.zip xray -d /usr/local/bin && chmod +x /usr/local/bin/xray \
 && rm /tmp/x.zip && apt-get purge -y unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV DATA_DIR=/data
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PANEL_PORT:-8000}"]
