"""CLI: cortago run <url-ou-arquivo>"""

import json
import time

import typer
from rich.console import Console
from rich.table import Table

from cortago import config, download, highlights, render, subtitles, transcribe

app = typer.Typer(add_completion=False, help="Gera Shorts automaticamente a partir de um vídeo.")
console = Console()


@app.callback()
def main() -> None:
    pass


def _slug(text: str) -> str:
    return download._slug(text)[:40]


def _metadata(clip: highlights.Clip, source: download.SourceInfo) -> str:
    credit = f"Créditos: {source.channel}" + (f" — {source.url}" if source.url else "")
    tags = " ".join(f"#{t.lstrip('#')}" for t in clip.hashtags)
    return f"{clip.title}\n\n{clip.description}\n\n{credit}\n\n{tags}\n"


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
    reselect: bool = typer.Option(False, help="Pede nova seleção ao Claude mesmo se já existir"),
) -> None:
    if layout not in ("blur", "crop"):
        raise typer.BadParameter("layout deve ser 'blur' ou 'crop'")

    t0 = time.time()
    with console.status("Baixando vídeo..."):
        info = download.fetch(source, config.JOBS_DIR)
    job = info.path.parent
    console.print(f"[green]✓[/] {info.title} ({info.duration / 60:.1f} min) → {job}")

    with console.status("Transcrevendo (mlx-whisper)..."):
        tr = transcribe.transcribe(info.path, job / "transcript.json", language)
    console.print(f"[green]✓[/] Transcrição: {len(tr.words)} palavras, idioma {tr.language}")

    clips_file = job / "clips.json"
    if clips_file.exists() and not reselect:
        picked = [highlights.Clip.model_validate(c) for c in json.loads(clips_file.read_text())]
        console.print(f"[green]✓[/] Usando seleção salva ({len(picked)} cortes). Use --reselect pra refazer.")
    else:
        with console.status(f"Claude escolhendo cortes ({config.CLAUDE_MODEL})..."):
            picked, usage = highlights.pick_clips(info, tr, clips, min_seconds, max_seconds)
        clips_file.write_text(json.dumps([c.model_dump() for c in picked], ensure_ascii=False, indent=2))
        console.print(
            f"[green]✓[/] {len(picked)} cortes escolhidos "
            f"(tokens: {usage.input_tokens} entrada / {usage.output_tokens} saída)"
        )

    out_dir = job / "clips"
    out_dir.mkdir(exist_ok=True)
    for i, clip in enumerate(picked, 1):
        name = f"{i:02d}_{_slug(clip.title)}"
        ass = out_dir / f"{name}.ass"
        subtitles.write_ass(tr.words, clip.start, clip.end, clip.hook, ass)
        with console.status(f"Renderizando {i}/{len(picked)}..."):
            render.render_clip(info.path, clip.start, clip.end, ass, out_dir / f"{name}.mp4", layout)  # type: ignore[arg-type]
        (out_dir / f"{name}.txt").write_text(_metadata(clip, info), encoding="utf-8")

    table = Table("#", "Nota", "Duração", "Título", "Por quê")
    for i, c in enumerate(picked, 1):
        table.add_row(str(i), str(c.score), f"{c.end - c.start:.0f}s", c.title, c.reason)
    console.print(table)
    console.print(f"\n[bold green]Pronto em {time.time() - t0:.0f}s[/] → {out_dir}")


if __name__ == "__main__":
    app()
