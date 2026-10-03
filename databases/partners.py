from sqlmodel import Session, select

from model.users import PartnerClient


def get_partner_client(client_id: str, session: Session | None = None) -> PartnerClient | None:
    statement = select(PartnerClient).where(PartnerClient.client_id == client_id)
    if session is not None:
        return session.exec(statement).first()
    from database import engine

    with Session(engine) as db_session:
        return db_session.exec(statement).first()


def create_partner_client(
    session: Session,
    *,
    client_id: str,
    secret_hash: str,
    allowed_scopes: str,
) -> PartnerClient | None:
    if get_partner_client(client_id, session) is not None:
        return None
    client = PartnerClient(
        client_id=client_id,
        secret_hash=secret_hash,
        allowed_scopes=allowed_scopes,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client
