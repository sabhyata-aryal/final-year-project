from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            user_role = getattr(getattr(request.user, 'profile', None), 'role', None)
            if user_role not in allowed_roles:
                return HttpResponseForbidden('403 Forbidden')

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
