from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from database import create_db_and_tables
from fastapi.middleware.cors import CORSMiddleware
from routes.auth import auth_router
from routes.consultas import consultas_router
from routes.pacientes import pacientes_router
from routes.profissionais import profissionais_router
from routes.partner_consultas import partner_consultas_router
from middleware.jwt import JWTAuthenticationMiddleware

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
# Mantém a aplicação utilizável também por scripts/testes que importam ``app``
# sem acionar o ciclo de vida do ASGI.
create_db_and_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(JWTAuthenticationMiddleware)

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.get("/health")
async def get() -> dict:
    return {"status": "ok"}

app.include_router(consultas_router)
app.include_router(pacientes_router)
app.include_router(profissionais_router)
app.include_router(auth_router)
app.include_router(partner_consultas_router)
