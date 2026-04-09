FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxcb1 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pdf-flask-handler/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 安装 MinerU
COPY MinerU /app/MinerU
RUN pip install -e /app/MinerU[pipeline]

COPY pdf-flask-handler/app.py /app/app.py
COPY pdf-flask-handler/uploads /app/uploads-sample
COPY pdf-flask-handler/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8001", "--timeout", "600", "app:app"]
