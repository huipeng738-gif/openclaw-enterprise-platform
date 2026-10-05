-- Demo / Development Test Data only. Fixed keys keep integration checks repeatable.
SET NAMES utf8mb4;
INSERT INTO customers (customer_no, name, phone, level, status, created_at) VALUES
  ('CUST-DEMO-001', '演示客户甲', '13800000001', 'vip', 'active', '2026-08-01 10:00:00'),
  ('CUST-DEMO-002', '演示客户乙', '13800000002', 'regular', 'active', '2026-08-05 11:00:00');

INSERT INTO orders (order_no, customer_id, status, total_amount, payment_status, created_at, updated_at) VALUES
  ('ORD-DEMO-001', (SELECT id FROM customers WHERE customer_no = 'CUST-DEMO-001'), 'shipped', 299.00, 'paid', '2026-09-01 09:00:00', '2026-09-02 09:00:00'),
  ('ORD-DEMO-002', (SELECT id FROM customers WHERE customer_no = 'CUST-DEMO-001'), 'pending', 49.00, 'unpaid', '2026-09-10 09:00:00', '2026-09-10 09:00:00'),
  ('ORD-DEMO-003', (SELECT id FROM customers WHERE customer_no = 'CUST-DEMO-002'), 'completed', 129.00, 'paid', '2026-09-12 09:00:00', '2026-09-13 09:00:00');

INSERT INTO order_items (order_id, product_name, sku, quantity, unit_price) VALUES
  ((SELECT id FROM orders WHERE order_no = 'ORD-DEMO-001'), '演示键盘', 'DEMO-KEYBOARD', 1, 199.00),
  ((SELECT id FROM orders WHERE order_no = 'ORD-DEMO-001'), '演示鼠标', 'DEMO-MOUSE', 2, 50.00),
  ((SELECT id FROM orders WHERE order_no = 'ORD-DEMO-002'), '演示数据线', 'DEMO-CABLE', 1, 49.00),
  ((SELECT id FROM orders WHERE order_no = 'ORD-DEMO-003'), '演示支架', 'DEMO-STAND', 1, 129.00);
