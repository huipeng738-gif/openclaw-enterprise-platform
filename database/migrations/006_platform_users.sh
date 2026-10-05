#!/bin/sh
set -eu

# 由 MySQL 初始化容器以 root 执行；业务账号只获平台账号表的必要写权限。
mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" <<SQL
CREATE TABLE IF NOT EXISTS platform_users (
  username VARCHAR(80) PRIMARY KEY,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('viewer','operator','admin') NOT NULL,
  disabled BOOLEAN NOT NULL DEFAULT FALSE,
  session_version BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT, INSERT, UPDATE, DELETE ON \`$MYSQL_DATABASE\`.platform_users TO '$MYSQL_USER'@'%';
SQL
