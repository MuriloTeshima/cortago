function toast(message, kind = "info") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `show ${kind}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => (el.className = ""), 3500);
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const source = document.querySelector(button.dataset.copy);
  await navigator.clipboard.writeText(source.value);
  toast(button.dataset.copyLabel || "Texto copiado");
  const original = button.textContent;
  button.textContent = "Copiado ✓";
  setTimeout(() => (button.textContent = original), 1500);
});

document.addEventListener("htmx:responseError", (event) => {
  let message = "Algo deu errado";
  try {
    const body = JSON.parse(event.detail.xhr.responseText);
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail)) message = "Verifique os campos do formulário";
  } catch {}
  toast(message, "error");
});

document.addEventListener("htmx:sendError", () => toast("Servidor fora do ar?", "error"));

// Prévia da música escolhida na edição do corte.
document.addEventListener("change", (event) => {
  const select = event.target.closest("[data-music-preview]");
  if (!select) return;
  const audio = document.querySelector(select.dataset.musicPreview);
  const option = select.selectedOptions[0];
  const track = option && !option.disabled && select.value !== "__none__" ? select.value : null;
  audio.pause();
  if (track) {
    audio.src = "/music/" + encodeURIComponent(track);
    audio.hidden = false;
    audio.play().catch(() => {});
  } else {
    audio.removeAttribute("src");
    audio.hidden = true;
  }
});

// Só uma música tocando por vez.
document.addEventListener("play", (event) => {
  if (event.target.tagName !== "AUDIO") return;
  document.querySelectorAll("audio").forEach((a) => a !== event.target && a.pause());
}, true);

// Prévia do som do gancho ao escolher no seletor.
document.addEventListener("change", (event) => {
  const select = event.target.closest("[data-sfx-preview]");
  if (!select || select.value === "none") return;
  new Audio("/sfx/" + select.value + ".wav").play().catch(() => {});
});

// Abas do editor de corte. A aba ativa fica no endereço (#audio), então recarregar ou voltar mantém o lugar.
function applyTab() {
  const tabs = [...document.querySelectorAll("[data-tab]")];
  if (!tabs.length) return;
  const names = tabs.map((t) => t.dataset.tab);
  const wanted = location.hash.slice(1);
  const active = names.includes(wanted) ? wanted : names[0];
  tabs.forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === active)));
  document.querySelectorAll("[data-panel]").forEach((p) => (p.hidden = p.dataset.panel !== active));
}

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (!tab) return;
  history.replaceState(null, "", "#" + tab.dataset.tab);
  applyTab();
});

window.addEventListener("hashchange", applyTab);
document.addEventListener("DOMContentLoaded", applyTab);
// Seções trocadas pelo HTMX (inclusive fora da área alvo) voltam visíveis; reaplica a aba ativa.
document.addEventListener("htmx:afterSettle", applyTab);
