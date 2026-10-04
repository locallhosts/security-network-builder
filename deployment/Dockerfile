FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system snb \
    && useradd --system --gid snb --home-dir /app --shell /usr/sbin/nologin snb

COPY pyproject.toml README.md ./
COPY src ./src
COPY profiles ./profiles

RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && mkdir -p /app/data /app/reports \
    && chown -R snb:snb /app

USER snb

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=3).read()"

CMD ["sh", "-c", "exec python -m uvicorn snb.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
