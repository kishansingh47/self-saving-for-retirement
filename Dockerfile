# docker build -t blk-hacking-ind-name-lastname .
FROM python:3.12-slim
# Linux selection criteria: Debian slim image for small footprint, fast startup, and stable package ecosystem.

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 5477

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5477"]
