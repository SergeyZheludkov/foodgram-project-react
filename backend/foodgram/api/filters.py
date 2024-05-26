from django_filters import AllValuesMultipleFilter, CharFilter
from django_filters.rest_framework import FilterSet

from recipes.models import Recipe, Ingredient


class RecipeFilter(FilterSet):
    tags = AllValuesMultipleFilter(field_name='tags__slug')

    class Meta:
        model = Recipe
        fields = ('author', 'tags')


class IngredientFilter(FilterSet):
    name = CharFilter(field_name='name', lookup_expr='startswith')

    class Meta:
        model = Ingredient
        fields = ('name',)
