from fastapi import Depends, HTTPException, status

from core.security import get_current_claims


def require_roles(*allowed_roles: str):
    def _dependency(claims: dict = Depends(get_current_claims)) -> dict:
        user_role = claims.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return claims

    return _dependency
