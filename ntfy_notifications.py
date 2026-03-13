"""
Модуль отправки push-уведомлений через ntfy.sh (или самохостинг ntfy).
Использует только стандартную библиотеку Python (urllib) — без зависимостей.
"""

import threading
import urllib.request
import urllib.error
import base64
import logging

logger = logging.getLogger("ntfy")


def _encode_header(val: str) -> str:
    """Кодирует строку для HTTP-заголовка через RFC 2047 (base64-utf8).
    Нужно потому что HTTP-заголовки должны быть ASCII."""
    try:
        val.encode("ascii")
        return val
    except UnicodeEncodeError:
        encoded = base64.b64encode(val.encode("utf-8")).decode("ascii")
        return f"=?utf-8?b?{encoded}?="


def _send_ntfy(topic: str, title: str, message: str,
               tags: list = None, priority: int = 3,
               server: str = "https://ntfy.sh"):
    """Синхронная отправка — вызывается из потока."""
    if not topic:
        return

    url = f"{server.rstrip('/')}/{topic}"
    body = message.encode("utf-8")

    headers = {
        "Title":        _encode_header(title),
        "Priority":     str(priority),
        "Content-Type": "text/plain; charset=utf-8",
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body_resp = resp.read(200).decode("utf-8", errors="replace")
            print(f"[ntfy] OK: POST {url} -> {status} {body_resp}", flush=True)
    except urllib.error.HTTPError as e:
        body_resp = e.read(500).decode("utf-8", errors="replace")
        print(f"[ntfy] HTTPError {e.code}: {body_resp}", flush=True)
    except urllib.error.URLError as e:
        print(f"[ntfy] URLError: {e.reason} (url={url})", flush=True)
    except Exception as e:
        print(f"[ntfy] Exception: {type(e).__name__}: {e}", flush=True)


def send_notification(topic: str, title: str, message: str,
                      tags: list = None, priority: int = 3,
                      server: str = "https://ntfy.sh"):
    """Асинхронная отправка в фоновом потоке."""
    if not topic:
        print("[ntfy] topic пустой, пропускаем", flush=True)
        return

    print(f"[ntfy] Запуск отправки: topic={topic!r} server={server!r} title={title!r}", flush=True)

    t = threading.Thread(
        target=_send_ntfy,
        args=(topic, title, message, tags, priority, server),
        daemon=False,
    )
    t.start()


# ─────────────────────────────────────────────
# Конкретные события
# ─────────────────────────────────────────────

def notify_new_login(user, ip: str, device: str, server: str = "https://ntfy.sh"):
    send_notification(
        topic=user.push_token,
        title="Новый вход в аккаунт",
        message=f"Устройство: {device}\nIP: {ip}",
        priority=4,
        server=server,
    )


def notify_new_message(recipient_user, sender_username: str, preview: str,
                       server: str = "https://ntfy.sh"):
    send_notification(
        topic=recipient_user.push_token,
        title=f"Сообщение от {sender_username}",
        message=preview if preview else "Вложение",
        priority=3,
        server=server,
    )


def notify_group_message(member_user, sender_username: str, group_name: str,
                         preview: str, server: str = "https://ntfy.sh"):
    send_notification(
        topic=member_user.push_token,
        title=group_name,
        message=f"{sender_username}: {preview}" if preview else f"{sender_username}: Вложение",
        priority=3,
        server=server,
    )
