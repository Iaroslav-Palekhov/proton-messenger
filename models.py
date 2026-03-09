from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    avatar = db.Column(db.String(200), default='avatars/default.png')
    bio = db.Column(db.String(200), default='')
    status = db.Column(db.String(50), default='online')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    owned_groups = db.relationship('Group', backref='owner', lazy=True)
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    sessions = db.relationship('UserSession', backref='user', lazy=True, cascade='all, delete-orphan')

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), default='')
    icon = db.Column(db.String(200), default='group_icons/default.png')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('GroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy=True)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('Message', backref='chat', lazy=True, cascade='all, delete-orphan')
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=True, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    content = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(200), nullable=True)
    file_path = db.Column(db.String(200), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    file_category = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False, index=True)

    reply_to_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    forwarded_from_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    is_forwarded = db.Column(db.Boolean, default=False)
    show_forward_sender = db.Column(db.Boolean, default=True)

    reply_to = db.relationship('Message', foreign_keys=[reply_to_id], remote_side=[id], backref='replies')
    forwarded_from = db.relationship('Message', foreign_keys=[forwarded_from_id], remote_side=[id], backref='forwarded_copies')

    is_pinned = db.Column(db.Boolean, default=False)
    pinned_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    pinned_at = db.Column(db.DateTime, nullable=True)

    link_url = db.Column(db.String(500), nullable=True)
    link_title = db.Column(db.String(200), nullable=True)
    link_description = db.Column(db.Text, nullable=True)
    link_image = db.Column(db.String(500), nullable=True)
    link_fetched_at = db.Column(db.DateTime, nullable=True)

class ForwardedMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    forwarded_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    forwarded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    forwarded_to_chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=True)
    forwarded_to_group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    show_sender = db.Column(db.Boolean, default=True)
    forwarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    original_message = db.relationship('Message', foreign_keys=[original_message_id])
    forwarded_message = db.relationship('Message', foreign_keys=[forwarded_message_id])
    forwarded_by = db.relationship('User', foreign_keys=[forwarded_by_id])


class PasswordReset(db.Model):
    """Модель для токенов сброса пароля"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('reset_tokens', lazy=True))


class UserSession(db.Model):
    """
    Хранит информацию об активных и завершённых сессиях пользователя.
    Позволяет показывать устройства входа и завершать конкретные сессии.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # Уникальный токен сессии (хранится в Flask session)
    session_token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Информация об устройстве / браузере
    ip_address = db.Column(db.String(45), nullable=True)       # IPv4 или IPv6
    user_agent = db.Column(db.String(500), nullable=True)      # Полный UA-string
    device_type = db.Column(db.String(20), nullable=True)      # mobile / tablet / desktop
    browser = db.Column(db.String(100), nullable=True)         # Chrome 120, Safari 17...
    os = db.Column(db.String(100), nullable=True)              # Windows 11, iOS 17...
    country = db.Column(db.String(100), nullable=True)         # Страна (опционально)
    city = db.Column(db.String(100), nullable=True)            # Город (опционально)

    # Временны́е метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow)   # Время входа
    last_active = db.Column(db.DateTime, default=datetime.utcnow)  # Последняя активность
    ended_at = db.Column(db.DateTime, nullable=True)               # Время выхода (NULL = активна)

    # Флаги
    is_active = db.Column(db.Boolean, default=True)
    is_current = db.Column(db.Boolean, default=False)  # Текущая сессия пользователя

    def end_session(self):
        """Завершает сессию"""
        self.is_active = False
        self.ended_at = datetime.utcnow()

    def duration_str(self):
        """Возвращает читаемую длительность сессии"""
        end = self.ended_at or datetime.utcnow()
        delta = end - self.created_at
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if days > 0:
            return f"{days} д. {hours} ч."
        elif hours > 0:
            return f"{hours} ч. {minutes} мин."
        else:
            return f"{minutes} мин."

    def last_active_str(self):
        """Возвращает читаемое время последней активности"""
        now = datetime.utcnow()
        delta = now - self.last_active
        if delta.seconds < 60:
            return "только что"
        elif delta.seconds < 3600:
            return f"{delta.seconds // 60} мин. назад"
        elif delta.days == 0:
            return f"{delta.seconds // 3600} ч. назад"
        elif delta.days == 1:
            return "вчера"
        else:
            return self.last_active.strftime('%d.%m.%Y %H:%M')


class BlockedUser(db.Model):
    """Чёрный список — заблокированные пользователи."""
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    blocker = db.relationship('User', foreign_keys=[blocker_id], backref=db.backref('blocked_users', lazy=True))
    blocked_user = db.relationship('User', foreign_keys=[blocked_id])

    __table_args__ = (db.UniqueConstraint('blocker_id', 'blocked_id', name='unique_block'),)