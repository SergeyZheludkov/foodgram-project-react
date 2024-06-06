from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Follow

User = get_user_model()


class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'following')


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'last_name', 'email')
    list_filter = ('username', 'email')
    search_fields = ('username', 'email')


admin.site.register(User, UserAdmin)
admin.site.register(Follow, FollowAdmin)
