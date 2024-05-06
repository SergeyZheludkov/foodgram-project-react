from django.urls import include, path
from djoser.views import TokenDestroyView
from rest_framework.routers import DefaultRouter

from .views import CustomUserViewSet, CustomObtainAuthToken

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/login/', CustomObtainAuthToken.as_view()),
    path('auth/token/logout/', TokenDestroyView.as_view()),
]
