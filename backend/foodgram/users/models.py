from django.contrib.auth.models import AbstractUser
from django.db import models

MAX_FIELD_LENGTH = 150


class MyUser(AbstractUser):
    """Переопределение стандартного пользователя."""

    first_name = models.CharField('Имя', max_length=MAX_FIELD_LENGTH)
    last_name = models.CharField('Фамилия', max_length=MAX_FIELD_LENGTH)
    email = models.EmailField('Почта', unique=True)
    # по умолчанию для EmailField max_length=254


class Follow(models.Model):
    """Модель подписчиков."""

    user = models.ForeignKey(
        MyUser, on_delete=models.CASCADE, related_name='subscriber',
        verbose_name='Подписчик')
    following = models.ForeignKey(
        MyUser, on_delete=models.CASCADE, related_name='following',
        verbose_name='Подписан на')

    class Meta:
        verbose_name = 'подписчик'
        verbose_name_plural = 'Подписчики'

    def __str__(self):
        return self.user.username
