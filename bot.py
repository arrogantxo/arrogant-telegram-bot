import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = Path(os.getenv("BOT_DB_PATH", str(BASE_DIR / "bot_data.db")))
USERS_PATH = Path(os.getenv("BOT_USERS_PATH", str(BASE_DIR / "known_users.json")))


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "config.json not found. Copy config.example.json to config.json and fill it in."
        )
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_config(config: dict[str, Any]) -> None:
    token = str(os.getenv("BOT_TOKEN") or config.get("bot_token", "")).strip()
    if not token or token == "<SECRET>" or ":" not in token:
        raise ValueError(
            "Invalid bot token. Set BOT_TOKEN in environment or paste the real token into config.json."
        )


def load_known_users() -> dict[str, Any]:
    if not USERS_PATH.exists():
        return {}
    with USERS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_known_users(data: dict[str, Any]) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


CONFIG = load_config()
validate_config(CONFIG)


def load_timezone():
    timezone_name = CONFIG.get("timezone", "Asia/Tashkent")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Tashkent":
            return timezone(timedelta(hours=5), name="Asia/Tashkent")
        return timezone.utc


TIMEZONE = load_timezone()
CATEGORIES = CONFIG.get(
    "categories",
    [
        "съемка",
        "сценарий",
        "монтаж",
        "дизайн",
        "публикация",
        "созвон",
        "согласование",
        "выезд",
        "отчет",
        "дедлайн",
        "сторис",
        "reels",
    ],
)


CATEGORY_ALIASES = {
    "съемка": ["съемка", "съёмка", "снимать", "съемки", "съёмки", "выезд", "контент съемка"],
    "сценарий": ["сценарий", "сценарии", "script", "сценарист"],
    "монтаж": ["монтаж", "смонтировать", "смонтируй", "монтажер", "монтажёр", "редактировать"],
    "дизайн": ["дизайн", "дизайнер", "баннер", "афиша", "постер", "макет"],
    "публикация": ["публикация", "выложить", "опубликовать", "пост", "публиковать"],
    "созвон": ["созвон", "звонок", "колл", "встреча", "созвониться"],
    "согласование": ["согласование", "согласовать", "утверждение", "утвердить"],
    "выезд": ["выезд"],
    "отчет": ["отчет", "отчёт", "отчитаться"],
    "дедлайн": ["дедлайн", "срок"],
    "сторис": ["сторис", "stories", "story"],
    "reels": ["reels", "рилс", "рельс", "риелс", "реелс"],
}


ROLE_ALIASES = {
    "manager": ["manager", "менеджер", "руководитель", "я", "мне"],
    "montaj": ["montaj", "монтажер", "монтажёр", "мобилограф", "монтаж"],
    "publisher": ["publisher", "публикация", "публикатор", "постинг", "выкладка"],
    "videograf": ["videograf", "видеограф", "оператор", "съемщик"],
    "scriptwriter": ["scriptwriter", "сценарист", "копирайтер"],
    "designer": ["designer", "дизайнер", "дизайн"],
    "smm": ["smm", "смм", "smm manager", "контентщик"],
}


def now_local() -> datetime:
    return datetime.now(TIMEZONE)


def format_datetime(value: datetime) -> str:
    return value.astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M")


