
import httpx
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def mock_catalogue(monkeypatch, handler):
    original_client = httpx.AsyncClient

    def create_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(main.httpx, "AsyncClient", create_client)


# Test 1: Health check
def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# Test 2: Catalogue tra ve thanh cong
def test_products_success(monkeypatch):
    products = [
        {"id": 1, "name": "Laptop", "price": 1500, "stock": 10}
    ]

    def handler(request):
        return httpx.Response(200, json=products)

    mock_catalogue(monkeypatch, handler)

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == products


# Test 3: Catalogue khong ket noi duoc
def test_products_unavailable(monkeypatch):
    def handler(request):
        raise httpx.ConnectError(
            "Connection failed",
            request=request
        )

    mock_catalogue(monkeypatch, handler)

    response = client.get("/products")

    assert response.status_code == 503


# Test 4: Catalogue phan hoi qua thoi gian
def test_products_timeout(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout(
            "Request timed out",
            request=request
        )

    mock_catalogue(monkeypatch, handler)

    response = client.get("/products")

    assert response.status_code == 504

# Test 5: Readiness check
def test_readiness():
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["service"] == "api-service"