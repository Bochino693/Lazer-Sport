/* ======================================================================
   OS ADESIVOS NOS CARDS (LEIA-ME, seção 72)

   O produto com adesivos (a mesma máquina com outra arte: Air Game Kids,
   "Astronautas" e "Alienígenas") aparece num card só, e o card reveza a
   capa de cada adesivo -- "rodando as duas imagens". O selo "2 adesivos"
   (core/templatetags/adesivos.py) traz a lista das capas; aqui a foto do
   card troca de uma para a outra, com um esmaecer curto, só enquanto o card
   está na tela e a aba à vista. Com "reduzir movimento", não troca.
   ====================================================================== */
(function () {
  "use strict";

  const INTERVALO = 2600;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const cards = new Map(); // o selo -> { foto, capas, indice, visivel }

  const trocar = (estado) => {
    const { foto, capas } = estado;
    estado.indice = (estado.indice + 1) % capas.length;
    const proxima = capas[estado.indice];
    const pre = new Image();
    pre.decoding = "async";
    pre.onload = () => {
      foto.classList.add("card-adesivos-troca");
      window.setTimeout(() => {
        foto.removeAttribute("srcset");
        foto.src = proxima;
        foto.classList.remove("card-adesivos-troca");
      }, 220);
    };
    pre.src = proxima;
  };

  const vigia = "IntersectionObserver" in window
    ? new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        const estado = cards.get(e.target);
        if (estado) estado.visivel = e.isIntersecting;
      });
    }, { rootMargin: "100px 0px" })
    : null;

  const procurar = (raiz) => {
    raiz.querySelectorAll("[data-adesivos-capas]").forEach((selo) => {
      if (cards.has(selo)) return;
      let capas = [];
      try { capas = JSON.parse(selo.dataset.adesivosCapas || "[]"); } catch (erro) { capas = []; }
      const foto = selo.parentElement && selo.parentElement.querySelector("img");
      if (!foto || capas.length < 2) return;
      // a primeira capa é a que o card já mostra
      foto.style.transition = "opacity .22s ease";
      cards.set(selo, { foto, capas, indice: 0, visivel: !vigia });
      if (vigia) vigia.observe(selo);
    });
  };

  const comecar = () => {
    procurar(document);
    window.setInterval(() => {
      if (document.hidden) return;
      cards.forEach((estado) => { if (estado.visivel) trocar(estado); });
    }, INTERVALO);
    let agendado = 0;
    new MutationObserver(() => {
      if (agendado) return;
      agendado = window.setTimeout(() => { agendado = 0; procurar(document); }, 150);
    }).observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", comecar);
  else comecar();
})();
