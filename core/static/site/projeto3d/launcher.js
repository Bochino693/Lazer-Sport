/* ======================================================================
   MONTE SEU ESPAÇO COMO UM LAUNCHER DE JOGOS
   (partials/projeto3d_app.html, projeto3d.css)

   O projeto3d.js cuida do 3D e das escolhas, igual sempre. Este arquivo só
   arruma a casa em volta dele:

     * AS ABAS (na Arena e na ficha do pedido no painel): um passo por vez
       -- Espaço, Modelo, Áreas, Máquinas, O que coube e Fotos --, com o
       "Voltar" e o "Próximo", o sinal de passo pronto, o que já foi
       escolhido embaixo do nome de cada aba e o resumo vivo da barra do
       topo (metros, uso, quantos itens), que chega pelo evento "p3d:mudou";

     * O APP DE TELA CHEIA (só na Arena 3D, dentro de [data-p3d-launcher]):
       abre por cima de tudo (100dvh, a página parada e escondida embaixo)
       e fecha no X, no Esc e no voltar do celular (history.pushState e
       popstate). O endereço #monte-seu-espaco e o link de um projeto (#p=)
       abrem o app direto. O projeto3d.js (e com ele o 3D) só é baixado
       quando o app abre pela primeira vez. No celular, o painel é uma
       folha embaixo do 3D: arrastar a alça para cima a faz crescer.
   ====================================================================== */

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const metros = (v) => (Math.round(v * 100) / 100).toFixed(2).replace(".", ",").replace(",00", "");
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
const NOMES = { espaco: "Espaço", modelo: "Modelo", areas: "Áreas", maquinas: "Máquinas", coube: "O que coube", fotos: "Fotos" };

/* ======================================================================
   AS ABAS
   ====================================================================== */
