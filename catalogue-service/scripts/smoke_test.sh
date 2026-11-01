#!/usr/bin/env bash
# Smoke test cho catalogue-service: kiểm tra CRUD, mã lỗi và /metrics theo API Contract.
#
# Cách chạy (cần bash và curl; service và PostgreSQL đang chạy):
#   docker compose up --build -d          # ở thư mục gốc repo
#   bash catalogue-service/scripts/smoke_test.sh                    # mặc định http://localhost:8001
#   BASE_URL=http://localhost:8001 bash catalogue-service/scripts/smoke_test.sh
#
# Thoát với mã 0 nếu mọi kiểm tra đều đạt, khác 0 nếu có kiểm tra thất bại.

BASE_URL="${BASE_URL:-http://localhost:8001}"
BODY="$(mktemp)"
HEADERS="$(mktemp)"
trap 'rm -f "$BODY" "$HEADERS"' EXIT

PASS=0
FAIL=0

check() {  # check "<mô tả>" <điều kiện: 0 = đạt>
  if [ "$2" -eq 0 ]; then
    PASS=$((PASS + 1)); echo "  [OK]   $1"
  else
    FAIL=$((FAIL + 1)); echo "  [FAIL] $1"
    echo "         body: $(head -c 300 "$BODY")"
  fi
}

# req <METHOD> <PATH> [JSON_BODY]  -> in mã HTTP, lưu body vào $BODY, header vào $HEADERS
req() {
  local method="$1" path="$2" data="${3:-}"
  if [ -n "$data" ]; then
    curl -s -o "$BODY" -D "$HEADERS" -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" -d "$data" "$BASE_URL$path"
  else
    curl -s -o "$BODY" -D "$HEADERS" -w "%{http_code}" -X "$method" "$BASE_URL$path"
  fi
}

echo "== Smoke test catalogue-service tại $BASE_URL =="

echo "-- Health"
code=$(req GET /health);  check "GET /health -> 200" $([ "$code" = 200 ] && echo 0 || echo 1)
grep -q '"service":"catalogue-service"' "$BODY"; check "/health có service = catalogue-service" $?
code=$(req GET /ready);   check "GET /ready -> 200 (DB sẵn sàng)" $([ "$code" = 200 ] && echo 0 || echo 1)

echo "-- Tạo sản phẩm"
code=$(req POST /products '{"name":"Smoke Laptop","description":"test","price":1500.5,"stock":10}')
check "POST /products -> 201" $([ "$code" = 201 ] && echo 0 || echo 1)
ID=$(sed -E 's/.*"id":([0-9]+).*/\1/' "$BODY")
check "Response có id số nguyên (id=$ID)" $([[ "$ID" =~ ^[0-9]+$ ]] && echo 0 || echo 1)
grep -q '"price":1500.5' "$BODY"; check "price trả về dạng số 1500.5" $?
grep -q '"stock":10' "$BODY";     check "stock = 10" $?

echo "-- Đọc"
code=$(req GET "/products/$ID"); check "GET /products/$ID -> 200" $([ "$code" = 200 ] && echo 0 || echo 1)
grep -q '"name":"Smoke Laptop"' "$BODY"; check "name đúng" $?
code=$(req GET "/products?limit=1&offset=0"); check "GET /products?limit=1 -> 200" $([ "$code" = 200 ] && echo 0 || echo 1)
head -c 1 "$BODY" | grep -q '\['; check "Danh sách là MẢNG JSON (đúng contract)" $?
grep -qi '^x-total-count: [0-9]\+' "$HEADERS"; check "Có header X-Total-Count" $?

echo "-- Cập nhật"
code=$(req PUT "/products/$ID" '{"name":"Smoke Laptop v2","description":null,"price":1999,"stock":5}')
check "PUT /products/$ID -> 200" $([ "$code" = 200 ] && echo 0 || echo 1)
grep -q '"name":"Smoke Laptop v2"' "$BODY"; check "name đã đổi" $?
grep -q '"description":null' "$BODY"; check "description null được chấp nhận" $?

echo "-- Lỗi"
code=$(req GET /products/999999999); check "GET id không tồn tại -> 404" $([ "$code" = 404 ] && echo 0 || echo 1)
grep -q '"detail"' "$BODY"; check "Lỗi có dạng {\"detail\": ...}" $?
code=$(req PUT /products/999999999 '{"name":"x","price":1,"stock":1}'); check "PUT id không tồn tại -> 404" $([ "$code" = 404 ] && echo 0 || echo 1)
code=$(req DELETE /products/999999999); check "DELETE id không tồn tại -> 404" $([ "$code" = 404 ] && echo 0 || echo 1)
code=$(req POST /products '{"name":"x","price":-1,"stock":1}'); check "POST price âm -> 422" $([ "$code" = 422 ] && echo 0 || echo 1)
grep -q '"detail"' "$BODY"; check "422 có {\"detail\": ...}" $?
code=$(req POST /products '{"name":"x","price":1000000000,"stock":1}'); check "POST price vượt NUMERIC(10,2) -> 422 (không phải 500)" $([ "$code" = 422 ] && echo 0 || echo 1)
code=$(req POST /products '{"price":1}'); check "POST thiếu name -> 422" $([ "$code" = 422 ] && echo 0 || echo 1)
code=$(req GET /products/abc); check "GET id không phải số -> 422" $([ "$code" = 422 ] && echo 0 || echo 1)

echo "-- Xóa"
code=$(req DELETE "/products/$ID"); check "DELETE /products/$ID -> 204" $([ "$code" = 204 ] && echo 0 || echo 1)
code=$(req GET "/products/$ID");    check "GET sau khi xóa -> 404" $([ "$code" = 404 ] && echo 0 || echo 1)

echo "-- Metrics (cùng quy ước với api-service)"
code=$(req GET /metrics); check "GET /metrics -> 200" $([ "$code" = 200 ] && echo 0 || echo 1)
grep -q '^http_requests_total{' "$BODY"; check "Có http_requests_total" $?
grep -q '^http_request_duration_seconds_bucket{' "$BODY"; check "Có http_request_duration_seconds (histogram)" $?
grep -q '^http_request_errors_total{.*status_code="404"' "$BODY"; check "Có http_request_errors_total với status_code=404" $?
grep -q 'http_requests_total{[^}]*method="POST"[^}]*route="/products"[^}]*status_code="201"' "$BODY" \
  || grep -q 'http_requests_total{[^}]*route="/products"[^}]*status_code="201"' "$BODY"; check "Nhãn route và status_code đúng quy ước (route=\"/products\", status_code=\"201\")" $?
grep -q 'route="/products/{product_id}"' "$BODY"; check "route dùng mẫu /products/{product_id}, không dùng id thật" $?
grep -q "route=\"/products/$ID\"" "$BODY"; [ $? -ne 0 ]; check "Không có route chứa id thật (tránh bùng nổ cardinality)" $?
grep -qE 'route="/(health|ready|metrics)"' "$BODY"; [ $? -ne 0 ]; check "/health, /ready, /metrics không bị đếm" $?
grep -q '^process_cpu_seconds_total' "$BODY"; check "Có process_cpu_seconds_total" $?

echo
echo "Kết quả: $PASS đạt, $FAIL thất bại"
[ "$FAIL" -eq 0 ]
