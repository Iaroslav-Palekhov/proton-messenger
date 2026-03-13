# Gamma Messenger

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg?cacheSeconds=2592000)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Python](https://img.shields.io/badge/Python-3.9+-yellow.svg)
![SQLite](https://img.shields.io/badge/SQLite-3-lightblue.svg)
![License](https://img.shields.io/badge/license-MIT-red.svg)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

**Современный мессенджер с групповыми чатами, файлообменником и real-time обновлениями**

[🌐 Демо](https://chat.termux.ru) · [🐛 Сообщить об ошибке](https://github.com/Iaroslav-Palekhov/gamma-messenger/issues) · [💡 Предложить функцию](https://github.com/Iaroslav-Palekhov/gamma-messenger/issues)

</div>

---

## Содержание

- [Возможности](#возможности)
- [Скриншоты](#скриншоты)
- [Технологический стек](#технологический-стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Структура проекта](#структура-проекта)
- [API и маршруты](#api-и-маршруты)
- [Безопасность](#безопасность)
- [Участие в разработке](#участие-в-разработке)

---

## Возможности

<table>
  <tr>
    <td width="50%">
      <h3>Личные сообщения</h3>
      Приватные чаты между пользователями с отметками о прочтении и историей переписки.
    </td>
    <td width="50%">
      <h3>Групповые чаты</h3>
      Создавайте группы с гибкой системой ролей: владелец, администратор, участник.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>Файлообменник</h3>
      Отправляйте файлы до 500 МБ — изображения, документы, видео, архивы и исполняемые файлы с автоматической классификацией по типу.
    </td>
    <td width="50%">
      <h3>Превью ссылок</h3>
      Автоматическое извлечение Open Graph метаданных (заголовок, описание, изображение) из отправленных URL.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>Ответы на сообщения</h3>
      Цитируйте и отвечайте на конкретные сообщения в диалоге или группе.
    </td>
    <td width="50%">
      <h3>Пересылка</h3>
      Пересылайте сообщения между чатами и группами с сохранением или скрытием оригинального отправителя.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>Закреплённые сообщения</h3>
      Закрепляйте важные сообщения в чатах и группах для быстрого доступа.
    </td>
    <td width="50%">
      <h3>Управление сессиями</h3>
      Просматривайте активные устройства и завершайте сторонние сессии удалённо.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>Чёрный список</h3>
      Блокируйте нежелательных пользователей прямо из профиля или настроек безопасности.
    </td>
    <td width="50%">
      <h3>Адаптивный дизайн</h3>
      Интерфейс корректно отображается на ПК, планшетах и мобильных устройствах.
    </td>
  </tr>
</table>

---

## Скриншоты

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="screenshots/login.png" alt="Вход в приложение" width="300">
        <br><em>Страница входа</em>
      </td>
      <td align="center">
        <img src="screenshots/chat.png" alt="Личный чат" width="300">
        <br><em>Личный чат</em>
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="screenshots/profile.png" alt="Профиль пользователя" width="300">
        <br><em>Профиль пользователя</em>
      </td>
      <td align="center">
        <img src="screenshots/group_members.png" alt="Участники группы" width="300">
        <br><em>Участники группы</em>
      </td>
    </tr>
  </table>
</div>

---

## Технологический стек

### Backend

| Технология | Версия | Назначение |
|---|---|---|
| **Python** | 3.9+ | Основной язык |
| **Flask** | 2.3.3 | Веб-фреймворк |
| **Flask-SQLAlchemy** | — | ORM для работы с базой данных |
| **Flask-Login** | — | Управление аутентификацией и сессиями |
| **Flask-Compress** | — | Gzip/Brotli сжатие HTTP-ответов |
| **SQLite / PostgreSQL** | — | База данных (через `DATABASE_URL`) |
| **Pillow** | — | Обработка и сжатие изображений |
| **BeautifulSoup4** | — | Парсинг HTML для превью ссылок |
| **Werkzeug** | — | Утилиты безопасности, обработка файлов |
| **requests** | — | HTTP-запросы для извлечения метаданных |

### Frontend

| Технология | Назначение |
|---|---|
| **Jinja2** | Шаблонизатор (встроен в Flask) |
| **JS** | Интерактивность без сторонних фреймворков |
| **Fetch API** | AJAX-запросы к серверу |

### Инфраструктура

| Компонент | Назначение |
|---|---|
| **Werkzeug `secure_filename`** | Безопасное сохранение имён файлов |
| **`secrets` модуль** | Генерация криптографически стойкого `SECRET_KEY` |
| **UUID4** | Уникальные имена загружаемых файлов |
| **Connection Pool** | Оптимизированный пул соединений SQLAlchemy |

---

## Архитектура

```
gamma-messenger/
├── papirus.py          # Точка входа, инициализация Flask-приложения
├── config.py           # Конфигурация (Dev/Production)
├── models.py           # ORM-модели SQLAlchemy
├── routing.py          # Регистрация всех маршрутов
├── security.py         # Инициализация модуля безопасности
├── utils.py            # Вспомогательные функции (файлы, превью ссылок)
├── templates/          # Jinja2 HTML-шаблоны
│   ├── base.html
│   ├── chat.html
│   ├── chats.html
│   ├── group_chat.html
│   ├── group_members.html
│   ├── profile.html
│   ├── edit_profile.html
│   ├── security.html
│   ├── devices.html
│   ├── blacklist.html
│   ├── password.html
│   ├── login.html
│   ├── register.html
│   ├── forgot_password.html
│   └── reset_password.html
├── static/
│   └── uploads/        # Загружаемые файлы (создаётся автоматически)
│       ├── avatars/
│       ├── group_icons/
│       ├── images/
│       ├── videos/
│       ├── audio/
│       ├── documents/
│       ├── archives/
│       ├── executables/
│       └── other/
├── requirements.txt
├── run_linux.sh
└── run_windows.bat
```

### Модели данных

```
User ──< Message >── Chat
 │                    │
 ├──< GroupMember >── Group ──< Message
 ├──< UserSession
 └──< BlockedUser
```

| Модель | Описание |
|---|---|
| `User` | Аккаунт пользователя: email, username, avatar, bio, статус |
| `Chat` | Приватный чат между двумя пользователями |
| `Group` | Групповой чат с иконкой и описанием |
| `GroupMember` | Связь пользователя с группой + роль (`owner`/`admin`/`member`) |
| `Message` | Сообщение с поддержкой текста, файлов, ответов, пересылки, закрепления |
| `UserSession` | Активная сессия пользователя с информацией об устройстве и IP |
| `BlockedUser` | Запись о блокировке между двумя пользователями |
| `PasswordReset` | Токен сброса пароля с временем истечения |
| `ForwardedMessage` | Метаданные пересланного сообщения |

---

## Быстрый старт

### Предварительные требования

- Python **3.9** или выше
- `pip` (менеджер пакетов Python)
- Git

### Автоматическая установка

**Linux (Debian/Ubuntu):**
```bash
curl -o run_linux.sh https://raw.githubusercontent.com/Iaroslav-Palekhov/gamma-messenger/refs/heads/main/run_linux.sh
sudo chmod +x ./run_linux.sh
sudo ./run_linux.sh
```

**Windows:**

Скачайте и запустите [`run_windows.bat`](https://github.com/Iaroslav-Palekhov/gamma-messenger/blob/main/run_windows.bat)

### Ручная установка

```bash
# 1. Клонирование репозитория
git clone https://github.com/Iaroslav-Palekhov/gamma-messenger.git
cd gamma-messenger

# 2. Создание виртуального окружения
python -m venv venv

# 3. Активация (Linux/Mac)
source venv/bin/activate
# Активация (Windows)
venv\Scripts\activate

# 4. Установка зависимостей
pip install -r requirements.txt

# 5. Запуск
python papirus.py
```

После запуска откройте браузер по адресу: **http://localhost:2200**

При первом старте автоматически создаются:
- Папки для загрузки файлов (`static/uploads/...`)
- Дефолтные аватарки для пользователей и групп
- База данных SQLite (`database.db`)
- Файл `.secret_key` с криптографически стойким ключом

---

## Конфигурация

Все параметры задаются через переменные окружения или в `config.py`.

| Переменная | По умолчанию | Описание |
|---|---|---|
| `FLASK_SECRET_KEY` | Авто-генерация | Секретный ключ Flask (обязательно задать в продакшене) |
| `DATABASE_URL` | `sqlite:///database.db` | URI базы данных. Поддерживает PostgreSQL |
| `PASSWORD_PEPPER` | `papirus-pepper-...` | Статическая добавка к хешам паролей |
| `MESSAGE_ENCRYPTION_KEY` | `None` | Ключ шифрования сообщений (опционально) |
| `MAX_CONTENT_LENGTH` | `500 МБ` | Максимальный размер загружаемого файла |

### Пример `.env` для продакшена

```env
FLASK_SECRET_KEY=your-very-long-random-secret-key
DATABASE_URL=postgresql://user:password@localhost/gamma
PASSWORD_PEPPER=your-unique-pepper-string
MESSAGE_ENCRYPTION_KEY=your-32-byte-encryption-key
```

### Production vs Development

В `config.py` предусмотрены два профиля:

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
| `GET/POST` | `/login` | Вход в аккаунт |
| `GET/POST` | `/register` | Регистрация |
| `GET` | `/logout` | Выход |
| `GET/POST` | `/forgot_password` | Запрос сброса пароля |
| `GET/POST` | `/reset_password/<token>` | Сброс пароля по токену |

### Чаты и сообщения

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/chats` | Список всех диалогов |
| `GET` | `/chat/<chat_id>` | Открыть личный чат |
| `GET` | `/start_chat?username=...` | Начать новый диалог |
| `GET` | `/group/<group_id>` | Открыть групповой чат |
| `POST` | `/send_message` | Отправить сообщение |
| `POST` | `/edit_message/<id>` | Редактировать сообщение |
| `POST` | `/delete_message/<id>` | Удалить сообщение |
| `POST` | `/pin_message/<id>` | Закрепить сообщение |
| `POST` | `/forward_message` | Переслать сообщение |

### Группы

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/create_group` | Создать группу |
| `GET` | `/group/<id>/members` | Список участников |
| `POST` | `/group/<id>/add_member` | Добавить участника |
| `POST` | `/group/<id>/remove_member/<uid>` | Удалить участника |
| `POST` | `/group/<id>/change_role/<uid>` | Изменить роль |
| `POST` | `/group/<id>/leave` | Покинуть группу |

### Профиль и безопасность

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/profile/<user_id>` | Просмотр профиля |
| `GET/POST` | `/edit_profile` | Редактирование профиля |
| `GET` | `/security` | Раздел безопасности |
| `POST` | `/security/change_password` | Смена пароля |
| `GET` | `/security/devices` | Активные устройства |
| `POST` | `/security/terminate_session/<id>` | Завершить сессию |
| `POST` | `/security/terminate_all_sessions` | Завершить все сессии |
| `GET` | `/security/blacklist` | Чёрный список |
| `POST` | `/security/block/<uid>` | Заблокировать пользователя |
| `POST` | `/security/unblock/<uid>` | Разблокировать пользователя |

---

## Безопасность

Приложение реализует несколько уровней защиты:

**Аутентификация и сессии**
- Хеширование паролей с pepper-добавкой через Werkzeug
- Уникальный `session_token` для каждой сессии, хранится в БД
- Принудительный разлогин при удалённом завершении сессии
- `SESSION_COOKIE_HTTPONLY = True` — защита от XSS-кражи куки
- `SESSION_COOKIE_SAMESITE = 'Lax'` — защита от CSRF

**Управление файлами**
- Все имена файлов обрабатываются через `secure_filename`
- Файлам присваивается UUID4-префикс во избежание коллизий и directory traversal
- Автоматическое сжатие и ресайз изображений (макс. 800×800, quality 85)
- Категоризация по типу с раздельными папками хранения

**Контроль доступа**
- 24-часовая блокировка управления сессиями для новых аккаунтов
- Ограничение на длину сообщений (`MAX_MESSAGE_LENGTH = 4000`)
- Rate limiting через `RATELIMIT_ENABLED`
- Автоматическая генерация `SECRET_KEY` при первом запуске с правами `0o600`

**Сеть**
- Gzip/Brotli компрессия ответов через `flask-compress`
- Connection pool с автопроверкой (`pool_pre_ping = True`) и переиспользованием соединений

---

## Участие в разработке

Вклад приветствуется! Пожалуйста, следуйте стандартному GitHub flow:

```bash
# 1. Форкните репозиторий
# 2. Создайте ветку для вашей функции
git checkout -b feature/your-feature-name

# 3. Зафиксируйте изменения
git commit -m "feat: add your feature"

# 4. Отправьте ветку
git push origin feature/your-feature-name

# 5. Откройте Pull Request
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

Распространяется под лицензией **GPL-3**. Подробнее см. файл [LICENSE](LICENSE).

---

<div align="center">
  Сделано с ❤️ · <a href="https://github.com/Iaroslav-Palekhov/gamma-messenger">GitHub</a>
</div>
