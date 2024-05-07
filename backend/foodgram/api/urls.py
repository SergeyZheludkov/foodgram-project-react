from django.urls import include, path
from djoser.views import TokenDestroyView
from rest_framework.routers import DefaultRouter

from .views import (
    CustomUserViewSet, CustomObtainAuthToken, TagViewSet, IngredientViewSet
)

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='users')
router.register('tags', TagViewSet, basename='tags')
router.register('ingredients', IngredientViewSet, basename='ingredients')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/login/', CustomObtainAuthToken.as_view()),
    path('auth/token/logout/', TokenDestroyView.as_view()),
]
