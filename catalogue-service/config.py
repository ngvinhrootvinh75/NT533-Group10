"""Cấu hình catalogue-service, đọc hoàn toàn từ biến môi trường.

Tên biến bám theo docs/contract.md. Khi chạy trên Kubernetes, DB_NAME/DB_USER/DB_PASSWORD
được lấy từ Secret `postgres-secret` (xem k8s/deployment.yaml).
"""

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    port: int = _int("PORT", 8001)
    log_level: str = os.getenv("LOG_LEVEL", "info").upper()

    db_host: str = os.getenv("DB_HOST", "postgres-service")
    db_port: int = _int("DB_PORT", 5432)
    db_name: str = os.getenv("DB_NAME", "shopdb")
    db_user: str = os.getenv("DB_USER", "shop")
    db_password: str = os.getenv("DB_PASSWORD", "")

    # Connection pool: mỗi Pod giữ tối đa db_pool_max kết nối tới PostgreSQL.
    # Với HPA tối đa 8 Pod x 10 = 80 kết nối, thấp hơn max_connections mặc định (100) của PostgreSQL.
    db_pool_min: int = _int("DB_POOL_MIN", 2)
    db_pool_max: int = _int("DB_POOL_MAX", 10)
    db_pool_timeout: int = _int("DB_POOL_TIMEOUT_SECONDS", 5)

    # Khi Pod khởi động trước DB, thử lại thay vì chết ngay.
    db_connect_retries: int = _int("DB_CONNECT_RETRIES", 30)
    db_connect_delay: int = _int("DB_CONNECT_DELAY_SECONDS", 2)

    # Giới hạn phân trang cho GET /products
    default_limit: int = _int("DEFAULT_LIMIT", 100)
    max_limit: int = _int("MAX_LIMIT", 1000)

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password}"
        )


settings = Settings()
