# Deploy на Railway

Эта инструкция нужна, чтобы быстро перезалить бот и не забыть важные настройки.

## Файлы для GitHub

Загрузить:

- `bot.py`
- `Dockerfile`
- `README.md`
- `DEPLOY.md`
- `ROLES.md`
- `config.example.json`
- `.env.example`
- `.gitignore`

Не загружать:

- `config.json`
- `bot_data.db`
- `known_users.json`
- `custom_roles.json`
- `__pycache__`

## Dockerfile

Рабочий `Dockerfile`:

```dockerfile
FROM python:3.14-slim

WORKDIR /app

COPY bot.py ./
COPY config.example.json ./config.json

CMD ["python", "-u", "bot.py"]
```

## Railway Variables

```text
BOT_TOKEN=...
BOT_DB_PATH=/data/bot_data.db
BOT_USERS_PATH=/data/known_users.json
BOT_CUSTOM_ROLES_PATH=/data/custom_roles.json
OPENAI_API_KEY=sk-...
```

Что это значит:

- `BOT_TOKEN` — токен Telegram-бота
- `BOT_DB_PATH` — база задач
- `BOT_USERS_PATH` — файл известных пользователей
- `BOT_CUSTOM_ROLES_PATH` — роли, добавленные через `/addrole`
- `OPENAI_API_KEY` — нужен для голосовых сообщений

## Volume

Создай Railway Volume и примонтируй его к:

```text
/data
```

В нём будут храниться:

- `bot_data.db`
- `known_users.json`
- `custom_roles.json`

## После деплоя

Сделай проверку:

1. `/start`
2. `/myid`
3. `/help`
4. `Какие задачи на сегодня?`
5. `Завтра съемка в 12, монтажер и видеограф`
6. `/roles`

## Если хочешь добавлять роли через бота

Пример:

```text
/addrole assistant3 123456789 Саид | саид,ассистент,said
```

Потом:

```text
/roles
```

И можно использовать роль в обычных сообщениях:

```text
Завтра съемка в 12, Саид
```

## Если что-то не работает

Проверь по порядку:

1. Railway сервис `Active`
2. в логах есть `Telegram Reminder Bot started`
3. токен актуальный
4. volume подключен к `/data`
5. сотрудник сначала написал `/start`
6. для голоса активен OpenAI billing
