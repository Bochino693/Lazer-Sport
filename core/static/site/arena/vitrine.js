/* A vitrine de fotos da arena: filtro por categoria e troca de foto.

   Mouse: a posição em cima da foto escolhe o lado (esquerda = primeira
   foto, direita = última), como nas lojas grandes. Dedo: arrastar de lado
   passa a foto, e o arrasto não vira clique no link. */

const grade = document.querySelector("[data-fotos-grade]");

if (grade) {
  const cartoes = Array.from(grade.querySelectorAll("[data-fotos-cartao]"));

  const mostrar = (midia, indice) => {
    const fotos = midia.querySelectorAll("img");
    if (fotos.length < 2) return;
    const alvo = (indice + fotos.length) % fotos.length;
    if (Number(midia.dataset.foto || 0) === alvo) return;
    midia.dataset.foto = String(alvo);
    fotos.forEach((foto, i) => foto.classList.toggle("ativa", i === alvo));
    midia.querySelectorAll(".arena-foto-pontos i").forEach((ponto, i) => ponto.classList.toggle("ativo", i === alvo));
  };

  cartoes.forEach((cartao) => {
    const midia = cartao.querySelector(".arena-foto-midia");
    if (!midia || midia.querySelectorAll("img").length < 2) return;
    let inicio = null;
    let arrastou = false;

    midia.addEventListener("pointermove", (evento) => {
      if (evento.pointerType !== "mouse") return;
      const caixa = midia.getBoundingClientRect();
      const total = midia.querySelectorAll("img").length;
      mostrar(midia, Math.min(total - 1, Math.floor(((evento.clientX - caixa.left) / caixa.width) * total)));
    });
    midia.addEventListener("pointerleave", (evento) => {
      if (evento.pointerType === "mouse") mostrar(midia, 0);
    });

    midia.addEventListener("pointerdown", (evento) => {
      if (evento.pointerType === "mouse") return;
      inicio = { x: evento.clientX, y: evento.clientY };
      arrastou = false;
    });
    midia.addEventListener("pointerup", (evento) => {
      if (!inicio) return;
      const dx = evento.clientX - inicio.x;
      const dy = evento.clientY - inicio.y;
      inicio = null;
      if (Math.abs(dx) > 28 && Math.abs(dx) > Math.abs(dy)) {
        arrastou = true;
        mostrar(midia, Number(midia.dataset.foto || 0) + (dx < 0 ? 1 : -1));
      }
    });
    midia.addEventListener("pointercancel", () => { inicio = null; });
    midia.addEventListener("click", (evento) => {
      if (arrastou) {
        evento.preventDefault();
        arrastou = false;
      }
    });
  });

  const filtros = document.querySelector("[data-fotos-filtros]");
  if (filtros) {
    filtros.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-fotos-categoria]");
      if (!botao) return;
      const categoria = botao.dataset.fotosCategoria;
      filtros.querySelectorAll("[data-fotos-categoria]").forEach((b) => {
        const ativo = b === botao;
        b.classList.toggle("ativo", ativo);
        b.setAttribute("aria-pressed", ativo ? "true" : "false");
      });
      cartoes.forEach((cartao) => {
        const lista = (cartao.dataset.categorias || "").split("|");
        cartao.hidden = Boolean(categoria) && !lista.includes(categoria);
      });
    });
  }
}
