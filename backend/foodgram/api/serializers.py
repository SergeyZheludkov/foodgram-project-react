import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db.models import F
from django.shortcuts import get_object_or_404
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers
from django.http import Http404

from recipes.models import (Ingredient, Recipe, Tag,
                            TagRecipe, IngredientRecipe)

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
    recipes_count = serializers.IntegerField(source='author.count',
                                             read_only=True)

    class Meta(CustomUserSerializer.Meta):
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes_count', 'recipes')

    def get_recipes(self, user):
        recipes_limit = self.context.get('rec_limit')
        if recipes_limit:
            recipes_limit = self.validate_recipes_limit(recipes_limit)
        return user.author.values(
            'id', 'image', 'name', 'cooking_time'
        )[:recipes_limit]

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


class RecipeSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True, many=False)
    ingredients = serializers.SerializerMethodField()
    tags = TagSerializer(read_only=True, many=True, allow_empty=False)
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
        self.validate_tags()
        self.validate_ingredients()

        recipe = super().create(validated_data)

        ingredients = self.initial_data.get('ingredients')

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

        tags_id = self.initial_data.get('tags')

        TagRecipe.objects.bulk_create(
            [
                TagRecipe(
                    tag=get_object_or_404(Tag, pk=tag_id),
                    recipe=recipe
                )
                for tag_id in tags_id
            ]
        )

        return recipe

    def update(self, instance, validated_data):
        self.validate_tags()
        self.validate_ingredients()
        return super().update(instance, validated_data)

    def validate_tags(self):
        if self.initial_data['tags'] == []:
            raise serializers.ValidationError('Нет данных о тэге')

        tags_id = self.initial_data['tags']

        if len(tags_id) != len(set(tags_id)):
            raise serializers.ValidationError('Тэги повторяются!')

        for tag_id in tags_id:
            if not Tag.objects.filter(id=tag_id).exists():
                raise serializers.ValidationError('Проверьте id тэгов!')

    def validate_ingredients(self):
        if 'ingredients' not in self.initial_data or (
            self.initial_data['ingredients'] == []
        ):
            raise serializers.ValidationError('Нет данных об ингредиентах')

        ingredients = self.initial_data['ingredients']

        ingredient_ids = []

        for ingredient in ingredients:
            if not Ingredient.objects.filter(id=ingredient['id']).exists():
                raise serializers.ValidationError('Проверьте id ингредиентов!')
            ingredient_ids.append(ingredient['id'])
            if ingredient['amount'] < 1:
                raise serializers.ValidationError(
                    'Количество ингредиента должно быть не меньше 1')

        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError('Ингредиенты повторяются!')


class RecipeCreateIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        source='ingredient', queryset=Ingredient.objects.all()
    )

    class Meta:
        model = IngredientRecipe
        fields = '__all__'


class RecipeShoppingCartSerializer(RecipeSerializer):

    class Meta(RecipeSerializer.Meta):
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class CustomAuthTokenSerializer(serializers.Serializer):
    """Изменение пары авторизации с username-password на email-password."""

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
                user = get_object_or_404(User, email=email, password=password)
            except Http404:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg, code='authorization')
        else:
            msg = 'Must include "email" and "password".'
            raise serializers.ValidationError(msg, code='authorization')

        data['user'] = user
        return data
