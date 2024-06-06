FROM python:3.9
WORKDIR /app
RUN pip install gunicorn==20.1.0
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .

# команды для миграции, загрузки тестовых данных (включая, суперюзера),
# сборки статики и запуска сервера gunicorn
ENTRYPOINT ["sh", "app/entrypoint.sh"]