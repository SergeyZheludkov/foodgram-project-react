from django_filters import ModelMultipleChoiceFilter, AllValuesMultipleFilter
from django_filters.rest_framework import FilterSet

from recipes.models import Recipe, Tag


class RecipeFilter(FilterSet):
    tags = AllValuesMultipleFilter(field_name='tags__slug')

    class Meta:
        model = Recipe
        fields = ('author', 'tags')
