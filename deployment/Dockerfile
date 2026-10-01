FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

EXPOSE 8765

CMD ["python", "-m", "snb", "dashboard", "--host", "0.0.0.0"]
