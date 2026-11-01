# API CONTRACT – NT533 GROUP 10

**Version:** 1.1
**Người thiết kế:** TV1 – API Service (v1.0); TV2 bổ sung mục 4, 8 đến 14 (v1.1)
**Trạng thái:** Quy ước triển khai chung, mọi thành viên thực hiện theo hợp đồng này.

> Mọi thay đổi phá vỡ contract (endpoint, port, tên Service, tên biến môi trường, tên metric) phải **sửa file này trước**, báo cả nhóm, rồi mới sửa code/YAML.

### Lịch sử thay đổi

| Phiên bản | Nội dung |
|---|---|
| 1.0 | TV1: kiến trúc, API Service, Catalogue, Product, mã lỗi |
| 1.1 | TV2: thêm `/ready` và `/metrics` cho Catalogue, `limit/offset`, `DELETE` trả 204, mục 8 đến 14 (K8s, biến môi trường, metrics, tài nguyên, load test). Các điểm TV2 tự quyết nằm ở mục 14 |

---

## 1. Kiến trúc hệ thống

Client → Ingress → API Service → Catalogue Service → PostgreSQL

API Service không truy cập trực tiếp PostgreSQL. Catalogue Service chịu trách nhiệm tương tác với cơ sở dữ liệu.

## 2. Thông tin các Service

| Thành phần | Công nghệ | Port | Kubernetes Service |
|---|---|---|---|
| API Service | Python FastAPI | 8000 | api-service |
| Catalogue Service | Python FastAPI | 8001 | catalogue-service |
| Database | PostgreSQL 16 | 5432 | postgres-service |

API Service gọi Catalogue qua địa chỉ cấu hình bằng biến môi trường `CATALOGUE_BASE_URL`.

- Local: `http://127.0.0.1:8001`
- Kubernetes: `http://catalogue-service:8001`
- Timeout: 3 giây (cấu hình được bằng biến môi trường, xem mục 9)

## 3. API Service Endpoints

### GET /health

Mục đích: Kiểm tra API Service đang hoạt động (không gọi Catalogue).

HTTP Status: `200 OK`

```json
{
  "status": "ok",
  "service": "api-service"
}
```

### GET /products

Mục đích: Lấy danh sách sản phẩm từ Catalogue Service.

HTTP Status: `200 OK`

```json
[
  {
    "id": 1,
    "name": "Laptop Dell XPS 15",
    "description": "Laptop cao cấp cho lập trình viên",
    "price": 1500.00,
    "stock": 10
  }
]
```

Nếu không có sản phẩm, trả về mảng rỗng `[]` và HTTP 200.

### GET /metrics

Metrics Prometheus của API Service (mục 10).

### 3.1 Đề xuất bổ sung cho API Service (cần TV1 xác nhận)

Contract v1.0 chỉ có `GET /products`, nhưng kịch bản tải cần cả đọc chi tiết và ghi. Đề xuất API Service chuyển tiếp nguyên path, body và mã trạng thái tới Catalogue (không có tiền tố `/api`):

| Method | Endpoint | Chuyển tiếp tới | Thành công |
|---|---|---|---|
| GET | /products/{id} | `GET /products/{id}` | 200 |
| POST | /products | `POST /products` | 201 |
| PUT | /products/{id} | `PUT /products/{id}` | 200 |
| DELETE | /products/{id} | `DELETE /products/{id}` | 204 (không body) |

Nếu TV1 không nhận phần này thì script tải (mục 13) chỉ còn `GET /products`.

## 4. Catalogue Service Endpoints

| Method | Endpoint | Chức năng | Thành công | Lỗi |
|---|---|---|---|---|
| GET | /health | Liveness, không chạm DB | 200 | |
| GET | /ready | Readiness, có kiểm tra DB | 200 | 503 khi mất DB |
| GET | /metrics | Metrics Prometheus | 200 | |
| GET | /products?limit=&offset= | Danh sách sản phẩm (mảng) | 200 | 422 |
| GET | /products/{id} | Lấy sản phẩm theo ID | 200 | 404, 422 |
| POST | /products | Thêm sản phẩm | 201 | 422 |
| PUT | /products/{id} | Cập nhật toàn bộ sản phẩm | 200 | 404, 422 |
| DELETE | /products/{id} | Xóa sản phẩm | 204 | 404 |

- `GET /products`: trả **mảng JSON**. `limit` mặc định 100, tối đa 1000; `offset` mặc định 0. Tổng số bản ghi nằm ở header `X-Total-Count`.
- `POST`/`PUT` nhận body gồm `name`, `description`, `price`, `stock`. Các trường do server quản lý không được gửi.

```json
{
  "name": "Laptop Dell XPS 15",
  "description": "Laptop cao cấp cho lập trình viên",
  "price": 1500,
  "stock": 10
}
```