def parse_datetime(date_str: str, time_str: str) -> datetime:
    value = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return value.replace(tzinfo=TIMEZONE)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def human_help_text() -> str:
    return (
        "Можно писать просто по-человечески.\n\n"
        "Примеры:\n"
        "- Завтра съемка в 12, монтажер и видеограф\n"
        "- Сегодня в 18:00 выложить пост, publisher\n"
        "- Завтра в 10 сценарий для сценариста\n"
        "- Напомни всей команде о съемке завтра в 9\n"
        "- Какие задачи на сегодня?\n\n"
        "Старые команды тоже работают: /add, /broadcast, /list, /today"
    )


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    target_chat_id INTEGER NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    is_broadcast INTEGER NOT NULL DEFAULT 0,
                    sent INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending'
                )
                """
            )
            conn.commit()

    def add_reminder(
        self,
        title: str,
        category: str,
        remind_at: datetime,
        target_key: str,
        target_name: str,
        target_chat_id: int,
        created_by: int,
        is_broadcast: bool,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO reminders
                (
                    title, category, remind_at, target_key, target_name,
                    target_chat_id, created_by, created_at, is_broadcast
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    category,
                    remind_at.isoformat(),
                    target_key,
                    target_name,
                    target_chat_id,
                    created_by,
                    now_local().isoformat(),
                    1 if is_broadcast else 0,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_reminders(self, only_today: bool = False) -> list[sqlite3.Row]:
        query = """
            SELECT *
            FROM reminders
            WHERE status = 'pending'
        """
        params: list[Any] = []
        if only_today:
            start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
            end = now_local().replace(hour=23, minute=59, second=59, microsecond=999999)
            query += " AND remind_at BETWEEN ? AND ?"
            params.extend([start.isoformat(), end.isoformat()])
        query += " ORDER BY remind_at ASC"
        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def mark_done(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE reminders SET status = 'done' WHERE id = ? AND status = 'pending'",
                (task_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete(self, task_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def due_reminders(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM reminders
                WHERE status = 'pending' AND sent = 0 AND remind_at <= ?
                ORDER BY remind_at ASC
                """,
                (now_local().isoformat(),),
            ).fetchall()

    def mark_sent(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (task_id,))
            conn.commit()


storage = Storage(DB_PATH)


@dataclass
class TelegramBot:
    token: str

    @property
    def api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        params = params or {}

        if files:
            boundary = "----CodexMultipartBoundary7MA4YWxkTrZu0gW"
            body = bytearray()

            for key, value in params.items():
                body.extend(f"--{boundary}\r\n".encode())
                body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
                body.extend(str(value).encode("utf-8"))
                body.extend(b"\r\n")

            for field_name, (filename, content, content_type) in files.items():
                body.extend(f"--{boundary}\r\n".encode())
                body.extend(
                    f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
                )
                body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
                body.extend(content)
                body.extend(b"\r\n")

            body.extend(f"--{boundary}--\r\n".encode())
            headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
            req = urllib.request.Request(
                f"{self.api_base}/{method}",
                data=bytes(body),
                headers=headers,
                method="POST",
            )
        else:
            encoded = urllib.parse.urlencode(params).encode("utf-8")
            req = urllib.request.Request(f"{self.api_base}/{method}", data=encoded, method="POST")

        with urllib.request.urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("ok", False):
                print(f"[telegram_api] {method} failed: {payload}", flush=True)
            return payload

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        params = {"timeout": 25}
        if offset is not None:
            params["offset"] = offset
        result = self.request("getUpdates", params)
        return result.get("result", [])

    def send_message(self, chat_id: int, text: str) -> None:
        self.request("sendMessage", {"chat_id": chat_id, "text": text})

    def get_file(self, file_id: str) -> dict[str, Any]:
        return self.request("getFile", {"file_id": file_id}).get("result", {})

    def download_file_bytes(self, file_path: str) -> bytes:
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read()


BOT_TOKEN = os.getenv("BOT_TOKEN") or CONFIG["bot_token"]
bot = TelegramBot(BOT_TOKEN)


def is_admin(chat_id: int) -> bool:
    return chat_id in CONFIG.get("admins", [])


def team_map() -> dict[str, dict[str, Any]]:
    return CONFIG.get("team", {})


def find_target(key: str) -> tuple[str, int]:
    if key in team_map():
        member = team_map()[key]
        return member["name"], int(member["chat_id"])
    if key in CONFIG.get("group_chats", {}):
        return key, int(CONFIG["group_chats"][key])
    raise KeyError(f"Unknown employee or group key: {key}")


