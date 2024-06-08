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
from users.models import Follow

User = get_user_model()


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = '__all__'


class APIUserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор при регистрации нового пользователя."""

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name')

    def validate(self, data):
        """Проверка наличия пароля."""
        if not self.initial_data.get('password'):
            raise serializers.ValidationError('Не введен пароль!')
        return data


class ResetPasswordeSerializer(serializers.Serializer):
    """Сериализатор при замене пароля."""

    current_password = serializers.CharField(required=True, allow_blank=False)
    new_password = serializers.CharField(required=True, allow_blank=False)

    def validate_current_password(self, current_password):
        if not check_password(current_password,
                              self.context.get('request').user.password):
            raise serializers.ValidationError('Неверный текущий пароль!')
        return current_password


class APIUserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed')

    def get_is_subscribed(self, user_obj):
        """Уточнение подписан ли автор запроса на конкретного пользователя."""
        request = self.context.get('request')
        if request is None:
            return False
        user = request.user
        # у анонимов и на анонимов нет возможности подписываться
        if user.is_anonymous or user_obj.is_anonymous:
            return False

        return user.subscriber.filter(following=user_obj).exists()


class UserSubscribeSerializer(APIUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(source='recipes.count',
                                             read_only=True)

    class Meta(APIUserSerializer.Meta):
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes_count', 'recipes')

    def get_recipes(self, user):
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit')

        if recipes_limit:
            recipes_limit = self.validate_recipes_limit(recipes_limit)
        recipes = user.recipes.all()[:recipes_limit]
        serializer = RecipeShortenInfoSerializer(recipes, many=True)
        return serializer.data

    def validate_recipes_limit(self, recipe_limit):
        try:
            recipe_limit = int(recipe_limit)
        except ValueError as exc:
            raise serializers.ValidationError(
                'Значение recipes_limit должно быть числом!'
            ) from exc
        return recipe_limit


class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для вывода полной информации о рецепте."""

    author = APIUserSerializer()
    ingredients = serializers.SerializerMethodField()
    tags = TagSerializer(many=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'tags', 'image', 'name',
                  'text', 'cooking_time', 'is_favorited',
                  'is_in_shopping_cart')

    def get_ingredients(self, recipe):
        return recipe.ingredients.values('id', 'name', 'measurement_unit',
                                         amount=F('ingredient_recipe__amount'))

    def get_is_favorited(self, recipe):
        return self.get_additional_fields(recipe.favorites)

    def get_is_in_shopping_cart(self, recipe):
        return self.get_additional_fields(recipe.carts)

    def get_additional_fields(self, recipe_related_manager_obj):
        request = self.context.get('request')
        if request is None:
            return False

        user = request.user
        if user.is_anonymous:
            return False

        return user.pk in list(
            recipe_related_manager_obj.values_list('user__pk', flat=True)
        )


class RecipeShortenInfoSerializer(RecipeReadSerializer):
    """Сериализатор для вывода сокращенной информации о рецепте."""

    class Meta(RecipeReadSerializer.Meta):
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class IngredientAmountSerializer(serializers.ModelSerializer):
    """Сериализатор для проверки данных ингредиентов при создании рецепта.

    Проверка наличия номера id в таблице модели Ingredient.
    Проверка значения amount.
    """

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
    """Сериализатор для создания и обновления рецептов."""

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
        tags = validated_data.pop('tags')

        recipe = Recipe.objects.create(
            **validated_data, author=self.context.get('request').user)

        self.ingredient_recipe_bulk_create(recipe, ingredients)
        self.tag_recipe_bulk_create(recipe, tags)

        return recipe

    def update(self, recipe, validated_data):
        """Обновление рецепта, с учетом обновлений в связанных таблицах."""
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')

        Recipe.objects.filter(pk=recipe.pk).update(
            **validated_data, author=self.context.get('request').user)

        # метод clear() доступен для RelatedManager объектов
        # только для полей с атрибутом null=True
        recipe.ingredient_recipe.clear()
        self.ingredient_recipe_bulk_create(recipe, ingredients)

        recipe.tag_recipe.clear()
        self.tag_recipe_bulk_create(recipe, tags)

        return recipe

    def validate(self, initial_data):
        """Дополнительная нештатная проверка наличия полей.

        Необходима, поскольку согласно ТЗ:
          1) поля ingredients и tags - обязательны:
          2) метод обновления: PATCH
        При этом по умолчанию сериализатор не проверяет для метода PATCH
        наличие полей и не вызывает методы validate_field.
        """
        if not initial_data.get('ingredients'):
            raise serializers.ValidationError('Нет поля ingredients!')

        if not initial_data.get('tags'):
            raise serializers.ValidationError('Нет поля tags!')

        return initial_data

    def validate_ingredients(self, ingredients):
        """Проверка введенных ингредиентов на повторяемость.

        Параметр UniqueValidator для поля сериализатора неприменим,
        поскольку записи модели Ingredient при создании рецепта не создаются.
        """
        ingredient_names = [ingredient.get('id') for ingredient in ingredients]

        if len(set(ingredient_names)) < len(ingredient_names):
            raise serializers.ValidationError('Ингредиенты повторяются!')

        return ingredients

    def validate_tags(self, tags):
        """Проверка введенных тэгов на повторяемость.

        Параметр UniqueValidator для поля сериализатора неприменим,
        поскольку записи модели Tag при создании рецепта не создаются.
        """
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError('Тэги повторяются!')

        return tags

    def ingredient_recipe_bulk_create(self, recipe, ingredients):
        """Создание записей в таблице IngredientRecipe."""
        IngredientRecipe.objects.bulk_create(
            [
                IngredientRecipe(
                    ingredient_id=ingredient.get('id').pk,
                    recipe=recipe,
                    amount=ingredient.get('amount')
                )
                for ingredient in ingredients
            ]
        )

    def tag_recipe_bulk_create(self, recipe, tags):
        """Создание записей в таблице TagRecipe."""
        TagRecipe.objects.bulk_create(
            TagRecipe(tag_id=tag.pk, recipe=recipe)
            for tag in tags
        )


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


class SubscriptionAddSerializer(FavoriteShoppingCartAddSerializer):
    """Сериализатор для добавления подписок."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    following = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Follow
        fields = ('user', 'following')
        validators = [
            UniqueTogetherValidator(
                queryset=Follow.objects.all(),
                fields=('user', 'following'),
                message='Уже подписан!'
            )
        ]

    def validate(self, data):
        user = data.get('user')
        following = data.get('following')
        if user and user == following:
            raise serializers.ValidationError(
                'Невозможно подписаться на самого себя!')
        return data

    def create(self, validated_data):
        return Follow.objects.create(**validated_data)


class APIAuthTokenSerializer(serializers.Serializer):
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

        if not email or not password:
            raise serializers.ValidationError(
                'Запрос должен включать "email" и "password".')

        try:
            user = get_object_or_404(User, email=email)
        except Http404 as exc:
            raise serializers.ValidationError(
                'Невозможно залогиниться по полученным данным.') from exc

        if not check_password(password, user.password):
            raise serializers.ValidationError('Неверный пароль!')

        return data