## 5. Cấu trúc Product

| Trường | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | Integer | do server sinh |
| name | String | bắt buộc, 1 đến 255 ký tự |
| description | String hoặc null | tùy chọn |
| price | Number | bắt buộc, >= 0 |
| stock | Integer | mặc định 0, >= 0 |

Trường `created_at`, `updated_at` do PostgreSQL quản lý, chưa trả về trong API phiên bản 1.x.

## 6. Quy ước xử lý lỗi

| Trường hợp | HTTP Status |
|---|---|
| Thành công | 200 |
| Tạo sản phẩm thành công | 201 |
| Xóa thành công | 204 |
| Dữ liệu gửi lên không hợp lệ | 422 |
| Không tìm thấy sản phẩm | 404 |
| Catalogue gặp lỗi nội bộ | 500 |
| API không kết nối được Catalogue | 503 |
| Catalogue phản hồi quá timeout | 504 |

Định dạng lỗi thống nhất:

```json
{
  "detail": "Thông báo lỗi"
}
```

Catalogue chỉ trả 500 cho lỗi nội bộ. Các mã 503 và 504 (trừ `/ready` của Catalogue) là mã **API Service tự sinh**.

## 7. Quy định tích hợp

- Catalogue Service phải tương thích với API Contract phiên bản 1.x.
- API Service chạy cổng 8000, Catalogue Service chạy cổng 8001.
- Hai service trao đổi dữ liệu bằng HTTP REST và JSON.
- Catalogue Service truy cập PostgreSQL qua `postgres-service:5432` khi chạy trên Kubernetes.
- API Service cần hỗ trợ logging, xử lý timeout và xuất Prometheus metrics tại `/metrics`.
- Mọi thay đổi phá vỡ API Contract phải được thông báo và thống nhất trong nhóm trước khi áp dụng.

---

## 8. Quy ước Kubernetes

| Hạng mục | Giá trị |
|---|---|
| Namespace ứng dụng | `shop` |
| Namespace giám sát | `monitoring` |
| Tên port của Service | `http` (bắt buộc, để ServiceMonitor chọn được) |
| Label | `app: api-service`, `app: catalogue-service`, `app: postgres` |
| Kiểu Service | api-service và catalogue-service: ClusterIP. postgres-service: headless (`clusterIP: None`) |
| Ra Ingress | **Chỉ** `api-service:8000`. Catalogue và PostgreSQL chỉ truy cập nội bộ |

## 9. Biến môi trường và Secret

### catalogue-service

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `PORT` | 8001 | |
| `DB_HOST` | `postgres-service` | |
| `DB_PORT` | 5432 | |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `shopdb`, `shop`, (rỗng) | K8s: lấy từ Secret bên dưới |
| `LOG_LEVEL` | `info` | |
| `DB_POOL_MIN`, `DB_POOL_MAX` | 2, 10 | số kết nối mỗi Pod |
| `DB_CONNECT_RETRIES`, `DB_CONNECT_DELAY_SECONDS` | 30, 2 | chờ DB khi khởi động |

### api-service

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `PORT` | 8000 | |
| `CATALOGUE_BASE_URL` | `http://catalogue-service:8001` | |
| `CATALOGUE_TIMEOUT_SECONDS` | 3 | TV1 xác nhận tên biến |
| `LOG_LEVEL` | `info` | |

### Secret `postgres-secret` (namespace `shop`, TV3 tạo)

| Key | Giá trị |
|---|---|
| `POSTGRES_DB` | `shopdb` |
| `POSTGRES_USER` | `shop` |
| `POSTGRES_PASSWORD` | đặt riêng, **không commit lên Git** |

Schema: Catalogue tự chạy `CREATE TABLE IF NOT EXISTS products ...` khi khởi động, TV3 không cần viết `init.sql`. Dữ liệu mẫu: `catalogue-service/scripts/seed.py`.

## 10. Metrics (cả api-service và catalogue-service)

Expose tại `GET /metrics`, cùng port với API.

| Tên metric | Loại | Label |
|---|---|---|
| `http_requests_total` | Counter | `method`, `path`, `status` |
| `http_request_duration_seconds` | Histogram | `method`, `path` |
| `http_requests_in_progress` | Gauge | `method` |
| `process_cpu_seconds_total`, `process_resident_memory_bytes` | mặc định của thư viện | |

Quy ước:
- `path` là **mẫu route**, không phải đường dẫn thật. Catalogue: `/products` và `/products/{product_id}`. API Service nên dùng cùng mẫu.
- Không đếm `/metrics`, `/health`, `/ready`.
- Bucket histogram: `0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5`.
- Không thêm label tên service vào metric; Prometheus phân biệt service bằng label `job`/`service` do ServiceMonitor gắn.

