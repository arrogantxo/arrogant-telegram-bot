# Deploy на Railway

Этот файл нужен, чтобы быстро развернуть бота заново без лишних догадок.

## Что нужно перед запуском

Нужно подготовить:

1. Telegram-бота через `@BotFather`
2. GitHub-репозиторий с файлами бота
3. Railway-проект
4. Railway Volume
5. OpenAI API key, если хочешь голосовые команды

## Какие файлы должны быть в GitHub

Нужно загрузить:

- `bot.py`
- `Dockerfile`
- `README.md`
- `DEPLOY.md`
- `ROLES.md`
- `config.example.json`
- `.env.example`
- `.gitignore`

Нельзя загружать:

- `config.json`
- `bot_data.db`
- `known_users.json`
- `__pycache__`

## Dockerfile

Рабочий `Dockerfile` должен быть таким:

```dockerfile
FROM python:3.14-slim

WORKDIR /app

COPY bot.py ./
COPY config.example.json ./config.json

CMD ["python", "-u", "bot.py"]
```

## Railway Variables

Добавь в Railway:

```text
BOT_TOKEN=...
BOT_DB_PATH=/data/bot_data.db
BOT_USERS_PATH=/data/known_users.json
OPENAI_API_KEY=sk-...
```

Что значит каждая переменная:

- `BOT_TOKEN` — токен Telegram-бота
- `BOT_DB_PATH` — путь к SQLite базе
- `BOT_USERS_PATH` — путь к файлу известных пользователей
- `OPENAI_API_KEY` — ключ OpenAI для голосовых сообщений

## Railway Volume

Создай `Volume` и примонтируй его в:

```text
/data
```

Он нужен для:

- `bot_data.db`
- `known_users.json`

## Порядок деплоя

1. Загрузи все рабочие файлы в GitHub
2. Подключи GitHub-репозиторий к Railway
3. Проверь `Dockerfile`
4. Добавь Railway Variables
5. Подключи Volume на `/data`
6. Нажми `Deploy`

## Что должно быть в логах

В Railway logs должно быть примерно:

```text
Telegram Reminder Bot started
Timezone: Asia/Tashkent
```

Если после `/start` всё в порядке, в логах будет что-то вроде:

```text
[poll] received 1 updates
[update] chat_id=... username=... text=/start
```

## Первый запуск после деплоя

Сделай так:

1. открой бота в Telegram
2. отправь `/start`
3. отправь `/myid`
4. отправь `/help`
5. проверь фразу:

```text
Какие задачи на сегодня?
```

6. проверь фразу:

```text
Завтра съемка в 12, монтажер и видеограф
```

## Если голосовые не работают

Проверь:

1. есть ли `OPENAI_API_KEY`
2. есть ли активный billing у OpenAI API
3. не закончилась ли квота

Если квота закончилась, бот будет работать текстом, но голосовые не распознаются.

## Если хочешь добавить сотрудников

См. файл [ROLES.md](/D:/SMM%20Arrogant/%D0%9E%D0%B7%D0%B1%D0%B5%D0%B3%D0%B8%D0%BC%20%D0%BC%D0%BE%D0%BB%D0%BB/04_%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B/telegram_reminder_bot/ROLES.md).
