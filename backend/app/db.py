"""Database engine. SQLite (a local file) by default; Postgres (Supabase) when DATABASE_URL is set. Everything else is plain SQLModel, so both work."""
import logging

from sqlalchemy import event, inspect
from sqlmodel import Session, SQLModel, create_engine

from app import config
from app.models import AuditEvent, Case, utcnow

log = logging.getLogger("karyakarta.db")


def normalise_database_url(url: str) -> str:
    """postgres:// and postgresql:// -> the psycopg 3 driver; Supabase needs SSL, so add sslmode=require when the URL says nothing about it."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    if url.startswith("postgresql+psycopg://") and "sslmode=" not in url:
        host = url.split("@")[-1].split("/")[0].split(":")[0]
        if host not in {"localhost", "127.0.0.1", "db", "postgres"}:
            url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


def is_postgres() -> bool:
    return bool(config.DATABASE_URL)


def make_engine():
    if is_postgres():
        # Small pool: a free database allows few connections. prepare_threshold=None keeps psycopg compatible with Supabase's transaction pooler (pgbouncer).
        return create_engine(normalise_database_url(config.DATABASE_URL), pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=240,
                             connect_args={"prepare_threshold": None})
    return create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False, "timeout": 30})


engine = make_engine()

if not is_postgres():
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")   # readers (SSE polling) don't block pipeline writers
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def _ensure_columns() -> None:
    """create_all() never alters existing tables; add any columns new models gained (ADD COLUMN works on SQLite and Postgres)."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if have and col.name not in have:
                    ddl = col.type.compile(engine.dialect)
                    default = " DEFAULT " + (repr(col.default.arg) if col.default is not None and not callable(col.default.arg) else "NULL")
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{default}')


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_columns()
    log.info("database ready (%s)", "postgres" if is_postgres() else f"sqlite {config.DB_PATH}")


def get_session():
    with Session(engine) as session:
        yield session


def audit(session: Session, case_id: str, actor: str, action: str, detail: str = "",
          tone: str = "neutral", doc_id: str | None = None) -> AuditEvent:
    """Every state change goes through here so the timeline and SSE feed never miss one."""
    ev = AuditEvent(case_id=case_id, actor=actor, action=action, detail=detail, tone=tone, doc_id=doc_id)
    session.add(ev)
    case = session.get(Case, case_id)
    if case:
        case.updated_at = utcnow()
        session.add(case)
    session.commit()
    session.refresh(ev)
    return ev
