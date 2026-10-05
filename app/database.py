import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Lee .env de la raiz del proyecto. No sobreescribe variables ya definidas en
# el entorno, asi que APP_ENV pasado por consola tiene prioridad sobre .env.
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Solo existen estos dos entornos. Cualquier otro valor es un error de
# configuracion y se detiene el arranque en vez de caer silenciosamente en prod.
VALID_ENVS = ("dev", "prod")
DEFAULT_ENV = "prod"
DB_FILENAMES = {"dev": "poker_trainer.dev.db", "prod": "poker_trainer.db"}


def resolve_env() -> str:
    raw = (os.getenv("APP_ENV") or "").strip().lower()
    if not raw:
        return DEFAULT_ENV
    if raw not in VALID_ENVS:
        raise RuntimeError(
            f"APP_ENV inválido: {raw!r}. Solo se admiten {VALID_ENVS}."
        )
    return raw


APP_ENV = resolve_env()

DB_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, DB_FILENAMES[APP_ENV])
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
