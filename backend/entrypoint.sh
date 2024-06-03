python manage.py makemigrations
python manage.py migrate --no-input
python manage.py loaddata db.json
python manage.py collectstatic --no-input
cp -r /app/collected_static/. /backend_static/static/

gunicorn --bind 0.0.0.0:8000 foodgram.wsgi