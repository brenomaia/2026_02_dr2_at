from sqlmodel import Session, select

from database import engine
from model.users import User


def get_user_by_username(username: str, session: Session | None = None) -> User | None:
    statement = select(User).where(User.username == username)
    if session is not None:
        return session.exec(statement).first()
    with Session(engine) as db_session:
        return db_session.exec(statement).first()


def create_user(
    session: Session, *, username: str, password_hash: str, role: str
) -> User | None:
    if get_user_by_username(username, session) is not None:
        return None

    user = User(username=username, password_hash=password_hash, role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
