FROM python:3.14-slim

WORKDIR /app

COPY bot.py config.json ./

CMD ["python", "-u", "bot.py"]
