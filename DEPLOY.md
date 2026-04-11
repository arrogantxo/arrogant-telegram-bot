# Deploy на Railway

Этот файл описывает, как запустить Telegram Reminder Bot на Railway так, чтобы он работал 24/7 без компьютера.

## Что уже поддерживает бот

- текстовые команды
- напоминания сотрудникам
- напоминания в общий чат
- SQLite база задач
- хранение известных пользователей
- голосовые сообщения через OpenAI API

## Что нужно для работы

1. Telegram-бот из `@BotFather`
2. Railway проект
3. Railway Variables
4. Railway Volume
5. OpenAI API key для голосовых команд

## Важные секреты

Никогда не храни в GitHub:

- реальный `BOT_TOKEN`
- реальный `OPENAI_API_KEY`

Если токен Telegram уже где-то публиковался:

1. открой `@BotFather`
2. выбери бота
3. перевыпусти токен
4. используй только новый токен

## Railway Variables

В Railway Variables должны быть:

```text
BOT_TOKEN=...
BOT_DB_PATH=/data/bot_data.db
BOT_USERS_PATH=/data/known_users.json
OPENAI_API_KEY=sk-...
```

## Что означает каждая переменная

- `BOT_TOKEN` — токен Telegram-бота
- `BOT_DB_PATH` — путь к базе SQLite
- `BOT_USERS_PATH` — путь к файлу известных пользователей
- `OPENAI_API_KEY` — ключ OpenAI для распознавания голосовых

## Volume

Создай и подключи Railway Volume.

Mount path:

```text
/data
```

Это нужно для:

- `bot_data.db`
- `known_users.json`

## GitHub

В репозитории должны быть только безопасные файлы:

- `bot.py`
- `Dockerfile`
- `README.md`
- `DEPLOY.md`
- `config.example.json`
- `.env.example`
- `.gitignore`

Не загружай в GitHub:

- `config.json`
- `bot_data.db`
- `known_users.json`

## Dockerfile

Рабочий `Dockerfile` должен быть таким:

```dockerfile
FROM python:3.14-slim

WORKDIR /app

COPY bot.py ./
COPY config.example.json ./config.json

CMD ["python", "-u", "bot.py"]
```

## Порядок запуска на Railway

1. Подключи GitHub-репозиторий к Railway
2. Убедись, что Railway использует правильный `Dockerfile`
3. Добавь все Railway Variables
4. Подключи Volume на `/data`
5. Нажми `Deploy`

## Как понять, что всё работает

В логах Railway должно быть примерно:

```text
Telegram Reminder Bot started
Timezone: Asia/Tashkent
```

После отправки `/start` в Telegram должно появиться что-то вроде:

```text
[poll] received 1 updates
[update] chat_id=... username=... text=/start
```

## Что сделать после первого запуска

1. Напиши боту `/start`
2. Отправь `/myid`
3. Отправь `/help`
4. Отправь `/categories`

Потом попроси сотрудников тоже написать боту `/start`.

## Голосовые команды

Чтобы голосовые команды работали:

1. добавь `OPENAI_API_KEY` в Railway Variables
2. сделай `Redeploy`

После этого бот сможет:

- распознавать голос в текст
- отвечать на голосовые команды
- помогать с задачами через голос

## Что можно говорить голосом

Примеры:

- "Какие у меня задачи на сегодня?"
- "Завтра в 10 утра напомни монтажеру смонтировать reels"
- "Напомни всей команде о съемке завтра в 9 утра"

## Если бот не отвечает

Проверяй по порядку:

1. сервис Railway должен быть `Active`
2. в логах не должно быть `HTTP Error 404`
3. токен должен быть реальным и актуальным
4. `BOT_TOKEN` должен быть в Railway Variables
5. volume должен быть подключен в `/data`
6. `OPENAI_API_KEY` должен быть задан для голосовых команд

## Текущая логика проекта

Сейчас бот уже подходит для:

- `Озбегим молл`
- напоминаний по съемкам
- напоминаний по сценариям
- задач по монтажу
- задач по публикации
- работы команды через текст и голос
