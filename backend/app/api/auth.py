from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthenticatedUser)
async def current_user(
    user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> AuthenticatedUser:
    return user
