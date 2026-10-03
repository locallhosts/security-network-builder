FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip \
    && pip install .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn snb.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
