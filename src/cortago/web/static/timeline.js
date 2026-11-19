// Timeline do editor de corte: trechos que entram no vídeo, correção de legenda e prévia sem render.
// Tempos em segundos do arquivo baixado; a régua mostra o tempo do vídeo original (+ offset).

const MIN_SEGMENT = 0.12;
const SNAP_SECONDS = 0.12;
const ZOOM_LEVELS = [20, 35, 60, 100, 160];

function fmt(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") Object.assign(node.style, v);
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  node.append(...children);
  return node;
}

class Timeline {
  constructor(root) {
    this.root = root;
    this.clipId = root.dataset.clip;
    this.zoom = 2;
    this.load();
  }

  async load() {
    this.root.classList.add("loading");
    const res = await fetch(`/clips/${this.clipId}/timeline.json`);
    if (!res.ok) {
      this.root.textContent = "Não foi possível carregar a timeline.";
      return;
    }
    this.data = await res.json();
    this.segments = this.data.segments.map((s) => [...s]);
    this.gpBlocks = (this.data.gameplay?.blocks || []).map((b) => ({ ...b }));
    this.fixes = {};
    for (const w of this.data.words) if (w.text !== w.original) this.fixes[w.key] = w.text;
    this.dirty = false;
    this.root.classList.remove("loading");
    this.build();
  }

  // ---------- geometria ----------

  get pps() {
    return ZOOM_LEVELS[this.zoom];
  }
  x(t) {
    return (t - this.data.window[0]) * this.pps;
  }
  t(clientX) {
    const rect = this.inner.getBoundingClientRect();
    const t = this.data.window[0] + (clientX - rect.left) / this.pps;
    return Math.min(Math.max(t, this.data.window[0]), this.data.window[1]);
  }
  snap(t) {
    let best = t;
    let dist = SNAP_SECONDS;
    for (const w of this.data.words) {
      for (const edge of [w.start, w.end]) {
        if (Math.abs(edge - t) < dist) {
          dist = Math.abs(edge - t);
          best = edge;
        }
      }
    }
    return best;
  }
  total() {
    return this.segments.reduce((sum, [a, b]) => sum + (b - a), 0);
  }
  segmentAt(t) {
    return this.segments.findIndex(([a, b]) => t >= a && t < b);
  }

  // ---------- montagem ----------

  build() {
    const d = this.data;
    this.root.replaceChildren();
    this.status = el("span", { class: "tl-status small muted" });
    this.info = el("span", { class: "tl-info small" });
    this.clock = el("span", { class: "tl-clock small" }, "0:00");
    this.playBtn = el("button", { class: "btn small", type: "button", onclick: () => this.togglePlay() }, "▶ Prévia");
    this.saveBtn = el("button", { class: "btn small primary", type: "button", onclick: () => this.save() }, "Salvar e renderizar");

    const toolbar = el(
      "div",
      { class: "tl-toolbar" },
      this.playBtn,
      this.clock,
      this.info,
      el("span", { class: "tl-spacer" }),
      el("button", { class: "btn small", type: "button", title: "Divide o trecho na posição do cursor (atalho: S)", onclick: () => this.split() }, "Dividir no cursor"),
      el("button", { class: "btn small", type: "button", title: "Menos zoom", onclick: () => this.setZoom(-1) }, "−"),
      el("button", { class: "btn small", type: "button", title: "Mais zoom", onclick: () => this.setZoom(1) }, "+"),
      el("button", { class: "btn small", type: "button", onclick: () => this.reset(), title: "Descarta os ajustes da timeline" }, "Restaurar automático"),
      this.status,
      this.saveBtn,
    );

    this.video = el("video", { class: "tl-source", preload: "metadata", src: d.source, playsinline: "" });
    this.video.addEventListener("loadedmetadata", () => this.seek(this.segments[0][0]));
    this.video.addEventListener("play", () => (this.playBtn.textContent = "❚❚ Pausar"));
    this.video.addEventListener("pause", () => (this.playBtn.textContent = "▶ Prévia"));
    this.video.addEventListener("seeked", () => this.flushSeek());

    this.inner = el("div", { class: "tl-inner" });
    this.scroller = el("div", { class: "tl-scroller", tabindex: "0" }, this.inner);
    this.scroller.addEventListener("keydown", (e) => this.onKey(e));

    this.root.append(
      toolbar,
      el("div", { class: "tl-body" }, this.video, this.scroller),
      el(
        "p",
        { class: "muted small tl-help" },
        "Arraste as bordas dos trechos para ajustar (elas encaixam no começo/fim das palavras), × remove um trecho, ",
        "clique numa palavra para corrigir a legenda. Arraste a agulha (ou na régua, miniaturas e onda) para navegar; ",
        "← → movem 1s (Shift: 0,1s), Espaço toca/pausa, S divide.",
        this.gpBlocks.length ? " Na última linha, clique num bloco para trocar entre quem fala e a gameplay." : "",
      ),
    );
    this.drawTracks();
    this.updateInfo();
    // Abre já mostrando o começo do corte (a janela tem margem antes dele).
    requestAnimationFrame(() => (this.scroller.scrollLeft = Math.max(this.x(this.segments[0][0]) - 60, 0)));
    if (!this.ticking) {
      this.ticking = true; // um único ciclo de atualização, mesmo recarregando a timeline
      requestAnimationFrame(() => this.tick());
    }
  }

