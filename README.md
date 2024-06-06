# Проект «Фудграм»

![workflow status](https://github.com/SergeyZheludkov/foodgram-project-react/actions/workflows/main.yml/badge.svg)

## Описание

Дипломный проект "Яндекс.Практикум" по курсу "Python-разработчик буткемп"

Развернут на домене: https://zhsv-foodgram.crabdance.com/

Данные для входа администратора: 
 - логин: zhsv2@yandex.ru
 - пароль: admin

Функционал:
 - сайт, на котором пользователи могут публиковать рецепты, добавлять чужие рецепты в избранное и подписываться на публикации других авторов. Пользователям сайта также доступен сервис «Список покупок».

## Использованные технологии

Django 3.2 - базовый фреймворк проекта
https://docs.djangoproject.com/en/  3.2/ 

Django REST Framework 3.12 - библиотека Django для разработки REST API
https://www.django-rest-framework.org/ 

## Как запустить проект:

Клонировать репозиторий и перейти в него в командной строке:

```
git clone git@github.com:SergeyZheludkov/foodgram-project-react.git 
```

```
cd foodgram-project-react
```

Cоздать и активировать виртуальное окружение:

```
python -m venv venv
```

```
source venv/Scripts/activate
```

Установить пакетный менеджер и зависимости из файла requirements.txt:

```
python -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

Выполнить миграции:

```
python manage.py migrate
```

Запустить проект:

```
python manage.py runserver
```

Загрузить тестовые данные:

```
python manage.py loaddata db.json
```
Список ингредиентов входит в тестовые данные, но может быть загружен отдельно:

```
python manage.py load_ingredients
```

## Регистрация пользователей

Пользователь отправляет POST-запрос с параметрами:
- email
- username
- first_name
- last_name
- password
на эндпоинт: /api/users/

Пользователь отправляет POST-запрос с параметрами:
- email
- username
на эндпоинт: /api/v1/auth/token/ 
и получает токен, который ему необходимо будет отправлять вместе с каждым запросом.

## Примеры запросов к API

### Пользователи

Получение списка всех пользователей - GET запрос на эндпоинт: /api/users/

Получение информации о конкретном пользователе - GET запрос на эндпоинт:  /api/users/{id}/

Смена пароля - POST запрос с параметрами current_password, new_password на эндпойнт: /api/users/set_password/

### Тэги

Получение списка тэгов - GET запрос на эндпоинт: /api/tags/

Получение информации о конкретном тэге - GET запрос на эндпоинт:  /api/tags/{id}/

### Рецепты

Получение списка рецептов - GET запрос на эндпоинт: /api/recipes/

Получение информации о конкретном рецепте - GET запрос на эндпоинт:  /api/recipes/{id}/

Публикация рецепта (только для авторизованных пользователей) - POST запрос на эндпоинт: /api/recipes/

Обновление и удаление рецепта (только для автора рецепта) - PATCH и DELETE запрос на эндпойт: /api/recipes/{id}/

### Список покупок (доступно только авторизованным пользователям)

Скачивание списка покупок - GET запрос на эндпоинт: /api/recipes/download_shopping_cart/

Добавление и удаление рецепта с {id} в список покупок - POST и DELETE запрос на эндпойнт: /api/recipes/{id}/shopping_cart/

### Избранное (доступно только авторизованным пользователям)

Добавление и удаление рецепта с {id} в избранное - POST и DELETE запрос на эндпойнт: /api/recipes/{id}/favorite/

### Подписки

Получение списка подписок пользователя - GET запрос на эндпойнт: /api/users/subscriptions/

Подписаться/отписаться на пользователя с {id} - POST/DELETE запрос на эндпойнт: /api/users/{id}/subscribe/

### Ингредиенты

Получение списка ингредиентов - GET запрос на эндпоинт: /api/ingredients/

Получение информации о конкретном ингредиенте - GET запрос на эндпоинт:  /api/ingredients/{id}/

## Автор

Сергей Желудков
(Github: [@SergeyZheludkov](https://github.com/SergeyZheludkov/))