def reminder_line(row: sqlite3.Row) -> str:
    remind_at = datetime.fromisoformat(row["remind_at"]).astimezone(TIMEZONE)
    return (
        f"#{row['id']} | {format_datetime(remind_at)} | {row['target_name']} | "
        f"{row['category']} | {row['title']}"
    )


def list_text(rows: list[sqlite3.Row], title: str) -> str:
    if not rows:
        return f"{title}\nПока пусто."
    lines = [title]
    lines.extend(reminder_line(row) for row in rows)
    return "\n".join(lines)


def help_text() -> str:
    return (
        "Бот напоминаний.\n\n"
        "Быстрый режим:\n"
        "- Завтра съемка в 12, монтажер и видеограф\n"
        "- Сегодня в 18:00 публикация, publisher\n"
        "- Какие задачи на сегодня?\n\n"
        "Команды:\n"
        "/myid - показать chat id\n"
        "/team - показать сотрудников\n"
        "/categories - показать категории\n"
        "/users - кто уже написал боту\n"
        "/list - все активные задачи\n"
        "/today - задачи на сегодня\n"
        "/add YYYY-MM-DD HH:MM employee_key category text\n"
        "/broadcast YYYY-MM-DD HH:MM category text"
    )


def categories_text() -> str:
    lines = ["Категории задач:"]
    lines.extend(f"- {item}" for item in CATEGORIES)
    return "\n".join(lines)


def team_text() -> str:
    lines = ["Сотрудники и ключи:"]
    for key, data in team_map().items():
        lines.append(f"- {key}: {data['name']} ({data['chat_id']})")
    if CONFIG.get("group_chats"):
        lines.append("Группы:")
        for key, chat_id in CONFIG["group_chats"].items():
            lines.append(f"- {key}: {chat_id}")
    return "\n".join(lines)


def users_text() -> str:
    users = load_known_users()
    if not users:
        return "Пока никто не написал боту."
    lines = ["Пользователи, которые уже писали боту:"]
    for chat_id, info in users.items():
        username = info.get("username") or "-"
        full_name = info.get("full_name") or "-"
        lines.append(f"- {full_name} | @{username} | {chat_id}")
    return "\n".join(lines)


def handle_add(chat_id: int, text: str, broadcast: bool = False) -> str:
    parts = text.split(maxsplit=5 if not broadcast else 4)
    expected = 6 if not broadcast else 5
    if len(parts) < expected:
        if broadcast:
            return "Формат: /broadcast YYYY-MM-DD HH:MM category text"
        return "Формат: /add YYYY-MM-DD HH:MM employee_key category text"

    if broadcast:
        _, date_str, time_str, category, title = parts
        target_key = "main_team"
    else:
        _, date_str, time_str, target_key, category, title = parts

    if category not in CATEGORIES:
        return "Неизвестная категория.\n" + categories_text()

    remind_at = parse_datetime(date_str, time_str)
    target_name, target_chat_id = find_target(target_key)
    task_id = storage.add_reminder(
        title=title,
        category=category,
        remind_at=remind_at,
        target_key=target_key,
        target_name=target_name,
        target_chat_id=target_chat_id,
        created_by=chat_id,
        is_broadcast=broadcast,
    )
    return (
        f"Задача создана: #{task_id}\n"
        f"Когда: {format_datetime(remind_at)}\n"
        f"Кому: {target_name}\n"
        f"Категория: {category}\n"
        f"Задача: {title}"
    )


def detect_query(text: str) -> str | None:
    lower = normalize_text(text)
    if "сегодня" in lower and "задач" in lower:
        return list_text(storage.list_reminders(only_today=True), "Задачи на сегодня:")
    if "сегодня" in lower and "что" in lower and "у меня" in lower:
        return list_text(storage.list_reminders(only_today=True), "Задачи на сегодня:")
    if "список задач" in lower and "сегодня" in lower:
        return list_text(storage.list_reminders(only_today=True), "Задачи на сегодня:")
    return None


