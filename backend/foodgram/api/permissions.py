from rest_framework import permissions


class IsAuthorOrAdminOrReadOnly(permissions.IsAuthenticatedOrReadOnly):

    def has_object_permission(self, request, view, recipe_obj):
        return bool(
            request.method in permissions.SAFE_METHODS or (
                request.user and recipe_obj.author == request.user
            ) or request.user.is_staff
        )
