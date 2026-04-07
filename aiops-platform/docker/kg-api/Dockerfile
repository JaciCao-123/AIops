FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    neo4j==5.15.0 \
    openai==1.6.1 \
    python-dotenv==1.0.0 \
    pydantic==2.5.2 \
    httpx==0.25.0

COPY app.py /app/

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]