from .session_auth import get_session_user


def session_user(request):
    return {'session_user': get_session_user(request)}
