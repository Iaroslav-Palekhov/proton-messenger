# Papirus Messenger

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg?cacheSeconds=2592000)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Python](https://img.shields.io/badge/Python-3.9+-yellow.svg)
![SQLite](https://img.shields.io/badge/SQLite-3-lightblue.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-red.svg)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**Современный self-hosted мессенджер с групповыми чатами, файлообменником и real-time обновлениями**

[Демо](https://chat.termux.ru) · [Сообщить об ошибке](https://github.com/Iaroslav-Palekhov/gamma-messenger/issues) · [Предложить функцию](https://github.com/Iaroslav-Palekhov/gamma-messenger/issues)

---

## Содержание

- [Возможности](#возможности)
- [Технологический стек](#технологический-стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [API и маршруты](#api-и-маршруты)
- [Socket.IO события](#socketio-события)
- [Безопасность](#безопасность)
- [Участие в разработке](#участие-в-разработке)
- [Лицензия](#лицензия)

---

## Возможности

### Сообщения и чаты

Приватные чаты между пользователями с отметками о прочтении, историей переписки и индикатором набора текста в реальном времени. Групповые чаты с гибкой системой ролей: владелец, администратор, участник.

Поддерживаются ответы на конкретные сообщения, пересылка между чатами и группами (с сохранением или скрытием оригинального отправителя), закрепление важных сообщений, редактирование и мягкое удаление.

### Файлообменник

Отправка файлов до 500 МБ — изображения, документы, видео, архивы и исполняемые файлы. Файлы автоматически классифицируются по типу и сохраняются в раздельные папки. Изображения сжимаются и ресайзятся до 800x800 px при загрузке.

### Превью ссылок

Автоматическое извлечение Open Graph метаданных (заголовок, описание, изображение) из отправленных URL через фоновый поток. Результат доставляется клиенту по Socket.IO без блокировки интерфейса.

### Экспорт истории

Экспорт переписки (личной или групповой) в ZIP-архив: HTML-страница с сообщениями и все вложения. Доступно из интерфейса чата.

### Поиск по сообщениям

Полнотекстовый поиск по истории чата или группы. Возвращает список совпадений с контекстом.

### Медиагалерея

Просмотр всех изображений, файлов или других медиа из чата или группы в одном месте через отдельный эндпоинт.

### Push-уведомления

Интеграция с ntfy (self-hosted или публичный ntfy.sh). Уведомления о новых сообщениях и входах в аккаунт. Топик и сервер настраиваются индивидуально для каждого пользователя, доступна отправка тестового уведомления.

### Управление сессиями

Просмотр всех активных устройств с информацией о браузере, ОС и IP-адресе. Удалённое завершение отдельной сессии или всех сразу. Ntfy-уведомление отправляется при новом входе в аккаунт.

### Контакты и чёрный список

Список контактов с возможностью добавлять и удалять пользователей. Блокировка нежелательных пользователей из профиля или раздела безопасности.

### Адаптивный интерфейс

Отдельный сайдбар и CSS-слой для десктопного разрешения, корректное отображение на планшетах и мобильных устройствах.

---

## Технологический стек

### Backend

| Технология | Версия | Назначение |
|---|---|---|
| Python | 3.9+ | Основной язык |
| Flask | 2.3.3 | Веб-фреймворк |
| Flask-SQLAlchemy | — | ORM для работы с базой данных |
| Flask-Login | — | Управление аутентификацией и сессиями |
| Flask-SocketIO | — | WebSocket / real-time события |
| Flask-Compress | — | Gzip/Brotli сжатие HTTP-ответов |
| SQLite / PostgreSQL | — | База данных (переключается через `DATABASE_URL`) |
| Pillow | — | Обработка и сжатие изображений |
| BeautifulSoup4 | — | Парсинг HTML для превью ссылок |
| Werkzeug | — | Утилиты безопасности, обработка файлов |
| cryptography | — | Опциональное шифрование тела сообщений |
| user-agents | — | Парсинг User-Agent для страницы устройств |
| requests | — | HTTP-запросы для извлечения метаданных и ntfy |

### Frontend

| Технология | Назначение |
|---|---|
| Jinja2 | Шаблонизатор (встроен в Flask) |
| Vanilla JS + Fetch API | Интерактивность без сторонних фреймворков |
| Socket.IO (клиент) | Real-time обновления |

### Инфраструктура

| Компонент | Назначение |
|---|---|
| Werkzeug `secure_filename` | Безопасное сохранение имён файлов |
| `secrets` модуль | Генерация криптографически стойкого `SECRET_KEY` |
| UUID4 | Уникальные имена загружаемых файлов |
| Connection Pool | Оптимизированный пул соединений SQLAlchemy |
| ntfy | Push-уведомления (self-hosted или ntfy.sh) |

---

## Архитектура

```
papirus/
├── papirus.py              # Точка входа, инициализация Flask-приложения
├── config.py               # Конфигурация (Dev/Production)
├── models.py               # ORM-модели SQLAlchemy
├── routing.py              # Регистрация всех маршрутов и API
├── socketio_events.py      # Socket.IO обработчики real-time событий
├── security.py             # Шифрование, хеширование, rate limiting, санитизация
├── ntfy_notifications.py   # Отправка push-уведомлений через ntfy
├── utils.py                # Вспомогательные функции (файлы, превью ссылок)
├── templates/
│   ├── base.html
│   ├── chat.html
│   ├── chats.html
│   ├── group_chat.html
│   ├── group_members.html
│   ├── profile.html
│   ├── edit_profile.html
│   ├── security.html
│   ├── devices.html
│   ├── notifications.html
│   ├── blacklist.html
│   ├── contacts.html
│   ├── password.html
│   ├── login.html
│   ├── register.html
│   ├── forgot_password.html
│   └── reset_password.html
├── static/
│   ├── css/
│   │   ├── style.css
│   │   ├── chats.css
│   │   └── desktop_sidebar.css
│   ├── js/
│   │   ├── script.js
│   │   ├── desktop_sidebar.js
│   │   └── socket.io.min.js
│   └── uploads/            # Создаётся автоматически
│       ├── avatars/
│       ├── group_icons/
│       ├── images/
│       ├── videos/
│       ├── audio/
│       ├── documents/
│       ├── archives/
│       ├── executables/
│       └── other/
└── requirements.txt
```

### Модели данных

```
User ──< Message >── Chat
 │                    │
 ├──< GroupMember >── Group ──< Message
 ├──< UserSession
 ├──< BlockedUser
 └──< Contact
```

| Модель | Описание |
|---|---|
| `User` | Аккаунт пользователя: email, username, avatar, bio, статус, push_token |
| `Chat` | Приватный чат между двумя пользователями |
| `Group` | Групповой чат с иконкой и описанием |
| `GroupMember` | Связь пользователя с группой + роль (`owner` / `admin` / `member`) |
| `Message` | Сообщение: текст, файл, ответ, пересылка, закреп, превью ссылки, мягкое удаление |
| `ForwardedMessage` | Метаданные пересланного сообщения |
| `UserSession` | Активная сессия с информацией об устройстве, браузере и IP |
| `BlockedUser` | Запись о блокировке между двумя пользователями |
| `Contact` | Контакт пользователя |
| `PasswordReset` | Токен сброса пароля с временем истечения |

---

## Быстрый старт

### Требования

- Python 3.9 или выше
- pip
- Git

### Установка

### Автоматическая установка

**Linux (Debian/Ubuntu):**
```bash
curl -o run_linux.sh https://raw.githubusercontent.com/Iaroslav-Palekhov/gamma-messenger/refs/heads/main/run_linux.sh
sudo chmod +x ./run_linux.sh
./run_linux.sh
```

**Windows:**

Скачайте и запустите [`run_windows.bat`](https://github.com/Iaroslav-Palekhov/gamma-messenger/blob/main/run_windows.bat)


```bash
# Клонирование репозитория
git clone https://github.com/Iaroslav-Palekhov/gamma-messenger.git
cd gamma-messenger

# Создание и активация виртуального окружения
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python papirus.py
```

**Android:**

```
# Скачайте приложение
https://github.com/Iaroslav-Palekhov/gamma-server-android/releases/download/Release/gamma-server-arm64_v8a.apk

# Скачайте termux

# скачайте ntfy server

error

# Выполните в термуксе termux-setup-storage и разрешите доступ к файлам потом скопируйте и запустите сервис уведомлений

# Потом запустите и сервер мессенджера и готово
```

После запуска откройте браузер по адресу: **http://localhost:2200**

При первом старте автоматически создаются папки для загрузки файлов, дефолтные аватарки, база данных SQLite (`database.db`) и файл `.secret_key` с криптографически стойким ключом (права `0o600`).

---

## Конфигурация

Все параметры задаются через переменные окружения или в `config.py`.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `FLASK_SECRET_KEY` | Авто-генерация | Секретный ключ Flask (обязательно задать в продакшене) |
| `DATABASE_URL` | `sqlite:///database.db` | URI базы данных. Поддерживает PostgreSQL |
| `PASSWORD_PEPPER` | `papirus-pepper-...` | Статическая добавка к хешам паролей |
| `MESSAGE_ENCRYPTION_KEY` | `None` | Ключ шифрования тела сообщений (опционально) |
| `MAX_CONTENT_LENGTH` | `500 МБ` | Максимальный размер загружаемого файла |
| `NTFY_SERVER` | `https://ntfy.sh` | Адрес ntfy-сервера по умолчанию |

### Пример `.env` для продакшена

```env
FLASK_SECRET_KEY=your-very-long-random-secret-key
DATABASE_URL=postgresql://user:password@localhost/papirus
PASSWORD_PEPPER=your-unique-pepper-string
MESSAGE_ENCRYPTION_KEY=your-32-byte-encryption-key
NTFY_SERVER=https://ntfy.your-domain.com
```

### Production vs Development

```python
# Development (по умолчанию)
DEBUG = True
SESSION_COOKIE_SECURE = False   # HTTP

# Production
DEBUG = False
SESSION_COOKIE_SECURE = True    # Только HTTPS
REMEMBER_COOKIE_SECURE = True
```

---

## API и маршруты

### Аутентификация

| Метод | Путь | Описание |
|---|---|---|
| `GET / POST` | `/login` | Вход в аккаунт |
| `GET / POST` | `/register` | Регистрация |
| `GET` | `/logout` | Выход |
| `GET / POST` | `/forgot_password` | Запрос сброса пароля |
| `GET / POST` | `/reset_password/<token>` | Сброс пароля по токену |

### Чаты

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/chats` | Список всех диалогов и групп |
| `GET` | `/chat/<chat_id>` | Открыть личный чат |
| `GET / POST` | `/start_chat?username=...` | Начать новый диалог |
| `POST` | `/chat/<chat_id>/delete` | Удалить чат |
| `GET` | `/api/get_chats_data` | JSON: список чатов с метаданными |

### Группы

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/groups` | Список групп пользователя |
| `POST` | `/group/create` | Создать группу |
| `GET` | `/group/<group_id>` | Открыть групповой чат |
| `GET` | `/group/<group_id>/members` | Список участников |
| `POST` | `/group/<group_id>/add_member` | Добавить участника |
| `POST` | `/group/<group_id>/remove_member/<user_id>` | Удалить участника |
| `POST` | `/group/<group_id>/change_role/<user_id>` | Изменить роль участника |
| `POST` | `/group/<group_id>/edit` | Редактировать название / иконку группы |
| `POST` | `/group/<group_id>/delete` | Удалить группу (только владелец) |
| `POST` | `/group/<group_id>/leave` | Покинуть группу |

### Сообщения

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/send_message` | Отправить сообщение (текст, файл, изображение) |
| `POST` | `/edit_message/<message_id>` | Редактировать текст сообщения |
| `POST` | `/delete_message/<message_id>` | Удалить сообщение (мягкое удаление) |
| `POST` | `/pin_message/<message_id>` | Закрепить сообщение |
| `POST` | `/unpin_message/<message_id>` | Открепить сообщение |
| `POST` | `/forward_message` | Переслать сообщение в чат или группу |
| `GET` | `/get_messages/<chat_id>` | JSON: история сообщений чата |
| `GET` | `/get_pinned_messages/<context_id>` | JSON: закреплённые сообщения |
| `GET` | `/get_unread_counts` | JSON: количество непрочитанных по чатам |
| `GET` | `/get_chats_and_groups_for_forward` | JSON: список доступных получателей для пересылки |
| `GET` | `/search_messages/<context_id>?q=...&is_group=...` | Поиск по истории чата или группы |
| `GET` | `/export_chat/<context_id>?is_group=...` | Экспорт переписки в ZIP (HTML + вложения) |
| `GET` | `/get_media/<context_id>?type=...&is_group=...` | Медиагалерея чата или группы |
| `GET` | `/download/<filepath>` | Скачать вложение |

### Профиль

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/profile/<user_id>` | Просмотр профиля пользователя |
| `GET / POST` | `/profile/edit` | Редактирование профиля (имя, биография, аватар) |

### Контакты

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/contacts` | Список контактов |
| `POST` | `/contacts/add/<user_id>` | Добавить контакт |
| `POST` | `/contacts/remove/<user_id>` | Удалить контакт |

### Безопасность

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/security` | Раздел безопасности |
| `GET` | `/security/password` | Страница смены пароля |
| `POST` | `/security/change_password` | Сменить пароль |
| `GET` | `/security/devices` | Активные сессии (устройства) |
| `POST` | `/security/terminate_session/<session_id>` | Завершить сессию по ID |
| `POST` | `/security/terminate_all_sessions` | Завершить все сессии, кроме текущей |
| `GET` | `/security/blacklist` | Чёрный список |
| `POST` | `/security/block/<user_id>` | Заблокировать пользователя |
| `POST` | `/security/unblock/<user_id>` | Разблокировать пользователя |
| `GET` | `/security/notifications` | Настройки push-уведомлений (ntfy) |
| `POST` | `/security/notifications/save` | Сохранить ntfy-топик и сервер |
| `POST` | `/security/notifications/test` | Отправить тестовое уведомление |
| `POST` | `/security/notifications/remove` | Отвязать ntfy-топик |

### Утилиты

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/search_users?q=...` | Поиск пользователей по имени или email |

---

## Socket.IO события

### Клиент -> Сервер

| Событие | Данные | Описание |
|---|---|---|
| `join_chat` | `{ chat_id }` | Подключиться к комнате личного чата |
| `leave_chat` | `{ chat_id }` | Покинуть комнату личного чата |
| `join_group` | `{ group_id }` | Подключиться к комнате группы |
| `leave_group` | `{ group_id }` | Покинуть комнату группы |
| `send_message` | `{ chat_id / group_id, content, ... }` | Отправить сообщение через WebSocket |
| `typing` | `{ chat_id / group_id, is_typing }` | Индикатор набора текста |
| `messages_read` | `{ chat_id / group_id }` | Отметить сообщения как прочитанные |
| `heartbeat` | — | Поддержание соединения и обновление last_seen |

### Сервер -> Клиент

| Событие | Описание |
|---|---|
| `new_message` | Новое сообщение в чате или группе |
| `chat_updated` | Обновление метаданных чата (последнее сообщение, время) |
| `group_updated` | Обновление метаданных группы |
| `message_deleted` | Сообщение удалено |
| `message_edited` | Текст сообщения изменён |
| `link_preview_ready` | Превью ссылки готово (доставляется асинхронно) |
| `typing` | Пользователь набирает сообщение |
| `user_status` | Изменение статуса пользователя (online / offline + last_seen) |

---

## Безопасность

### Аутентификация и сессии

Пароли хешируются через Werkzeug с pepper-добавкой (`PASSWORD_PEPPER`). Каждой сессии присваивается уникальный `session_token`, хранящийся в БД. При удалённом завершении сессии токен инвалидируется немедленно. Cookie защищены флагами `HttpOnly` и `SameSite=Lax`; в продакшене включается `Secure`.

Ntfy-уведомление отправляется при каждом новом входе в аккаунт, если пользователь настроил push-топик.

### Шифрование сообщений

При наличии `MESSAGE_ENCRYPTION_KEY` тело сообщений шифруется симметричным алгоритмом через библиотеку `cryptography` перед записью в базу и расшифровывается при чтении.

### Управление файлами

Все имена файлов обрабатываются через `secure_filename`. Файлам присваивается UUID4-префикс для исключения коллизий и directory traversal. Изображения пересжимаются через Pillow (максимум 800x800, quality 85). Хранение разделено по категориям файлов.

### Контроль доступа и rate limiting

Rate limiting реализован через встроенный `RateLimiter` в `security.py` (включается параметром `RATELIMIT_ENABLED`). Новые аккаунты имеют 24-часовое ограничение на управление сессиями. Длина сообщений ограничена `MAX_MESSAGE_LENGTH = 4000`. Все входные данные проходят санитизацию через `InputSanitizer`: обрезка пробелов, проверка на SQL-инъекции, валидация email и имени пользователя. Security headers (CSP, X-Frame-Options, X-Content-Type-Options и др.) устанавливаются через `after_request`.

### Сеть

Gzip/Brotli сжатие ответов через `flask-compress`. Connection pool с `pool_pre_ping=True` и автопереподключением.

---

## Участие в разработке

Вклад приветствуется. Следуйте стандартному GitHub flow:

```bash
# Форкните репозиторий, затем:
git checkout -b feature/your-feature-name
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
# Откройте Pull Request
```

### Соглашение о коммитах

Используется формат [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — новая функциональность
- `fix:` — исправление ошибки
- `docs:` — обновление документации
- `refactor:` — рефакторинг кода
- `style:` — изменения форматирования

---

## Лицензия

Распространяется под лицензией **GPL-3.0**. Подробнее см. файл [LICENSE](LICENSE).

---

Сделано с любовью · [GitHub](https://github.com/Iaroslav-Palekhov/gamma-messenger)
