from flask import Flask, session, redirect, url_for
from flask_login import LoginManager, logout_user, current_user
from config import Config
from models import db, User, UserSession
from routing import register_routes
from utils import create_upload_folders, create_default_avatars
from security import init_security
from socketio_events import socketio
from datetime import datetime
import os

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Flask-SocketIO
    socketio.init_app(app)

    # Сжатие ответов (gzip/brotli) — уменьшает трафик на 60-80%
    try:
        from flask_compress import Compress
        Compress(app)
    except ImportError:
        print("[INFO] flask-compress не установлен. Запусти: pip install flask-compress")

    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Создаём папки для загрузок
    with app.app_context():
        create_upload_folders(app)
        create_default_avatars(app)
        db.create_all()

    # Регистрируем маршруты
    register_routes(app, db, login_manager)

    # Инициализируем модуль безопасности (после регистрации маршрутов!)
    init_security(app)

    # ============================================================
    # ПРОВЕРКА ВАЛИДНОСТИ СЕССИИ ПРИ КАЖДОМ ЗАПРОСЕ
    # ============================================================
    # Если сессия была завершена удалённо (например через страницу
    # безопасности с другого устройства), пользователь будет
    # принудительно разлогинен при следующем запросе.

    @app.before_request
    def validate_session():
        # Проверяем только авторизованных пользователей
        if not current_user.is_authenticated:
            return

        # Пропускаем статику
        from flask import request
        if request.endpoint and request.endpoint.startswith('static'):
            return

        # Получаем токен текущей сессии из Flask session
        session_token = session.get('session_token')

        if not session_token:
            # Нет токена — старая сессия до введения системы сессий,
            # создаём новую запись автоматически
            return

        # Кэшируем результат валидации в g, чтобы не лезть в БД дважды за запрос
        from flask import g as _g
        cache_key = f'sess_valid_{session_token}'
        if hasattr(_g, cache_key):
            return

        # Ищем сессию в БД
        user_session = UserSession.query.filter_by(
            session_token=session_token,
            user_id=current_user.id
        ).first()

        if not user_session:
            # Токен не найден в БД — разлогиниваем
            logout_user()
            session.clear()
            return redirect(url_for('login'))

        if not user_session.is_active:
            # Сессия была завершена удалённо — принудительно разлогиниваем
            logout_user()
            session.clear()
            return redirect(url_for('login'))

        # Помечаем как проверенное для этого запроса
        setattr(_g, cache_key, True)

        # Обновляем время последней активности (не чаще раза в минуту)
        now = datetime.utcnow()
        delta = now - user_session.last_active
        if delta.total_seconds() > 60:
            user_session.last_active = now
            db.session.commit()

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=2200, allow_unsafe_werkzeug=True)
