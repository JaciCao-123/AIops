import os
import time
import random
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import requests
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "unknown-service")
OTEL_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
DOWNSTREAM_URL = os.environ.get("DOWNSTREAM_URL", "")

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT)))
trace.set_tracer_provider(provider)

RequestsInstrumentor().instrument()

app = FastAPI(title=SERVICE_NAME)
FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)

@app.get("/health")
def health():
    return {"status": "healthy", "service": SERVICE_NAME}

@app.get("/")
def index():
    with tracer.start_as_current_span(f"{SERVICE_NAME}-index"):
        time.sleep(random.uniform(0.01, 0.05))
        return {
            "service": SERVICE_NAME,
            "message": f"Hello from {SERVICE_NAME}!",
            "timestamp": time.time()
        }

@app.get("/api/order")
def create_order():
    with tracer.start_as_current_span("create-order"):
        time.sleep(random.uniform(0.02, 0.08))
        
        order_id = f"ORD-{random.randint(10000, 99999)}"
        
        product_info = {}
        if DOWNSTREAM_URL:
            try:
                with tracer.start_as_current_span("call-product-service"):
                    response = requests.get(f"{DOWNSTREAM_URL}/api/product", timeout=5)
                    product_info = response.json()
            except Exception as e:
                product_info = {"error": str(e)}
        
        return {
            "service": SERVICE_NAME,
            "order_id": order_id,
            "product_info": product_info,
            "timestamp": time.time()
        }

@app.get("/api/product")
def get_product():
    with tracer.start_as_current_span("get-product"):
        time.sleep(random.uniform(0.05, 0.15))
        
        if random.random() < 0.1:
            raise Exception("Database connection timeout!")
        
        products = [
            {"id": 1, "name": "iPhone 15", "price": 7999},
            {"id": 2, "name": "MacBook Pro", "price": 14999},
            {"id": 3, "name": "AirPods Pro", "price": 1999}
        ]
        
        return {
            "service": SERVICE_NAME,
            "products": products,
            "timestamp": time.time()
        }

@app.get("/error")
def trigger_error():
    with tracer.start_as_current_span("error-span"):
        raise Exception(f"This is a test error from {SERVICE_NAME}!")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
