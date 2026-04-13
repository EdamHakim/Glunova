from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import user_repo
from app.schemas.user import UserUpdate


def update_me(db: Session, user: User, data: UserUpdate) -> User:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    return user_repo.update(db, user)
