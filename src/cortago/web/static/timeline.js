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
        "clique numa palavra para corrigir a legenda e na régua para posicionar o cursor. Espaço toca/pausa.",
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
    ruler.addEventListener("pointerdown", (e) => this.seek(this.t(e.clientX)));

    const strip = el("div", { class: "tl-row tl-strip", style: { backgroundImage: `url("${d.filmstrip}")` } });
    const wave = el("div", { class: "tl-row tl-wave", style: { backgroundImage: `url("${d.waveform}")` } });
    for (const row of [strip, wave]) row.addEventListener("pointerdown", (e) => this.seek(this.t(e.clientX)));

    this.segRow = el("div", { class: "tl-row tl-segs" });
    this.wordRow = el("div", { class: "tl-row tl-words" });
    this.playhead = el("div", { class: "tl-playhead" });
    this.inner.append(ruler, strip, wave, this.segRow, this.wordRow, this.playhead);
    this.drawSegments();
    this.drawWords();
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
        if (!e.target.classList.contains("tl-handle") && !e.target.classList.contains("tl-del")) this.seek(this.t(e.clientX));
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
    this.video.currentTime = t;
  }

  togglePlay() {
    if (!this.video.paused) return this.video.pause();
    if (this.segmentAt(this.video.currentTime) < 0) this.seek(this.segments[0][0]);
    this.video.play();
  }

  tick() {
    if (!this.root.isConnected) return; // saiu da página
    const t = this.video.currentTime;
    if (!this.video.paused && this.segmentAt(t) < 0) {
      // Pula as partes removidas, como no vídeo final.
      const next = this.segments.find(([a]) => a > t);
      if (next) this.seek(next[0]);
      else {
        this.video.pause();
        this.seek(this.segments[0][0]);
      }
    }
    if (this.playhead) {
      const x = this.x(t);
      this.playhead.style.transform = `translateX(${x}px)`;
      if (!this.video.paused && (x < this.scroller.scrollLeft || x > this.scroller.scrollLeft + this.scroller.clientWidth - 40)) {
        this.scroller.scrollLeft = x - 40;
      }
    }
    this.clock.textContent = fmt(t + this.data.offset);
    requestAnimationFrame(() => this.tick());
  }

  // ---------- salvar ----------

  async save() {
    this.saveBtn.disabled = true;
    this.status.textContent = "salvando…";
    const res = await fetch(`/clips/${this.clipId}/timeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ segments: this.segments, words: this.fixes }),
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
