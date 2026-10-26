# RaktSanket API image.
#
#   docker build -t raktsanket-api backend
#   # release step (run once per deploy, before starting new containers):
#   docker run --rm --env-file <secrets> raktsanket-api python -m alembic upgrade head
#   docker run -p 8000:8000 --env-file <secrets> raktsanket-api
#
# All configuration comes from the environment (see .env.production.example);
# no .env file or database is baked into the image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WEB_CONCURRENCY=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1

# xgboost needs the OpenMP runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY models ./models
COPY data ./data

RUN useradd --system --uid 10001 --no-create-home raktsanket
USER raktsanket

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4).status == 200 else 1)"

# --proxy-headers + FORWARDED_ALLOW_IPS: trust X-Forwarded-For only from the
# load balancer, so login throttling sees real client addresses.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS}"]
