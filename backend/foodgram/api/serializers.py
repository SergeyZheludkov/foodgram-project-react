import base64

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.files.base import ContentFile
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.validators import UniqueTogetherValidator

from recipes.models import (Favorite, Ingredient, Recipe, ShoppingCart,
                            Tag, TagRecipe, IngredientRecipe)

User = get_user_model()


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = '__all__'


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор при регистрации нового пользователя."""

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name')

    def validate(self, data):
        """Проверка наличия пароля."""
        if not self.initial_data.get('password'):
            raise serializers.ValidationError('Не введен пароль!')
        return data


class CustomUserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed')

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        following = get_object_or_404(User, pk=obj.id)
        return following.following.filter(user_id=user.pk).exists()


class UserSubscribeSerializer(CustomUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count',
                                             read_only=True)

    class Meta(CustomUserSerializer.Meta):
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes_count', 'recipes')

    def get_recipes(self, user):
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit')

        if recipes_limit:
            recipes_limit = self.validate_recipes_limit(recipes_limit)
        return user.recipes.values('id', 'image', 'name',
                                   'cooking_time')[:recipes_limit]

    def validate_recipes_limit(self, recipe_limit):
        try:
            recipe_limit = int(recipe_limit)
        except ValueError:
            raise serializers.ValidationError(
                'Значение recipes_limit должно быть числом!'
            )
        return recipe_limit


class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


# class TagFieldInRecipe(serializers.Field):
#     def get_attribute(self, recipe):
#         return recipe

#     def to_representation(self, recipe):
#         tags_list = recipe.tag_recipe.all().values_list('tag')
#         tags_obj = Tag.objects.filter(pk__in=tags_list)
#         return TagSerializer(tags_obj, many=True).data

#     def to_internal_value(self, tags_list):
#         return tags_list


class RecipeSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True, many=False)
    ingredients = serializers.SerializerMethodField()
    tags = TagSerializer(read_only=True, many=True)
    image = Base64ImageField()
    is_favorited = serializers.BooleanField(read_only=True, default=False)
    is_in_shopping_cart = serializers.BooleanField(read_only=True,
                                                   default=False)

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'tags', 'image', 'name',
                  'text', 'cooking_time', 'is_favorited',
                  'is_in_shopping_cart')

    def get_ingredients(self, recipe):
        return recipe.ingredients.values('id', 'name', 'measurement_unit',
                                         amount=F('ingredient_recipe__amount'))

    def create(self, validated_data):
        """Валидация и привязка tags и ingredients к recipe в ручном режиме."""
        ingredients = self.validate_ingredients()
        tags_id = self.validate_tags()

        recipe = Recipe.objects.create(
            **validated_data, author=self.context.get('request').user
        )
        self.ingredient_recipe_bulk_create(recipe, ingredients)
        self.tag_recipe_bulk_create(recipe, tags_id)

        return recipe

    def update(self, recipe, validated_data):
        """Обновление рецепта, с учетом обновлений в связанных таблицах."""
        ingredients = self.validate_ingredients()
        recipe.ingredient_recipe.all().delete()
        self.ingredient_recipe_bulk_create(recipe, ingredients)

        tags_id = self.validate_tags()
        recipe.tag_recipe.all().delete()
        self.tag_recipe_bulk_create(recipe, tags_id)

        return super().update(recipe, validated_data)

    def validate_ingredients(self):
        ingredients = self.initial_data.get('ingredients')

        if ingredients is None or ingredients == []:
            raise serializers.ValidationError('Нет данных об ингредиентах')

        ingredient_ids = []
        for ingredient in ingredients:
            ingredient_ids.append(ingredient['id'])
            if ingredient['amount'] < 1:
                raise serializers.ValidationError(
                    'Количество ингредиента должно быть не меньше 1')

        ingredient_ids_quantity = len(ingredient_ids)

        if len(set(ingredient_ids)) < ingredient_ids_quantity:
            raise serializers.ValidationError('Ингредиенты повторяются!')

        ingredients_in_db = Ingredient.objects.in_bulk(id_list=ingredient_ids,
                                                       field_name='pk')
        if len(ingredients_in_db) < ingredient_ids_quantity:
            raise serializers.ValidationError('Проверьте id ингредиентов!')

        return ingredients

    def ingredient_recipe_bulk_create(self, recipe, ingredients):
        """Создание записей в таблице IngredientRecipe."""
        IngredientRecipe.objects.bulk_create(
            [
                IngredientRecipe(
                    ingredient=get_object_or_404(
                        Ingredient, pk=ingredient.get('id')
                    ),
                    recipe=recipe,
                    amount=ingredient.get('amount')
                )
                for ingredient in ingredients
            ]
        )

    def validate_tags(self):

        tags_id = self.initial_data.get('tags')

        if tags_id is None or tags_id == []:
            raise serializers.ValidationError('Нет данных о тэге')

        if len(tags_id) != len(set(tags_id)):
            raise serializers.ValidationError('Тэги повторяются!')

        for tag_id in tags_id:
            if not Tag.objects.filter(id=tag_id).exists():
                raise serializers.ValidationError('Проверьте id тэгов!')

        return tags_id

    def tag_recipe_bulk_create(self, recipe, tags_id):
        """Создание записей в таблице TagRecipe."""
        TagRecipe.objects.bulk_create(
            [
                TagRecipe(
                    tag=get_object_or_404(Tag, pk=tag_id),
                    recipe=recipe
                )
                for tag_id in tags_id
            ]
        )


class RecipeShortenInfoSerializer(RecipeSerializer):
    """Сериализатор вывода сокращенной информации о рецепте."""

    class Meta(RecipeSerializer.Meta):
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteShoppingCartAddSerializer(serializers.ModelSerializer):
    """Общее в сериализаторах для добавления в избранное и в список покупок."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        fields = ('user', 'recipe')


class FavoriteAddSerializer(FavoriteShoppingCartAddSerializer):
    """Сериализатор для добавления в избранное."""

    class Meta(FavoriteShoppingCartAddSerializer.Meta):
        model = Favorite
        validators = [
            UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже отмечен!'
            )
        ]


class ShoppingCartAddSerializer(FavoriteShoppingCartAddSerializer):
    """Сериализатор для добавления в список покупок."""

    class Meta(FavoriteShoppingCartAddSerializer.Meta):
        model = ShoppingCart
        validators = [
            UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже отмечен!'
            )
        ]


class CustomAuthTokenSerializer(serializers.Serializer):
    """Сериализатор запроса токена."""

    email = serializers.CharField(label='Email', write_only=True)
    password = serializers.CharField(
        label='Password', style={'input_type': 'password'},
        trim_whitespace=False, write_only=True
    )
    token = serializers.CharField(label='auth-token', read_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            try:
                user = get_object_or_404(User, email=email)
            except Http404 as exc:
                raise serializers.ValidationError(
                    'Невозможно залогиниться по полученным данным.') from exc
        else:
            raise serializers.ValidationError(
                'Запрос должен включать "email" и "password".')

        if not check_password(password, user.password):
            raise serializers.ValidationError('Неверный пароль!')

        data['user'] = user
        return data
