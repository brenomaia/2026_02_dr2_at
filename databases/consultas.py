from uuid import UUID

from sqlmodel import Session, select

from model.consultas import Consulta, ConsultaCreate, ConsultaUpdate, utc_now


def get_consulta_by_id(session: Session, consulta_id: UUID) -> Consulta | None:
    statement = select(Consulta).where(Consulta.id == consulta_id)
    return session.exec(statement).first()


def list_consultas(session: Session) -> list[Consulta]:
    return list(session.exec(select(Consulta)).all())


def create_consulta(session: Session, payload: ConsultaCreate) -> Consulta:
    consulta = Consulta(**payload.model_dump())
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta


def update_consulta(
    session: Session, consulta: Consulta, payload: ConsultaUpdate
) -> Consulta:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(consulta, field, value)
    consulta.updated_at = utc_now()
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta


def update_doctor_notes(
    session: Session, consulta: Consulta, doctor_notes: str
) -> Consulta:
    consulta.doctor_notes = doctor_notes
    consulta.updated_at = utc_now()
    session.add(consulta)
    session.commit()
    session.refresh(consulta)
    return consulta


def delete_consulta(session: Session, consulta: Consulta) -> None:
    session.delete(consulta)
    session.commit()