export function iniciarAbas(raiz) {
  const lista = $('[role="tablist"]', raiz);
  const abas = [...raiz.querySelectorAll("[data-aba]")];
  if (!lista || !abas.length) return null;
  const painelDe = (nome) => $(`[data-aba-painel="${nome}"]`, raiz);
  const caixa = $("[data-paineis]", raiz);
  const voltar = $("[data-aba-voltar]", raiz);
  const proximo = $("[data-aba-proximo]", raiz);
  const proximoNome = $("[data-aba-proximo-nome]", raiz);
  const fim = $("[data-aba-fim]", raiz);
  const onde = $("[data-aba-onde]", raiz);
  const cliente = (raiz.dataset.modo || "cliente") === "cliente";
  // o projeto que já chega montado (o link #p=, o pedido no painel): os passos dele já estão prontos
  const doLink = Boolean($("#p3dEstado")) || /^#p=/.test(location.hash);
  const mexidas = new Set(); // as abas em que a pessoa mexeu
  const deixadas = new Set(); // as abas que ela já viu e deixou (passou adiante)
  const vistas = new Set();
  let atual = (abas.find((b) => b.getAttribute("aria-selected") === "true") || abas[0]).dataset.aba;
  let ultimo = null; // o último "p3d:mudou" (o resultado da arrumação)
  vistas.add(atual);

  const visiveis = () => abas.filter((b) => !b.hidden);

  function ativar(nome, { foco = false } = {}) {
    const botao = abas.find((b) => b.dataset.aba === nome && !b.hidden);
    if (!botao) return;
    if (nome !== atual) deixadas.add(atual);
    atual = nome;
    vistas.add(nome);
    for (const b of abas) {
      const esta = b === botao;
      b.setAttribute("aria-selected", String(esta));
      b.tabIndex = esta ? 0 : -1;
      const p = painelDe(b.dataset.aba);
      if (p) p.hidden = !esta;
    }
    raiz.dataset.aba = nome;
    if (caixa) caixa.scrollTop = 0;
    // a aba fica à vista na fila que rola de lado (a ficha estreita do painel)
    if (lista.scrollWidth > lista.clientWidth + 2) {
      const l = botao.offsetLeft - lista.offsetLeft;
      if (l < lista.scrollLeft || l + botao.offsetWidth > lista.scrollLeft + lista.clientWidth) lista.scrollLeft = l - 8;
    }
    if (foco) botao.focus({ preventScroll: true });
    rodape();
    marcar();
    raiz.dispatchEvent(new CustomEvent("p3d:aba", { detail: { aba: nome } }));
  }

  /** O pé do painel: Voltar, "Passo 2 de 6", "Próximo: Áreas" (no último passo do site, o pedido). */
  function rodape() {
    const vs = visiveis();
    const i = Math.max(0, vs.findIndex((b) => b.dataset.aba === atual));
    const seguinte = vs[i + 1];
    if (voltar) voltar.disabled = i === 0;
    if (proximo) proximo.hidden = !seguinte;
    if (proximoNome && seguinte) proximoNome.textContent = `: ${NOMES[seguinte.dataset.aba] || ""}`;
    if (fim) fim.hidden = Boolean(seguinte);
    if (onde) onde.textContent = `Passo ${i + 1} de ${vs.length}`;
    // o foco não se perde num botão que sumiu
    if (proximo && proximo.hidden && document.activeElement === proximo) (fim && !fim.hidden ? fim : voltar)?.focus();
    if (voltar && voltar.disabled && document.activeElement === voltar) proximo?.focus();
  }
  function andar(passo) {
    const vs = visiveis();
    const i = vs.findIndex((b) => b.dataset.aba === atual);
    const alvo = vs[i + passo];
    if (alvo) ativar(alvo.dataset.aba);
  }

  /* ---------------------------------------------------------------- o que cada passo já tem */
  const valor = (nome) => Number(String($(`[name="${nome}"]`, raiz)?.value || "").replace(",", "."));
  const soma = (sel) => [...raiz.querySelectorAll(sel)].reduce((s, o) => s + (Number(o.textContent) || 0), 0);
  function situacao(nome) {
    const confirmada = mexidas.has(nome) || deixadas.has(nome) || doLink;
    if (nome === "espaco") {
      const l = valor("largura"), c = valor("comprimento"), h = valor("pe_direito");
      const ok = l > 0 && c > 0 && h > 0;
      return { sub: ok ? `${metros(l)} × ${metros(c)} m · pé-direito ${metros(h)} m` : "Falta a medida do lugar", feita: ok && confirmada };
    }
    if (nome === "modelo") {
      const area = $("#p3dModelos [aria-pressed='true'] b", raiz);
      const pronto = $("#p3dProntos:not([hidden]) [data-pronto]:not([data-pronto=''])[aria-pressed='true'] b", raiz);
      const texto = (pronto || area)?.textContent || "";
      return { sub: texto || "O espaço, o estilo e a cor", feita: Boolean(area) && confirmada };
    }
    if (nome === "areas") {
      const a = raiz.querySelectorAll("#p3dAreas [aria-pressed='true']").length;
      const g = soma("#p3dGrandes output");
      const partes = [a && plural(a, "área a mais", "áreas a mais"), g && plural(g, "brinquedo", "brinquedos")].filter(Boolean);
      return { sub: partes.join(" · ") || "Opcional", feita: a + g > 0 || deixadas.has(nome) };
    }
    if (nome === "maquinas") {
      const n = soma("#p3dMaquinas output");
      return { sub: n ? plural(n, "máquina", "máquinas") : deixadas.has(nome) ? "Nenhuma (opcional)" : "Nenhuma ainda", feita: n > 0 || deixadas.has(nome) };
    }
    if (nome === "coube") {
      const d = ultimo;
      return {
        sub: d ? `${d.noProjeto} no projeto${d.deFora ? ` · ${d.deFora} de fora` : ""}` : "O resultado da arrumação",
        feita: vistas.has(nome),
        alerta: Boolean(d && d.deFora),
      };
    }
    if (nome === "fotos") {
      const n = raiz.querySelectorAll("#p3dFotos > li").length;
      return { sub: n ? plural(n, "foto", "fotos") : cliente ? "Até 3 fotos do lugar" : "As fotos do cliente", feita: n > 0 };
    }
    return { sub: "", feita: false };
  }

  const barra = $("[data-progresso-barra]", raiz);
  const progressoN = $("[data-progresso-n]", raiz);
  const progressoTotal = $("[data-progresso-total]", raiz);
  function marcar() {
    const vs = visiveis();
    let prontas = 0;
    vs.forEach((b, i) => {
      const s = situacao(b.dataset.aba);
      const sub = $("[data-aba-sub]", b);
      if (sub && sub.textContent !== s.sub) sub.textContent = s.sub;
      b.classList.toggle("p3d-aba--feita", s.feita);
      b.classList.toggle("p3d-aba--alerta", Boolean(s.alerta));
      const num = $("[data-aba-num]", b);
      if (num) num.innerHTML = s.feita ? '<i class="fa-solid fa-check"></i>' : String(i + 1);
      // o leitor de tela ouve o nome, o que já tem e se está pronto
      b.setAttribute("aria-description", `${s.sub}${s.feita ? " · pronto" : ""}`);
      if (s.feita) prontas++;
    });
    if (barra) barra.style.width = `${Math.round((prontas / Math.max(1, vs.length)) * 100)}%`;
    if (progressoN) progressoN.textContent = String(prontas);
    if (progressoTotal) progressoTotal.textContent = String(vs.length);
    contarMaquinas();
  }
  let pedido = 0;
  const marcarLogo = () => { cancelAnimationFrame(pedido); pedido = requestAnimationFrame(marcar); };

  /* ---------------------------------------------------------------- o resumo vivo da barra do topo */
  const resumo = $("#p3dResumo", raiz);
  function mostrarResumo() {
    if (!resumo || !ultimo) return;
    const { espaco, numeros, noProjeto, deFora } = ultimo;
    $('[data-resumo="metros"]', resumo).textContent = `${metros(Number(espaco.largura))} × ${metros(Number(espaco.comprimento))} m`;
    $('[data-resumo="uso"]', resumo).innerHTML = `<b>${Math.round(Number(numeros.ocupacao) || 0)}%</b><span class="p3d-so-largo"> em uso</span>`;
    $('[data-resumo="itens"]', resumo).innerHTML = `${plural(noProjeto, "item", "itens")}${deFora ? ` <span class="p3d-resumo-fora">· ${deFora} de fora</span>` : ""}`;
  }

  /* ---------------------------------------------------------------- a conta das máquinas, embaixo da busca */
  const conta = $("[data-maquinas-conta]", raiz);
  function contarMaquinas() {
    if (!conta) return;
    const todas = raiz.querySelectorAll("#p3dMaquinas > [data-item]");
    if (!todas.length) { conta.textContent = ""; return; }
    const vistasNaBusca = [...todas].filter((li) => !li.hidden).length;
    const escolhidas = soma("#p3dMaquinas output");
    const busca = vistasNaBusca < todas.length ? `${vistasNaBusca} de ${todas.length} na busca` : plural(todas.length, "máquina", "máquinas");
    conta.innerHTML = `${busca}${escolhidas ? ` · <b>${plural(escolhidas, "escolhida", "escolhidas")}</b>` : ""}`;
  }
  $("#p3dBusca", raiz)?.addEventListener("input", () => setTimeout(contarMaquinas, 0));

  /* ---------------------------------------------------------------- os eventos */
  lista.addEventListener("click", (e) => {
    const b = e.target.closest("[data-aba]");
    if (b) ativar(b.dataset.aba);
  });
  lista.addEventListener("keydown", (e) => {
    const vs = visiveis();
    const i = vs.indexOf(document.activeElement);
    if (i < 0) return;
    const j = { ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: vs.length - 1 }[e.key];
    if (j === undefined) return;
    e.preventDefault();
    ativar(vs[(j + vs.length) % vs.length].dataset.aba, { foco: true });
  });
  voltar?.addEventListener("click", () => andar(-1));
  proximo?.addEventListener("click", () => andar(1));

  // mexer num passo (digitar a medida, tocar num modelo, numa máquina) conta para o sinal de pronto
  const aoMexer = (e) => {
    const p = e.target.closest("[data-aba-painel]");
    if (!p || !raiz.contains(p)) return;
    mexidas.add(p.dataset.abaPainel);
    // a ideia pronta escolhe o espaço e o modelo de uma vez
    if (e.target.closest("[data-proposta]")) mexidas.add("modelo");
    marcarLogo();
  };
  raiz.addEventListener("input", aoMexer);
  raiz.addEventListener("click", aoMexer);

  // a pílula do 3D ("8 no projeto · 1 de fora") abre o "O que coube": na captura, antes de o
  // projeto3d.js rolar até o resultado (que assim já está à vista no painel)
  raiz.addEventListener("click", (e) => { if (e.target.closest("#p3dPilula")) ativar("coube"); }, true);

  raiz.addEventListener("p3d:mudou", (e) => {
    ultimo = e.detail;
    mostrarResumo();
    marcarLogo();
  });

  // as fotos: a aba some quando o passo some (sem 3D no aparelho; no painel, sem fotos do cliente)
  const passoFotos = $("#p3dFotosPasso", raiz);
  const abaFotos = abas.find((b) => b.dataset.aba === "fotos");
  function conferirFotos() {
    if (!abaFotos || !passoFotos) return;
    const some = passoFotos.hidden;
    if (abaFotos.hidden !== some) {
      abaFotos.hidden = some;
      if (some && atual === "fotos") andar(-1);
      rodape();
    }
    marcarLogo();
  }
  if (passoFotos) {
    new MutationObserver(conferirFotos).observe(passoFotos, { attributes: true, attributeFilter: ["hidden"] });
    const listaFotos = $("#p3dFotos", raiz);
    if (listaFotos) new MutationObserver(marcarLogo).observe(listaFotos, { childList: true });
  }

  conferirFotos();
  rodape();
  marcar();
  return { ativar, atual: () => atual };
}

