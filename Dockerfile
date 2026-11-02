FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    HOST=0.0.0.0 \
    PORT=8080 \
    DEMO_MODE=true

RUN groupadd --gid 10001 tracker \
    && useradd --uid 10001 --gid tracker \
       --no-create-home --shell /usr/sbin/nologin tracker \
    && mkdir -p /data \
    && chown tracker:tracker /data

WORKDIR /app

COPY app/ ./app/
COPY static/ ./static/

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "app.main"]
