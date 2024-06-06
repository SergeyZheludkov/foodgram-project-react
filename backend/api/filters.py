from django_filters import AllValuesMultipleFilter, CharFilter
from django_filters.rest_framework import FilterSet

from recipes.models import Recipe, Ingredient


class RecipeFilter(FilterSet):
    tags = AllValuesMultipleFilter(field_name='tags__slug')
    # BooleanFilter на SQLite не обрабатывает 0 и 1, только true и false
    # поэтому выбран менее очевидный тип CharFilter
    is_favorited = CharFilter(method='filter_is_favorited')
    is_in_shopping_cart = CharFilter(method='filter_is_in_cart')

    class Meta:
        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, is_favorite):
        user = self.request.user
        if is_favorite and not user.is_anonymous:
            is_favorite = self.transform_to_int_filter_param(
                'is_favorite', is_favorite)
            if is_favorite == 1:
                return queryset.filter(favorites__user=user)
        return queryset

    def filter_is_in_cart(self, queryset, name, is_in_cart):
        user = self.request.user
        if is_in_cart and not user.is_anonymous:
            is_in_cart = self.transform_to_int_filter_param(
                'is_in_shopping_cart', is_in_cart)
            if is_in_cart == 1:
                return queryset.filter(carts__user=user)
        return queryset

    def transform_to_int_filter_param(self, param_name, param_value):
        try:
            param_value = int(param_value)
        except ValueError:
            raise ValueError(f'Значение {param_name} должно быть 0 или 1!')
        return param_value


class IngredientFilter(FilterSet):
    name = CharFilter(lookup_expr='startswith')

    class Meta:
        model = Ingredient
        fields = ('name',)
