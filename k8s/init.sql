CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products (name, description, price, stock) VALUES
('Laptop Dell XPS 15', 'Laptop cao cấp cho lập trình viên', 1500.00, 10),
('Bàn phím cơ Keychron K2', 'Bàn phím cơ không dây Bluetooth', 99.99, 50),
('Chuột Logitech MX Master 3S', 'Chuột công thái học cao cấp', 119.00, 30),
('Màn hình Dell UltraSharp 27', 'Màn hình 4K hiển thị sắc nét', 450.00, 15);