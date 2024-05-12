from django.contrib import admin

from .models import (Favorite, Ingredient, Recipe, ShoppingCart, Tag)


class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit')
    list_filter = ('name',)
    search_fields = ('name',)


class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'author', 'in_favorite_count')
    list_filter = ('name', 'author', 'tags')

    def in_favorite_count(self, recipe):
        return Favorite.objects.filter(recipe=recipe).count()


class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'slug')


admin.site.register(Recipe, RecipeAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Favorite)
admin.site.register(ShoppingCart)
