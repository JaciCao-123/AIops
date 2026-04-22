FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY app.py .

EXPOSE 5000

ENV SERVICE_NAME=unknown
ENV OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

CMD ["python", "app.py"]