/* ======================================================================
   O APP DE TELA CHEIA (a Arena 3D)
   ====================================================================== */
const ALVO = /^#(?:p=|monte-seu-espaco$)/;

export function iniciarTelaCheia(app, raiz) {
  const html = document.documentElement;
  const grade = $("[data-p3d-app]", raiz);
  let aberto = false;
  let baixado = false;
  let voltaFoco = null;
  let rolagem = 0;
  let chegouAberto = false; // o app abriu pelo endereço (e não por um toque nesta página)

  // o app mora no fim do <body>: nenhum pai com transform ou contain prende o position: fixed,
  // e o resto da página pode sumir enquanto ele está aberto (projeto3d.css: .p3dl-so-app)
  if (app.parentElement !== document.body) document.body.appendChild(app);
  app.setAttribute("role", "dialog");
  app.setAttribute("aria-modal", "true");
  app.setAttribute("aria-labelledby", "p3dTitulo");
  raiz.dataset.fechado = "1";

  function baixar() {
    if (baixado) return;
    baixado = true;
    import(app.dataset.appJs).catch((erro) => {
      console.error("Monte seu espaço: o app não carregou", erro);
      raiz.classList.add("p3d--sem-3d");
    });
  }

  function abrir(historia = "empurrar") {
    if (aberto) return;
    aberto = true;
    const ativo = document.activeElement;
    voltaFoco = ativo instanceof HTMLElement && !app.contains(ativo) && ativo !== document.body ? ativo : null;
    rolagem = window.scrollY;
    raiz.dataset.fechado = "0";
    if (historia === "empurrar") {
      // o voltar do celular fecha o app (e não sai da página)
      try { history.pushState({ p3dApp: true }, "", raiz.dataset.endereco || "#monte-seu-espaco"); } catch (_) { /* nada */ }
    }
    app.classList.add("p3dl--aberto");
    html.classList.add("p3dl-trava", "p3dl-so-app");
    baixar();
    requestAnimationFrame(() => ($('[role="tab"][aria-selected="true"]', raiz) || $("[data-fechar-app]", raiz))?.focus({ preventScroll: true }));
    raiz.dispatchEvent(new CustomEvent("p3d:abriu"));
  }

  function fechar(daHistoria = false) {
    if (!aberto) return;
    aberto = false;
    raiz.dataset.fechado = "1";
    raiz.querySelectorAll("dialog[open]").forEach((d) => (d.close ? d.close() : d.removeAttribute("open")));
    app.classList.remove("p3dl--aberto");
    html.classList.remove("p3dl-trava", "p3dl-so-app");
    // a página volta para onde estava; quem chegou com o app aberto cai na chamada dele
    const chamada = document.getElementById("monte-seu-espaco");
    if (chegouAberto && chamada) {
      const folga = parseFloat(getComputedStyle(html).getPropertyValue("--ls-ancora-offset")) || 96;
      window.scrollTo(0, Math.max(0, chamada.getBoundingClientRect().top + window.scrollY - folga));
    } else {
      window.scrollTo(0, rolagem);
    }
    chegouAberto = false;
    if (!daHistoria) {
      if (history.state && history.state.p3dApp) history.back();
      else { try { history.replaceState(null, "", location.pathname + location.search); } catch (_) { /* nada */ } }
    }
    const volta = voltaFoco && document.contains(voltaFoco) ? voltaFoco : $("[data-abrir-montador]");
    volta?.focus?.({ preventScroll: true });
    raiz.dispatchEvent(new CustomEvent("p3d:fechou"));
  }

  // os botões e links que abrem o app: o "Abrir o montador", a prévia e todo link para #monte-seu-espaco
  // desta página (o do topo, o do menu). Na captura: o ls-ancoras.js não chega a rolar até a seção.
  document.addEventListener("click", (e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const alvo = e.target.closest?.("[data-abrir-montador], a[href]");
    if (!alvo || app.contains(alvo)) return;
    if (!alvo.matches("[data-abrir-montador]")) {
      if (alvo.target === "_blank") return;
      let url;
      try { url = new URL(alvo.href, location.href); } catch (_) { return; }
      if (url.origin !== location.origin || url.pathname !== location.pathname || !ALVO.test(url.hash)) return;
    }
    e.preventDefault();
    abrir();
  }, true);

  raiz.querySelectorAll("[data-fechar-app]").forEach((b) => b.addEventListener("click", () => fechar()));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !aberto || e.defaultPrevented) return;
    if (raiz.querySelector("dialog[open]")) return; // o diálogo aberto fecha primeiro (ele mesmo cuida do Esc)
    if (e.target.matches?.('input[type="search"]') && e.target.value) return; // o Esc limpa a busca antes
    e.preventDefault();
    fechar();
  });
  window.addEventListener("popstate", () => {
    const doApp = Boolean(history.state && history.state.p3dApp);
    if (aberto && !doApp) fechar(true);
    else if (!aberto && doApp) abrir("ficar"); // o "avançar" do navegador
  });
  // o endereço trocado à mão (ou um link que não passou pelo clique acima)
  window.addEventListener("hashchange", () => {
    if (aberto || !ALVO.test(location.hash)) return;
    try { history.replaceState({ p3dApp: true }, "", location.href); } catch (_) { /* nada */ }
    chegouAberto = true;
    abrir("ficar");
  });

  iniciarFolha(raiz, grade);

  // a chegada com o app no endereço: a página sem o app fica atrás dele no histórico,
  // e o voltar do celular fecha o app em vez de sair do site
  if (ALVO.test(location.hash)) {
    chegouAberto = true;
    if (!(history.state && history.state.p3dApp)) {
      const destino = location.hash;
      try {
        history.replaceState(null, "", location.pathname + location.search);
        history.pushState({ p3dApp: true }, "", destino);
      } catch (_) { /* nada */ }
    }
    abrir("ficar");
  } else {
    // a casca aberta pelo script da página (o endereço dizia) e que o endereço não pede mais
    app.classList.remove("p3dl--aberto");
    html.classList.remove("p3dl-trava");
  }
  return { abrir, fechar, aberto: () => aberto };
}

