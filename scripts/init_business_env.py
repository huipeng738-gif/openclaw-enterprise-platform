"""Create local demo database credentials without replacing existing values."""
from pathlib import Path
import secrets


# 仅首次生成项目内的 Demo MySQL 配置，已有文件保持不变。
def main():
    target = Path(__file__).resolve().parents[1] / '.env.business'
    if target.exists():
        print('Business database environment already exists; unchanged')
        return
    root_password = secrets.token_urlsafe(32)
    app_password = secrets.token_urlsafe(32)
    target.write_text(
        'MYSQL_DATABASE=openclaw_business\n'
        'MYSQL_USER=openclaw_app\n'
        f'MYSQL_PASSWORD={app_password}\n'
        f'MYSQL_ROOT_PASSWORD={root_password}\n'
        'BUSINESS_DB_HOST=mysql\n'
        'BUSINESS_DB_PORT=3306\n'
        'BUSINESS_DB_NAME=openclaw_business\n'
        'BUSINESS_DB_USER=openclaw_app\n'
        f'BUSINESS_DB_PASSWORD={app_password}\n'
        'BUSINESS_DB_TIMEOUT_SECONDS=5\n', encoding='utf-8')
    target.chmod(0o600)
    print('Created local demo business database environment')


if __name__ == '__main__':
    main()
