"""Persistência de jobs e cortes (SQLite via SQLModel)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum

from pydantic_core import PydanticUndefined
from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine, select

from cortago import config


def _now() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    SELECTING = "selecting"
    RENDERING = "rendering"
    DONE = "done"
    ERROR = "error"

    @property
    def running(self) -> bool:
        return self not in (JobStatus.DONE, JobStatus.ERROR)


class ClipStatus(StrEnum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    DISCARDED = "discarded"


class RenderStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    DONE = "done"
    ERROR = "error"


class Job(SQLModel, table=True):
    # AUTOINCREMENT: ids nunca são reaproveitados, então URLs de vídeo antigas não colidem com novas.
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    source: str
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None

    title: str | None = None
    channel: str | None = None
    url: str | None = None
    duration: float | None = None
    source_file: str | None = None  # nome do arquivo dentro da pasta do job

    layout: str = "blur"
    max_clips: int = 5
    min_seconds: int = 20
    max_seconds: int = 60
    language: str | None = None
    music: bool = True  # sortear música de fundo para os cortes

    # Trecho a processar, em segundos do vídeo original (None = do começo / até o fim).
    range_start: float | None = None
    range_end: float | None = None
    # Em que segundo do vídeo original o arquivo baixado começa (> 0 quando só o trecho foi baixado).
    source_offset: float = 0.0

    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    def window(self) -> tuple[float, float | None]:
        """Trecho a processar, em segundos do arquivo baixado (fim None = até o fim do arquivo)."""
        start = max((self.range_start or 0.0) - self.source_offset, 0.0)
        end = None if self.range_end is None else self.range_end - self.source_offset
        return start, end

    def file_end(self) -> float | None:
        """Até onde vai o material utilizável, em segundos do arquivo (fim do trecho ou do vídeo)."""
        limit = self.range_end or self.duration
        return None if limit is None else limit - self.source_offset

    @property
    def dir_name(self) -> str:
        return f"{self.id:05d}"

    @property
    def display_title(self) -> str:
        return self.title or self.source


class Clip(SQLModel, table=True):
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    position: int

    start: float
    end: float
    title: str
    hook: str
    description: str
    hashtags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    score: int
    reason: str

    status: ClipStatus = ClipStatus.SUGGESTED
    render_status: RenderStatus = RenderStatus.PENDING
    render_error: str | None = None
    render_version: int = 0
    # None = ainda não escolhida (sorteia no render); "" = sem música; senão, nome do arquivo em MUSIC_DIR.
    music_track: str | None = None
    # Ajuste manual do volume da música em % sobre o nível automático (100 = automático).
    music_level: int = 100

    # Efeitos de retenção (ver effects.py). Cortes novos recebem os padrões do .env; os antigos ficam sem efeitos.
    jump_cuts: bool = False
    intro_zoom: str = "none"
    hook_anim: bool = False
    hook_sfx: str = "none"
    progress_bar: bool = False

    # Ajustes manuais da timeline (edição não destrutiva). None = nada ajustado à mão.
    # {"segments": [[ini, fim], ...]  # trechos que entram, em segundos do arquivo (substitui o corte automático)
    #  "words": {"12.34": "texto"}}   # correções de legenda, pela posição da palavra (início com 2 casas)
    edit: dict | None = Field(default=None, sa_column=Column(JSON))

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def file_stem(self) -> str:
        return f"clip_{self.position:02d}"


_engine = None


def engine():
    global _engine
    if _engine is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{config.DATA_DIR / 'cortago.db'}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(_engine)
        migrate(_engine)
    return _engine


def use_engine(new_engine) -> None:
    """Troca o engine (usado nos testes)."""
    global _engine
    _engine = new_engine
    SQLModel.metadata.create_all(_engine)
    migrate(_engine)


def _sql_literal(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def migrate(eng) -> list[str]:
    """Adiciona colunas novas em tabelas existentes (SQLite não faz isso no create_all).

    Cobre só mudanças aditivas, que é o que este projeto precisa por enquanto. Se um dia
    for preciso renomear/remover colunas, é hora de adotar o Alembic.
    """
    added = []
    with eng.begin() as conn:
        for model in (Job, Clip):
            table = model.__table__
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table.name})")}
            if not existing:  # tabela nova: o create_all já cria completa
                continue
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(eng.dialect)}"
                field = model.model_fields[column.name]
                if not column.nullable:
                    if field.default is None or field.default is PydanticUndefined:
                        raise RuntimeError(
                            f"{table.name}.{column.name}: coluna obrigatória nova precisa de um valor padrão fixo"
                        )
                    ddl += f" NOT NULL DEFAULT {_sql_literal(field.default)}"
                conn.exec_driver_sql(ddl)
                added.append(f"{table.name}.{column.name}")
    return added


@contextmanager
def session() -> Iterator[Session]:
    with Session(engine(), expire_on_commit=False) as s:
        yield s


def get_job(job_id: int) -> Job | None:
    with session() as s:
        return s.get(Job, job_id)


def update_job(job_id: int, **fields) -> Job:
    with session() as s:
        job = s.get(Job, job_id)
        assert job is not None, f"job {job_id} não existe"
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = _now()
        s.add(job)
        s.commit()
        s.refresh(job)
        return job


def update_clip(clip_id: int, **fields) -> Clip:
    with session() as s:
        clip = s.get(Clip, clip_id)
        assert clip is not None, f"clip {clip_id} não existe"
        for k, v in fields.items():
            setattr(clip, k, v)
        s.add(clip)
        s.commit()
        s.refresh(clip)
        return clip


def job_clips(job_id: int) -> list[Clip]:
    with session() as s:
        return list(s.exec(select(Clip).where(Clip.job_id == job_id).order_by(Clip.position)))
