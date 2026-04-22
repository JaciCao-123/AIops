import os
import time
import random
import requests
from flask import Flask, jsonify, request
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

SERVICE_NAME = os.environ.get("SERVICE_NAME", "unknown")
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:5001")
DATABASE_URL = os.environ.get("DATABASE_URL", "http://database:5002")

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)))
trace.set_tracer_provider(provider)

RequestsInstrumentor().instrument()

app = Flask(SERVICE_NAME)
FlaskInstrumentor().instrument_app(app)

tracer = trace.get_tracer(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": SERVICE_NAME})

@app.route("/")
def index():
    with tracer.start_as_current_span(f"{SERVICE_NAME}-index"):
        if SERVICE_NAME == "frontend":
            return handle_frontend()
        elif SERVICE_NAME == "backend":
            return handle_backend()
        elif SERVICE_NAME == "database":
            return handle_database()
        return jsonify({"error": "unknown service"})

def handle_frontend():
    with tracer.start_as_current_span("frontend-process"):
        time.sleep(random.uniform(0.01, 0.05))
        
        try:
            response = requests.get(f"{BACKEND_URL}/api/data", timeout=5)
            backend_data = response.json()
        except Exception as e:
            backend_data = {"error": str(e)}
        
        return jsonify({
            "service": "frontend",
            "message": "Hello from Frontend!",
            "backend_response": backend_data,
            "timestamp": time.time()
        })

@app.route("/api/data")
def backend_api():
    with tracer.start_as_current_span("backend-api"):
        time.sleep(random.uniform(0.02, 0.08))
        
        try:
            response = requests.get(f"{DATABASE_URL}/query", timeout=5)
            db_data = response.json()
        except Exception as e:
            db_data = {"error": str(e)}
        
        return jsonify({
            "service": "backend",
            "data": {"user": "test", "role": "admin"},
            "database_response": db_data
        })

def handle_backend():
    return backend_api()

@app.route("/query")
def database_query():
    with tracer.start_as_current_span("database-query"):
        time.sleep(random.uniform(0.05, 0.15))
        
        if random.random() < 0.1:
            raise Exception("Database connection timeout!")
        
        return jsonify({
            "service": "database",
            "result": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"}
            ],
            "query_time": time.time()
        })

def handle_database():
    return database_query()

@app.route("/error")
def trigger_error():
    with tracer.start_as_current_span("error-span"):
        raise Exception("This is a test error!")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
