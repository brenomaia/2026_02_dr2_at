from collections.abc import Generator

from sqlmodel import SQLModel, Session, create_engine, select

from config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    # Importa os modelos antes de construir os metadados do SQLModel.
    from model.users import User, initial_users

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for user in initial_users():
            exists = session.exec(select(User).where(User.username == user.username)).first()
            if exists is None:
                session.add(user)
        session.commit()
