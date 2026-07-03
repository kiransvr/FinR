from __future__ import annotations


class AuthorizationError(Exception):
    pass


def require_role(user_role: str, required_role: str) -> None:
    if user_role != required_role:
        raise AuthorizationError(f"{required_role} role required")
