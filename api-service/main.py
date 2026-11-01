
from fastapi import FastAPI

app = FastAPI(title="NT533 Group10 - API Service")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "api-service"
    }

@app.get("/products")
def get_products():
    return [
        {
            "id": 1,
            "name": "Laptop Dell XPS 15",
            "description": "Laptop cao cấp",
            "price": 1500.00,
            "stock": 10
        },
        {
            "id": 2,
            "name": "Bàn phím Keychron K2",
            "description": "Bàn phím cơ",
            "price": 99.99,
            "stock": 50
        }
    ]