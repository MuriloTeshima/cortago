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
  toast("Texto copiado");
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
