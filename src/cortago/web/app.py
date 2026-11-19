"""Interface web: monta a aplicação. As rotas ficam em `web/routes/`, separadas por assunto."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cortago import config, db, worker
from cortago.web.common import HERE
from cortago.web.routes import clips, library, media, timeline, videos


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.engine()
    config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
    worker.recover()
    yield


app = FastAPI(title="CortaGo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
for module in (videos, clips, timeline, library, media):
    app.include_router(module.router)