def detect_date(text: str) -> datetime.date:
    lower = normalize_text(text)
    today = now_local().date()

    if "послезавтра" in lower:
        return today + timedelta(days=2)
    if "завтра" in lower:
        return today + timedelta(days=1)
    if "сегодня" in lower:
        return today

    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lower)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return datetime(year, month, day).date()

    dot_match = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](20\d{2}))?\b", lower)
    if dot_match:
        day = int(dot_match.group(1))
        month = int(dot_match.group(2))
        year = int(dot_match.group(3)) if dot_match.group(3) else today.year
        return datetime(year, month, day).date()

    return today


def detect_time(text: str) -> tuple[int, int]:
    lower = normalize_text(text)
    match = re.search(r"\b(?:в\s*)?(\d{1,2})[:.](\d{2})\b", lower)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
    else:
        match = re.search(r"\b(?:в\s*)?(\d{1,2})(?:\s*час(?:а|ов)?)?\b", lower)
        if not match:
            return 9, 0
        hour = int(match.group(1))
        minute = 0

    if any(word in lower for word in ["вечера", "дня", "pm"]) and hour < 12:
        hour += 12
    if "утра" in lower and hour == 12:
        hour = 0
    return hour, minute


def detect_category(text: str) -> str:
    lower = normalize_text(text)
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return category
    return "задача" if "задача" in CATEGORIES else CATEGORIES[0]


def detect_targets(text: str, author_chat_id: int) -> tuple[list[str], bool]:
    lower = normalize_text(text)
    if "всем" in lower or "всей команде" in lower or "в команду" in lower:
        return ["main_team"], True

    targets: list[str] = []
    for key in team_map():
        aliases = set(ROLE_ALIASES.get(key, []))
        aliases.add(key.lower())
        member_name = str(team_map()[key].get("name", "")).lower()
        if member_name:
            aliases.add(member_name)
        if any(alias and alias in lower for alias in aliases):
            targets.append(key)

    if not targets:
        for key, member in team_map().items():
            if int(member["chat_id"]) == author_chat_id:
                return [key], False
        return ["manager"], False

    unique_targets: list[str] = []
    for item in targets:
        if item not in unique_targets:
            unique_targets.append(item)
    return unique_targets, False


