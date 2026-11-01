# Catalogue Service (TV2)

CRUD danh mục sản phẩm, port **8001**, FastAPI + PostgreSQL. Tuân theo `docs/contract.md` (API Contract v1.1).

## 1. Trạng thái bàn giao

| Hạng mục | Trạng thái |
|---|---|
| Code CRUD, `/health`, `/ready`, `/metrics` | Đã viết, **chưa chạy thử end-to-end** (xem mục 2) |
| Dockerfile (non-root, python:3.12-slim) | Đã viết, chưa build thử |
| `docker-compose.yml` (ở thư mục gốc repo) | Đã viết, chưa chạy thử |
| `k8s/deployment.yaml`, `service.yaml`, `hpa.yaml` | Đã viết, YAML hợp lệ, chưa apply lên cụm |
| `scripts/seed.py` (500 sản phẩm) | Đã viết, chưa chạy thử |
| `scripts/smoke_test.sh` | Đã viết, chạy sau khi service lên |

## 2. Việc đầu tiên cần làm (10 phút): chạy thử và đẩy image v0.1

Code được viết trong môi trường không có Docker, FastAPI hay PostgreSQL nên chưa có lần chạy thật. Hãy chạy theo thứ tự:

```bash
# 1. Chạy cả DB và service ở local (thư mục gốc repo)
docker compose up --build -d

# 2. Kiểm tra toàn bộ endpoint, mã lỗi, metrics (mọi dòng phải [OK])
./catalogue-service/scripts/smoke_test.sh

# 3. Nạp 500 sản phẩm mẫu
docker compose exec catalogue-service python scripts/seed.py --count 500 --reset

# 4. Build và đẩy image cho TV3/TV4 kéo về dùng
docker build -t <dockerhub-user>/catalogue-service:v0.1 ./catalogue-service
docker push <dockerhub-user>/catalogue-service:v0.1
docker tag  <dockerhub-user>/catalogue-service:v0.1 <dockerhub-user>/catalogue-service:latest
docker push <dockerhub-user>/catalogue-service:latest
```

Nếu `smoke_test.sh` có dòng `[FAIL]`, sửa trước khi báo cho các bạn khác.

## 3. Biến môi trường

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `PORT` | `8001` | |
| `DB_HOST` | `postgres-service` | tên Service của DB |
| `DB_PORT` | `5432` | |
| `DB_NAME` | `shopdb` | K8s: lấy từ Secret `postgres-secret`, key `POSTGRES_DB` |
| `DB_USER` | `shop` | K8s: key `POSTGRES_USER` |
| `DB_PASSWORD` | (rỗng) | K8s: key `POSTGRES_PASSWORD` |
| `LOG_LEVEL` | `info` | |
| `DB_POOL_MIN` / `DB_POOL_MAX` | `2` / `10` | số kết nối mỗi Pod; 8 Pod x 10 = 80, dưới giới hạn 100 của PostgreSQL |
| `DB_POOL_TIMEOUT_SECONDS` | `5` | |
| `DB_CONNECT_RETRIES` / `DB_CONNECT_DELAY_SECONDS` | `30` / `2` | chờ DB tối đa 60 giây khi khởi động |
| `DEFAULT_LIMIT` / `MAX_LIMIT` | `100` / `1000` | phân trang của `GET /products` |

## 4. Endpoint

| Method | Path | Thành công | Lỗi có thể gặp |
|---|---|---|---|
| GET | `/health` | 200 `{"status":"ok","service":"catalogue-service"}` | |
| GET | `/ready` | 200 | 503 khi mất DB |
| GET | `/metrics` | 200 (text Prometheus) | |
| GET | `/products?limit=&offset=` | 200, **mảng** sản phẩm | 422 |
| GET | `/products/{id}` | 200 | 404, 422 |
| POST | `/products` | 201 | 422 |
| PUT | `/products/{id}` | 200 | 404, 422 |
| DELETE | `/products/{id}` | 204 (không có body) | 404 |

- Product: `id`, `name`, `description` (có thể `null`), `price`, `stock`. `created_at`/`updated_at` có trong DB nhưng chưa trả về ở v1.x.
- `GET /products` trả mảng thuần (đúng contract). Tổng số bản ghi nằm ở header **`X-Total-Count`**. Mặc định `limit=100`, tối đa `1000`.
- Mọi lỗi có dạng `{"detail": "<thông báo>"}`. Lỗi không lường trước trả `500`.

```bash
curl -s -X POST localhost:8001/products -H 'Content-Type: application/json' \
  -d '{"name":"Laptop Dell XPS 15","description":"Laptop cao cấp","price":1500,"stock":10}'
curl -s "localhost:8001/products?limit=5"
curl -s -X DELETE localhost:8001/products/1 -i
```

## 5. Health, readiness và vì sao tách đôi

