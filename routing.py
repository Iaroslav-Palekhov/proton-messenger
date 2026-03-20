from flask import render_template, request, jsonify, redirect, url_for, send_from_directory, session
from flask_login import login_user, login_required, logout_user, current_user
from security import PasswordSecurity
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from sqlalchemy import text as sa_text
import os
import mimetypes
import secrets
import threading
import zipfile
import io
import shutil

from models import User, Group, GroupMember, Chat, Message, ForwardedMessage, PasswordReset, UserSession, BlockedUser, Contact, UserPrivacy
from socketio_events import socketio
from utils import (
    compress_image, get_file_category, get_file_icon,
    format_file_size, is_file_too_large, save_file,
    extract_link_preview, contains_url, extract_urls_from_text
)

def register_routes(app, db, login_manager):

    @app.after_request
    def add_cache_headers(response):
        """Кэшируем статику на 30 дней, HTML не кэшируем."""
        if request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=2592000, immutable'
        elif response.content_type and 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СЕССИЙ
    # ============================================================

    def _parse_user_agent(ua_string):
        """Разбирает User-Agent строку в читаемый вид."""
        try:
            import user_agents as ua_lib
            ua = ua_lib.parse(ua_string)
            browser  = f"{ua.browser.family} {ua.browser.version_string}".strip()
            os_info  = f"{ua.os.family} {ua.os.version_string}".strip()
            if ua.is_mobile:
                device_type = 'mobile'
            elif ua.is_tablet:
                device_type = 'tablet'
            else:
                device_type = 'desktop'
            return browser, os_info, device_type
        except Exception:
            short_ua = (ua_string[:80] if ua_string else 'Неизвестно')
            return short_ua, 'Неизвестно', 'desktop'

    def _get_client_ip():
        """Получает реальный IP клиента с учётом прокси."""
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'

    def _create_session_record(user_id, session_token, is_current=False):
        """Создаёт запись о новой сессии в БД."""
        ua_string = request.user_agent.string or ''
        browser, os_info, device_type = _parse_user_agent(ua_string)

        sess = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=_get_client_ip(),
            user_agent=ua_string[:500],
            browser=browser[:100],
            os=os_info[:100],
            device_type=device_type,
            is_active=True,
            is_current=is_current
        )
        db.session.add(sess)
        db.session.commit()
        return sess

    def _current_session_age():
        """Возвращает возраст текущей сессии в секундах. None если сессия не найдена."""
        current_token = session.get('session_token')
        if not current_token:
            return None
        sess = UserSession.query.filter_by(
            session_token=current_token,
            user_id=current_user.id
        ).first()
        if not sess:
            return None
        return (datetime.utcnow() - sess.created_at).total_seconds()

    def _is_blocked_between(user_a_id, user_b_id):
        return BlockedUser.query.filter(
            ((BlockedUser.blocker_id == user_a_id) & (BlockedUser.blocked_id == user_b_id)) |
            ((BlockedUser.blocker_id == user_b_id) & (BlockedUser.blocked_id == user_a_id))
        ).first() is not None

    def _get_status_display(target_user, viewer_id):
        """Возвращает статус target_user с учётом его настроек приватности."""
        if target_user.id == viewer_id:
            return target_user.status
        privacy = UserPrivacy.query.filter_by(user_id=target_user.id).first()
        setting = privacy.last_seen if privacy else 'all'
        if setting == 'nobody':
            return target_user.status if target_user.status == 'online' else 'offline'
        if setting == 'contacts':
            i_am_contact = Contact.query.filter_by(owner_id=target_user.id, contact_id=viewer_id).first() is not None
            if not i_am_contact:
                return target_user.status if target_user.status == 'online' else 'offline'
        return target_user.status

    def _get_last_seen_display(target_user, viewer_id):
        """Возвращает строку last_seen с учётом приватности. None если не показывать точное время."""
        if target_user.id == viewer_id:
            return target_user.last_seen.strftime('%d.%m.%Y %H:%M') if target_user.last_seen else None
        if target_user.status == 'online':
            return None
        privacy = UserPrivacy.query.filter_by(user_id=target_user.id).first()
        setting = privacy.last_seen if privacy else 'all'
        if setting == 'nobody':
            return 'недавно'
        if setting == 'contacts':
            i_am_contact = Contact.query.filter_by(owner_id=target_user.id, contact_id=viewer_id).first() is not None
            if not i_am_contact:
                return 'недавно'
        return target_user.last_seen.strftime('%d.%m.%Y %H:%M') if target_user.last_seen else 'давно'

    # ============================================================
    # ИНДЕКС
    # ============================================================

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('chats'))
        return redirect(url_for('login'))

    # ============================================================
    # АВТОРИЗАЦИЯ
    # ============================================================

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('chats'))

        if request.method == 'POST':
            import re
            email    = (request.form.get('email') or '').strip()[:254]
            username = (request.form.get('username') or '').strip()[:32]
            password = request.form.get('password') or ''
            password2 = request.form.get('password2') or ''

            if not email or not password or not username:
                return render_template('register.html', error='Заполните все поля')

            # Username: 5-32, только буквы/цифры/_
            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                return render_template('register.html', error='Имя пользователя: от 5 до 32 символов (буквы, цифры, _)')

            # Email базовая проверка
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                return render_template('register.html', error='Введите корректный email')

            # Пароль минимум 8 символов
            if len(password) < 8:
                return render_template('register.html', error='Пароль должен быть минимум 8 символов')

            if len(password) > 128:
                return render_template('register.html', error='Пароль слишком длинный (максимум 128 символов)')

            # Подтверждение пароля (если поле передано)
            if password2 and password != password2:
                return render_template('register.html', error='Пароли не совпадают')

            if User.query.filter_by(email=email).first():
                return render_template('register.html', error='Пользователь с такой почтой уже существует')

            if User.query.filter_by(username=username).first():
                return render_template('register.html', error='Имя пользователя уже занято')

            hashed_password = PasswordSecurity.hash_password(password)
            user = User(email=email, username=username, password=hashed_password)

            db.session.add(user)
            db.session.commit()

            login_user(user)
            session.permanent = True

            tok = secrets.token_hex(32)
            session['session_token'] = tok
            _create_session_record(user.id, tok, is_current=True)

            return redirect(url_for('chats'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('chats'))

        if request.method == 'POST':
            username = (request.form.get('username') or '').strip()[:254]
            password = request.form.get('password') or ''

            # Базовые проверки входных данных
            if not username or not password:
                return render_template('login.html', error='Заполните все поля')

            if len(password) > 128:
                return render_template('login.html', error='Неверный email/username или пароль')

            # Простая защита от брутфорса через сессию
            fail_key = '_login_fails'
            fail_time_key = '_login_fail_time'
            import time as _time

            fails = session.get(fail_key, 0)
            fail_time = session.get(fail_time_key, 0)

            # Сброс счётчика если прошло больше 15 минут
            if _time.time() - fail_time > 900:
                fails = 0

            if fails >= 10:
                remaining = int(900 - (_time.time() - fail_time))
                mins = remaining // 60
                return render_template('login.html', error=f'Слишком много попыток. Подождите {mins} мин.')

            user = User.query.filter(
                (User.email == username) | (User.username == username)
            ).first()

            if user and PasswordSecurity.verify_password(password, user.password):
                # Сброс счётчика при успехе
                session.pop(fail_key, None)
                session.pop(fail_time_key, None)

                login_user(user)
                session.permanent = True
                user.status    = 'online'
                user.last_seen = datetime.utcnow()
                db.session.commit()

                tok = secrets.token_hex(32)
                session['session_token'] = tok
                new_sess = _create_session_record(user.id, tok, is_current=True)

                # ── ntfy уведомление о новом входе ──
                try:
                    if user.push_token:
                        from ntfy_notifications import notify_new_login
                        device_str = f"{new_sess.browser or 'Браузер'} · {new_sess.os or 'ОС неизвестна'}"
                        ntfy_server = user.ntfy_server or app.config.get('NTFY_SERVER', 'https://ntfy.sh')
                        notify_new_login(user, new_sess.ip_address or '?', device_str, server=ntfy_server)
                except Exception:
                    pass

                return redirect(url_for('chats'))
            else:
                session[fail_key] = fails + 1
                session[fail_time_key] = _time.time()
                return render_template('login.html', error='Неверный email/username или пароль')

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        current_token = session.get('session_token')
        if current_token:
            sess = UserSession.query.filter_by(session_token=current_token).first()
            if sess:
                sess.end_session()

        current_user.status    = 'offline'
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        logout_user()
        return redirect(url_for('login'))

    # ============================================================
    # ЧАТЫ
    # ============================================================

    @app.route('/chats')
    @login_required
    def chats():
        # Личные чаты — один запрос с joinedload
        user_chats = Chat.query.filter(
            (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
        ).options(joinedload(Chat.user1), joinedload(Chat.user2)).order_by(Chat.last_message_at.desc()).all()

        chat_ids = [c.id for c in user_chats]
        if chat_ids:
            last_msg_subq = db.session.query(
                Message.chat_id, func.max(Message.id).label('max_id')
            ).filter(Message.chat_id.in_(chat_ids)).group_by(Message.chat_id).subquery()
            last_msgs = {m.chat_id: m for m in Message.query.join(
                last_msg_subq, Message.id == last_msg_subq.c.max_id).all()}
            unread_rows = db.session.query(
                Message.chat_id, func.count(Message.id)
            ).filter(
                Message.chat_id.in_(chat_ids),
                Message.receiver_id == current_user.id,
                Message.is_read == False
            ).group_by(Message.chat_id).all()
            unread_map = {r[0]: r[1] for r in unread_rows}
        else:
            last_msgs = {}; unread_map = {}

        chats_data = []
        for c in user_chats:
            chats_data.append({
                'id': c.id, 'type': 'private',
                'other_user': c.user2 if c.user1_id == current_user.id else c.user1,
                'last_message': last_msgs.get(c.id),
                'unread_count': unread_map.get(c.id, 0),
                'last_message_time': c.last_message_at
            })

        # Группы — один запрос с joinedload
        user_groups = GroupMember.query.filter_by(user_id=current_user.id).options(
            joinedload(GroupMember.group)
        ).all()
        group_ids = [m.group.id for m in user_groups if m.group]
        if group_ids:
            last_gsubq = db.session.query(
                Message.group_id, func.max(Message.id).label('max_id')
            ).filter(Message.group_id.in_(group_ids)).group_by(Message.group_id).subquery()
            last_gmsgs = {m.group_id: m for m in Message.query.join(
                last_gsubq, Message.id == last_gsubq.c.max_id).all()}
            unread_grows = db.session.query(
                Message.group_id, func.count(Message.id)
            ).filter(
                Message.group_id.in_(group_ids),
                Message.is_read == False,
                Message.sender_id != current_user.id
            ).group_by(Message.group_id).all()
            unread_gmap = {r[0]: r[1] for r in unread_grows}
        else:
            last_gmsgs = {}; unread_gmap = {}

        for m in user_groups:
            g = m.group
            if not g: continue
            chats_data.append({
                'id': g.id, 'type': 'group', 'group': g,
                'last_message': last_gmsgs.get(g.id),
                'unread_count': unread_gmap.get(g.id, 0),
                'last_message_time': g.last_message_at
            })

        chats_data.sort(key=lambda x: x['last_message_time'], reverse=True)
        return render_template('chats.html', chats=chats_data)

    @app.route('/start_chat', methods=['GET', 'POST'])
    @login_required
    def start_chat():
        if request.method == 'GET':
            username = request.args.get('username')
        else:
            username = request.form.get('username')

        if not username or username == current_user.username:
            return redirect(url_for('chats'))

        other_user = User.query.filter_by(username=username).first()
        if not other_user:
            return redirect(url_for('chats'))

        # Нельзя создать чат если есть блокировка в любую сторону
        if _is_blocked_between(current_user.id, other_user.id):
            return redirect(url_for('chats'))

        # Проверяем настройку приватности собеседника: кто может писать ему
        other_privacy = UserPrivacy.query.filter_by(user_id=other_user.id).first()
        if other_privacy and other_privacy.who_can_write == 'contacts':
            # Разрешаем только если current_user есть в контактах собеседника
            is_in_contacts = Contact.query.filter_by(
                owner_id=other_user.id, contact_id=current_user.id
            ).first() is not None
            if not is_in_contacts:
                # Чат уже существует — можно открыть (собеседник сам начал)
                existing = Chat.query.filter(
                    ((Chat.user1_id == current_user.id) & (Chat.user2_id == other_user.id)) |
                    ((Chat.user1_id == other_user.id) & (Chat.user2_id == current_user.id))
                ).first()
                if existing:
                    return redirect(url_for('chat', chat_id=existing.id))
                return redirect(url_for('chats'))

        existing_chat = Chat.query.filter(
            ((Chat.user1_id == current_user.id) & (Chat.user2_id == other_user.id)) |
            ((Chat.user1_id == other_user.id) & (Chat.user2_id == current_user.id))
        ).first()

        if existing_chat:
            return redirect(url_for('chat', chat_id=existing_chat.id))

        new_chat = Chat(user1_id=current_user.id, user2_id=other_user.id)
        db.session.add(new_chat)
        db.session.commit()

        return redirect(url_for('chat', chat_id=new_chat.id))

    @app.route('/chat/<int:chat_id>')
    @login_required
    def chat(chat_id):
        chat_obj = Chat.query.get_or_404(chat_id)
        if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
            return redirect(url_for('chats'))

        other_user = chat_obj.user2 if chat_obj.user1_id == current_user.id else chat_obj.user1

        # Только последние 50 сообщений — остальные грузятся lazy через get_messages
        messages = Message.query.filter_by(chat_id=chat_id, is_deleted=False).options(
            joinedload(Message.sender), joinedload(Message.reply_to)
        ).order_by(Message.timestamp.desc()).limit(50).all()
        messages = list(reversed(messages))

        # Помечаем прочитанными одним UPDATE
        db.session.query(Message).filter(
            Message.chat_id == chat_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).update({'is_read': True}, synchronize_session=False)
        db.session.commit()

        # Закреплённые — без N+1
        pinned_messages_raw = Message.query.filter_by(
            chat_id=chat_id, is_pinned=True, is_deleted=False
        ).options(joinedload(Message.sender)).order_by(Message.pinned_at.desc()).all()

        pinned_messages = []
        for msg in pinned_messages_raw:
            pinned_messages.append({
                'id': msg.id,
                'content': msg.content,
                'sender_name': msg.sender.username if msg.sender else 'Unknown',
                'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M'),
                'has_image': bool(msg.image_path),
                'has_file': bool(msg.file_path),
                'file_name': msg.file_name
            })

        # Проверяем блокировку между участниками
        chat_is_blocked = _is_blocked_between(current_user.id, other_user.id)

        # Применяем настройки приватности собеседника для отображения статуса
        other_status_display = _get_status_display(other_user, current_user.id)
        other_last_seen_display = _get_last_seen_display(other_user, current_user.id)

        return render_template('chat.html', chat=chat_obj, messages=messages,
                               other_user=other_user, pinned_messages=pinned_messages,
                               chat_is_blocked=chat_is_blocked,
                               other_status_display=other_status_display,
                               other_last_seen_display=other_last_seen_display)

    @app.route('/chat/<int:chat_id>/delete', methods=['POST'])
    @login_required
    def delete_chat(chat_id):
        chat = Chat.query.get_or_404(chat_id)

        if chat.user1_id != current_user.id and chat.user2_id != current_user.id:
            return jsonify({'error': 'Нет доступа'}), 403

        try:
            messages = Message.query.filter_by(chat_id=chat_id).all()
            for message in messages:
                ForwardedMessage.query.filter(
                    (ForwardedMessage.original_message_id == message.id) |
                    (ForwardedMessage.forwarded_message_id == message.id)
                ).delete()

            Message.query.filter_by(chat_id=chat_id).delete()
            db.session.delete(chat)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка при удалении чата: {str(e)}'}), 500

    @app.route('/api/get_chats_data')
    @login_required
    def get_chats_data():
        """API endpoint для получения обновлённых данных чатов"""
        user_chats = Chat.query.filter(
            (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
        ).options(
            joinedload(Chat.user1),
            joinedload(Chat.user2)
        ).order_by(Chat.last_message_at.desc()).all()

        chats_data = []
        for chat in user_chats:
            other_user   = chat.user2 if chat.user1_id == current_user.id else chat.user1
            last_message = Message.query.filter_by(chat_id=chat.id).order_by(Message.timestamp.desc()).first()
            unread_count = Message.query.filter_by(
                chat_id=chat.id,
                receiver_id=current_user.id,
                is_read=False
            ).count()

            last_message_preview = ''
            if last_message:
                if last_message.content:
                    prefix = 'Вы: ' if last_message.sender_id == current_user.id else ''
                    last_message_preview = f"{prefix}{last_message.content[:30]}"
                elif last_message.image_path:
                    last_message_preview = '[Фото]'
                elif last_message.file_path:
                    last_message_preview = f'[Файл] {last_message.file_name[:20] if last_message.file_name else "Файл"}'
            else:
                last_message_preview = 'Нет сообщений'

            chats_data.append({
                'id': chat.id,
                'type': 'private',
                'other_user_id': other_user.id,
                'other_username': other_user.username,
                'other_avatar': url_for('static', filename=f'uploads/{other_user.avatar}'),
                'other_status': _get_status_display(other_user, current_user.id),
                'last_message': last_message_preview,
                'last_message_time': chat.last_message_at.strftime('%H:%M') if chat.last_message_at else '',
                'unread_count': unread_count,
                'chat_url': url_for('chat', chat_id=chat.id)
            })

        user_memberships = GroupMember.query.filter_by(user_id=current_user.id).options(
            joinedload(GroupMember.group)
        ).all()
        for membership in user_memberships:
            group        = membership.group
            last_message = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()
            unread_count = Message.query.filter(
                Message.group_id == group.id,
                Message.is_read == False,
                Message.sender_id != current_user.id
            ).count()

            last_message_preview = ''
            if last_message:
                if last_message.content:
                    prefix = 'Вы: ' if last_message.sender_id == current_user.id else f'{last_message.sender.username if last_message.sender else "Пользователь"}: '
                    last_message_preview = f"{prefix}{last_message.content[:30]}"
                elif last_message.image_path:
                    last_message_preview = '[Фото]'
                elif last_message.file_path:
                    last_message_preview = f'[Файл] {last_message.file_name[:20] if last_message.file_name else "Файл"}'
            else:
                last_message_preview = 'Нет сообщений'

            chats_data.append({
                'id': group.id,
                'type': 'group',
                'group_name': group.name,
                'group_icon': url_for('static', filename=f'uploads/{group.icon}'),
                'members_count': len(group.members),
                'last_message': last_message_preview,
                'last_message_time': group.last_message_at.strftime('%H:%M') if group.last_message_at else '',
                'unread_count': unread_count,
                'chat_url': url_for('group_chat', group_id=group.id)
            })

        chats_data.sort(key=lambda x: x['last_message_time'] or '', reverse=True)
        total_unread = sum(c['unread_count'] for c in chats_data)

        return jsonify({
            'chats': chats_data,
            'total_unread': total_unread
        })

    # ============================================================
    # ПРОФИЛЬ
    # ============================================================

    @app.route('/profile/<int:user_id>')
    @login_required
    def profile(user_id):
        user = User.query.get_or_404(user_id)

        is_blocked = False
        is_contact = False
        if user.id != current_user.id:
            is_blocked = BlockedUser.query.filter_by(
                blocker_id=current_user.id,
                blocked_id=user.id
            ).first() is not None
            is_contact = Contact.query.filter_by(
                owner_id=current_user.id,
                contact_id=user.id
            ).first() is not None

        return render_template('profile.html', profile_user=user, is_blocked=is_blocked, is_contact=is_contact,
                               profile_status_display=_get_status_display(user, current_user.id),
                               profile_last_seen_display=_get_last_seen_display(user, current_user.id))

    @app.route('/profile/edit', methods=['GET', 'POST'])
    @login_required
    def edit_profile():
        if request.method == 'POST':
            username = request.form.get('username')
            bio      = request.form.get('bio')
            avatar   = request.files.get('avatar')

            if username:
                username = username.strip()
                if len(username) < 5:
                    return jsonify({'error': 'Имя пользователя должно содержать минимум 5 символов'}), 400
                existing_user = User.query.filter_by(username=username).first()
                if existing_user and existing_user.id != current_user.id:
                    return jsonify({'error': 'Имя пользователя уже занято'}), 400
                current_user.username = username

            if bio is not None:
                current_user.bio = bio

            if avatar and avatar.filename:
                try:
                    filepath, _ = save_file(avatar, 'avatar', app)
                    current_user.avatar = filepath
                except Exception as e:
                    return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400

            db.session.commit()
            return jsonify({'success': True})

        return render_template('edit_profile.html')

    # ============================================================
    # БЕЗОПАСНОСТЬ — ГЛАВНАЯ (меню)
    # ============================================================

    @app.route('/security')
    @login_required
    def security():
        sessions = UserSession.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()

        blocked_count = BlockedUser.query.filter_by(blocker_id=current_user.id).count()

        return render_template('security.html', sessions=sessions, blocked_count=blocked_count)

    @app.route('/theme')
    @login_required
    def theme_page():
        return render_template('theme.html')

    # ============================================================
    # БЕЗОПАСНОСТЬ — СМЕНА ПАРОЛЯ (страница)
    # ============================================================

    @app.route('/security/password')
    @login_required
    def security_password():
        return render_template('password.html')

    @app.route('/security/change_password', methods=['POST'])
    @login_required
    def change_password():
        current_password = request.form.get('current_password', '').strip()
        new_password     = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'Заполните все поля'}), 400

        if not PasswordSecurity.verify_password(current_password, current_user.password):
            return jsonify({'error': 'Неверный текущий пароль'}), 400

        if new_password != confirm_password:
            return jsonify({'error': 'Новые пароли не совпадают'}), 400

        if len(new_password) < 8:
            return jsonify({'error': 'Пароль должен быть минимум 8 символов'}), 400

        if new_password == current_password:
            return jsonify({'error': 'Новый пароль совпадает со старым'}), 400

        current_user.password = PasswordSecurity.hash_password(new_password)
        db.session.commit()

        try:
            from security import SecurityAudit
            SecurityAudit.log_password_reset(current_user.id, current_user.username)
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Пароль успешно изменён'})

    # ============================================================
    # БЕЗОПАСНОСТЬ — УСТРОЙСТВА
    # ============================================================

    @app.route('/security/devices')
    @login_required
    def security_devices():
        sessions = UserSession.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(UserSession.last_active.desc()).all()

        current_token = session.get('session_token')
        current_sess  = None
        for s in sessions:
            s.is_current = (s.session_token == current_token)
            if s.is_current:
                current_sess = s

        # account_too_new — текущая сессия моложе 24 часов
        account_too_new = False
        if current_sess:
            age = datetime.utcnow() - current_sess.created_at
            account_too_new = age < timedelta(hours=24)

        # Для каждой сессии определяем, заблокирована ли кнопка завершения.
        # Если текущая сессия новая (< 24ч), блокируем только те устройства,
        # которые тоже зашли меньше 24 часов назад.
        # Устройства старше 24ч всегда можно завершить (они уже "отсидели").
        for s in sessions:
            if s.is_current:
                s.terminate_locked = False
            elif account_too_new:
                sess_age = datetime.utcnow() - s.created_at
                s.terminate_locked = sess_age < timedelta(hours=24)
            else:
                s.terminate_locked = False

        return render_template('devices.html', sessions=sessions, account_too_new=account_too_new)

    @app.route('/security/terminate_session/<int:session_id>', methods=['POST'])
    @login_required
    def terminate_session(session_id):
        sess = UserSession.query.filter_by(
            id=session_id,
            user_id=current_user.id
        ).first_or_404()

        current_token = session.get('session_token')
        if sess.session_token == current_token:
            return jsonify({'error': 'Нельзя завершить текущую сессию. Используйте «Выйти».'}), 400

        # Если текущая сессия новее 24 часов — проверяем возраст завершаемой сессии.
        # Завершать можно только те устройства, которые сами старше 24 часов (уже "отсидели").
        age_seconds = _current_session_age()
        if age_seconds is not None and age_seconds < 86400:  # текущая сессия моложе 24ч
            target_age = (datetime.utcnow() - sess.created_at).total_seconds()
            if target_age < 86400:  # завершаемая тоже моложе 24ч — блокируем
                return jsonify({'error': 'Управление устройствами доступно через 24 ч. после входа'}), 403

        sess.end_session()
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/security/terminate_all_sessions', methods=['POST'])
    @login_required
    def terminate_all_sessions():
        """Завершает все сессии кроме текущей."""
        # Проверяем возраст текущей сессии
        age_seconds = _current_session_age()
        if age_seconds is not None and age_seconds < 86400:
            return jsonify({'error': 'Управление устройствами доступно через 24 ч. после входа'}), 403

        current_token   = session.get('session_token')
        sessions_to_end = UserSession.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()

        ended = 0
        for s in sessions_to_end:
            if s.session_token != current_token:
                s.end_session()
                ended += 1

        db.session.commit()
        return jsonify({'success': True, 'ended': ended})

    # ============================================================
    # БЕЗОПАСНОСТЬ — ЧЁРНЫЙ СПИСОК
    # ============================================================

    @app.route('/security/blacklist')
    @login_required
    def security_blacklist():
        blocked_users = BlockedUser.query.filter_by(blocker_id=current_user.id)\
            .order_by(BlockedUser.created_at.desc()).all()
        return render_template('blacklist.html', blocked_users=blocked_users)

    @app.route('/security/block/<int:user_id>', methods=['POST'])
    @login_required
    def block_user(user_id):
        if user_id == current_user.id:
            return jsonify({'error': 'Нельзя заблокировать себя'}), 400

        User.query.get_or_404(user_id)

        existing = BlockedUser.query.filter_by(
            blocker_id=current_user.id,
            blocked_id=user_id
        ).first()

        if existing:
            return jsonify({'error': 'Пользователь уже заблокирован'}), 400

        block = BlockedUser(blocker_id=current_user.id, blocked_id=user_id)
        db.session.add(block)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/security/unblock/<int:user_id>', methods=['POST'])
    @login_required
    def unblock_user(user_id):
        block = BlockedUser.query.filter_by(
            blocker_id=current_user.id,
            blocked_id=user_id
        ).first()

        if not block:
            return jsonify({'error': 'Пользователь не заблокирован'}), 404

        db.session.delete(block)
        db.session.commit()
        return jsonify({'success': True})

    # ============================================================
    # ПРИВАТНОСТЬ
    # ============================================================

    @app.route('/security/privacy')
    @login_required
    def security_privacy():
        """Страница настроек приватности."""
        privacy = UserPrivacy.query.filter_by(user_id=current_user.id).first()
        if not privacy:
            privacy = UserPrivacy(user_id=current_user.id)
            db.session.add(privacy)
            db.session.commit()
        return render_template('privacy.html', privacy=privacy)

    @app.route('/security/privacy', methods=['POST'])
    @login_required
    def security_privacy_save():
        """Сохраняет настройку приватности (AJAX)."""
        data = request.get_json(silent=True) or {}
        setting = data.get('setting')
        value   = data.get('value')

        allowed = {
            'who_can_write': ('all', 'contacts'),
            'last_seen':     ('all', 'contacts', 'nobody'),
        }

        if setting not in allowed or value not in allowed[setting]:
            return jsonify({'ok': False, 'error': 'Недопустимое значение'}), 400

        privacy = UserPrivacy.query.filter_by(user_id=current_user.id).first()
        if not privacy:
            privacy = UserPrivacy(user_id=current_user.id)
            db.session.add(privacy)

        setattr(privacy, setting, value)
        db.session.commit()
        return jsonify({'ok': True})

    # ============================================================
    # КОНТАКТЫ
    # ============================================================

    @app.route('/contacts')
    @login_required
    def contacts():
        user_contacts = Contact.query.filter_by(owner_id=current_user.id)\
            .order_by(Contact.created_at.desc()).all()
        return render_template('contacts.html', contacts=user_contacts)

    @app.route('/contacts/add/<int:user_id>', methods=['POST'])
    @login_required
    def add_contact(user_id):
        if user_id == current_user.id:
            return jsonify({'error': 'Нельзя добавить себя в контакты'}), 400
        User.query.get_or_404(user_id)
        existing = Contact.query.filter_by(owner_id=current_user.id, contact_id=user_id).first()
        if existing:
            return jsonify({'error': 'Уже в контактах'}), 400
        contact = Contact(owner_id=current_user.id, contact_id=user_id)
        db.session.add(contact)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/contacts/remove/<int:user_id>', methods=['POST'])
    @login_required
    def remove_contact(user_id):
        contact = Contact.query.filter_by(owner_id=current_user.id, contact_id=user_id).first()
        if not contact:
            return jsonify({'error': 'Не найдено в контактах'}), 404
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/search_users')
    @login_required
    def search_users():
        q = request.args.get('q', '').strip()
        if len(q) < 1:
            return jsonify({'users': []})
        users = User.query.filter(
            User.username.ilike(f'%{q}%'),
            User.id != current_user.id
        ).limit(20).all()
        result = []
        for u in users:
            is_contact = Contact.query.filter_by(owner_id=current_user.id, contact_id=u.id).first() is not None
            result.append({
                'id': u.id,
                'username': u.username,
                'avatar': f'/static/uploads/{u.avatar}',
                'status': u.status,
                'is_contact': is_contact,
                'profile_url': url_for('profile', user_id=u.id),
            })
        return jsonify({'users': result})

    # ============================================================
    # PUSH УВЕДОМЛЕНИЯ — СОХРАНИТЬ ТОКЕН
    # ============================================================

    @app.route('/security/notifications')
    @login_required
    def security_notifications():
        """Страница настройки ntfy push-уведомлений."""
        # ntfy_server хранится в БД
        ntfy_server = current_user.ntfy_server or ''
        return render_template('notifications.html', ntfy_server=ntfy_server)

    @app.route('/security/notifications/save', methods=['POST'])
    @login_required
    def save_ntfy_settings():
        """Сохраняет ntfy-топик и (опционально) URL сервера."""
        topic  = (request.form.get('topic') or '').strip()
        server = (request.form.get('server') or '').strip()

        if not topic:
            return jsonify({'error': 'Укажите топик'}), 400

        # Базовая валидация: только безопасные символы
        import re
        if not re.match(r'^[A-Za-z0-9_\-]{1,200}$', topic):
            return jsonify({'error': 'Топик может содержать только буквы, цифры, _ и -'}), 400

        current_user.push_token = topic

        # Сервер теперь хранится в БД
        current_user.ntfy_server = server if server else None
        db.session.commit()

        return jsonify({'success': True})

    @app.route('/security/notifications/test', methods=['POST'])
    @login_required
    def test_ntfy_notification():
        """Отправляет тестовое ntfy-уведомление."""
        topic  = (request.form.get('topic') or '').strip()
        server = (request.form.get('server') or '').strip() or 'https://ntfy.sh'

        if not topic:
            return jsonify({'error': 'Укажите топик'}), 400

        try:
            from ntfy_notifications import send_notification
            send_notification(
                topic=topic,
                title='[!] Тестовое уведомление',
                message='Push-уведомления настроены и работают корректно!',
                priority=3,
                server=server,
            )
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/security/notifications/remove', methods=['POST'])
    @login_required
    def remove_ntfy_settings():
        """Отключает push-уведомления."""
        current_user.push_token = None
        current_user.ntfy_server = None
        db.session.commit()
        session.pop('ntfy_server', None)
        return jsonify({'success': True})

    # ============================================================
    # ГРУППЫ
    # ============================================================

    @app.route('/groups')
    @login_required
    def groups():
        user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
        groups_data = []

        for membership in user_groups:
            group        = membership.group
            last_message = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()
            unread_count = Message.query.filter_by(
                group_id=group.id,
                is_read=False
            ).filter(Message.sender_id != current_user.id).count()

            groups_data.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'icon': group.icon,
                'members_count': len(group.members),
                'last_message': last_message,
                'unread_count': unread_count,
                'role': membership.role,
                'last_message_time': group.last_message_at
            })

        return render_template('groups.html', groups=groups_data)

    @app.route('/group/create', methods=['POST'])
    @login_required
    def create_group():
        name        = request.form.get('name')
        description = request.form.get('description', '')
        icon        = request.files.get('icon')

        if not name:
            return jsonify({'error': 'Название группы обязательно'}), 400

        group = Group(
            name=name,
            description=description,
            owner_id=current_user.id
        )

        if icon and icon.filename:
            try:
                filepath, _ = save_file(icon, 'group_icon', app)
                group.icon = filepath
            except Exception as e:
                return jsonify({'error': f'Ошибка обработки иконки: {str(e)}'}), 400

        db.session.add(group)
        db.session.flush()

        owner_member = GroupMember(
            group_id=group.id,
            user_id=current_user.id,
            role='owner'
        )
        db.session.add(owner_member)
        db.session.commit()

        return redirect(url_for('group_chat', group_id=group.id))

    @app.route('/group/<int:group_id>')
    @login_required
    def group_chat(group_id):
        group = Group.query.get_or_404(group_id)

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if not membership:
            return redirect(url_for('groups'))

        # Только последние 50 сообщений
        messages = Message.query.filter_by(group_id=group_id, is_deleted=False).options(
            joinedload(Message.sender), joinedload(Message.reply_to)
        ).order_by(Message.timestamp.desc()).limit(50).all()
        messages = list(reversed(messages))

        # Помечаем прочитанными одним UPDATE
        db.session.query(Message).filter(
            Message.group_id == group_id,
            Message.sender_id != current_user.id,
            Message.is_read == False
        ).update({'is_read': True}, synchronize_session=False)
        db.session.commit()

        # Закреплённые — без N+1
        pinned_messages_raw = Message.query.filter_by(
            group_id=group_id, is_pinned=True, is_deleted=False
        ).options(joinedload(Message.sender)).order_by(Message.pinned_at.desc()).all()

        pinned_messages = []
        for msg in pinned_messages_raw:
            pinned_messages.append({
                'id': msg.id,
                'content': msg.content,
                'sender_name': msg.sender.username if msg.sender else 'Unknown',
                'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M'),
                'has_image': bool(msg.image_path),
                'has_file': bool(msg.file_path),
                'file_name': msg.file_name
            })

        return render_template('group_chat.html', group=group, messages=messages,
                               membership=membership, pinned_messages=pinned_messages)

    @app.route('/group/<int:group_id>/members')
    @login_required
    def group_members(group_id):
        group = Group.query.get_or_404(group_id)

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if not membership:
            return redirect(url_for('groups'))

        members = GroupMember.query.filter_by(group_id=group_id).all()
        return render_template('group_members.html', group=group, members=members, current_membership=membership)

    @app.route('/group/<int:group_id>/add_member', methods=['POST'])
    @login_required
    def add_group_member(group_id):
        group = Group.query.get_or_404(group_id)

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if not membership or membership.role not in ['owner', 'admin']:
            return jsonify({'error': 'Недостаточно прав'}), 403

        username = request.form.get('username')
        user     = User.query.filter_by(username=username).first()

        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        existing = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=user.id
        ).first()

        if existing:
            return jsonify({'error': 'Пользователь уже в группе'}), 400

        new_member = GroupMember(
            group_id=group_id,
            user_id=user.id,
            role='member'
        )

        db.session.add(new_member)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/group/<int:group_id>/remove_member/<int:user_id>', methods=['POST'])
    @login_required
    def remove_group_member(group_id, user_id):
        group = Group.query.get_or_404(group_id)

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if not membership or membership.role not in ['owner', 'admin']:
            return jsonify({'error': 'Недостаточно прав'}), 403

        if user_id == group.owner_id:
            return jsonify({'error': 'Нельзя удалить владельца группы'}), 400

        member = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=user_id
        ).first()

        if not member:
            return jsonify({'error': 'Участник не найден'}), 404

        db.session.delete(member)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/group/<int:group_id>/change_role/<int:user_id>', methods=['POST'])
    @login_required
    def change_group_role(group_id, user_id):
        group = Group.query.get_or_404(group_id)

        if current_user.id != group.owner_id:
            return jsonify({'error': 'Только владелец может назначать админов'}), 403

        new_role = request.form.get('role')
        if new_role not in ['admin', 'member']:
            return jsonify({'error': 'Некорректная роль'}), 400

        member = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=user_id
        ).first()

        if not member:
            return jsonify({'error': 'Участник не найден'}), 404

        member.role = new_role
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/group/<int:group_id>/edit', methods=['POST'])
    @login_required
    def edit_group(group_id):
        group = Group.query.get_or_404(group_id)

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if not membership or membership.role not in ['owner', 'admin']:
            return jsonify({'error': 'Недостаточно прав'}), 403

        name        = request.form.get('name')
        description = request.form.get('description')
        icon        = request.files.get('icon')

        if name:
            group.name = name

        if description is not None:
            group.description = description

        if icon and icon.filename:
            try:
                filepath, _ = save_file(icon, 'group_icon', app)
                group.icon = filepath
            except Exception as e:
                return jsonify({'error': f'Ошибка обработки иконки: {str(e)}'}), 400

        db.session.commit()
        return redirect(url_for('group_chat', group_id=group.id))

    @app.route('/group/<int:group_id>/set_write_permission', methods=['POST'])
    @login_required
    def set_group_write_permission(group_id):
        group = Group.query.get_or_404(group_id)
        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()
        if not membership or membership.role not in ['owner', 'admin']:
            return jsonify({'error': 'Недостаточно прав'}), 403
        permission = request.json.get('write_permission', 'all')
        if permission not in ['all', 'admins_only']:
            return jsonify({'error': 'Неверное значение'}), 400
        group.write_permission = permission
        db.session.commit()
        return jsonify({'success': True, 'write_permission': group.write_permission})

    @app.route('/group/<int:group_id>/delete', methods=['POST'])
    @login_required
    def delete_group(group_id):
        group = Group.query.get_or_404(group_id)

        if current_user.id != group.owner_id:
            return jsonify({'error': 'Только владелец может удалить группу'}), 403

        try:
            messages = Message.query.filter_by(group_id=group_id).all()
            for message in messages:
                ForwardedMessage.query.filter(
                    (ForwardedMessage.original_message_id == message.id) |
                    (ForwardedMessage.forwarded_message_id == message.id)
                ).delete()

            Message.query.filter_by(group_id=group_id).delete()
            GroupMember.query.filter_by(group_id=group_id).delete()
            db.session.delete(group)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Ошибка при удалении группы: {str(e)}'}), 500

    @app.route('/group/<int:group_id>/leave', methods=['POST'])
    @login_required
    def leave_group(group_id):
        group = Group.query.get_or_404(group_id)

        if current_user.id == group.owner_id:
            return jsonify({'error': 'Владелец не может покинуть группу. Передайте права или удалите группу.'}), 400

        membership = GroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()

        if membership:
            db.session.delete(membership)
            db.session.commit()

        return jsonify({'success': True})

    # ============================================================
    # СООБЩЕНИЯ
    # ============================================================

    @app.route('/send_message', methods=['POST'])
    @login_required
    def send_message():
        chat_id     = request.form.get('chat_id')
        group_id    = request.form.get('group_id')
        content     = request.form.get('content')
        file        = request.files.get('file')
        reply_to_id = request.form.get('reply_to_id')

        message = Message(
            sender_id=current_user.id,
            content=content if content else None,
            reply_to_id=reply_to_id if reply_to_id else None
        )

        if content and contains_url(content):
            urls = extract_urls_from_text(content)
            if urls:
                first_url = urls[0]
                # Получаем превью асинхронно, чтобы не блокировать ответ
                def fetch_preview_async(app_ctx, msg_id, url):
                    with app_ctx:
                        try:
                            preview_data = extract_link_preview(url)
                            if preview_data:
                                from models import db as _db, Message as _Msg
                                msg = _Msg.query.get(msg_id)
                                if msg:
                                    msg.link_url         = preview_data['url']
                                    msg.link_title       = preview_data['title']
                                    msg.link_description = preview_data['description']
                                    msg.link_image       = preview_data['image']
                                    msg.link_fetched_at  = datetime.utcnow()
                                    _db.session.commit()
                        except Exception:
                            pass

        if chat_id:
            chat_obj = Chat.query.get_or_404(chat_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403

            receiver_id = chat_obj.user2_id if chat_obj.user1_id == current_user.id else chat_obj.user1_id

            # Запрет отправки если заблокированы (в любую сторону)
            if _is_blocked_between(current_user.id, receiver_id):
                return jsonify({'error': 'blocked'}), 403

            message.chat_id     = chat_id
            message.receiver_id = receiver_id
            chat_obj.last_message_at = datetime.utcnow()

        elif group_id:
            group      = Group.query.get_or_404(group_id)
            membership = GroupMember.query.filter_by(
                group_id=group_id,
                user_id=current_user.id
            ).first()

            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403

            # Проверка прав на запись
            if getattr(group, 'write_permission', 'all') == 'admins_only':
                if membership.role not in ['owner', 'admin']:
                    return jsonify({'error': 'write_restricted'}), 403

            message.group_id      = group_id
            group.last_message_at = datetime.utcnow()

        if file and file.filename:
            filename      = file.filename
            file_category = get_file_category(filename)
            message.file_category = file_category
            message.file_name     = filename
            message.file_type     = file.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if is_file_too_large(file_size, app):
                return jsonify({'error': f'Файл слишком большой. Максимальный размер: {app.config["MAX_CONTENT_LENGTH"] / (1024*1024)} MB'}), 400

            try:
                filepath, size = save_file(file, file_category, app)
                if file_category == 'image':
                    message.image_path = filepath
                else:
                    message.file_path = filepath
                message.file_size = size
            except Exception as e:
                return jsonify({'error': f'Ошибка сохранения файла: {str(e)}'}), 400

        db.session.add(message)
        db.session.commit()

        # Запускаем получение превью ссылки в фоне (если нужно)
        if content and contains_url(content):
            urls = extract_urls_from_text(content)
            if urls:
                msg_id = message.id
                first_url = urls[0]
                t = threading.Thread(
                    target=fetch_preview_async,
                    args=(app.app_context(), msg_id, first_url),
                    daemon=True
                )
                t.start()

        # ntfy push-уведомления для всех сообщений (текст, файлы, картинки)
        try:
            from ntfy_notifications import notify_new_message, notify_group_message
            preview = message.content[:60] if message.content else (
                '[Фото]' if message.image_path else f'[Файл] {message.file_name or "Файл"}'
            )
            if message.chat_id and message.receiver_id:
                from models import User as _User
                recipient = _User.query.get(message.receiver_id)
                if recipient and recipient.push_token:
                    ntfy_server = recipient.ntfy_server or app.config.get('NTFY_SERVER', 'https://ntfy.sh')
                    notify_new_message(recipient, current_user.username, preview, server=ntfy_server)
            elif message.group_id:
                from models import GroupMember as _GM, Group as _Group, User as _User
                group = _Group.query.get(message.group_id)
                members = _GM.query.filter_by(group_id=message.group_id).all()
                for m in members:
                    if m.user_id == current_user.id:
                        continue
                    member_user = _User.query.get(m.user_id)
                    if member_user and member_user.push_token:
                        ntfy_server = member_user.ntfy_server or app.config.get('NTFY_SERVER', 'https://ntfy.sh')
                        notify_group_message(
                            member_user, current_user.username,
                            group.name if group else 'Группа',
                            preview, server=ntfy_server
                        )
        except Exception:
            pass  # ntfy не должен ломать отправку сообщения

        # Эмитим WS-событие new_message чтобы получатель увидел файл/изображение мгновенно
        if file and file.filename:
            try:
                from socketio_events import socketio as _sio, _serialize_message, _emit_chat_update, _emit_group_update
                payload = _serialize_message(message, current_user.id, app)
                if message.chat_id:
                    _sio.emit('new_message', payload, to=f'chat_{message.chat_id}')
                    _emit_chat_update(message.chat_id, message, message.receiver_id)
                elif message.group_id:
                    _sio.emit('new_message', payload, to=f'group_{message.group_id}')
                    _emit_group_update(message.group_id, message)
            except Exception:
                pass  # Не блокируем ответ если WS недоступен

        return jsonify({
            'success': True,
            'message_id': message.id,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'content': message.content,
            'image_path': url_for('download_file', filepath=message.image_path) if message.image_path else None,
            'file_path': url_for('download_file', filepath=message.file_path) if message.file_path else None,
            'file_name': message.file_name,
            'file_size': format_file_size(message.file_size) if message.file_size else None,
            'file_category': message.file_category,
            'file_icon': get_file_icon(message.file_name) if message.file_name else None,
            'link_url': message.link_url,
            'link_title': message.link_title,
            'link_description': message.link_description,
            'link_image': message.link_image,
            'is_forwarded': message.is_forwarded,
            'reply_to_id': message.reply_to_id
        })

    @app.route('/forward_message', methods=['POST'])
    def forward_message():
        message_id      = request.form.get('message_id')
        target_type     = request.form.get('target_type')
        target_id       = request.form.get('target_id')
        show_sender     = request.form.get('show_sender', 'true').lower() == 'true'
        additional_text = request.form.get('additional_text', '')

        original_message = Message.query.get_or_404(message_id)

        if original_message.chat_id:
            chat = Chat.query.get(original_message.chat_id)
            if not chat or (chat.user1_id != current_user.id and chat.user2_id != current_user.id):
                return jsonify({'error': 'Нет доступа к оригинальному сообщению'}), 403
        elif original_message.group_id:
            membership = GroupMember.query.filter_by(
                group_id=original_message.group_id,
                user_id=current_user.id
            ).first()
            if not membership:
                return jsonify({'error': 'Нет доступа к оригинальному сообщению'}), 403

        if original_message.content and additional_text:
            forwarded_content = f"{additional_text}\n\n{original_message.content}"
        elif original_message.content:
            forwarded_content = original_message.content
        elif additional_text:
            forwarded_content = additional_text
        else:
            forwarded_content = None

        forwarded_message = Message(
            sender_id=current_user.id,
            content=forwarded_content,
            is_forwarded=True,
            forwarded_from_id=original_message.id,
            show_forward_sender=show_sender
        )

        if original_message.image_path:
            forwarded_message.image_path = original_message.image_path
        elif original_message.file_path:
            forwarded_message.file_path     = original_message.file_path
            forwarded_message.file_name     = original_message.file_name
            forwarded_message.file_type     = original_message.file_type
            forwarded_message.file_size     = original_message.file_size
            forwarded_message.file_category = original_message.file_category

        if target_type == 'chat':
            chat_obj = Chat.query.get_or_404(target_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа к чату'}), 403

            receiver_id = chat_obj.user2_id if chat_obj.user1_id == current_user.id else chat_obj.user1_id
            forwarded_message.chat_id     = target_id
            forwarded_message.receiver_id = receiver_id
            chat_obj.last_message_at      = datetime.utcnow()

        elif target_type == 'group':
            group      = Group.query.get_or_404(target_id)
            membership = GroupMember.query.filter_by(
                group_id=target_id,
                user_id=current_user.id
            ).first()

            if not membership:
                return jsonify({'error': 'Нет доступа к группе'}), 403

            forwarded_message.group_id = target_id
            group.last_message_at      = datetime.utcnow()

        db.session.add(forwarded_message)
        db.session.flush()

        forwarded_record = ForwardedMessage(
            original_message_id=original_message.id,
            forwarded_message_id=forwarded_message.id,
            forwarded_by_id=current_user.id,
            forwarded_to_chat_id=forwarded_message.chat_id,
            forwarded_to_group_id=forwarded_message.group_id,
            show_sender=show_sender
        )

        db.session.add(forwarded_record)
        db.session.commit()

        # Эмитим WS-событие new_message — получатели увидят пересланное сообщение мгновенно
        try:
            from socketio_events import socketio as _sio, _serialize_message, _emit_chat_update, _emit_group_update
            payload = _serialize_message(forwarded_message, current_user.id, app)
            if forwarded_message.chat_id:
                _sio.emit('new_message', payload, to=f'chat_{forwarded_message.chat_id}')
                _emit_chat_update(forwarded_message.chat_id, forwarded_message, forwarded_message.receiver_id)
            elif forwarded_message.group_id:
                _sio.emit('new_message', payload, to=f'group_{forwarded_message.group_id}')
                _emit_group_update(forwarded_message.group_id, forwarded_message)
        except Exception:
            pass  # Не блокируем ответ если WS недоступен

        return jsonify({
            'success': True,
            'message_id': forwarded_message.id,
            'timestamp': forwarded_message.timestamp.strftime('%H:%M')
        })

    @app.route('/get_chats_and_groups_for_forward')
    @login_required
    def get_chats_and_groups_for_forward():
        user_chats = Chat.query.filter(
            (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
        ).order_by(Chat.last_message_at.desc()).all()

        chats_data = []
        for chat in user_chats:
            other_user = chat.user2 if chat.user1_id == current_user.id else chat.user1
            chats_data.append({
                'id': chat.id,
                'type': 'chat',
                'name': other_user.username,
                'avatar': url_for('static', filename=f'uploads/{other_user.avatar}'),
                'last_message_time': chat.last_message_at.strftime('%H:%M')
            })

        user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
        groups_data = []
        for membership in user_groups:
            group = membership.group
            groups_data.append({
                'id': group.id,
                'type': 'group',
                'name': group.name,
                'avatar': url_for('static', filename=f'uploads/{group.icon}'),
                'members_count': len(group.members),
                'last_message_time': group.last_message_at.strftime('%H:%M')
            })

        all_targets = chats_data + groups_data
        all_targets.sort(key=lambda x: x['last_message_time'], reverse=True)
        return jsonify(all_targets)

    @app.route('/get_messages/<int:chat_id>')
    @login_required
    def get_messages(chat_id):
        last_id   = request.args.get('last_id',   0, type=int)
        before_id = request.args.get('before_id', 0, type=int)
        is_group  = request.args.get('is_group', False, type=bool)

        if is_group:
            group      = Group.query.get_or_404(chat_id)
            membership = GroupMember.query.filter_by(
                group_id=chat_id,
                user_id=current_user.id
            ).first()

            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403

            q = Message.query.filter(
                Message.group_id == chat_id,
                Message.is_deleted == False
            ).options(
                joinedload(Message.sender),
                joinedload(Message.reply_to),
                joinedload(Message.forwarded_from)
            )
            if before_id:
                messages = list(reversed(q.filter(Message.id < before_id).order_by(Message.timestamp.desc()).limit(30).all()))
            else:
                messages = q.filter(Message.id > last_id).order_by(Message.timestamp).all()

            for msg in messages:
                if msg.sender_id != current_user.id and not msg.is_read:
                    msg.is_read = True

            db.session.commit()
        else:
            chat_obj = Chat.query.get_or_404(chat_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403

            q = Message.query.filter(
                Message.chat_id == chat_id,
                Message.is_deleted == False
            ).options(
                joinedload(Message.sender),
                joinedload(Message.reply_to),
                joinedload(Message.forwarded_from)
            )
            if before_id:
                messages = list(reversed(q.filter(Message.id < before_id).order_by(Message.timestamp.desc()).limit(30).all()))
            else:
                messages = q.filter(Message.id > last_id).order_by(Message.timestamp).all()

            for msg in messages:
                if msg.receiver_id == current_user.id and not msg.is_read:
                    msg.is_read = True

            db.session.commit()

        # Собираем все нужные sender_id для reply/forward одним запросом
        extra_user_ids = set()
        for msg in messages:
            if msg.reply_to:
                extra_user_ids.add(msg.reply_to.sender_id)
            if msg.forwarded_from:
                extra_user_ids.add(msg.forwarded_from.sender_id)

        extra_users = {}
        if extra_user_ids:
            for u in User.query.filter(User.id.in_(extra_user_ids)).all():
                extra_users[u.id] = u

        messages_data = []
        for msg in messages:
            sender = msg.sender

            file_url = None
            if msg.file_path:
                file_url = url_for('download_file', filepath=msg.file_path)
            elif msg.image_path:
                file_url = url_for('download_file', filepath=msg.image_path)

            file_size_formatted = format_file_size(msg.file_size) if msg.file_size else None
            file_icon           = get_file_icon(msg.file_name) if msg.file_name else '[file]'

            reply_to_data = None
            if msg.reply_to:
                reply_msg    = msg.reply_to
                reply_sender = extra_users.get(reply_msg.sender_id) or reply_msg.sender
                reply_to_data = {
                    'id': reply_msg.id,
                    'sender_id': reply_msg.sender_id,
                    'sender_name': reply_sender.username if reply_sender else 'Unknown',
                    'content': reply_msg.content[:100] if reply_msg.content else None,
                    'has_image': bool(reply_msg.image_path),
                    'has_file': bool(reply_msg.file_path),
                    'file_name': reply_msg.file_name
                }

            forwarded_from_data = None
            if msg.is_forwarded and msg.forwarded_from:
                original_msg    = msg.forwarded_from
                original_sender = extra_users.get(original_msg.sender_id) or original_msg.sender
                forwarded_from_data = {
                    'id': original_msg.id,
                    'sender_id': original_msg.sender_id,
                    'sender_name': original_sender.username if original_sender else 'Unknown',
                    'show_sender': msg.show_forward_sender
                }

            messages_data.append({
                'id': msg.id,
                'sender_id': msg.sender_id,
                'sender_name': sender.username if sender else 'Unknown',
                'sender_username': sender.username if sender else 'Unknown',
                'sender_avatar': url_for('static', filename=f'uploads/{sender.avatar}') if sender else url_for('static', filename='uploads/avatars/default.png'),
                'content': msg.content,
                'image_path': url_for('download_file', filepath=msg.image_path) if msg.image_path else None,
                'file_path': file_url,
                'file_name': msg.file_name,
                'file_type': msg.file_type,
                'file_size': file_size_formatted,
                'file_category': msg.file_category or get_file_category(msg.file_name) if msg.file_name else None,
                'file_icon': file_icon,
                'timestamp': msg.timestamp.strftime('%H:%M'),
                'is_read': msg.is_read,
                'is_edited': msg.is_edited,
                'reply_to': reply_to_data,
                'is_forwarded': msg.is_forwarded,
                'forwarded_from': forwarded_from_data,
                'show_forward_sender': msg.show_forward_sender,
                'link_url': msg.link_url,
                'link_title': msg.link_title,
                'link_description': msg.link_description,
                'link_image': msg.link_image,
            })

        return jsonify(messages_data)

    @app.route('/download/<path:filepath>')
    @login_required
    def download_file(filepath):
        from flask import make_response
        directory = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(filepath))
        filename  = os.path.basename(filepath)
        response  = make_response(send_from_directory(directory, filename, as_attachment=True))
        # Кэшируем файлы на 7 дней (они иммутабельны — uuid в имени)
        response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
        return response

    @app.route('/delete_message/<int:message_id>', methods=['POST'])
    @login_required
    def delete_message(message_id):
        message = Message.query.get_or_404(message_id)
        if message.sender_id != current_user.id:
            return jsonify({'error': 'Нет прав для удаления этого сообщения'}), 403
        chat_id = message.chat_id
        group_id = message.group_id
        message.is_deleted = True
        message.content    = None
        db.session.commit()
        # Уведомляем других участников через WebSocket
        try:
            from socketio_events import broadcast_message_deleted
            broadcast_message_deleted(message_id, chat_id=chat_id, group_id=group_id)
        except Exception:
            pass
        return jsonify({'success': True})

    @app.route('/edit_message/<int:message_id>', methods=['POST'])
    @login_required
    def edit_message(message_id):
        message = Message.query.get_or_404(message_id)
        if message.sender_id != current_user.id:
            return jsonify({'error': 'Нет прав для редактирования этого сообщения'}), 403
        new_content = request.form.get('content', '').strip()
        if not new_content:
            return jsonify({'error': 'Текст сообщения не может быть пустым'}), 400
        chat_id = message.chat_id
        group_id = message.group_id
        message.content   = new_content
        message.is_edited = True
        db.session.commit()
        # Уведомляем через WebSocket
        try:
            from socketio_events import broadcast_message_edited
            broadcast_message_edited(message_id, new_content, chat_id=chat_id, group_id=group_id)
        except Exception:
            pass
        return jsonify({'success': True, 'content': new_content})

    @app.route('/get_unread_counts')
    @login_required
    def get_unread_counts():
        private_chats = Chat.query.filter(
            (Chat.user1_id == current_user.id) | (Chat.user2_id == current_user.id)
        ).all()

        total_unread = 0

        for chat in private_chats:
            unread = Message.query.filter_by(
                chat_id=chat.id,
                receiver_id=current_user.id,
                is_read=False
            ).count()
            total_unread += unread

        user_groups = GroupMember.query.filter_by(user_id=current_user.id).all()
        for membership in user_groups:
            unread = Message.query.filter_by(
                group_id=membership.group_id,
                is_read=False
            ).filter(Message.sender_id != current_user.id).count()
            total_unread += unread

        return jsonify({'unread_count': total_unread})

    # ============================================================
    # ЗАКРЕПЛЕНИЕ СООБЩЕНИЙ
    # ============================================================

    @app.route('/pin_message/<int:message_id>', methods=['POST'])
    @login_required
    def pin_message(message_id):
        message = Message.query.get_or_404(message_id)
        if message.chat_id:
            chat_obj = Chat.query.get(message.chat_id)
            if not chat_obj or (chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id):
                return jsonify({'error': 'Нет доступа'}), 403
        elif message.group_id:
            membership = GroupMember.query.filter_by(group_id=message.group_id, user_id=current_user.id).first()
            if not membership or membership.role not in ['owner', 'admin']:
                return jsonify({'error': 'Только администраторы могут закреплять сообщения'}), 403
        message.is_pinned    = True
        message.pinned_by_id = current_user.id
        message.pinned_at    = datetime.utcnow()
        db.session.commit()
        sender = User.query.get(message.sender_id)
        return jsonify({
            'success': True, 'message_id': message.id,
            'content': message.content,
            'sender_name': sender.username if sender else 'Unknown',
            'timestamp': message.timestamp.strftime('%H:%M'),
            'has_image': bool(message.image_path),
            'has_file': bool(message.file_path),
            'file_name': message.file_name
        })

    @app.route('/unpin_message/<int:message_id>', methods=['POST'])
    @login_required
    def unpin_message(message_id):
        message = Message.query.get_or_404(message_id)
        if message.chat_id:
            chat_obj = Chat.query.get(message.chat_id)
            if not chat_obj or (chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id):
                return jsonify({'error': 'Нет доступа'}), 403
        elif message.group_id:
            membership = GroupMember.query.filter_by(group_id=message.group_id, user_id=current_user.id).first()
            if not membership or membership.role not in ['owner', 'admin']:
                return jsonify({'error': 'Только администраторы могут откреплять сообщения'}), 403
        message.is_pinned    = False
        message.pinned_by_id = None
        message.pinned_at    = None
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/get_pinned_messages/<int:context_id>')
    @login_required
    def get_pinned_messages(context_id):
        is_group = request.args.get('is_group', 'false').lower() == 'true'
        if is_group:
            membership = GroupMember.query.filter_by(group_id=context_id, user_id=current_user.id).first()
            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403
            pinned = Message.query.filter_by(group_id=context_id, is_pinned=True, is_deleted=False).order_by(Message.pinned_at.desc()).all()
        else:
            chat_obj = Chat.query.get_or_404(context_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403
            pinned = Message.query.filter_by(chat_id=context_id, is_pinned=True, is_deleted=False).order_by(Message.pinned_at.desc()).all()
        result = []
        for msg in pinned:
            sender = User.query.get(msg.sender_id)
            result.append({
                'id': msg.id, 'content': msg.content,
                'sender_name': sender.username if sender else 'Unknown',
                'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M'),
                'has_image': bool(msg.image_path),
                'has_file': bool(msg.file_path),
                'file_name': msg.file_name
            })
        return jsonify(result)

    # ============================================================
    # ПОИСК В ЧАТЕ
    # ============================================================

    @app.route('/search_messages/<int:context_id>')
    @login_required
    def search_messages(context_id):
        is_group  = request.args.get('is_group', 'false').lower() == 'true'
        query_str = request.args.get('q', '').strip()
        if not query_str:
            return jsonify([])

        if is_group:
            membership = GroupMember.query.filter_by(group_id=context_id, user_id=current_user.id).first()
            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403
            messages = Message.query.filter(
                Message.group_id == context_id,
                Message.content.ilike(f'%{query_str}%'),
                Message.is_deleted == False
            ).order_by(Message.timestamp.desc()).limit(50).all()
        else:
            chat_obj = Chat.query.get_or_404(context_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403
            messages = Message.query.filter(
                Message.chat_id == context_id,
                Message.content.ilike(f'%{query_str}%'),
                Message.is_deleted == False
            ).options(joinedload(Message.sender)).order_by(Message.timestamp.desc()).limit(50).all()

        result = []
        for msg in messages:
            sender = msg.sender
            result.append({
                'id': msg.id, 'content': msg.content,
                'sender_name': sender.username if sender else 'Unknown',
                'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M'),
                'is_mine': msg.sender_id == current_user.id
            })
        return jsonify(result)

    # ============================================================
    # ЭКСПОРТ ЧАТА
    # ============================================================

    @app.route('/export_chat/<int:context_id>')
    @login_required
    def export_chat(context_id):
        """Экспорт истории чата в ZIP (HTML + вложения). Только для ПК."""
        is_group = request.args.get('is_group', False, type=bool)

        # Проверяем доступ и собираем метаданные
        if is_group:
            group = Group.query.get_or_404(context_id)
            membership = GroupMember.query.filter_by(
                group_id=context_id, user_id=current_user.id
            ).first()
            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403
            chat_title = group.name
            chat_subtitle = f'{len(group.members)} участников'
            messages = Message.query.filter(
                Message.group_id == context_id,
                Message.is_deleted == False
            ).options(
                joinedload(Message.sender),
                joinedload(Message.reply_to)
            ).order_by(Message.timestamp).all()
        else:
            chat_obj = Chat.query.get_or_404(context_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403
            other = chat_obj.user2 if chat_obj.user1_id == current_user.id else chat_obj.user1
            chat_title = other.username
            chat_subtitle = 'Личный чат'
            messages = Message.query.filter(
                Message.chat_id == context_id,
                Message.is_deleted == False
            ).options(
                joinedload(Message.sender),
                joinedload(Message.reply_to)
            ).order_by(Message.timestamp).all()

        upload_folder = app.config.get('UPLOAD_FOLDER', 'static/uploads')

        # Список вложений для копирования в архив
        attachments = {}  # original_path -> archive_path
        for msg in messages:
            for fpath in [msg.image_path, msg.file_path]:
                if fpath and fpath not in attachments:
                    full = os.path.join(upload_folder, fpath)
                    if os.path.exists(full):
                        attachments[fpath] = f'files/{fpath}'

        # Читаем CSS для вставки в HTML
        css_path = os.path.join(app.static_folder, 'css', 'style.css')
        try:
            with open(css_path, 'r', encoding='utf-8') as f:
                base_css = f.read()
        except Exception:
            base_css = ''

        # Группируем сообщения по дате
        from itertools import groupby
        def date_key(m):
            return m.timestamp.strftime('%d %B %Y')

        # Генерируем HTML
        html_lines = []
        html_lines.append('<!DOCTYPE html>')
        html_lines.append('<html lang="ru"><head><meta charset="utf-8">')
        html_lines.append(f'<title>Экспорт: {chat_title}</title>')
        html_lines.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
        html_lines.append('<style>')
        # Минимальный встроенный стиль — не тащим весь style.css
        html_lines.append('''
:root {
  --bg: #1a1a2e; --bg2: #16213e; --bg3: #0f3460;
  --text: #e0e0e0; --text2: #a0a0b0; --accent: #4f8ef7;
  --border: #2a2a4a; --bubble-me: #1e3a6e; --bubble-other: #1e1e3a;
  --radius: 12px; --danger: #e74c3c;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 15px; line-height: 1.5; }
.export-header { background: var(--bg2); border-bottom: 1px solid var(--border); padding: 20px 32px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 10; }
.export-header h1 { font-size: 20px; font-weight: 700; }
.export-header p { color: var(--text2); font-size: 13px; margin-top: 2px; }
.export-meta { margin-left: auto; color: var(--text2); font-size: 13px; text-align: right; }
.messages-wrap { max-width: 860px; margin: 0 auto; padding: 24px 16px; }
.date-divider { text-align: center; margin: 24px 0 12px; }
.date-divider span { background: var(--bg3); color: var(--text2); font-size: 12px; padding: 4px 14px; border-radius: 20px; }
.msg-row { display: flex; gap: 10px; margin-bottom: 6px; align-items: flex-end; }
.msg-row.me { flex-direction: row-reverse; }
.avatar-sm { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.bubble { max-width: 68%; background: var(--bubble-other); border-radius: var(--radius); padding: 8px 12px; word-break: break-word; }
.me .bubble { background: var(--bubble-me); }
.sender-name { font-size: 12px; font-weight: 600; color: var(--accent); margin-bottom: 2px; }
.msg-text { white-space: pre-wrap; }
.msg-time { font-size: 11px; color: var(--text2); margin-top: 4px; text-align: right; }
.msg-img { max-width: 320px; max-height: 320px; border-radius: 8px; display: block; margin-top: 6px; }
.msg-file { display: inline-flex; align-items: center; gap: 8px; background: var(--bg3); border-radius: 8px; padding: 8px 12px; margin-top: 6px; color: var(--text); text-decoration: none; font-size: 13px; }
.msg-file:hover { opacity: .8; }
.reply-block { border-left: 3px solid var(--accent); padding: 4px 8px; margin-bottom: 6px; font-size: 12px; color: var(--text2); border-radius: 0 6px 6px 0; background: rgba(79,142,247,.08); }
.reply-block b { color: var(--accent); }
.fwd-label { font-size: 11px; color: var(--text2); margin-bottom: 4px; font-style: italic; }
.system-msg { text-align: center; color: var(--text2); font-size: 12px; margin: 8px 0; }
''')
        html_lines.append('</style></head><body>')

        # Шапка
        export_time = datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')
        html_lines.append(f'''
<div class="export-header">
  <div>
    <h1>{chat_title}</h1>
    <p>{chat_subtitle}</p>
  </div>
  <div class="export-meta">
    <div>Сообщений: {len(messages)}</div>
    <div>Экспорт: {export_time}</div>
  </div>
</div>
<div class="messages-wrap">
''')

        current_date = None
        for msg in messages:
            msg_date = msg.timestamp.strftime('%d %B %Y')
            if msg_date != current_date:
                current_date = msg_date
                html_lines.append(f'<div class="date-divider"><span>{msg_date}</span></div>')

            is_me = msg.sender_id == current_user.id
            row_class = 'msg-row me' if is_me else 'msg-row'
            sender = msg.sender
            sender_name = sender.username if sender else 'Unknown'
            time_str = msg.timestamp.strftime('%H:%M')

            # Аватар
            if sender and sender.avatar:
                avatar_src = f'files/{sender.avatar}' if sender.avatar in attachments else f'https://ui-avatars.com/api/?name={sender_name}&size=32&background=4f8ef7&color=fff'
            else:
                avatar_src = f'https://ui-avatars.com/api/?name={sender_name}&size=32&background=4f8ef7&color=fff'

            html_lines.append(f'<div class="{row_class}">')
            html_lines.append(f'<img class="avatar-sm" src="{avatar_src}" alt="{sender_name}">')
            html_lines.append('<div class="bubble">')

            # Имя отправителя (в группах всегда, в личных — только у собеседника)
            if is_group or not is_me:
                html_lines.append(f'<div class="sender-name">{sender_name}</div>')

            # Пересылка
            if msg.is_forwarded and msg.forwarded_from:
                orig_sender = msg.forwarded_from.sender
                orig_name = orig_sender.username if orig_sender else 'Unknown'
                html_lines.append(f'<div class="fwd-label">Переслано от {orig_name}</div>')

            # Цитата
            if msg.reply_to and not msg.reply_to.is_deleted:
                r = msg.reply_to
                r_sender = r.sender
                r_name = r_sender.username if r_sender else 'Unknown'
                r_text = r.content[:80] if r.content else ('[Фото]' if r.image_path else '[Файл]')
                html_lines.append(f'<div class="reply-block"><b>{r_name}:</b> {r_text}</div>')

            # Картинка
            if msg.image_path:
                img_src = attachments.get(msg.image_path, f'files/{msg.image_path}')
                html_lines.append(f'<img class="msg-img" src="{img_src}" alt="Фото">')

            # Файл
            if msg.file_path:
                file_href = attachments.get(msg.file_path, f'files/{msg.file_path}')
                fname = msg.file_name or 'Файл'
                fsize = format_file_size(msg.file_size) if msg.file_size else ''
                html_lines.append(f'<a class="msg-file" href="{file_href}" download="{fname}">[file] {fname} {fsize}</a>')

            # Текст
            if msg.content:
                import html as html_mod
                safe_text = html_mod.escape(msg.content)
                html_lines.append(f'<div class="msg-text">{safe_text}</div>')

            html_lines.append(f'<div class="msg-time">{time_str}</div>')
            html_lines.append('</div></div>')  # bubble, msg-row

        html_lines.append('</div></body></html>')
        html_content = '\n'.join(html_lines)

        # Собираем ZIP в памяти
        zip_buffer = io.BytesIO()
        safe_title = ''.join(c for c in chat_title if c.isalnum() or c in '_ -')[:40]
        html_filename = f'chat_{safe_title}.html'

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(html_filename, html_content.encode('utf-8'))
            for orig_path, arc_path in attachments.items():
                full = os.path.join(upload_folder, orig_path)
                try:
                    zf.write(full, arc_path)
                except Exception:
                    pass

        zip_buffer.seek(0)
        zip_name = f'export_{safe_title}.zip'

        from flask import send_file
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_name,
            mimetype='application/zip'
        )

    # ============================================================
    # ВОССТАНОВЛЕНИЕ ПАРОЛЯ
    # ============================================================

    @app.route('/forgot_password', methods=['GET', 'POST'])
    def forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for('chats'))

        if request.method == 'POST':
            username = request.form.get('username')
            email    = request.form.get('email')

            if not username or not email:
                return render_template('forgot_password.html', error='Заполните все поля')

            user = User.query.filter_by(username=username, email=email).first()

            if not user:
                return render_template('forgot_password.html',
                                       success='Если данные верны, инструкции отправлены на email')

            PasswordReset.query.filter_by(user_id=user.id, used=False).delete()

            token = secrets.token_urlsafe(32)

            reset_request = PasswordReset(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )

            db.session.add(reset_request)
            db.session.commit()

            return redirect(url_for('reset_password', token=token))

        return render_template('forgot_password.html')

    @app.route('/reset_password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        if current_user.is_authenticated:
            return redirect(url_for('chats'))

        reset_request = PasswordReset.query.filter_by(token=token, used=False).first()

        if not reset_request:
            return render_template('forgot_password.html',
                                   error='Недействительная ссылка для сброса пароля')

        if reset_request.expires_at < datetime.utcnow():
            reset_request.used = True
            db.session.commit()
            return render_template('forgot_password.html',
                                   error='Срок действия ссылки истек')

        if request.method == 'POST':
            new_password     = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not new_password or not confirm_password:
                return render_template('reset_password.html', error='Заполните все поля', token=token)

            if new_password != confirm_password:
                return render_template('reset_password.html', error='Пароли не совпадают', token=token)

            if len(new_password) < 8:
                return render_template('reset_password.html',
                                       error='Пароль должен быть минимум 8 символов', token=token)

            user = User.query.get(reset_request.user_id)
            if not user:
                return render_template('forgot_password.html', error='Пользователь не найден')

            user.password      = PasswordSecurity.hash_password(new_password)
            reset_request.used = True
            db.session.commit()

            try:
                from security import SecurityAudit
                SecurityAudit.log_password_reset(user.id, user.username)
            except Exception:
                pass

            return render_template('login.html',
                                   success='Пароль успешно изменен. Теперь вы можете войти.')

        return render_template('reset_password.html', token=token)

    # ============================================================
    # МЕДИАГАЛЕРЕЯ
    # ============================================================

    @app.route('/get_media/<int:context_id>')
    @login_required
    def get_media(context_id):
        is_group   = request.args.get('is_group', 'false').lower() == 'true'
        media_type = request.args.get('type', 'images')
        if is_group:
            membership = GroupMember.query.filter_by(group_id=context_id, user_id=current_user.id).first()
            if not membership:
                return jsonify({'error': 'Нет доступа'}), 403
            base_query = Message.query.filter(Message.group_id == context_id, Message.is_deleted == False)
        else:
            chat_obj = Chat.query.get_or_404(context_id)
            if chat_obj.user1_id != current_user.id and chat_obj.user2_id != current_user.id:
                return jsonify({'error': 'Нет доступа'}), 403
            base_query = Message.query.filter(Message.chat_id == context_id, Message.is_deleted == False)

        result = []
        if media_type == 'images':
            msgs = base_query.filter(Message.image_path != None).options(joinedload(Message.sender)).order_by(Message.timestamp.desc()).limit(100).all()
            for msg in msgs:
                sender = msg.sender
                result.append({
                    'id': msg.id,
                    'url': url_for('download_file', filepath=msg.image_path),
                    'sender_name': sender.username if sender else 'Unknown',
                    'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M')
                })
        elif media_type == 'files':
            msgs = base_query.filter(Message.file_path != None).options(joinedload(Message.sender)).order_by(Message.timestamp.desc()).limit(100).all()
            for msg in msgs:
                sender = msg.sender
                result.append({
                    'id': msg.id,
                    'url': url_for('download_file', filepath=msg.file_path),
                    'file_name': msg.file_name,
                    'file_size': format_file_size(msg.file_size) if msg.file_size else None,
                    'file_icon': get_file_icon(msg.file_name) if msg.file_name else '[file]',
                    'sender_name': sender.username if sender else 'Unknown',
                    'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M')
                })
        elif media_type == 'links':
            msgs = base_query.filter(Message.link_url != None).options(joinedload(Message.sender)).order_by(Message.timestamp.desc()).limit(100).all()
            for msg in msgs:
                sender = msg.sender
                result.append({
                    'id': msg.id,
                    'url': msg.link_url,
                    'title': msg.link_title,
                    'description': msg.link_description,
                    'image': msg.link_image,
                    'sender_name': sender.username if sender else 'Unknown',
                    'timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M')
                })
        return jsonify(result)

    # ============================================================
    # СТРАНИЦЫ ПРИЛОЖЕНИЙ
    # ============================================================

    @app.route('/app')
    def apps_page():
        return render_template('app.html')

    @app.route('/app/ntfy')
    def app_ntfy():
        return render_template('app_ntfy.html')

    return app