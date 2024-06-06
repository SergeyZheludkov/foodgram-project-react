from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()
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
        default_related_name = 'tags'

    def __str__(self):
        return self.slug


class Ingredient(models.Model):
    """Модель для ингредиента."""

    name = models.CharField('Название', max_length=128)
    measurement_unit = models.CharField('Единица измерения', max_length=128)

    class Meta:
        verbose_name = 'ингредиент'
        verbose_name_plural = 'Ингредиенты'
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'measurement_unit'),
                name='unique_key_ingredient'
            )
        ]
        ordering = ('name',)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """Модель для рецепта."""

    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               verbose_name='Автор')
    ingredients = models.ManyToManyField(
        Ingredient, verbose_name='Ингредиенты', through='IngredientRecipe'
    )
    tags = models.ManyToManyField(Tag, verbose_name='тэги',
                                  through='TagRecipe')
    image = models.ImageField('Картинка', upload_to='recipes/images/')
    name = models.CharField('Название', max_length=200, unique=True)
    text = models.TextField('Описание')
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления, мин', validators=[MinValueValidator(1)])
    pub_date = models.DateTimeField(auto_now_add=True,
                                    verbose_name='Дата публикации')

    class Meta:
        verbose_name = 'рецепт'
        verbose_name_plural = 'Рецепты'
        default_related_name = 'recipes'
        ordering = ('-pub_date',)

    def __str__(self):
        return self.name


class IngredientRecipe(models.Model):
    """Модель для описания ингредиентов в рецепте."""

    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE,
                                   verbose_name='Ингредиент', null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               verbose_name='Рецепт', null=True)
    amount = models.PositiveSmallIntegerField(
        verbose_name='Количество', validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = 'ингредиенты рецепта'
        verbose_name_plural = 'Ингредиенты рецептов'
        constraints = [
            models.UniqueConstraint(
                fields=('recipe', 'ingredient'),
                name='unique_key_recipe_ingredient'
            )
        ]
        default_related_name = 'ingredient_recipe'

    def __str__(self):
        return f'{self.ingredient} - {self.recipe}'


class TagRecipe(models.Model):
    """Модель для описания тэгов в рецепте."""

    tag = models.ForeignKey(Tag, on_delete=models.CASCADE,
                            verbose_name='Тэг', null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               verbose_name='Рецепт', null=True)

    class Meta:
        verbose_name = 'тэги рецепта'
        verbose_name_plural = 'Тэги рецептов'
        constraints = [
            models.UniqueConstraint(
                fields=('recipe', 'tag'), name='unique_key_recipe_tag'
            )
        ]
        default_related_name = 'tag_recipe'

    def __str__(self):
        return f'{self.tag} - {self.recipe}'


class UserRecipeModel(models.Model):
    """Абстрактная модель для моделей избранного и списка покупок."""

    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             verbose_name='Пользователь')
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE,
                               verbose_name='Рецепт в избранном')

    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.user.username} - {self.recipe.name}'


class Favorite(UserRecipeModel):
    """Модель избранного."""

    class Meta:
        verbose_name = 'избранное'
        verbose_name_plural = 'Избранное'
        default_related_name = 'favorites'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='unique_key_user_recipe_favorite'
            )
        ]


class ShoppingCart(UserRecipeModel):
    """Модель списка покупок."""

    class Meta:
        verbose_name = 'рецепт в списке'
        verbose_name_plural = 'Список покупок'
        default_related_name = 'carts'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='unique_key_user_recipe_shopcart'
            )
        ]
