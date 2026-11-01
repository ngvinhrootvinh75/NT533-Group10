# API CONTRACT – NT533 GROUP 10

**Version:** 1.0  
**Người thiết kế:** TV1 – API Service  
**Trạng thái:** Quy ước triển khai chung, TV2 thực hiện theo hợp đồng này.

## 1. Kiến trúc hệ thống

Client → API Service → Catalogue Service → PostgreSQL

API Service không truy cập trực tiếp PostgreSQL. Catalogue Service chịu trách nhiệm tương tác với cơ sở dữ liệu.

## 2. Thông tin các Service

| Thành phần | Công nghệ | Port | Kubernetes Service |
|---|---|---|---|
| API Service | Python FastAPI | 8000 | api-service |
| Catalogue Service | Python FastAPI | 8001 | catalogue-service |
| Database | PostgreSQL | 5432 | postgres-service |

API Service gọi Catalogue qua địa chỉ cấu hình bằng biến môi trường `CATALOGUE_BASE_URL`.

- Local: `http://127.0.0.1:8001`
- Kubernetes: `http://catalogue-service:8001`
- Timeout: 3 giây

## 3. API Service Endpoints

### GET /health

Mục đích: Kiểm tra API Service đang hoạt động.

HTTP Status: `200 OK`

Response:

```json
{
  "status": "ok",
  "service": "api-service"
}
```

### GET /products

Mục đích: Lấy danh sách sản phẩm từ Catalogue Service.

HTTP Status: `200 OK`

Response:

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

Dữ liệu hiện tại là dữ liệu mẫu. Khi hoàn thiện tích hợp, API Service phải lấy dữ liệu thực từ Catalogue Service.

### GET /ready

Mục đích: Kiểm tra API Service sẵn sàng nhận request.

HTTP Status: 200 OK

Response:
{
  "status": "ready",
  "service": "api-service"
}

Lưu ý: Readiness hiện tại chỉ kiểm tra API Service,
chưa kiểm tra trạng thái Catalogue Service.

## 4. Catalogue Service Endpoints

TV2 triển khai các endpoint sau:

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | /health | Kiểm tra Catalogue Service |
| GET | /products | Lấy danh sách sản phẩm |
| GET | /products/{id} | Lấy sản phẩm theo ID |
| POST | /products | Thêm sản phẩm |
| PUT | /products/{id} | Cập nhật sản phẩm |
| DELETE | /products/{id} | Xóa sản phẩm |

Catalogue phải trả về JSON theo cấu trúc dữ liệu được thống nhất.

## 5. Cấu trúc Product

| Trường | Kiểu dữ liệu |
|---|---|
| id | Integer |
| name | String |
| description | String hoặc null |
| price | Number |
| stock | Integer |

Trường `created_at` được PostgreSQL quản lý, chưa bắt buộc trả về trong API phiên bản 1.0.

## 6. Quy ước xử lý lỗi

| Trường hợp | HTTP Status |
|---|---|
| Thành công | 200 |
| Tạo sản phẩm thành công | 201 |
| Dữ liệu gửi lên không hợp lệ | 422 |
| Không tìm thấy sản phẩm | 404 |
| Catalogue gặp lỗi nội bộ | 500 |
| API không kết nối được Catalogue | 503 |
| Catalogue phản hồi quá timeout | 504 |
| Catalogue trả lỗi HTTP hoặc dữ liệu không hợp lệ | 502 |

Định dạng lỗi thống nhất:

```json
{
  "detail": "Thông báo lỗi"
}
```

## 7. Quy định tích hợp

- Catalogue Service phải tương thích với API Contract phiên bản 1.0.
- API Service chạy cổng 8000.
- Catalogue Service chạy cổng 8001.
- Hai service trao đổi dữ liệu bằng HTTP REST và JSON.
- Catalogue Service truy cập PostgreSQL qua `postgres-service:5432` khi chạy trên Kubernetes.
- API Service cần hỗ trợ logging, xử lý timeout và xuất Prometheus metrics tại `/metrics`.
- Mọi thay đổi phá vỡ API Contract phải được thông báo và thống nhất trong nhóm trước khi áp dụng.