import base64

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.files.base import ContentFile
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
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
        context = self.context.get('request')
        if context is None:
            return False
        user = context.user
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


class RecipeReadSerializer(serializers.ModelSerializer):
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


class IngredientAmountSerializer(serializers.ModelSerializer):

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all(),
                                            many=False, allow_empty=False)
    amount = serializers.IntegerField()

    class Meta:
        model = Ingredient
        fields = ('id', 'amount')

    def validate_amount(self, amount):
        if amount < 1:
            raise serializers.ValidationError(
                'Количество ингредиента должно быть не меньше 1')
        return amount


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    ingredients = IngredientAmountSerializer(many=True, allow_empty=False)
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(),
                                              many=True, allow_empty=False)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image',
                  'name', 'text', 'cooking_time')

    def to_representation(self, instance):
        """Формирование данных для вывода."""
        serializer = RecipeReadSerializer(instance, many=False)
        return serializer.data

    def create(self, validated_data):
        """Создание рецепта и привязка tags и ingredients к recipe."""
        ingredients = validated_data.pop('ingredients')
        tags_slug = validated_data.pop('tags')

        recipe = Recipe.objects.create(
            **validated_data, author=self.context.get('request').user)
        self.ingredient_recipe_bulk_create(recipe, ingredients)
        self.tag_recipe_bulk_create(recipe, tags_slug)

        return recipe

    def update(self, recipe, validated_data):
        """Обновление рецепта, с учетом обновлений в связанных таблицах."""
        try:
            ingredients = validated_data.pop('ingredients')
        except KeyError:
            raise serializers.ValidationError('Нет поля ingredients!')

        try:
            tags_slug = validated_data.pop('tags')
        except KeyError:
            raise serializers.ValidationError('Нет поля tags!')

        Recipe.objects.filter(pk=recipe.pk).update(**validated_data)

        recipe.ingredient_recipe.all().delete()
        self.ingredient_recipe_bulk_create(recipe, ingredients)

        recipe.tag_recipe.all().delete()
        self.tag_recipe_bulk_create(recipe, tags_slug)

        return recipe

    def validate_ingredients(self, ingredients):
        """Проверка введенных ингредиентов на повторяемость.

        Параметр UniqueValidator для поля сериализатора неприменим,
        поскольку записи модели Ingredient при создании рецепта не создаются.
        """
        ingredient_names = [ingredient.get('id') for ingredient in ingredients]

        if len(set(ingredient_names)) < len(ingredient_names):
            raise serializers.ValidationError('Ингредиенты повторяются!')

        return ingredients

    def validate_tags(self, tags_slug):
        """Проверка введенных тэгов на повторяемость.

        Параметр UniqueValidator для поля сериализатора неприменим,
        поскольку записи модели Tag при создании рецепта не создаются.
        """
        if len(tags_slug) != len(set(tags_slug)):
            raise serializers.ValidationError('Тэги повторяются!')

        return tags_slug

    def ingredient_recipe_bulk_create(self, recipe, ingredients):
        """Создание записей в таблице IngredientRecipe."""
        IngredientRecipe.objects.bulk_create(
            [
                IngredientRecipe(
                    ingredient=get_object_or_404(
                        Ingredient, name=ingredient.get('id')
                    ),
                    recipe=recipe,
                    amount=ingredient.get('amount')
                )
                for ingredient in ingredients
            ]
        )

    def tag_recipe_bulk_create(self, recipe, tags_slug):
        """Создание записей в таблице TagRecipe."""
        TagRecipe.objects.bulk_create(
            [
                TagRecipe(
                    tag=get_object_or_404(Tag, slug=tag_slug),
                    recipe=recipe
                )
                for tag_slug in tags_slug
            ]
        )


class RecipeShortenInfoSerializer(RecipeReadSerializer):
    """Сериализатор вывода сокращенной информации о рецепте."""

    class Meta(RecipeReadSerializer.Meta):
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
