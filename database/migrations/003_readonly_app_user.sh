#!/bin/sh
set -eu

# mysql:8.4 initially grants the configured application user full database rights.
# Restrict this Demo application's account to SELECT after schema and seed setup.
case "$MYSQL_USER:$MYSQL_DATABASE" in
  *[!A-Za-z0-9_:]*|'') echo 'Invalid Demo database identifiers' >&2; exit 1 ;;
esac
mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<SQL
REVOKE ALL PRIVILEGES, GRANT OPTION FROM '$MYSQL_USER'@'%';
GRANT SELECT ON \`$MYSQL_DATABASE\`.* TO '$MYSQL_USER'@'%';
SQL
