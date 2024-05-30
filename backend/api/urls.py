from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from djoser.views import TokenDestroyView
from rest_framework.routers import DefaultRouter

from .views import (
    CustomUserViewSet, CustomObtainAuthToken, TagViewSet, IngredientViewSet,
    RecipeViewSet
)

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='users')
router.register('tags', TagViewSet, basename='tags')
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('recipes', RecipeViewSet, basename='recipes')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/login/', CustomObtainAuthToken.as_view()),
    path('auth/token/logout/', TokenDestroyView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
