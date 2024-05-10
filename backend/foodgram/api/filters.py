from django_filters import ModelMultipleChoiceFilter, NumberFilter
from django_filters.rest_framework import FilterSet

from recipes.models import Recipe, Tag


class RecipeFilter(FilterSet):
    author = NumberFilter(field_name='author__id', lookup_expr='exact')
    tags = ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
    )

    class Meta:
        model = Recipe
        fields = ('author', 'tags')
