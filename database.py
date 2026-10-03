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
    from auth.authentication import hash_password
    from databases.partners import get_partner_client
    from model.users import PartnerClient, User, initial_users

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
        if settings.oauth_bootstrap_client_id and settings.oauth_bootstrap_client_secret:
            bootstrap_client = get_partner_client(settings.oauth_bootstrap_client_id, session)
            if bootstrap_client is None:
                session.add(
                    PartnerClient(
                        client_id=settings.oauth_bootstrap_client_id,
                        secret_hash=hash_password(settings.oauth_bootstrap_client_secret),
                        allowed_scopes=settings.oauth_bootstrap_client_scopes,
                    )
                )
            elif bootstrap_client.allowed_scopes == "consultas:read":
                # Migra o escopo inicial para a nomenclatura explícita de parceiro.
                bootstrap_client.allowed_scopes = settings.oauth_bootstrap_client_scopes
                session.add(bootstrap_client)
        session.commit()
