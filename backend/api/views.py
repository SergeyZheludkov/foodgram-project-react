import csv
from os.path import join

from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models import F, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import RecipeFilter, IngredientFilter
from .paginator import RecipePagination
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    APIUserSerializer, APIUserCreateSerializer,
    APIAuthTokenSerializer, FavoriteAddSerializer,
    ShoppingCartAddSerializer, TagSerializer, IngredientSerializer,
    RecipeReadSerializer, RecipeCreateUpdateSerializer,
    RecipeShortenInfoSerializer, ResetPasswordeSerializer,
    UserSubscribeSerializer
)
from recipes.models import (
    Ingredient, IngredientRecipe, Favorite, Recipe, ShoppingCart, Tag
)
from users.models import Follow

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthorOrAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = RecipePagination
    ordering = ('-pub_date',)

    def get_queryset(self):
        """Добавление полей is_favorited и is_in_shopping_cart."""
        queryset = Recipe.objects.prefetch_related('carts', 'favorites')
        return queryset

    def get_serializer_class(self):
        if self.action in {'create', 'partial_update'}:
            return RecipeCreateUpdateSerializer
        if self.action in {'to_shopping_cart_add_delete',
                           'to_favorite_add_delete'}:
            return RecipeShortenInfoSerializer
        return RecipeReadSerializer

    @action(('post', 'delete'), url_path='shopping_cart', detail=True,
            permission_classes=(IsAuthenticated,))
    def to_shopping_cart_add_delete(self, request, pk):
        """Добавление в список покупок и исключение."""
        return self.shopping_cart_favorite_actions(request, pk, ShoppingCart)

    @action(url_path='download_shopping_cart', detail=False,
            permission_classes=(IsAuthenticated,))
    def shopping_cart_download(self, request):
        """Формирование списка покупок."""
        ingredient_recipe_pks = request.user.carts.all().values(
            'recipe__ingredient_recipe'
        )
        shopping_cart = IngredientRecipe.objects.filter(
            pk__in=ingredient_recipe_pks
        ).values(name=F('ingredient__name')).annotate(amount=Sum('amount'))

        path = join(settings.MEDIA_ROOT, 'shopping_cart', 'shopping-list.csv')
        cart = open(path, "w+", newline='', encoding='utf-8')
        cart.truncate()
        csv_writer = csv.writer(cart)
        csv_writer.writerow(('Список покупок',))
        csv_writer.writerow(('Ингредиент', 'Количество'))

        # заполнение файла данными
        for ingredient in shopping_cart:
            csv_writer.writerow((ingredient['name'], ingredient['amount']))

        response = FileResponse(cart, content_type='text/csv')
        response[
            'Content-Disposition'] = 'attachment; filename=shopping-list.csv'

        return response

    @action(('post', 'delete'), url_path='favorite', detail=True,
            permission_classes=(IsAuthenticated,))
    def to_favorite_add_delete(self, request, pk):
        """Добавление в избранное и исключение."""
        return self.shopping_cart_favorite_actions(request, pk, Favorite)

    def shopping_cart_favorite_actions(self, request, pk, model):

        if request.method == 'DELETE':
            # извлечение рецепта с одновременной проверкой его существования
            recipe = self.get_object()

            deletion_quantity, _ = model.objects.filter(user=request.user,
                                                        recipe=recipe).delete()
            # проверяем количество удаленных объектов
            if deletion_quantity == 0:
                raise ParseError('Рецепт не отмечен!')
            return Response(status=status.HTTP_204_NO_CONTENT)

        model_data = {'user': self.request.user.pk, 'recipe': pk}
        if model == Favorite:
            serializer = FavoriteAddSerializer(data=model_data)
        else:
            serializer = ShoppingCartAddSerializer(data=model_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        serializer_for_output = self.get_serializer(self.get_object())
        return Response(serializer_for_output.data,
                        status=status.HTTP_201_CREATED)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class FoodgramUserViewSet(viewsets.ModelViewSet):
    # permission_classes = (IsAuthorOrAdminOrReadOnly,)
    queryset = User.objects.all()
    pagination_class = LimitOffsetPagination

    def perform_create(self, serializer):
        password = self.request.data.get('password')
        # шифрование пароля
        password = make_password(password)
        serializer.save(password=password)

    def get_serializer_class(self):
        if self.action == 'create':
            return APIUserCreateSerializer
        if self.action in {'subscription_create_delete', 'subscriptions'}:
            return UserSubscribeSerializer
        if self.action == 'reset_password':
            return ResetPasswordeSerializer
        return APIUserSerializer

    @action(url_path='me', detail=False,
            permission_classes=(IsAuthenticated,))
    def get_self(self, request):
        """Получение данных о самом пользователе."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(('post',), url_path='set_password', detail=False,
            permission_classes=(IsAuthenticated,))
    def reset_password(self, request):
        """Замена пароля."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = make_password(serializer.data.get('new_password'))
        self.request.user.password = new_password
        self.request.user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(('post', 'delete'), url_path='subscribe', detail=True,
            permission_classes=(IsAuthenticated,))
    def subscription_create_delete(self, request, pk):
        """Добавление и удаление подписки."""
        user_obj = self.get_object()
        user = request.user

        if request.method == 'DELETE':
            deletion_quantity, _ = user.subscriber.filter(
                following=user_obj).delete()
            if deletion_quantity == 0:
                return Response('Такой подписки нет!',
                                status=status.HTTP_400_BAD_REQUEST)
            return Response(status=status.HTTP_204_NO_CONTENT)

        if user_obj == user:
            return Response('Невозможно подписаться на самого себя!',
                            status=status.HTTP_400_BAD_REQUEST)

        if user.subscriber.filter(following=user_obj).exists():
            return Response('Уже подписан!',
                            status=status.HTTP_400_BAD_REQUEST)

        Follow.objects.create(user=request.user, following=user_obj)
        serializer = self.get_serializer(user_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(url_path='subscriptions', detail=False,
            permission_classes=(IsAuthenticated,))
    def subscriptions(self, request):
        """Список подписок пользователя."""
        subscribed_on = User.objects.filter(
            following__in=request.user.subscriber.all()
        )
        subscribed_on = self.paginate_queryset(subscribed_on)

        serializer = self.get_serializer(subscribed_on, many=True)
        return self.get_paginated_response(serializer.data)


class APIObtainAuthToken(ObtainAuthToken):
    serializer_class = APIAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        """Изменение ключа в ответе с 'token' на 'auth_token'."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # наличие такого user проверяется ранее в валидаторе сериализатора
        user = get_object_or_404(User,
                                 email=serializer.validated_data.get('email'))
        token, _ = Token.objects.get_or_create(user=user)

        return Response({'auth_token': token.key})