- `/health` (liveness): chỉ kiểm tra tiến trình, **không chạm DB**. DB sập thì Pod không bị restart hàng loạt.
- `/ready` (readiness): có `SELECT 1`. DB sập thì Pod bị rút khỏi Service (api-service nhận 503/504 nhanh, không đợi timeout), DB lên lại thì tự vào lại.
- Có `startupProbe` vì lúc khởi động service đợi DB tối đa 60 giây.

## 6. Metrics

`GET /metrics` cùng port 8001:

| Metric | Loại | Label |
|---|---|---|
| `http_requests_total` | Counter | `method`, `path`, `status` |
| `http_request_duration_seconds` | Histogram (bucket 5ms đến 5s) | `method`, `path` |
| `http_requests_in_progress` | Gauge | `method` |
| `process_cpu_seconds_total`, `process_resident_memory_bytes`, ... | mặc định của thư viện | |

- `path` là **mẫu route**: `/products` và `/products/{product_id}` (không phải id thật).
- `/health`, `/ready`, `/metrics` không bị đếm.

## 7. Triển khai Kubernetes

```bash
# Điều kiện: namespace shop, Secret postgres-secret và Service postgres-service của TV3 đã có
sed -i 's#DOCKERHUB_USER#<dockerhub-user>#' catalogue-service/k8s/deployment.yaml
kubectl apply -f catalogue-service/k8s/deployment.yaml -f catalogue-service/k8s/service.yaml
kubectl -n shop rollout status deploy/catalogue-service

# HPA cần Metrics Server (TV4). Kiểm tra: kubectl top pods -n shop
kubectl apply -f catalogue-service/k8s/hpa.yaml

# Nạp dữ liệu mẫu bên trong cụm
kubectl -n shop exec deploy/catalogue-service -- python scripts/seed.py --count 500 --reset
```

Nếu TV3 chưa có Secret, tạo tạm để test:

```bash
kubectl -n shop create secret generic postgres-secret \
  --from-literal=POSTGRES_DB=shopdb --from-literal=POSTGRES_USER=shop \
  --from-literal=POSTGRES_PASSWORD='<mat-khau-tu-dat>'
```

## 8. Bàn giao cho từng thành viên

### TV1 – api-service
- Địa chỉ gọi: `http://catalogue-service:8001` (K8s), `http://127.0.0.1:8001` (local, `docker compose up`).
- Danh sách trả về là **mảng JSON**; đọc `X-Total-Count` nếu cần tổng số.
- `DELETE` trả **204 không body**: api-service phải chuyển tiếp đúng (đừng cố parse JSON).
- Catalogue không bao giờ trả 503/504 cho nghiệp vụ; 503/504 là mã **api-service tự sinh** khi không kết nối được hoặc quá timeout 3 giây.
- Có thể chạy `docker compose up postgres-service catalogue-service` để có catalogue thật mà không cần mock.

### TV3 – database và load test
- Catalogue cần: Service `postgres-service:5432`, Secret `postgres-secret` với 3 key `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, namespace `shop`.
- **Không cần init.sql**: catalogue tự `CREATE TABLE IF NOT EXISTS` khi khởi động, an toàn khi nhiều Pod khởi động cùng lúc (advisory lock).
- PostgreSQL mặc định `max_connections=100`; mỗi Pod catalogue giữ tối đa 10 kết nối. Nếu HPA lên 8 Pod là 80 kết nối, đừng hạ `max_connections`.
- Nạp dữ liệu: lệnh seed ở mục 7. Dùng `--reset` để id luôn là 1..N, khớp với script tải chọn id ngẫu nhiên 1..500. Lưu ý `--reset` xóa sạch dữ liệu.
- Endpoint cho script tải: xem docs/contract.md mục 13.

### TV4 – ingress và monitoring
- **Không** đưa catalogue-service ra Ingress. Chỉ `api-service:8000`.
- ServiceMonitor chọn Service theo label `app: catalogue-service`, port tên `http`, path `/metrics`, namespace `shop`. Pod cũng có sẵn annotation `prometheus.io/scrape` nếu bạn dùng cấu hình kiểu annotation.
- Tên metric và truy vấn PromQL mẫu: docs/contract.md mục 10.
- HPA (`k8s/hpa.yaml`) chờ Metrics Server; Deployment đã có `resources.requests` nên HPA tính được % CPU.

## 9. Quyết định TV2 tự đưa ra ngoài contract v1.0 (cần xác nhận)

1. `DELETE` trả **204** (không body).
2. `GET /products` hỗ trợ `limit` (mặc định 100, tối đa 1000) và `offset`; tổng số ở header `X-Total-Count`.
3. Thêm `GET /ready` ngoài `GET /health`.
4. Tên mẫu route trong metrics là `/products/{product_id}`.
5. `name` được cắt khoảng trắng đầu/cuối; `price` và `stock` không được âm.
6. Cho phép hai sản phẩm trùng tên.
