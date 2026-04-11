"""Сессионная «авторизация» без django.contrib.auth.login (MVP)."""

SESSION_USER_KEY = 'user_id'


def get_session_user(request):
    uid = request.session.get(SESSION_USER_KEY)
    if not uid:
        return None
    from .models import User

    return User.objects.filter(pk=uid).first()


def login_session(request, user):
    request.session[SESSION_USER_KEY] = str(user.pk)
    request.session['role'] = user.role
    request.session.modified = True