  drawTracks() {
    const d = this.data;
    const [lo, hi] = d.window;
    this.inner.replaceChildren();
    this.inner.style.width = `${(hi - lo) * this.pps}px`;

    const ruler = el("div", { class: "tl-ruler" });
    const step = this.pps >= 60 ? 1 : this.pps >= 35 ? 2 : 5;
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
      const major = Math.round(t) % (step * 5) === 0;
      ruler.append(
        el("span", { class: `tl-tick${major ? " major" : ""}`, style: { left: `${this.x(t)}px` } }, major ? fmt(t + d.offset) : ""),
      );
    }
    ruler.addEventListener("pointerdown", (e) => this.scrub(e));

    const strip = el("div", { class: "tl-row tl-strip", style: { backgroundImage: `url("${d.filmstrip}")` } });
    const wave = el("div", { class: "tl-row tl-wave", style: { backgroundImage: `url("${d.waveform}")` } });
    for (const row of [strip, wave]) row.addEventListener("pointerdown", (e) => this.scrub(e));

    this.segRow = el("div", { class: "tl-row tl-segs" });
    this.wordRow = el("div", { class: "tl-row tl-words" });
    // Agulha: a linha não captura cliques (deixa as bordas dos trechos clicáveis), só a cabeça.
    const knob = el("span", { class: "tl-knob", title: "Arraste para navegar (← → movem 1s; Shift: 0,1s)" });
    knob.addEventListener("pointerdown", (e) => this.scrub(e));
    this.playhead = el("div", { class: "tl-playhead" }, knob);
    this.inner.append(ruler, strip, wave, this.segRow, this.wordRow);
    if (this.gpBlocks.length) {
      this.gpRow = el("div", { class: "tl-row tl-gp" });
      this.inner.append(this.gpRow);
    } else this.gpRow = null;
    this.inner.append(this.playhead);
    this.drawSegments();
    this.drawWords();
    this.drawGameplay();
  }

  drawSegments() {
    this.segRow.replaceChildren();
    this.segments.forEach(([a, b], i) => {
      if (i > 0) {
        const prevEnd = this.segments[i - 1][1];
        if (a > prevEnd) {
          this.segRow.append(el("div", { class: "tl-gap", title: "Removido", style: { left: `${this.x(prevEnd)}px`, width: `${this.x(a) - this.x(prevEnd)}px` } }));
        }
      }
      const block = el(
        "div",
        { class: "tl-seg", style: { left: `${this.x(a)}px`, width: `${this.x(b) - this.x(a)}px` }, title: `${fmt(a + this.data.offset)}–${fmt(b + this.data.offset)}` },
        el("span", { class: "tl-handle left" }),
        el("span", { class: "tl-handle right" }),
      );
      if (this.segments.length > 1) {
        block.append(
          el("button", { class: "tl-del", type: "button", title: "Remover este trecho", onclick: (e) => { e.stopPropagation(); this.remove(i); } }, "×"),
        );
      }
      block.querySelector(".left").addEventListener("pointerdown", (e) => this.drag(e, i, 0));
      block.querySelector(".right").addEventListener("pointerdown", (e) => this.drag(e, i, 1));
      block.addEventListener("pointerdown", (e) => {
        if (!e.target.classList.contains("tl-handle") && !e.target.classList.contains("tl-del")) this.scrub(e);
      });
      this.segRow.append(block);
    });
    this.drawWordState();
  }

  drawWords() {
    this.wordRow.replaceChildren();
    this.wordEls = this.data.words.map((w) => {
      const chip = el(
        "button",
        { class: "tl-word", type: "button", title: w.original === (this.fixes[w.key] ?? w.text) ? w.original : `${w.original} → ${this.fixes[w.key] ?? w.text}`, style: { left: `${this.x(w.start)}px`, width: `${Math.max(this.x(w.end) - this.x(w.start), 6)}px` } },
        this.fixes[w.key] ?? w.original,
      );
      chip.addEventListener("click", () => this.editWord(w, chip));
      this.wordRow.append(chip);
      return chip;
    });
    this.drawWordState();
  }

  // Linha "Gameplay": cada bloco de frase mostra quem fala ou a gameplay. Clique troca.
  drawGameplay() {
    if (!this.gpRow) return;
    this.gpRow.replaceChildren();
    this.gpBlocks.forEach((b) => {
      const chip = el(
        "button",
        {
          class: `tl-gp-block${b.on ? " on" : ""}`,
          type: "button",
          title: `${fmt(b.start + this.data.offset)}–${fmt(b.end + this.data.offset)} · clique para trocar`,
          style: { left: `${this.x(b.start)}px`, width: `${Math.max(this.x(b.end) - this.x(b.start) - 2, 4)}px` },
        },
        b.on ? "Gameplay" : "Quem fala",
      );
      chip.addEventListener("click", () => {
        b.on = !b.on;
        this.changed();
        this.drawGameplay();
      });
      this.gpRow.append(chip);
    });
  }

  drawWordState() {
    if (!this.wordEls) return;
    this.data.words.forEach((w, i) => {
      const mid = (w.start + w.end) / 2;
      this.wordEls[i].classList.toggle("out", this.segmentAt(mid) < 0);
      this.wordEls[i].classList.toggle("fixed", w.key in this.fixes);
    });
  }

  // ---------- edição ----------

  drag(event, index, side) {
    event.preventDefault();
    event.stopPropagation();
    const handle = event.target;
    handle.setPointerCapture(event.pointerId);
    const move = (e) => {
      const seg = this.segments[index];
      const prev = this.segments[index - 1];
      const next = this.segments[index + 1];
      let t = this.snap(this.t(e.clientX));
      if (side === 0) t = Math.min(Math.max(t, prev ? prev[1] : this.data.window[0]), seg[1] - MIN_SEGMENT);
      else t = Math.max(Math.min(t, next ? next[0] : this.data.window[1]), seg[0] + MIN_SEGMENT);
      seg[side] = Math.round(t * 1000) / 1000;
      this.changed();
      this.drawSegments();
    };
    const up = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
  }

  // Arrastar a agulha (ou clicar e arrastar na régua, miniaturas, onda ou trechos).
  // A agulha segue o ponteiro na hora; o vídeo busca o quadro sem enfileirar buscas.
  scrub(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    this.scroller.focus({ preventScroll: true });
    const resume = !this.video.paused;
    if (resume) this.video.pause();
    this.root.classList.add("scrubbing");
    let lastX = event.clientX;
    let edgeTimer = null;
    const go = (clientX) => {
      this.scrubTime = this.t(clientX);
      this.render(this.scrubTime);
      this.requestSeek(this.scrubTime, true);
    };
    // Perto das bordas da área visível, rola a timeline para continuar arrastando.
    const edgeScroll = () => {
      const r = this.scroller.getBoundingClientRect();
      const margin = 40;
      const dx = lastX < r.left + margin ? lastX - (r.left + margin) : lastX > r.right - margin ? lastX - (r.right - margin) : 0;
      if (dx) {
        this.scroller.scrollLeft += Math.max(-30, Math.min(30, dx / 2));
        go(lastX);
      }
      edgeTimer = requestAnimationFrame(edgeScroll);
    };
    const move = (e) => {
      lastX = e.clientX;
      go(e.clientX);
      if (edgeTimer === null) edgeTimer = requestAnimationFrame(edgeScroll); // só depois de mexer
    };
    const up = () => {
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", up);
      target.removeEventListener("pointercancel", up);
      cancelAnimationFrame(edgeTimer);
      this.root.classList.remove("scrubbing");
      const t = this.scrubTime;
      this.scrubTime = null;
      this.requestSeek(t, false); // busca exata no fim do arraste
      if (resume) this.video.play();
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", up);
    target.addEventListener("pointercancel", up);
    go(event.clientX);
  }

  // Uma busca por vez: enquanto o vídeo ainda busca, guarda só o último tempo pedido.
  requestSeek(t, fast) {
    this.pendingSeek = { t, fast };
    if (this.video.seeking) return;
    this.flushSeek();
  }
  flushSeek() {
    const p = this.pendingSeek;
    if (!p) return;
    this.pendingSeek = null;
    if (p.fast && this.video.fastSeek) this.video.fastSeek(p.t);
    else this.video.currentTime = p.t;
  }

  nudge(seconds) {
    const [lo, hi] = this.data.window;
    const now = this.pendingSeek ? this.pendingSeek.t : this.video.currentTime; // busca ainda em curso
    const t = Math.min(Math.max(now + seconds, lo), hi);
    this.seek(t);
    this.render(t);
    const x = this.x(t);
    if (x < this.scroller.scrollLeft || x > this.scroller.scrollLeft + this.scroller.clientWidth) {
      this.scroller.scrollLeft = x - this.scroller.clientWidth / 2;
    }
  }

  split() {
    const t = this.video.currentTime;
    const i = this.segmentAt(t);
    if (i < 0) return toast("Posicione o cursor dentro de um trecho para dividir", "error");
    const [a, b] = this.segments[i];
    if (t - a < MIN_SEGMENT || b - t < MIN_SEGMENT) return toast("O cursor está muito perto da borda do trecho", "error");
    this.segments.splice(i, 1, [a, t], [t, b]);
    this.changed();
    this.drawSegments();
  }

  remove(i) {
    this.segments.splice(i, 1);
    this.changed();
    this.drawSegments();
  }

  editWord(word, chip) {
    const current = this.fixes[word.key] ?? word.original;
    const input = el("input", { class: "tl-word-input", value: current, maxlength: "40" });
    input.style.left = chip.style.left;
    chip.replaceWith(input);
    input.focus();
    input.select();
    let done = false;
    const finish = (commit) => {
      if (done) return;
      done = true;
      const text = input.value.trim();
      if (commit && text) {
        if (text === word.original) delete this.fixes[word.key];
        else this.fixes[word.key] = text;
        this.changed();
      }
      this.drawWords();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") finish(true);
      if (e.key === "Escape") finish(false);
      e.stopPropagation();
    });
    input.addEventListener("blur", () => finish(true));
  }

  setZoom(delta) {
    const center = this.video.currentTime;
    this.zoom = Math.min(Math.max(this.zoom + delta, 0), ZOOM_LEVELS.length - 1);
    this.drawTracks();
    this.scroller.scrollLeft = this.x(center) - this.scroller.clientWidth / 2;
  }

  onKey(e) {
    if (e.key === " ") {
      e.preventDefault();
      this.togglePlay();
    } else if (e.key.toLowerCase() === "s") {
      this.split();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      this.nudge((e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 0.1 : 1));
    }
  }

  changed() {
    this.dirty = true;
    this.updateInfo();
  }

  updateInfo() {
    const total = this.total();
    const n = this.segments.length;
    const over = total > this.data.max_seconds;
    const first = this.segments[0][0] + this.data.offset;
    const last = this.segments[n - 1][1] + this.data.offset;
    this.info.textContent = `${fmt(first)}–${fmt(last)} · ${total.toFixed(1)}s em ${n} trecho${n > 1 ? "s" : ""}`;
    this.info.classList.toggle("warn", over);
    this.saveBtn.disabled = !this.dirty || over;
    this.status.textContent = over
      ? `máximo de ${this.data.max_seconds}s`
      : this.dirty
        ? "alterações não salvas"
        : this.data.manual
          ? "ajustado à mão"
          : "automático";
  }

  // ---------- prévia ----------

  seek(t) {
    this.requestSeek(t, false);
  }

  // Posiciona a agulha e o relógio (durante o arraste, no tempo do ponteiro, não do vídeo).
  render(t) {
    if (this.playhead) this.playhead.style.transform = `translateX(${this.x(t)}px)`;
    this.clock.textContent = fmt(t + this.data.offset);
  }

  togglePlay() {
    if (!this.video.paused) return this.video.pause();
    if (this.segmentAt(this.video.currentTime) < 0) this.seek(this.segments[0][0]);
    this.video.play();
  }

  tick() {
    if (!this.root.isConnected) return; // saiu da página
    if (this.scrubTime != null) {
      requestAnimationFrame(() => this.tick());
      return; // durante o arraste quem posiciona a agulha é o ponteiro
    }
    const t = this.pendingSeek ? this.pendingSeek.t : this.video.currentTime;
    if (!this.video.paused && this.segmentAt(t) < 0) {
      // Pula as partes removidas, como no vídeo final.
      const next = this.segments.find(([a]) => a > t);
      if (next) this.seek(next[0]);
      else {
        this.video.pause();
        this.seek(this.segments[0][0]);
      }
    }
    this.render(t);
    if (this.playhead) {
      const x = this.x(t);
      if (!this.video.paused && (x < this.scroller.scrollLeft || x > this.scroller.scrollLeft + this.scroller.clientWidth - 40)) {
        this.scroller.scrollLeft = x - 40;
      }
    }
    requestAnimationFrame(() => this.tick());
  }

  // ---------- salvar ----------

  async save() {
    this.saveBtn.disabled = true;
    this.status.textContent = "salvando…";
    const res = await fetch(`/clips/${this.clipId}/timeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        segments: this.segments,
        words: this.fixes,
        ...(this.gpRow ? { gameplay: this.gpBlocks.filter((b) => b.on).map((b) => [b.start, b.end]) } : {}),
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      toast(typeof body.detail === "string" ? body.detail : "Não foi possível salvar", "error");
      this.updateInfo();
      return;
    }
    toast("Timeline salva — renderizando o vídeo");
    this.afterSave();
  }

  async reset() {
    const res = await fetch(`/clips/${this.clipId}/timeline/restaurar`, { method: "POST" });
    if (!res.ok) return toast("Não foi possível restaurar", "error");
    toast("Timeline restaurada para o automático");
    this.afterSave();
  }

  afterSave() {
    if (window.htmx) htmx.ajax("GET", `/clips/${this.clipId}/player`, { target: "#player", swap: "outerHTML" });
    this.video.pause();
    this.load();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-timeline]").forEach((root) => new Timeline(root));
});
