# Catalogue Service (TV2)

CRUD danh mục sản phẩm, port **8001**, FastAPI + PostgreSQL. Tuân theo `api-service/API_CONTRACT.md` (TV1). Cấu hình khớp với `k8s/database-statefulset.yaml` (TV3) và `k8s/ingress.yaml`, `k8s/hpa.yaml` (TV4).

## 1. Cấu trúc thư mục

```
catalogue-service/
├── app/            # config.py, db.py, schemas.py, metrics.py, main.py
├── scripts/        # seed.py (nạp dữ liệu mẫu), smoke_test.sh (kiểm tra nhanh)
├── Dockerfile
├── requirements.txt
└── README.md
k8s/catalogue-deployment.yaml   # Deployment + Service của catalogue
k8s/catalogue-hpa.yaml          # HPA của catalogue
docker-compose.yml              # chạy local ở thư mục gốc repo
```

## 2. Chạy thử ở máy local

```bash
docker compose up --build -d                       # ở thư mục gốc repo
bash catalogue-service/scripts/smoke_test.sh        # mọi dòng phải [OK] (cần bash: Git Bash hoặc WSL)
docker compose exec catalogue-service python scripts/seed.py --count 500 --reset
docker compose down -v                              # dọn sạch, kể cả dữ liệu
```

Compose dùng đúng `postgres:15-alpine`, DB `catalogue_db` và nạp `k8s/init.sql` của TV3, nên schema giống hệt trên cụm.

## 3. Biến môi trường

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `PORT` | `8001` | |
| `DB_HOST` | `postgres-service` | Service của TV3 |
| `DB_PORT` | `5432` | |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `catalogue_db` / `postgres` / (rỗng) | Phải khớp `POSTGRES_*` trong `database-statefulset.yaml` |
| `LOG_LEVEL` | `info` | |
| `DB_POOL_MIN` / `DB_POOL_MAX` | `1` / `8` | Mỗi Pod tối đa 8 kết nối. HPA max 10 Pod = 80, dưới `max_connections=100` của PostgreSQL |
| `DB_CONNECT_RETRIES` / `DB_CONNECT_DELAY_SECONDS` | `30` / `2` | Chờ DB tối đa 60 giây khi khởi động |
| `DEFAULT_LIMIT` / `MAX_LIMIT` | `100` / `1000` | Phân trang của `GET /products` |

## 4. Endpoint

| Method | Path | Thành công | Lỗi |
|---|---|---|---|
| GET | `/health` | 200 `{"status":"ok","service":"catalogue-service"}` | |
| GET | `/ready` | 200 | 503 khi mất DB |
| GET | `/metrics` | 200 (text Prometheus) | |
| GET | `/products?limit=&offset=` | 200, **mảng** sản phẩm | 422 |
| GET | `/products/{id}` | 200 | 404, 422 |
| POST | `/products` | 201 | 422 |
| PUT | `/products/{id}` | 200 | 404, 422 |
| DELETE | `/products/{id}` | **204, không có body** | 404 |

- Product: `id`, `name` (1 đến 255 ký tự), `description` (có thể `null`), `price` (0 đến 99.999.999,99), `stock` (>= 0).
- `GET /products` trả mảng thuần như contract. Tổng số bản ghi ở header `X-Total-Count`.
- Mọi lỗi có dạng `{"detail": "<thông báo>"}`. Lỗi không lường trước trả 500. Catalogue không tự sinh 502/503/504 (trừ `/ready`), đó là mã của api-service.

## 5. Metrics (cùng quy ước với api-service)

`GET /metrics` cùng port 8001, tên metric và nhãn giống `API_CONTRACT.md` mục 8:

| Metric | Loại | Nhãn |
|---|---|---|
| `http_requests_total` | Counter | `method`, `route`, `status_code` |
| `http_request_duration_seconds` | Histogram (bucket mặc định) | `method`, `route`, `status_code` |
| `http_request_errors_total` | Counter, status >= 400 | `method`, `route`, `status_code` |

- `route` là mẫu route: `/products` hoặc `/products/{product_id}`, không phải id thật.
- Catalogue **không đếm** `/metrics`, `/health`, `/ready` (để request của kubelet không làm nhiễu số liệu). api-service hiện chỉ loại `/metrics`, nên nên loại thêm hai endpoint kia để hai bên nhất quán.

## 6. Kubernetes (namespace `default`, như các file khác trong `k8s/`)

```bash
kubectl apply -f k8s/database-statefulset.yaml     # TV3
sed -i 's#DOCKERHUB_USER#<noi-chua-image>#' k8s/catalogue-deployment.yaml   # xem ghi chú bên dưới
kubectl apply -f k8s/catalogue-deployment.yaml
kubectl rollout status deploy/catalogue-service
kubectl apply -f k8s/catalogue-hpa.yaml            # cần Metrics Server (TV4)
kubectl exec deploy/catalogue-service -- python scripts/seed.py --count 500 --reset
```