/* ======================================================================
   A FOLHA DO CELULAR: o painel embaixo do 3D. Recolhida (a alça e o pé), na
   metade (o normal) ou alta. Arrastar a alça move a folha junto com o dedo
   (só o desenho: o 3D muda de tamanho uma vez, quando ela assenta); um
   toque na alça alterna entre a metade e alta.
   ====================================================================== */
function iniciarFolha(raiz, grade) {
  const alca = $("[data-folha-alca]", raiz);
  const painel = $(".p3d-painel", raiz);
  if (!alca || !painel || !grade) return;
  const FRACAO = { media: 0.45, alta: 0.68 }; // as mesmas do projeto3d.css
  const MINI = 118;
  const alturas = () => {
    const h = grade.clientHeight;
    return { mini: MINI, media: h * FRACAO.media, alta: h * FRACAO.alta };
  };
  const folhaNoCelular = () => getComputedStyle(alca).display !== "none";

  function pousar(estado, { animar = true } = {}) {
    const antes = painel.getBoundingClientRect().top;
    painel.style.transition = "none";
    painel.style.transform = "";
    grade.dataset.folha = estado;
    alca.setAttribute("aria-expanded", String(estado === "alta"));
    alca.setAttribute("aria-label", estado === "alta" ? "Diminuir o painel" : "Aumentar o painel");
    if (!animar || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // FLIP: a folha sai de onde o dedo largou e desliza até onde ela assentou
    const depois = painel.getBoundingClientRect().top;
    if (Math.abs(antes - depois) < 2) return;
    painel.style.transform = `translateY(${antes - depois}px)`;
    painel.getBoundingClientRect();
    painel.style.transition = "transform .24s cubic-bezier(.2, .8, .2, 1)";
    painel.style.transform = "";
    painel.addEventListener("transitionend", () => { painel.style.transition = ""; }, { once: true });
  }

  let arrasto = null;
  let arrastou = false;
  alca.addEventListener("pointerdown", (e) => {
    if (!folhaNoCelular()) return;
    alca.setPointerCapture(e.pointerId);
    arrasto = { id: e.pointerId, y: e.clientY, h: painel.getBoundingClientRect().height, t: performance.now(), vy: 0, ultimoY: e.clientY };
    arrastou = false;
    painel.style.transition = "none";
  });
  alca.addEventListener("pointermove", (e) => {
    if (!arrasto || e.pointerId !== arrasto.id) return;
    const dy = e.clientY - arrasto.y;
    if (Math.abs(dy) > 4) arrastou = true;
    const { mini, alta } = alturas();
    // a folha não passa da alta nem fica menor que a recolhida
    const limite = Math.min(Math.max(dy, -(alta - arrasto.h)), arrasto.h - mini);
    const agora = performance.now();
    arrasto.vy = (e.clientY - arrasto.ultimoY) / Math.max(1, agora - arrasto.t);
    arrasto.t = agora;
    arrasto.ultimoY = e.clientY;
    painel.style.transform = `translateY(${limite}px)`;
  });
  const soltar = (e) => {
    if (!arrasto || e.pointerId !== arrasto.id) return;
    const dy = e.clientY - arrasto.y;
    const inicio = arrasto;
    arrasto = null;
    if (!arrastou) { painel.style.transform = ""; return; }
    // aonde a folha vai: a altura mais perto de onde o dedo largou (com o embalo do gesto)
    const alvo = inicio.h - dy - inicio.vy * 180;
    const hs = alturas();
    const estado = Object.entries(hs).sort((a, b) => Math.abs(a[1] - alvo) - Math.abs(b[1] - alvo))[0][0];
    pousar(estado);
  };
  alca.addEventListener("pointerup", soltar);
  alca.addEventListener("pointercancel", soltar);
  alca.addEventListener("click", () => {
    if (arrastou) { arrastou = false; return; }
    pousar(grade.dataset.folha === "alta" ? "media" : grade.dataset.folha === "mini" ? "media" : "alta");
  });
  // trocar de aba com a folha recolhida a traz de volta para a metade
  raiz.addEventListener("p3d:aba", () => {
    if (grade.dataset.folha === "mini" && folhaNoCelular()) pousar("media");
  });
}

/* ---------------------------------------------------------------- começa */
const raiz = document.getElementById("p3d");
if (raiz && raiz.querySelector("[data-aba]")) {
  iniciarAbas(raiz);
  const app = raiz.closest("[data-p3d-launcher]");
  if (app && app.dataset.appJs) iniciarTelaCheia(app, raiz);
}