def build_title(text: str, category: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\b(сегодня|завтра|послезавтра)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bв\s*\d{1,2}([:.]\d{2})?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{1,2}\s*час(а|ов)?(\s*(утра|дня|вечера))?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(manager|montaj|publisher|videograf|scriptwriter|designer|smm)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(монтажер|монтажёр|мобилограф|видеограф|дизайнер|сценарист|менеджер)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bи\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    if cleaned:
        return cleaned[:180]
    return category.capitalize()


def create_natural_reminders(chat_id: int, text: str) -> str | None:
    lower = normalize_text(text)
    if lower.startswith("/"):
        return None

    query_reply = detect_query(text)
    if query_reply:
        return query_reply

    category = detect_category(text)
    targets, is_broadcast = detect_targets(text, chat_id)
    date_value = detect_date(text)
    hour, minute = detect_time(text)
    remind_at = datetime(
        date_value.year,
        date_value.month,
        date_value.day,
        hour,
        minute,
        tzinfo=TIMEZONE,
    )
    title = build_title(text, category)

    created: list[str] = []
    if is_broadcast:
        target_name, target_chat_id = find_target("main_team")
        task_id = storage.add_reminder(
            title=title,
            category=category,
            remind_at=remind_at,
            target_key="main_team",
            target_name=target_name,
            target_chat_id=target_chat_id,
            created_by=chat_id,
            is_broadcast=True,
        )
        return (
            f"Готово, поставил общее напоминание для команды.\n"
            f"#{task_id} | {format_datetime(remind_at)} | {category} | {title}"
        )

    for target_key in targets:
        target_name, target_chat_id = find_target(target_key)
        task_id = storage.add_reminder(
            title=title,
            category=category,
            remind_at=remind_at,
            target_key=target_key,
            target_name=target_name,
            target_chat_id=target_chat_id,
            created_by=chat_id,
            is_broadcast=False,
        )
        created.append(f"#{task_id} | {target_name} | {format_datetime(remind_at)} | {category}")

    if not created:
        return None

    return "Готово, создал задачи:\n" + "\n".join(created)


def parse_voice_text(voice_text: str, chat_id: int) -> str:
    result = create_natural_reminders(chat_id, voice_text)
    if result:
        return result

    return (
        "Я распознал голосовое, но не смог уверенно собрать задачу.\n"
        "Попробуй так:\n"
        "- Завтра съемка в 12, монтажер и видеограф\n"
        "- Напомни всей команде о съемке завтра в 9\n"
        "- Какие задачи на сегодня?"
    )


def transcribe_voice_message(message: dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return (
            "Голосовые команды пока не включены полностью: не задан OPENAI_API_KEY "
            "в Railway Variables."
        )

    voice = message.get("voice")
    if not voice:
        return "Голосовое сообщение не найдено."

    file_info = bot.get_file(voice["file_id"])
    file_path = file_info.get("file_path")
    if not file_path:
        return "Не удалось получить файл голосового сообщения."

    audio_bytes = bot.download_file_bytes(file_path)
    boundary = "----OpenAIAudioBoundary7MA4YWxkTrZu0gW"
    body = bytearray()

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    body.extend(b"gpt-4o-mini-transcribe\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="file"; filename="voice.ogg"\r\n')
    body.extend(b"Content-Type: audio/ogg\r\n\r\n")
    body.extend(audio_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("text", "").strip() or "Не удалось распознать голосовое."
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        print(f"[voice_transcription] HTTPError: {details}", flush=True)
        return f"Ошибка распознавания голосового через OpenAI. Детали: {details[:500]}"
    except Exception as exc:
        print(f"[voice_transcription] {exc}", flush=True)
        return f"Не удалось обработать голосовое сообщение: {exc}"


def handle_text_message(chat_id: int, text: str) -> None:
    if text == "/start":
        bot.send_message(chat_id, "Бот напоминаний подключен.\n" + help_text())
        return
    if text == "/help":
        bot.send_message(chat_id, help_text())
        return
    if text == "/myid":
        bot.send_message(chat_id, f"Ваш chat id: {chat_id}")
        return
    if text == "/team":
        bot.send_message(chat_id, team_text())
        return
    if text == "/categories":
        bot.send_message(chat_id, categories_text())
        return
    if text == "/users":
        bot.send_message(chat_id, users_text())
        return

    if text == "/add":
        bot.send_message(
            chat_id,
            "Можно не писать /add.\n"
            "Просто напиши обычным сообщением:\n"
            "- Завтра съемка в 12, монтажер и видеограф\n"
            "- Сегодня в 18:00 публикация, publisher\n\n"
            "Если хочешь старый формат:\n"
            "/add YYYY-MM-DD HH:MM employee_key category text",
        )
        return
    if text == "/broadcast":
        bot.send_message(
            chat_id,
            "Можно написать проще:\n"
            "Напомни всей команде о съемке завтра в 9\n\n"
            "Или старым форматом:\n"
            "/broadcast YYYY-MM-DD HH:MM category text",
        )
        return
    if text == "/list":
        bot.send_message(chat_id, list_text(storage.list_reminders(), "Активные задачи:"))
        return
    if text == "/today":
        bot.send_message(chat_id, list_text(storage.list_reminders(only_today=True), "Задачи на сегодня:"))
        return
    if text == "/done":
        bot.send_message(chat_id, "Формат: /done TASK_ID\nПример: /done 1")
        return
    if text == "/delete":
        bot.send_message(chat_id, "Формат: /delete TASK_ID\nПример: /delete 1")
        return

    if not is_admin(chat_id):
        bot.send_message(chat_id, "У вас нет прав для управления задачами.")
        return

    try:
        if text.startswith("/add "):
            bot.send_message(chat_id, handle_add(chat_id, text, broadcast=False))
        elif text.startswith("/broadcast "):
            bot.send_message(chat_id, handle_add(chat_id, text, broadcast=True))
        elif text.startswith("/done "):
            task_id = int(text.split(maxsplit=1)[1])
            ok = storage.mark_done(task_id)
            bot.send_message(chat_id, "Задача отмечена выполненной." if ok else "Задача не найдена.")
        elif text.startswith("/delete "):
            task_id = int(text.split(maxsplit=1)[1])
            ok = storage.delete(task_id)
            bot.send_message(chat_id, "Задача удалена." if ok else "Задача не найдена.")
        else:
            natural_result = create_natural_reminders(chat_id, text)
            if natural_result:
                bot.send_message(chat_id, natural_result)
            else:
                bot.send_message(chat_id, human_help_text())
    except Exception as exc:
        bot.send_message(chat_id, f"Ошибка: {exc}")


def handle_message(message: dict[str, Any]) -> None:
    chat_id = int(message["chat"]["id"])
    username = message["from"].get("username")

    users = load_known_users()
    users[str(chat_id)] = {
        "username": username,
        "full_name": " ".join(
            part
            for part in [message["from"].get("first_name"), message["from"].get("last_name")]
            if part
        ).strip(),
    }
    save_known_users(users)

    if message.get("voice"):
        print(f"[update] chat_id={chat_id} username={username} voice_message", flush=True)
        transcript = transcribe_voice_message(message)
        bot.send_message(chat_id, f"Распознанный текст:\n{transcript}")
        if transcript.startswith("Ошибка") or transcript.startswith("Не удалось") or transcript.startswith("Голосовые"):
            return
        bot.send_message(chat_id, parse_voice_text(transcript, chat_id))
        return

    text = message.get("text", "").strip()
    if not text:
        return

    print(f"[update] chat_id={chat_id} username={username} text={text}", flush=True)
    handle_text_message(chat_id, text)


def reminder_worker() -> None:
    while True:
        try:
            for row in storage.due_reminders():
                remind_at = datetime.fromisoformat(row["remind_at"]).astimezone(TIMEZONE)
                text = (
                    "Напоминание по задаче\n"
                    f"ID: {row['id']}\n"
                    f"Когда: {format_datetime(remind_at)}\n"
                    f"Категория: {row['category']}\n"
                    f"Задача: {row['title']}"
                )
                bot.send_message(int(row["target_chat_id"]), text)
                for admin_id in CONFIG.get("admins", []):
                    if int(admin_id) != int(row["target_chat_id"]):
                        bot.send_message(
                            int(admin_id),
                            f"Задача отправлена сотруднику {row['target_name']}\n{text}",
                        )
                storage.mark_sent(int(row["id"]))
        except Exception as exc:
            print(f"[reminder_worker] {exc}", flush=True)
        time.sleep(int(CONFIG.get("reminder_check_interval_seconds", 20)))


def main() -> None:
    print("Telegram Reminder Bot started", flush=True)
    print(f"Timezone: {CONFIG.get('timezone', 'Asia/Tashkent')}", flush=True)

    threading.Thread(target=reminder_worker, daemon=True).start()

    offset = None
    while True:
        try:
            updates = bot.get_updates(offset=offset)
            if updates:
                print(f"[poll] received {len(updates)} updates", flush=True)
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[main_loop] {exc}", flush=True)
            time.sleep(5)
        time.sleep(float(CONFIG.get("poll_interval_seconds", 2)))


if __name__ == "__main__":
    main()
