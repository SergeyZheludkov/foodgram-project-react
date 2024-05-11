import csv
from os.path import join

from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import RecipeFilter
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    CustomUserSerializer, CustomUserCreateSerializer,
    CustomAuthTokenSerializer, TagSerializer, IngredientSerializer,
    RecipeSerializer, RecipeShoppingCartSerializer, UserSubscribeSerializer
)
from recipes.models import (
    Ingredient, IngredientRecipe, Favorite, Recipe, ShoppingCart, Tag
)
from users.models import Follow

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = (IsAuthorOrAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def perform_create(self, serializer):
        """Переопределение единичной операции сохранения объекта модели."""
        serializer.save(author=self.request.user)

    def get_queryset(self):
        queryset = Recipe.objects.all()

        is_favorited = self.request.query_params.get('is_favorited')
        queryset = self.queryset_filter(queryset, Favorite, is_favorited)

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart')
        queryset = self.queryset_filter(queryset, ShoppingCart,
                                        is_in_shopping_cart)

        return queryset

    def queryset_filter(self, queryset, model, param):
        """Фильтрация по параметрам, которых нет в модели Recipe."""
        if param is not None:
            param = int(param)
            objs = model.objects.all()
            recipe_ids = []
            for obj in objs:
                if obj.user == self.request.user:
                    recipe_ids.append(obj.recipe.id)
            if param == 1:
                queryset = queryset.filter(id__in=recipe_ids)
            elif param == 0:
                queryset = queryset.exclude(id__in=recipe_ids)

        return queryset

    def get_serializer_class(self):
        if self.action in ('to_shopping_cart_add_delete',
                           'to_favorite_add_delete'):
            return RecipeShoppingCartSerializer
        return RecipeSerializer

    @action(['post', 'delete'], url_path='shopping_cart', detail=True,
            permission_classes=(IsAuthenticated,))
    def to_shopping_cart_add_delete(self, request, pk):
        """Добавление в список покупок и исключение."""
        return self.shopping_cart_favorite_actions(request, pk, ShoppingCart)

    @action(url_path='download_shopping_cart', detail=False,
            permission_classes=(IsAuthenticated,))
    def shopping_cart_download(self, request):
        """Формирование списка покупок."""
        shopping_carts = ShoppingCart.objects.filter(user=request.user)
        recipe_list = []
        for shopping_cart in shopping_carts:
            recipe_list.append(shopping_cart.recipe)
        ingredients_recipes = IngredientRecipe.objects.filter(
            recipe__in=recipe_list
        )

        # заполнение словаря: ингридиент-количество
        shopping_cart = {}
        for item in ingredients_recipes:
            name = item.ingredient.name
            amount = item.amount
            if name in shopping_cart.keys():
                # суммирование количества одинаковых ингридиентов
                shopping_cart[name] += amount
            else:
                shopping_cart[name] = amount

        path = join(settings.MEDIA_ROOT, 'shopping_cart', 'list.csv')
        cart = open(path, "w+", newline='', encoding='utf-8')
        cart.truncate()
        csv_writer = csv.writer(cart)
        csv_writer.writerow(('Список покупок',))
        csv_writer.writerow(('Ингредиент', 'Количество'))

        # заполнение файла данными
        for ingredient, amount in shopping_cart.items():
            csv_writer.writerow((ingredient, amount))

        response = FileResponse(cart, content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=list.csv'

        return response

    @action(['post', 'delete'], url_path='favorite', detail=True,
            permission_classes=(IsAuthenticated,))
    def to_favorite_add_delete(self, request, pk):
        """Добавление в избранное и исключение."""
        return self.shopping_cart_favorite_actions(request, pk, Favorite)

    def shopping_cart_favorite_actions(self, request, pk, model):
        try:
            recipe = get_object_or_404(Recipe, pk=pk)
        except Http404:
            return Response('Рецепт с таким номером не найден!',
                            status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'DELETE':
            model.objects.filter(user=request.user, 
                                 recipe=recipe).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if model.objects.filter(user=request.user, recipe=recipe).exists():
            return Response('Рецепт уже отмечен!',
                            status=status.HTTP_400_BAD_REQUEST)

        model.objects.create(user=request.user, recipe=recipe)
        serializer = self.get_serializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_fields = ('name',)
    search_fields = ('^name',)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = LimitOffsetPagination

    def perform_create(self, serializer):
        serializer.save(password=self.request.data.get('password'))

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        elif self.action in ('subscription_create_delete', "subscriptions"):
            return UserSubscribeSerializer
        return CustomUserSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['rec_limit'] = self.request.query_params.get('recipes_limit')
        return context

    @action(url_path='me', detail=False,
            permission_classes=(IsAuthenticated, ))
    def get_self(self, request):
        """Получение данных о самом пользователе."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(['post'], url_path='set_password', detail=False,
            permission_classes=(IsAuthenticated, ))
    def reset_password(self, request):
        """Замена пароля."""
        if request.data['current_password'] != request.user.password:
            return Response('Неверный текущий пароль!',
                            status=status.HTTP_400_BAD_REQUEST)

        self.request.user.password = request.data['new_password']
        self.request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(['post', 'delete'], url_path='subscribe', detail=True,
            permission_classes=(IsAuthenticated, ))
    def subscription_create_delete(self, request, pk):
        """Добавление и удаление подписки."""
        following = get_object_or_404(User, pk=pk)

        if request.method == 'DELETE':
            Follow.objects.filter(
                user=request.user, following=following
            ).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if following == request.user:
            return Response('Невозможно подписаться на самого себя!',
                            status=status.HTTP_400_BAD_REQUEST)

        if Follow.objects.filter(
            user=request.user, following=following
        ).exists():
            return Response('Уже подписан!',
                            status=status.HTTP_400_BAD_REQUEST)

        Follow.objects.create(user=request.user, following=following)
        serializer = self.get_serializer(following)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(url_path='subscriptions', detail=False,
            permission_classes=(IsAuthenticated, ))
    def subscriptions(self, request):
        """Список подписок пользователя."""
        subscriptions = Follow.objects.filter(user=self.request.user)

        following_list = []
        for subscription in subscriptions:
            following_list.append(subscription.following.username)

        subscribed_on = User.objects.filter(username__in=following_list)
        subscribed_on = self.paginate_queryset(subscribed_on)
        serializer = self.get_serializer(subscribed_on, many=True)
        return self.get_paginated_response(serializer.data)


class CustomObtainAuthToken(ObtainAuthToken):
    serializer_class = CustomAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        """Изменение ключа в ответе с 'token' на 'auth_token'."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({'auth_token': token.key})