- Image: `DOCKERHUB_USER/catalogue-service:v0.1` là chỗ giữ chỗ. Docker Hub: `<tai-khoan>/catalogue-service:v0.1`. GHCR: `ghcr.io/<owner-viet-thuong>/catalogue-service:v0.1`.
- Test không cần registry: `docker build -t catalogue-service:test ./catalogue-service` rồi `minikube image load catalogue-service:test`, và dùng `sed` đổi tên image thành `catalogue-service:test` trên đường ống `kubectl apply -f -`, không sửa file.
- Mật khẩu DB đang nằm thẳng trong `catalogue-deployment.yaml` vì `database-statefulset.yaml` cũng làm vậy. Khi TV3 chuyển sang Secret thì đổi `DB_PASSWORD` (và `DB_USER`, `DB_NAME`) sang `secretKeyRef`.

## 7. Thông tin bàn giao

### TV1 (api-service)
- Gọi catalogue qua `CATALOGUE_BASE_URL=http://catalogue-service:8001` (cùng namespace `default`). Local: `http://127.0.0.1:8001`.
- Catalogue trả mảng JSON cho `GET /products`, đúng cấu trúc trong `API_CONTRACT.md` mục 5.
- Hiện api-service chỉ có `GET /products`. Nếu muốn load test có ghi dữ liệu, cần chuyển tiếp thêm `GET/PUT/DELETE /products/{id}` và `POST /products`. `DELETE` trả **204 không body**; `404` của catalogue nên chuyển nguyên 404 (code hiện tại đổi mọi lỗi HTTP thành 502).
- Deployment api-service cần `resources.requests`, nếu không HPA của TV4 không tính được % CPU. Repo chưa có Deployment/Service của api-service, trong khi `ingress.yaml` và `hpa.yaml` đều đang trỏ vào chúng.

### TV3 (database, load test)
- Catalogue kết nối theo đúng `database-statefulset.yaml`: `postgres-service:5432`, DB `catalogue_db`, user `postgres`. Đổi một trong các giá trị này thì báo TV2.
- Bảng `products` do `init.sql` của TV3 tạo và là nguồn sự thật. Catalogue không sửa bảng, chỉ có câu `CREATE TABLE IF NOT EXISTS` giống hệt làm dự phòng. Đổi cấu trúc cột thì báo TV2 sửa `db.py`.
- Nạp dữ liệu mẫu: lệnh seed ở mục 6. `--reset` xóa sạch rồi đánh lại id 1..N, nên script tải có thể chọn id ngẫu nhiên 1..500. Nếu không `--reset`, id bắt đầu sau 2 dòng mẫu của `init.sql`.
- Script tải: coi `404` ở GET/PUT/DELETE theo id là hợp lệ khi có xóa. Ingress của TV4 đang giới hạn tốc độ (xem bên dưới), cần gỡ khi bắn tải.

### TV4 (ingress, monitoring, HPA)
- Catalogue **không** ra Ingress. Chỉ `api-service:8000`.
- ServiceMonitor: namespace `default`, Service có label `app: catalogue-service`, port tên `http`, path `/metrics`. Pod cũng có annotation `prometheus.io/scrape`.
- Metrics của catalogue và api-service dùng chung nhãn `route`, `status_code`, nên một bộ truy vấn PromQL dùng cho cả hai.
- `ingress.yaml` đang có `limit-rps: "20"` và `limit-connections: "10"`: kịch bản Spike (300 user) sẽ bị NGINX từ chối gần hết, request không tới Pod nên HPA không scale. Cần gỡ hoặc nâng hạn mức trong lúc bắn tải.
- Ingress đang trỏ `/` (Prefix) vào api-service nên `/metrics` của api-service cũng lộ ra ngoài, trong khi `API_CONTRACT.md` mục 8 yêu cầu hạn chế.
- `catalogue-hpa.yaml` dùng cùng ngưỡng với `hpa.yaml`: min 2, max 10, CPU 70%.

## 8. Đề xuất sửa `api-service/API_CONTRACT.md` (cần TV1 đồng ý)

1. Mục 4: thêm `GET /ready`, `GET /metrics`, tham số `limit`/`offset`, header `X-Total-Count`, `DELETE` trả 204.
2. Mục 2: PostgreSQL ghi 15 (đúng `postgres:15-alpine` của TV3).
3. Mục 8: ghi chú catalogue dùng cùng bộ metric và loại `/health`, `/ready` khỏi thống kê.
4. Ghi rõ namespace chung là `default`.
