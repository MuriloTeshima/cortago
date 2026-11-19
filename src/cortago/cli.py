"""CLI: `cortago serve` (interface web) e `cortago run` (processa direto no terminal)."""

import time

import typer
from rich.console import Console
from rich.table import Table

from cortago import config, db, pipeline, timecode
from cortago.db import ClipStatus

app = typer.Typer(add_completion=False, help="Gera Shorts automaticamente a partir de vídeos longos.")
console = Console()


@app.callback()
def main() -> None:
    pass


@app.command()
def doctor() -> None:
    """Mostra o que foi detectado neste computador e o que está faltando."""
    import os
    import platform
    import subprocess

    from cortago import hardware, music

    table = Table("Item", "Situação", show_header=False)
    ok, bad = "[green]✓[/]", "[red]✗[/]"
    problems = 0

    table.add_row("Sistema", f"{platform.system()} {platform.release()} ({platform.machine()})")

    ffmpeg = hardware.ffmpeg_path()
    if ffmpeg:
        filters = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
        has_ass = " ass " in filters
        table.add_row(
            "FFmpeg", f"{ok} {ffmpeg}" + ("" if has_ass else f"  {bad} sem libass (legendas não funcionam)")
        )
        problems += not has_ass
        table.add_row("Encoder de vídeo", hardware.video_encoder())
    else:
        table.add_row("FFmpeg", f"{bad} não encontrado no PATH (veja o README)")
        problems += 1

    setup = hardware.whisper_setup()
    device = {"apple-gpu": "GPU Apple", "cuda": "GPU NVIDIA", "cpu": "CPU (mais lento)"}[setup.device]
    table.add_row("Transcrição", f"{setup.backend} · {device} · {setup.model}")

    has_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    table.add_row("Chave da API do Claude", ok if has_key else f"{bad} defina ANTHROPIC_API_KEY no .env")
    problems += not has_key

    tracks = music.tracks()
    table.add_row("Músicas de fundo", f"{len(tracks)} em {config.MUSIC_DIR}")
    console.print(table)
    if problems:
        console.print(f"[red]{problems} problema(s) para resolver.[/]")
        raise typer.Exit(1)
    console.print("[green]Tudo pronto.[/]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Use 0.0.0.0 para acessar de outros aparelhos da rede"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False, help="Recarrega ao editar o código (desenvolvimento)"),
) -> None:
    """Abre a interface web."""
    import uvicorn

    console.print(f"CortaGo em [bold]http://{host}:{port}[/]")
    uvicorn.run("cortago.web.app:app", host=host, port=port, reload=reload, log_level="info")


@app.command()
def run(
    source: str = typer.Argument(
        ..., help="URL do vídeo (YouTube, Twitch VOD...) ou caminho de arquivo local"
    ),
    clips: int = typer.Option(5, "--clips", "-n", help="Quantidade máxima de cortes"),
    layout: str = typer.Option(
        "blur", help="blur (vídeo inteiro + fundo desfocado) ou crop (corta o centro)"
    ),
    language: str = typer.Option(None, "--lang", help="Idioma do áudio (pt, en...). Vazio = detectar"),
    min_seconds: int = typer.Option(20, "--min", help="Duração mínima do corte"),
    max_seconds: int = typer.Option(60, "--max", help="Duração máxima do corte"),
    music: bool = typer.Option(True, help="Música de fundo sorteada da biblioteca (CORTAGO_MUSIC_DIR)"),
    inicio: str = typer.Option(None, "--inicio", help="Processa só a partir deste ponto (ex.: 1:20:00)"),
    fim: str = typer.Option(None, "--fim", help="Processa só até este ponto (ex.: 2:00:00)"),
    gameplay: str = typer.Option(
        None, "--gameplay", help="Link ou arquivo de gameplay para alternar com quem fala (sem som)"
    ),
) -> None:
    """Processa um vídeo direto no terminal. O resultado também aparece na interface web."""
    try:
        job = pipeline.create_job(
            source,
            layout=layout,
            max_clips=clips,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            language=language,
            music=music,
            range_start=timecode.parse(inicio),
            range_end=timecode.parse(fim),
            gameplay_source=gameplay,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    t0 = time.time()
    try:
        with console.status("Começando...") as status:
            job = pipeline.run_job(job.id, log=status.update)  # type: ignore[arg-type]
    except Exception:
        failed = db.get_job(job.id)  # type: ignore[arg-type]
        console.print(f"[red]Falhou:[/] {failed.error if failed else 'erro desconhecido'}")
        raise typer.Exit(1) from None

    table = Table("#", "Nota", "Duração", "Título", "Por quê")
    for c in db.job_clips(job.id):  # type: ignore[arg-type]
        if c.status != ClipStatus.DISCARDED:
            table.add_row(str(c.position), str(c.score), f"{c.duration:.0f}s", c.title, c.reason)
    console.print(table)
    console.print(
        f"\n[bold green]Pronto em {time.time() - t0:.0f}s[/] → {pipeline.job_dir(job) / 'clips'}"
        f"\n[dim]{job.input_tokens} tokens de entrada / {job.output_tokens} de saída[/]"
    )


if __name__ == "__main__":
    app()
