from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework import filters, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .filters import RecipeFilter
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (
    CustomUserSerializer, CustomUserCreateSerializer,
    CustomAuthTokenSerializer, TagSerializer, IngredientSerializer,
    RecipeSerializer
)
from recipes.models import Ingredient, Favorite, Recipe, ShoppingCart, Tag

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

    def perform_create(self, serializer):
        serializer.save(password=self.request.data.get('password'))

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserSerializer

    @action(url_path='me', detail=False,
            permission_classes=(IsAuthenticated, ))
    def get_self(self, request):
        """Функция для получения данных о самом пользователе."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(['post'], url_path='set_password', detail=False,
            permission_classes=(IsAuthenticated, ))
    def reset_password(self, request):
        """Функция для замены пароля."""
        if request.data['current_password'] != request.user.password:
            return Response('Неверный текущий пароль!',
                            status=status.HTTP_400_BAD_REQUEST)

        self.request.user.password = request.data['new_password']
        self.request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomObtainAuthToken(ObtainAuthToken):
    serializer_class = CustomAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        """Изменение ключа в ответе с 'token' на 'auth_token'."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({'auth_token': token.key})
