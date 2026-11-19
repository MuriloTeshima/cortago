// Marcar a webcam: arraste sobre um quadro do vídeo para desenhar o retângulo da área da webcam.
// Guarda a área como fração do quadro (0–1) nos campos escondidos do formulário.

function initFacecam(root) {
  if (root.dataset.ready) return;
  root.dataset.ready = "1";
  const job = root.dataset.job;
  const img = root.querySelector("[data-facecam-img]");
  const stage = root.querySelector("[data-facecam-stage]");
  const box = root.querySelector("[data-facecam-rect]");
  const select = root.querySelector("[data-facecam-time]");
  const form = root.querySelector("form");
  const save = root.querySelector("[data-facecam-save]");
  const clear = root.querySelector("[data-facecam-clear]");
  const field = (k) => form.querySelector(`input[name="${k}"]`);
  let rect = root.dataset.rect ? JSON.parse(root.dataset.rect) : null;

  const draw = () => {
    box.hidden = !rect;
    if (!rect) return;
    Object.assign(box.style, {
      left: `${rect.x * 100}%`,
      top: `${rect.y * 100}%`,
      width: `${rect.w * 100}%`,
      height: `${rect.h * 100}%`,
    });
  };
  const store = () => {
    for (const k of ["x", "y", "w", "h"]) field(k).value = rect ? rect[k].toFixed(4) : "";
    save.disabled = !rect || rect.w < 0.03 || rect.h < 0.03;
  };
  const load = () => (img.src = `/media/${job}/quadro.jpg?t=${select.value}`);

  const point = (e) => {
    const r = img.getBoundingClientRect();
    return {
      x: Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1),
      y: Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1),
    };
  };
  stage.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    stage.setPointerCapture(e.pointerId);
    const a = point(e);
    const move = (ev) => {
      const b = point(ev);
      rect = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(b.x - a.x), h: Math.abs(b.y - a.y) };
      draw();
      store();
    };
    const up = () => {
      stage.removeEventListener("pointermove", move);
      stage.removeEventListener("pointerup", up);
    };
    stage.addEventListener("pointermove", move);
    stage.addEventListener("pointerup", up);
  });

  // "Tirar webcam": manda os campos vazios.
  clear?.addEventListener("click", () => {
    rect = null;
    for (const k of ["x", "y", "w", "h"]) field(k).value = "";
  });
  select.addEventListener("change", load);
  load();
  draw();
}

function initAllFacecams(scope) {
  (scope || document).querySelectorAll("[data-facecam]").forEach(initFacecam);
}

document.addEventListener("DOMContentLoaded", () => initAllFacecams());
// O painel do vídeo é trocado pelo HTMX (ao salvar, parar etc.): inicia o conteúdo novo.
document.addEventListener("htmx:load", (e) => initAllFacecams(e.target));
