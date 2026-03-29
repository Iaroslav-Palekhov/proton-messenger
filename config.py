import os
import secrets
from datetime import timedelta


def _get_or_create_secret_key():
    env_key = os.environ.get('FLASK_SECRET_KEY')
    if env_key:
        return env_key
    key_file = '.secret_key'
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key = f.read().strip()
            if len(key) >= 32:
                return key
    key = secrets.token_hex(64)
    try:
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        print(f"[SECURITY] Создан новый SECRET_KEY -> {key_file}")
    except Exception:
        pass
    return key


class Config:
    # Базовые настройки
    SECRET_KEY = _get_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Оптимизация SQLAlchemy connection pool
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': 10,
        'max_overflow': 5,
        'connect_args': {'check_same_thread': False},
    }

    # Кэширование статических файлов (30 дней)
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 30

    # Загрузка файлов
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500 MB
    ALLOWED_EXTENSIONS = None

    # Сессии и куки
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_HTTPONLY = True       # JS не может читать cookie
    SESSION_COOKIE_SAMESITE = 'Lax'     # Защита от CSRF
    SESSION_COOKIE_SECURE = False        # True только при HTTPS
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False

    # Безопасность
    PASSWORD_PEPPER = os.environ.get('PASSWORD_PEPPER', 'papirus-pepper-change-this-in-production')
    MESSAGE_ENCRYPTION_KEY = os.environ.get('MESSAGE_ENCRYPTION_KEY')
    MAX_MESSAGE_LENGTH = 4000
    MAX_USERNAME_LENGTH = 50
    MIN_PASSWORD_LENGTH = 8
    RATELIMIT_ENABLED = True

    # Сжатие ответов (Flask-Compress)
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/javascript',
        'application/javascript', 'application/json',
        'text/plain', 'image/svg+xml'
    ]
    COMPRESS_LEVEL = 9       # Баланс скорость/размер (1-9)
    COMPRESS_MIN_SIZE = 100   # Сжимаем только если > 500 байт

    # Push-уведомления (ntfy)
    NTFY_SERVER = os.environ.get('NTFY_SERVER', 'https://ntfy.sh')

    # Базовый URL для invite-ссылок групп (укажи домен или IP:порт, без слэша на конце)
    # Пример: "https://example.com" или "http://192.168.1.10:5000"
    LINK_URL = os.environ.get('LINK_URL', '')

    # Продакшен: раскомментируй при HTTPS:
    # SESSION_COOKIE_SECURE = True
    # REMEMBER_COOKIE_SECURE = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
