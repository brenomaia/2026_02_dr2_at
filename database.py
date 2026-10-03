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
            existing_user = session.exec(
                select(User).where(User.username == user.username)
            ).first()
            if existing_user is not None:
                continue

            # O seed anterior usava o mesmo ID para ``administrator``. Migra o
            # registro legado para o usuário padrão solicitado sem criar um
            # segundo administrador.
            legacy_user = session.get(User, user.id)
            if legacy_user is not None and legacy_user.username == "administrator":
                legacy_user.username = user.username
                legacy_user.password_hash = user.password_hash
                legacy_user.role = user.role
            elif legacy_user is None:
                session.add(user)
        session.commit()
