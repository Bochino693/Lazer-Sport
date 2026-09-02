/* O nome do ícone quando o menu está fechado.
   ==========================================================

   O menu fechado é uma coluna de 84px com onze ícones. Quem usa o
   painel todo dia reconhece todos; quem entrou esta semana não
   reconhece nenhum, e o remédio de sempre é o nome aparecer ao lado
   quando o ponteiro para em cima.

   Isso existia em CSS puro, num `::after` do próprio item, e nunca
   funcionou -- o item mora dentro do `.ls-nav`, que rola na vertical, e
   caixa que rola corta o que sai dela. O balão nascia dez pixels FORA e
   era aparado inteiro. Pior: por ser conteúdo largo dentro de uma caixa
   que rola, ele criava rolagem HORIZONTAL. Dava para arrastar o menu
   fechado para o lado e encontrar duzentos pixels de vazio.

   A saída é tirar o balão de dentro da caixa que rola: um elemento só,
   filho do `<body>`, preso à janela. Fora de qualquer scroller não há o
   que cortar. O preço é que a posição vertical passa a ser medida aqui,
   e não deduzida pelo CSS -- são as quatro linhas de `posicionar()`.
*/
(function (global, doc) {
  "use strict";

  var LARGURA_DO_TRILHO = 761;   // o mesmo corte do @media no CSS
  var FOLGA = 10;                // distância entre o ícone e o balão
  var dica = null;
  var alvo = null;

  function menuEmTrilho() {
    var lateral = doc.querySelector(".ls-sidebar");
    if (!lateral) return false;
    // Abaixo do corte a lateral vira gaveta com os nomes escritos, e
    // acima dele a classe `expandida` faz o mesmo: nos dois casos o nome
    // já está na tela e um balão repetindo-o só atrapalharia.
    if (global.innerWidth < LARGURA_DO_TRILHO) return false;
    return !lateral.classList.contains("expandida");
  }

  function caixa() {
    if (dica) return dica;
    dica = doc.createElement("div");
    dica.className = "ls-dica-trilho";
    // `aria-hidden` porque o nome JÁ é lido pelo leitor de tela: cada
    // item tem o texto dentro dele (o CSS só o esconde com `display`
    // quando o trilho está fechado... e `display:none` some da árvore de
    // acessibilidade). Por isso o item também carrega `aria-label` no
    // gabarito. Anunciar o balão seria repetir.
    dica.setAttribute("aria-hidden", "true");
    doc.body.appendChild(dica);
    return dica;
  }

  function posicionar(item) {
    var balao = caixa();
    balao.textContent = item.getAttribute("data-titulo") || item.textContent.trim();
    var r = item.getBoundingClientRect();
    // Mede depois de escrever o texto: a largura muda com ele.
    balao.style.left = Math.round(r.right + FOLGA) + "px";
    var altura = balao.offsetHeight;
    var topo = Math.round(r.top + (r.height - altura) / 2);
    // Não deixa escapar por cima nem por baixo da janela.
    topo = Math.max(6, Math.min(topo, global.innerHeight - altura - 6));
    balao.style.top = topo + "px";
    balao.classList.add("visivel");
  }

  function mostrar(item) {
    if (!menuEmTrilho()) return;
    alvo = item;
    posicionar(item);
  }

  function esconder() {
    alvo = null;
    if (dica) dica.classList.remove("visivel");
  }

  function itemDe(evento) {
    var no = evento.target;
    return no && no.closest ? no.closest(".ls-nav-item") : null;
  }

  doc.addEventListener("pointerover", function (evento) {
    // Só ponteiro de verdade. No toque o `pointerover` dispara junto com
    // o toque que já está navegando, e o balão apareceria durante a
    // troca de tela, sobre a tela nova.
    if (evento.pointerType === "touch") return;
    var item = itemDe(evento);
    if (item) mostrar(item); else if (alvo) esconder();
  }, true);

  doc.addEventListener("pointerout", function (evento) {
    if (alvo && itemDe(evento) === alvo) esconder();
  }, true);

  doc.addEventListener("focusin", function (evento) {
    var item = itemDe(evento);
    if (item) mostrar(item); else esconder();
  });

  doc.addEventListener("focusout", esconder);
  doc.addEventListener("click", esconder, true);

  // A posição foi MEDIDA, então ela envelhece: rolar o menu, rolar a
  // página, redimensionar ou abrir a lateral movem o item debaixo de um
  // balão que ficaria parado. Some, que é mais honesto do que remedir.
  global.addEventListener("resize", esconder);
  global.addEventListener("scroll", esconder, true);
})(window, document);
