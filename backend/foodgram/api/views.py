from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action, permission_classes
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import (
    CustomUserSerializer, CustomUserCreateSerializer,
    CustomAuthTokenSerializer,
)

User = get_user_model()


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
