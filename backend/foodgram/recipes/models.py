from django.db import models

MAX_LENGTH_HEX_COLOR = 7


class Tag(models.Model):
    """Модель для тега."""

    name = models.CharField('Название', max_length=128, unique=True)
    color = models.CharField('Цвет', max_length=MAX_LENGTH_HEX_COLOR,
                             unique=True)
    slug = models.SlugField('Слаг', unique=True)

    class Meta:
        verbose_name = 'тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """Модель для ингредиента."""

    name = models.CharField('Название', max_length=128, unique=True)
    measurement_unit = models.CharField('Единица измерения', max_length=128,
                                        unique=True)

    class Meta:
        verbose_name = 'ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return self.name
