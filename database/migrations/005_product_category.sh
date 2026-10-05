#!/bin/sh
set -eu

# Demo schema 的可重复增量迁移；旧业务记录保留未知类别。
case "$MYSQL_DATABASE" in
  *[!A-Za-z0-9_]*|'') echo 'Invalid Demo database name' >&2; exit 1 ;;
esac
count=$(mysql -N -u root -p"$MYSQL_ROOT_PASSWORD" -e \
  "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = '$MYSQL_DATABASE' AND table_name = 'order_items' AND column_name = 'product_category'")
if [ "$count" = 0 ]; then
  mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e \
    'ALTER TABLE order_items ADD COLUMN product_category VARCHAR(64) NULL'
fi

# 仅为明确标注为 Demo 的四个样例 SKU 补充类别，不猜测其他业务数据。
mysql --default-character-set=utf8mb4 -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" <<'SQL'
SET NAMES utf8mb4;
UPDATE order_items i JOIN orders o ON o.id = i.order_id
SET i.product_category = CASE i.sku
  WHEN 'DEMO-KEYBOARD' THEN '电脑配件'
  WHEN 'DEMO-MOUSE' THEN '电脑配件'
  WHEN 'DEMO-CABLE' THEN '数码配件'
  WHEN 'DEMO-STAND' THEN '数码配件'
END
WHERE o.order_no IN ('ORD-DEMO-001', 'ORD-DEMO-002', 'ORD-DEMO-003')
  AND i.sku IN ('DEMO-KEYBOARD', 'DEMO-MOUSE', 'DEMO-CABLE', 'DEMO-STAND');
SQL