Truy vấn PromQL mẫu cho dashboard (TV4):

```promql
# RPS theo service
sum(rate(http_requests_total[1m])) by (service)

# Tỷ lệ lỗi 5xx
sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))

# Độ trễ p95
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, service))
```

## 11. Probe, tài nguyên và HPA

| Thành phần | requests (CPU / RAM) | limits (CPU / RAM) | HPA |
|---|---|---|---|
| api-service | 100m / 128Mi | 500m / 256Mi | min 2, max 8, CPU 60% |
| catalogue-service | 100m / 128Mi | 500m / 256Mi | min 2, max 8, CPU 60% |
| postgres | 250m / 256Mi | 500m / 512Mi | không dùng |

- `resources.requests` là bắt buộc, nếu không HPA theo CPU% không hoạt động. Metrics Server do TV4 cài.
- Chiến lược cập nhật: `RollingUpdate`, `maxUnavailable: 0`, `maxSurge: 1` (Zero Downtime).
- Probe: `livenessProbe` → `/health` (không chạm dependency). `readinessProbe` → `/ready` với Catalogue (có kiểm tra DB), `/health` với API Service. Catalogue có thêm `startupProbe` vì đợi DB tối đa 60 giây khi khởi động.
- Các giá trị trên là khởi điểm, tinh chỉnh sau khi chạy kịch bản tải.

## 12. Docker image và cấu trúc repo

| Service | Image | Tag |
|---|---|---|
| api-service | `<dockerhub-user>/api-service` | `v0.1`, `latest` |
| catalogue-service | `<dockerhub-user>/catalogue-service` | `v0.1`, `latest` |

Tên tài khoản Docker Hub dùng chung: `____________` (cả nhóm điền).

```
.
├── api-service/            # TV1 (kèm k8s/: deployment, service, hpa)
├── catalogue-service/      # TV2 (kèm k8s/: deployment, service, hpa; scripts/: seed, smoke_test)
├── k8s/                    # TV3: namespace, database-statefulset, secret | TV4: ingress
├── monitoring/             # TV4: Prometheus, Grafana, ServiceMonitor
├── load-tests/             # TV3
├── docs/contract.md        # file này
├── docker-compose.yml      # chạy local: postgres + catalogue (+ api-service)
└── .github/workflows/      # CI/CD (hướng phát triển 1)
```

## 13. Dành cho load test (TV3)

Gọi qua Ingress tới API Service. Các dòng 2 đến 5 phụ thuộc mục 3.1 (TV1 xác nhận).

| Hành động | Request | Tỷ lệ gợi ý |
|---|---|---|
| Xem danh sách | `GET /products?limit=20&offset=<ngẫu nhiên>` | 60% |
| Xem chi tiết | `GET /products/{id}` (id ngẫu nhiên 1..500) | 25% |
| Tạo mới | `POST /products` | 10% |
| Cập nhật | `PUT /products/{id}` | 4% |
| Xóa | `DELETE /products/{id}` | 1% |

Trước khi bắn tải: `seed.py --count 500 --reset` để id hợp lệ trong khoảng 1..500. Xóa sản phẩm làm một số id trả 404, script tải cần coi 404 của `GET`/`PUT`/`DELETE` là hợp lệ, không tính vào Error Rate.

| Kịch bản | Gợi ý cấu hình |
|---|---|
| Normal Load | 20 user, giữ 10 phút |
| Spike Load | 20 → 300 user trong 30 giây, giữ 3 phút, rồi giảm về 20 |
| Sustained Load | 150 user, giữ 20 phút |

Chỉ số cần ghi lại: Response Time (p50/p95/p99), Error Rate, số Pod theo thời gian. Số liệu là gợi ý khởi điểm, điều chỉnh theo máy chạy cụm.

## 14. Các điểm cần cả nhóm xác nhận

TV2 tự quyết khi bổ sung v1.1, cần mọi người đồng ý hoặc đổi:

- [ ] `DELETE` trả 204 không body (TV1: chuyển tiếp đúng; TV3: script tải không parse JSON).
- [ ] Catalogue có `GET /ready`, probe readiness dùng `/ready`.
- [ ] `GET /products` có `limit`/`offset` và header `X-Total-Count`; response vẫn là mảng.
- [ ] Mục 3.1: API Service chuyển tiếp đủ CRUD (TV1).
- [ ] Tên biến timeout của API Service: `CATALOGUE_TIMEOUT_SECONDS` (TV1).
- [ ] Tên tài khoản Docker Hub chung.
- [ ] Hostname Ingress (đề xuất `shop.local`) và Ingress Controller NGINX (TV4).
- [ ] Cụm local: Minikube hay K3s.
