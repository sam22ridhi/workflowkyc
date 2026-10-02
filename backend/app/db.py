from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app import config
from app.models import AuditEvent, Case, utcnow

engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False, "timeout": 30})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")   # readers (SSE polling) don't block pipeline writers
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def _ensure_columns() -> None:
    """create_all() never alters existing tables; add any columns new models gained (SQLite ADD COLUMN)."""
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            have = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")')}
            for col in table.columns:
                if have and col.name not in have:
                    ddl = col.type.compile(engine.dialect)
                    default = " DEFAULT " + (repr(col.default.arg) if col.default is not None and not callable(col.default.arg) else "NULL")
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{default}')


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_columns()


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
