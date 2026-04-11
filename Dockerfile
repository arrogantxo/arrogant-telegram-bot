FROM python:3.14-slim

WORKDIR /app

COPY bot.py ./
COPY config.example.json ./config.json

CMD ["python", "bot.py"]
