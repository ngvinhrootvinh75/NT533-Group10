"""Nạp dữ liệu mẫu vào bảng products (phục vụ load test).

Chạy local:        python scripts/seed.py --count 500
Chạy trong K8s:    kubectl -n shop exec deploy/catalogue-service -- python scripts/seed.py --count 500
Xóa dữ liệu cũ:    thêm --reset (TRUNCATE và đặt lại id về 1, để id ngẫu nhiên 1..N trong script tải luôn hợp lệ)

Dùng chính các biến môi trường DB_* của service.
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import SCHEMA_STATEMENTS  # noqa: E402

CATEGORIES = ["Laptop", "Điện thoại", "Tai nghe", "Bàn phím", "Chuột", "Màn hình", "Ổ cứng SSD", "Loa", "Webcam", "Router"]
BRANDS = ["Dell", "HP", "Asus", "Lenovo", "Apple", "Samsung", "Logitech", "Sony", "Xiaomi", "Acer"]
DESCRIPTIONS = [
    "Hàng chính hãng, bảo hành 12 tháng",
    "Phù hợp cho lập trình viên và dân văn phòng",
    "Thiết kế nhỏ gọn, pin bền",
    "Hiệu năng cao, giá tốt",
    None,
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dữ liệu mẫu cho catalogue-service")
    parser.add_argument("--count", type=int, default=500, help="Số sản phẩm cần tạo (mặc định 500)")
    parser.add_argument("--reset", action="store_true", help="Xóa toàn bộ dữ liệu cũ và đặt lại id về 1")
    args = parser.parse_args()

    rng = random.Random(42)  # cố định seed để dữ liệu lặp lại được giữa các lần chạy
    rows = []
    for i in range(1, args.count + 1):
        name = f"{rng.choice(CATEGORIES)} {rng.choice(BRANDS)} #{i}"
        price = round(rng.uniform(5, 2500), 2)
        stock = rng.randint(0, 200)
        rows.append((name, rng.choice(DESCRIPTIONS), price, stock))

    with psycopg.connect(settings.conninfo, connect_timeout=10) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        if args.reset:
            conn.execute("TRUNCATE TABLE products RESTART IDENTITY")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO products (name, description, price, stock) VALUES (%s, %s, %s, %s)",
                rows,
            )
        total = conn.execute("SELECT count(*) FROM products").fetchone()[0]

    print(f"Đã thêm {len(rows)} sản phẩm. Tổng số hiện có: {total}")


if __name__ == "__main__":
    main()
