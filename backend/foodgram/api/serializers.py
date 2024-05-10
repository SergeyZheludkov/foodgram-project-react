import base64

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from django.http import Http404

from recipes.models import (Favorite, Ingredient, Recipe, ShoppingCart, Tag,
                            TagRecipe, IngredientRecipe)
from users.models import Follow

User = get_user_model()


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ('name', 'measurement_unit', 'id')


class TagSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tag
        fields = ('name', 'color', 'slug', 'id')


class CustomUserCreateSerializer(serializers.ModelSerializer):

    class Meta:
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
        if not user.is_active:  # обработка анонимов
            return False
        following = User.objects.get(pk=obj.id)
        return Follow.objects.filter(user=user, following=following).exists()


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)


class RecipeSerializer(serializers.ModelSerializer):
    author = CustomUserSerializer(read_only=True, many=False)
    ingredients = serializers.SerializerMethodField()
    tags = TagSerializer(read_only=True, many=True)
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'tags', 'image', 'name',
                  'text', 'cooking_time', 'is_favorited',
                  'is_in_shopping_cart')

    def get_ingredients(self, obj):
        ingredients = obj.ingredients.values(
            'id', 'name', 'measurement_unit',
            amount=F('ingredientrecipe__amount')
        )
        return ingredients

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        if not user.is_active:  # обработка анонимов
            return False
        recipe = Recipe.objects.get(pk=obj.id)
        return Favorite.objects.filter(user=user, recipe=recipe).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        if not user.is_active:  # обработка анонимов
            return False
        recipe = Recipe.objects.get(pk=obj.id)
        return ShoppingCart.objects.filter(user=user, recipe=recipe).exists()

    def create(self, validated_data):
        """Валидация и привязка tags и ingredients к recipe в ручном режиме."""
        self.custom_validate_tags()
        self.custom_validate_ingredients()

        recipe = Recipe.objects.create(**validated_data)

        ingredients = self.initial_data['ingredients']
        for ingredient in ingredients:
            current_ingredient = get_object_or_404(Ingredient,
                                                   pk=ingredient['id'])
            IngredientRecipe.objects.create(
                ingredient=current_ingredient,
                recipe=recipe,
                amount=ingredient['amount']
            )

        tags_id = self.initial_data['tags']
        for tag_id in tags_id:
            tag = get_object_or_404(Tag, pk=tag_id)
            TagRecipe.objects.create(tag=tag, recipe=recipe)

        return recipe
    
    def update(self, instance, validated_data):
        self.custom_validate_tags()
        self.custom_validate_ingredients()
        return super().update(instance, validated_data)

    def custom_validate_tags(self):
        if 'tags' not in self.initial_data or self.initial_data['tags'] == []:
            raise serializers.ValidationError('Нет данных о тэге')

        tags_id = self.initial_data['tags']

        if len(tags_id) != len(set(tags_id)):
            raise serializers.ValidationError('Тэги повторяются!')

        for tag_id in tags_id:
            if not Tag.objects.filter(id=tag_id).exists():
                raise serializers.ValidationError('Проверьте id тэгов!')

    def custom_validate_ingredients(self):
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
