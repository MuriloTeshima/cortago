"""Parar o processamento de um vídeo em qualquer etapa.

Cada tarefa do worker roda num "escopo" do vídeo (job). Pedir para parar invalida todos os escopos já criados
para aquele vídeo: a tarefa em andamento para no próximo ponto de verificação e as que estão na fila nem
começam. Tarefas enfileiradas depois do pedido valem normalmente.

Pontos de verificação: entre as etapas e entre cortes (`check`) e na resposta do Claude (streaming). Download e
transcrição rodam num processo separado (`call`) e o FFmpeg via `run`: os dois são encerrados na hora.

Fora do worker (CLI) não há escopo: as verificações não fazem nada e o Ctrl+C continua valendo.
"""

import subprocess
import threading
from contextlib import contextmanager

POLL_SECONDS = 0.3


class Cancelled(Exception):
    """O usuário pediu para parar."""

    def __init__(self, message: str = "Parado pelo usuário") -> None:
        super().__init__(message)


_lock = threading.Lock()
_generation: dict[int, int] = {}
_local = threading.local()


def token(job_id: int) -> int:
    """Versão atual do vídeo; tarefas criadas agora guardam este número."""
    with _lock:
        return _generation.get(job_id, 0)


def request(job_id: int) -> None:
    """Para tudo o que já foi criado para este vídeo (em andamento e na fila)."""
    with _lock:
        _generation[job_id] = _generation.get(job_id, 0) + 1


def is_cancelled(job_id: int, tok: int) -> bool:
    with _lock:
        return _generation.get(job_id, 0) != tok


@contextmanager
def scope(job_id: int, tok: int):
    """Marca a thread atual como trabalhando para `job_id` (criado com `tok`)."""
    previous = getattr(_local, "current", None)
    _local.current = (job_id, tok)
    try:
        yield
    finally:
        _local.current = previous


def current() -> tuple[int, int] | None:
    return getattr(_local, "current", None)


def requested() -> bool:
    cur = current()
    return cur is not None and is_cancelled(*cur)


def check() -> None:
    """Levanta `Cancelled` se pediram para parar o vídeo desta tarefa."""
    if requested():
        raise Cancelled()


def _child(conn, fn, args) -> None:
    try:
        conn.send((True, fn(*args)))
    except BaseException as exc:  # noqa: BLE001 — devolve qualquer erro para o processo principal
        try:
            conn.send((False, exc))
        except Exception:  # erro que não dá para serializar
            conn.send((False, RuntimeError(f"{type(exc).__name__}: {exc}")))
    finally:
        conn.close()


def _stop(proc) -> None:
    proc.terminate()
    proc.join(5)
    if proc.is_alive():
        proc.kill()
        proc.join()


def call(fn, *args):
    """Roda `fn(*args)` num processo separado para poder encerrá-lo na hora (download, transcrição).

    `fn` precisa ser uma função de módulo e o resultado, serializável. Fora do worker roda direto.
    """
    if current() is None:
        return fn(*args)
    check()
    import multiprocessing as mp

    ctx = mp.get_context("spawn")  # igual em macOS, Windows e Linux; não herda threads nem locks
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, fn, args), daemon=True)
    proc.start()
    child.close()
    try:
        while True:
            # Lê antes de esperar o fim: um resultado grande trava o filho até alguém ler o pipe.
            if parent.poll(POLL_SECONDS):
                ok, value = parent.recv()
                proc.join()
                break
            if requested():
                _stop(proc)
                raise Cancelled()
            if not proc.is_alive() and not parent.poll():
                raise RuntimeError(f"o processo terminou sem resposta (código {proc.exitcode})")
    finally:
        parent.close()
    if ok:
        return value
    raise value


def run(
    cmd: list[str], *, check: bool = False, text: bool = False, cwd=None, **kwargs
) -> subprocess.CompletedProcess:
    """Como `subprocess.run(..., capture_output=True)`, mas encerra o processo se pedirem para parar."""
    if text:
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text, cwd=cwd, **kwargs
    ) as proc:
        while True:
            try:
                out, err = proc.communicate(timeout=POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                if requested():
                    proc.kill()
                    proc.communicate()
                    raise Cancelled() from None
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, cmd, out, err)
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
