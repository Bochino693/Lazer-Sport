/* ======================================================================
   MONTE SEU ESPAÇO -- o app da Arena 3D (arena.html, #monte-seu-espaco) e da
   ficha do pedido no painel (sistema_interno, modo "painel").

   As escolhas ficam de um lado; o 3D, do outro. A cada mudança o
   arrumador (arrumador.js) refaz a planta e a página redesenha:
     * o CHÃO é uma textura só, desenhada num canvas: o piso, a grade de
       metro em metro, o corredor de 1,20 m (o caminho que o arrumador
       achou da entrada até cada coisa), as zonas de uso e de segurança e
       a entrada;
     * as PAREDES somem do lado da câmera (a casa de bonecas: vê-se dentro);
     * as áreas sob medida são desenhadas pelo projetista do painel
       (montar3d-gerador.js + montar3d-pecas.js: o mesmo código);
     * as máquinas, pelo .glb delas (no tamanho real) ou pelo mini 3D na
       medida, com a foto (maquinas3d.js).
   Desenha só quando algo muda (o celular agradece). Sem WebGL, a conta
   do que cabe continua valendo: a lista do resultado é a resposta.

   O estado vai no endereço (#p=...): o link abre o mesmo projeto.
   ====================================================================== */

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const metros = (v) => (Math.round(v * 100) / 100).toFixed(2).replace(".", ",").replace(",00", "");
const PADRAO = { largura: 20, comprimento: 15, pe_direito: 4 };

function escapar(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function codificar(estado) {
  const json = JSON.stringify(estado);
  return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodificar(texto) {
  try {
    const b = texto.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(b + "===".slice((b.length + 3) % 4)))));
  } catch (_) {
    return null;
  }
}

export async function iniciar(raiz) {
  const dados = JSON.parse($("#p3dDados").textContent || "{}");
  const modo = raiz.dataset.modo || "cliente";
  const [arrumadorMod, geradorMod] = await Promise.all([import(raiz.dataset.arrumador), import(raiz.dataset.gerador)]);
  const { arrumar, espacoParaTudo } = arrumadorMod;
  const itensPorId = new Map(dados.itens.map((i) => [i.id, i]));

  /* ---------------------------------------------------------------- o estado */
  const inicial = (() => {
    const fixo = $("#p3dEstado");
    if (fixo) return JSON.parse(fixo.textContent || "{}");
    const m = location.hash.match(/[#&]p=([^&]+)/);
    return (m && decodificar(m[1])) || null;
  })();
  const estado = {
    espaco: { ...PADRAO },
    principal: { tipo: "area", area: "esportivo" },
    areas: [],
    itens: {},
    estilo: "colorido",
    cor: dados.cores[0],
    semente: 1,
    // por área (trampolim, esportivo, baby): { porte: "auto" | "compacto" | "medio" | "grande", sem: [componentes tirados] }
    opcoes: {},
  };
  if (inicial) {
    Object.assign(estado.espaco, inicial.espaco || {});
    // o que vem do link é conferido: só área e item que existem
    const pi = inicial.principal;
    if (pi === null) estado.principal = null;
    else if (pi && pi.tipo === "area" && dados.areas[pi.area]) estado.principal = { tipo: "area", area: pi.area };
    else if (pi && pi.tipo === "item" && itensPorId.has(String(pi.id))) estado.principal = { tipo: "item", id: String(pi.id) };
    for (const k of ["largura", "comprimento", "pe_direito"]) {
      const v = Number(estado.espaco[k]);
      estado.espaco[k] = v > 0 && v <= 150 ? v : PADRAO[k];
    }
    estado.areas = Array.isArray(inicial.areas) ? inicial.areas.filter((a) => dados.areas[a]) : [];
    for (const linha of inicial.itens || []) if (itensPorId.has(String(linha.id))) estado.itens[String(linha.id)] = Number(linha.qtd) || 0;
    if (dados.estilos.includes(inicial.estilo)) estado.estilo = inicial.estilo;
    if (/^#[0-9a-f]{6}$/i.test(inicial.cor || "")) estado.cor = inicial.cor;
    estado.semente = Number(inicial.semente) || 1;
    for (const [chave, op] of Object.entries(inicial.opcoes || {})) {
      const a = dados.areas[chave];
      if (!a || !(a.portes || []).length || !op) continue;
      estado.opcoes[chave] = {
        porte: (a.portes || []).some((p) => p.chave === op.porte) ? op.porte : "auto",
        sem: Array.isArray(op.sem) ? op.sem.filter((c) => dados.componentes[c]) : [],
      };
    }
  }
  const escolha = () => ({
    principal: estado.principal,
    areas: estado.areas,
    itens: Object.entries(estado.itens).filter(([, q]) => q > 0).map(([id, qtd]) => ({ id, qtd })),
    estilo: estado.estilo,
    cor: estado.cor,
    semente: estado.semente,
    opcoes: estado.opcoes,
  });

  /* ---------------------------------------------------------------- os controles */
  const campo = (nome) => raiz.querySelector(`[name="${nome}"]`);
  for (const k of ["largura", "comprimento", "pe_direito"]) {
    const c = campo(k);
    if (!c) continue;
    c.value = String(estado.espaco[k]).replace(".", ",");
    c.addEventListener("input", () => {
      const v = Number(String(c.value).replace(",", "."));
      if (v > 0) { estado.espaco[k] = v; mudou(); }
    });
  }
  raiz.querySelectorAll("[data-medida]").forEach((b) => b.addEventListener("click", () => {
    const [l, c] = b.dataset.medida.split("x").map(Number);
    estado.espaco.largura = l;
    estado.espaco.comprimento = c;
    campo("largura").value = String(l).replace(".", ",");
    campo("comprimento").value = String(c).replace(".", ",");
    mudou();
  }));

  // o modelo do espaço: as áreas + "só máquinas"; e, na área escolhida, os modelos prontos do catálogo
  const listaModelos = $("#p3dModelos", raiz);
  const listaProntos = $("#p3dProntos", raiz);
  const areaDoPrincipal = () => (estado.principal ? (estado.principal.tipo === "area" ? estado.principal.area : (itensPorId.get(estado.principal.id) || {}).area) : "");
  function desenharModelos() {
    const atual = areaDoPrincipal();
    listaModelos.innerHTML = Object.entries(dados.areas).map(([chave, a]) => `
      <button type="button" class="p3d-modelo" data-area="${chave}" aria-pressed="${atual === chave}">
        <i class="fa-solid ${escapar(a.icone)}" aria-hidden="true"></i>
        <span><b>${escapar(a.nome)}</b><small>a partir de ${metros(a.min[0])} × ${metros(a.min[1])} m</small></span>
      </button>`).join("") + `
      <button type="button" class="p3d-modelo" data-area="" aria-pressed="${!estado.principal}">
        <i class="fa-solid fa-gamepad" aria-hidden="true"></i>
        <span><b>Só máquinas</b><small>fliperamas e jogos nas paredes</small></span>
      </button>`;
    const prontos = dados.itens.filter((i) => i.tipo === "grande" && i.area === atual);
    if (!atual || !prontos.length) {
      // sem modelo pronto (o trampolim park, a área baby): é o sob medida, com as opções abaixo
      listaProntos.hidden = true;
      listaProntos.innerHTML = "";
    } else {
      const sob = estado.principal && estado.principal.tipo === "area";
      listaProntos.hidden = false;
      listaProntos.innerHTML = `<p class="p3d-rotulo">Qual ${escapar(dados.areas[atual].nome.toLowerCase())}?</p>
        <button type="button" class="p3d-pronto" data-pronto="" aria-pressed="${sob}">
          <span class="p3d-pronto-foto p3d-pronto-foto--sob"><i class="fa-solid fa-wand-magic-sparkles" aria-hidden="true"></i></span>
          <span><b>Sob medida</b><small>desenhado para o seu espaço</small></span>
        </button>` + prontos.map((i) => `
        <button type="button" class="p3d-pronto" data-pronto="${escapar(i.id)}" aria-pressed="${!sob && estado.principal.id === i.id}">
          <span class="p3d-pronto-foto">${i.capa ? `<img src="${escapar(i.capa)}" alt="" loading="lazy">` : ""}</span>
          <span><b>${escapar(i.nome)}</b><small>${metros(i.medidas[1])} × ${metros(i.medidas[2])} m${i.modelo ? " · 3D" : ""}</small></span>
        </button>`).join("");
    }
  }
  listaModelos.addEventListener("click", (e) => {
    const b = e.target.closest("[data-area]");
    if (!b) return;
    estado.principal = b.dataset.area ? { tipo: "area", area: b.dataset.area } : null;
    estado.areas = estado.areas.filter((a) => a !== b.dataset.area);
    desenharModelos(); desenharAreas(); desenharOpcoes(); mudou();
  });
  listaProntos.addEventListener("click", (e) => {
    const b = e.target.closest("[data-pronto]");
    if (!b) return;
    estado.principal = b.dataset.pronto ? { tipo: "item", id: b.dataset.pronto } : { tipo: "area", area: areaDoPrincipal() };
    desenharModelos(); desenharOpcoes(); mudou();
  });

  // as opções das áreas sob medida que mudam com o tamanho: o porte (só os que cabem) e o que vai dentro
  const nomePorte = (area, chave) => ((dados.areas[area].portes || []).find((p) => p.chave === chave) || {}).nome || "";
  const opcaoDe = (area) => estado.opcoes[area] || { porte: "auto", sem: [] };
  /** Cabe no espaço (com a entrada e a passagem)? De qualquer lado. */
  function cabeNoEspaco(min) {
    const W = Number(estado.espaco.largura) - 0.6, D = Number(estado.espaco.comprimento) - 3.4;
    const [a, b] = min;
    return (a <= W && b <= D) || (b <= W && a <= D);
  }
  function porteEfetivo(area) {
    const portes = dados.areas[area].portes || [];
    const op = opcaoDe(area);
    const escolhido = portes.find((p) => p.chave === op.porte);
    if (escolhido) return escolhido;
    let melhor = portes[0];
    for (const p of portes) if (cabeNoEspaco(p.min)) melhor = p;
    return melhor;
  }
  function blocoDeOpcoes(area) {
    const a = dados.areas[area];
    const portes = a.portes || [];
    if (!portes.length) return "";
    const op = opcaoDe(area);
    const efetivo = porteEfetivo(area);
    const chips = [`<button type="button" class="p3d-chip" data-op-area="${area}" data-porte="auto" aria-pressed="${op.porte === "auto"}">Automático${op.porte === "auto" ? ` <small>(${escapar(efetivo.nome.toLowerCase())})</small>` : ""}</button>`]
      .concat(portes.map((p) => {
        const cabe = cabeNoEspaco(p.min);
        return `<button type="button" class="p3d-chip p3d-chip--porte" data-op-area="${area}" data-porte="${p.chave}" aria-pressed="${op.porte === p.chave}"${cabe ? "" : " disabled"} title="${cabe ? "" : "Não cabe no seu espaço"}">${escapar(p.nome)} <small>${metros(p.min[0])} × ${metros(p.min[1])} m</small></button>`;
      }));
    const comps = efetivo.componentes.filter((c) => !dados.fixos.includes(c)).map((c) => `
      <button type="button" class="p3d-chip p3d-chip--comp" data-op-area="${area}" data-comp="${c}" aria-pressed="${!op.sem.includes(c)}">${escapar(dados.componentes[c] || c)}</button>`).join("");
    return `<div class="p3d-opcao">
      <p class="p3d-rotulo">${escapar(a.nome)}: o tamanho</p>
      <div class="p3d-chips">${chips.join("")}</div>
      ${comps ? `<p class="p3d-rotulo">O que vai dentro</p><div class="p3d-chips">${comps}</div>` : ""}
    </div>`;
  }
  const caixaOpcoes = $("#p3dOpcoes", raiz);
  const caixaOpcoesMais = $("#p3dOpcoesMais", raiz);
  function desenharOpcoes() {
    const principal = estado.principal && estado.principal.tipo === "area" ? estado.principal.area : "";
    const p = principal ? blocoDeOpcoes(principal) : "";
    caixaOpcoes.innerHTML = p;
    caixaOpcoes.hidden = !p;
    const mais = estado.areas.filter((a) => a !== principal).map(blocoDeOpcoes).join("");
    caixaOpcoesMais.innerHTML = mais;
    caixaOpcoesMais.hidden = !mais;
  }
  const aoMexerNasOpcoes = (e) => {
    const b = e.target.closest("[data-op-area]");
    if (!b || b.disabled) return;
    const area = b.dataset.opArea;
    const op = { ...opcaoDe(area), sem: [...opcaoDe(area).sem] };
    if (b.dataset.porte) op.porte = b.dataset.porte;
    if (b.dataset.comp) op.sem = op.sem.includes(b.dataset.comp) ? op.sem.filter((c) => c !== b.dataset.comp) : op.sem.concat([b.dataset.comp]);
    estado.opcoes[area] = op;
    desenharOpcoes();
    mudou();
  };
  caixaOpcoes.addEventListener("click", aoMexerNasOpcoes);
  caixaOpcoesMais.addEventListener("click", aoMexerNasOpcoes);

  // o estilo e a cor-tema (das áreas sob medida e do mini 3D)
  const listaEstilos = $("#p3dEstilos", raiz);
  const nomesEstilo = { colorido: "Colorido", neon: "Neon", selva: "Selva" };
  listaEstilos.innerHTML = dados.estilos.map((s) => `<button type="button" class="p3d-chip" data-estilo="${s}" aria-pressed="${s === estado.estilo}">${nomesEstilo[s] || s}</button>`).join("");
  listaEstilos.addEventListener("click", (e) => {
    const b = e.target.closest("[data-estilo]");
    if (!b) return;
    estado.estilo = b.dataset.estilo;
    listaEstilos.querySelectorAll("[data-estilo]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    mudou();
  });
  const listaCores = $("#p3dCores", raiz);
  listaCores.innerHTML = dados.cores.map((c) => `<button type="button" class="p3d-cor" data-cor="${c}" style="--c:${c}" aria-label="Cor ${c}" aria-pressed="${c === estado.cor}"></button>`).join("");
  listaCores.addEventListener("click", (e) => {
    const b = e.target.closest("[data-cor]");
    if (!b) return;
    estado.cor = b.dataset.cor;
    listaCores.querySelectorAll("[data-cor]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    mudou();
  });

  // as outras áreas (as sob medida que não são o principal)
  const listaAreas = $("#p3dAreas", raiz);
  function desenharAreas() {
    const principal = estado.principal && estado.principal.tipo === "area" ? estado.principal.area : "";
    listaAreas.innerHTML = Object.entries(dados.areas).filter(([k]) => k !== principal).map(([chave, a]) => `
      <button type="button" class="p3d-chip p3d-chip--area" data-mais="${chave}" aria-pressed="${estado.areas.includes(chave)}">
        <i class="fa-solid ${escapar(a.icone)}" aria-hidden="true"></i> ${escapar(a.nome)}
      </button>`).join("");
  }
  listaAreas.addEventListener("click", (e) => {
    const b = e.target.closest("[data-mais]");
    if (!b) return;
    const k = b.dataset.mais;
    estado.areas = estado.areas.includes(k) ? estado.areas.filter((a) => a !== k) : estado.areas.concat([k]);
    b.setAttribute("aria-pressed", String(estado.areas.includes(k)));
    desenharOpcoes();
    mudou();
  });

  // os itens do catálogo: os brinquedos grandes e as máquinas, com a quantidade
  function cartaoDeItem(i) {
    const q = estado.itens[i.id] || 0;
    const medida = `${metros(i.medidas[1])} × ${metros(i.medidas[2])} m · ${metros(i.medidas[0])} m de altura`;
    return `<li class="p3d-item${q ? " p3d-item--com" : ""}" data-item="${escapar(i.id)}" data-busca="${escapar((i.nome + " " + i.categorias.join(" ")).toLowerCase())}">
      <span class="p3d-item-foto">${i.capa ? `<img src="${escapar(i.capa)}" alt="" loading="lazy">` : `<i class="fa-solid fa-cube" aria-hidden="true"></i>`}</span>
      <span class="p3d-item-texto"><b>${escapar(i.nome)}</b><small>${medida}</small>${i.modelo ? `<em class="p3d-selo">3D</em>` : ""}</span>
      <span class="p3d-qtd" role="group" aria-label="Quantidade de ${escapar(i.nome)}">
        <button type="button" data-menos aria-label="Menos">−</button><output>${q}</output><button type="button" data-mais-um aria-label="Mais">+</button>
      </span>
    </li>`;
  }
  const listaGrandes = $("#p3dGrandes", raiz);
  const listaMaquinas = $("#p3dMaquinas", raiz);
  const grandes = dados.itens.filter((i) => i.tipo === "grande");
  listaGrandes.innerHTML = grandes.map(cartaoDeItem).join("") || `<li class="p3d-vazio">Nenhum brinquedo grande no catálogo agora.</li>`;
  listaMaquinas.innerHTML = dados.itens.filter((i) => i.tipo === "maquina").map(cartaoDeItem).join("");
  const aoMudarQtd = (e) => {
    const li = e.target.closest("[data-item]");
    if (!li) return;
    const id = li.dataset.item;
    const passo = e.target.closest("[data-mais-um]") ? 1 : e.target.closest("[data-menos]") ? -1 : 0;
    if (!passo) return;
    estado.itens[id] = Math.max(0, Math.min(30, (estado.itens[id] || 0) + passo));
    $("output", li).textContent = String(estado.itens[id]);
    li.classList.toggle("p3d-item--com", estado.itens[id] > 0);
    mudou();
  };
  // a foto que não chega (fora do ar, apagada) vira o ícone, e não a imagem quebrada
  raiz.addEventListener("error", (e) => {
    const img = e.target;
    if (img.tagName !== "IMG" || !img.closest(".p3d-item-foto, .p3d-pronto-foto")) return;
    const caixa = img.parentElement;
    img.remove();
    caixa.innerHTML = `<i class="fa-solid fa-cube" aria-hidden="true"></i>`;
  }, true);
  listaGrandes.addEventListener("click", aoMudarQtd);
  listaMaquinas.addEventListener("click", aoMudarQtd);
  const busca = $("#p3dBusca", raiz);
  if (busca) {
    busca.addEventListener("input", () => {
      const termo = busca.value.trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
      listaMaquinas.querySelectorAll("[data-item]").forEach((li) => {
        li.hidden = termo && !li.dataset.busca.normalize("NFD").replace(/[̀-ͯ]/g, "").includes(termo);
      });
    });
  }

  /* ---------------------------------------------------------------- o resultado */
  const caixaResultado = $("#p3dResultado", raiz);
  const pilula = $("#p3dPilula", raiz);
  let resultado = null;
  let sugestao = null;
  function contarPorNome(lista) {
    const mapa = new Map();
    for (const i of lista) {
      const k = i.nome + "|" + (i.motivo || "");
      if (!mapa.has(k)) mapa.set(k, { ...i, qtd: 0 });
      mapa.get(k).qtd++;
    }
    return [...mapa.values()];
  }
  /** O nome da área com o porte que ela ficou ("Trampolim park (médio)"). */
  function nomeComPorte(i) {
    if (!i.area || !(dados.areas[i.area.tipo] || {}).portes || !dados.areas[i.area.tipo].portes.length) return i.nome;
    const op = opcaoDe(i.area.tipo);
    const porte = op.porte !== "auto" ? op.porte : (geradorMod.porteQueCabe(i.area.tipo, i.area.largura, i.area.profundidade) || {}).chave;
    const nome = nomePorte(i.area.tipo, porte);
    return nome ? `${i.nome} (${nome.toLowerCase()})` : i.nome;
  }
  function mostrarResultado() {
    const r = resultado;
    const coube = contarPorNome(r.itens);
    const fora = contarPorNome(r.recusados);
    const n = r.numeros;
    caixaResultado.innerHTML = `
      <div class="p3d-numeros">
        <span><b>${metros(n.area)} m²</b><small>o espaço</small></span>
        <span><b>${n.ocupacao}%</b><small>ocupado com uso</small></span>
        <span><b>${r.itens.length}</b><small>no projeto</small></span>
      </div>
      ${coube.length ? `<ul class="p3d-coube">${coube.map((i) => `<li><button type="button" data-ver="${escapar(i.nome)}"><i class="fa-solid fa-check" aria-hidden="true"></i> ${i.qtd > 1 ? `<b>${i.qtd}×</b> ` : ""}${escapar(nomeComPorte(i))}${i.area ? ` <small>${metros(i.area.largura)} × ${metros(i.area.profundidade)} m</small>` : ""}</button></li>`).join("")}</ul>` : `<p class="p3d-nota">Escolha o modelo do espaço e as máquinas.</p>`}
      ${fora.length ? `<p class="p3d-rotulo p3d-rotulo--fora">Ficou de fora</p><ul class="p3d-fora">${fora.map((i) => `<li><i class="fa-solid fa-xmark" aria-hidden="true"></i> <span>${i.qtd > 1 ? `<b>${i.qtd}×</b> ` : ""}<b>${escapar(i.nome)}</b>: ${escapar(i.motivo)}</span></li>`).join("")}</ul>` : ""}
      <div class="p3d-sugestao" id="p3dSugestao"${sugestao ? "" : " hidden"}></div>
      <p class="p3d-nota">Rascunho do arrumador: corredor de 1,20 m até cada coisa, área de quem joga na frente das máquinas e faixa de segurança em volta dos brinquedos. O projeto final é da nossa engenharia (NBR 16071).</p>`;
    pilula.innerHTML = `<i class="fa-solid fa-check" aria-hidden="true"></i> ${r.itens.length} no projeto${r.recusados.length ? ` <span class="p3d-pilula-fora"><i class="fa-solid fa-xmark" aria-hidden="true"></i> ${r.recusados.length} de fora</span>` : ""}`;
    pilula.classList.toggle("p3d-pilula--fora", r.recusados.length > 0);
    mostrarSugestao();
  }
  function mostrarSugestao() {
    const caixa = $("#p3dSugestao", raiz);
    if (!caixa) return;
    if (!sugestao) { caixa.hidden = true; return; }
    caixa.hidden = false;
    caixa.innerHTML = `<i class="fa-solid fa-ruler-combined" aria-hidden="true"></i>
      <span>Para caber tudo, o espaço precisaria ter uns <b>${metros(sugestao.largura)} × ${metros(sugestao.comprimento)} m</b>.</span>
      <button type="button" class="p3d-botao p3d-botao--leve" data-usar-sugestao>Ver nessa medida</button>`;
  }
  caixaResultado.addEventListener("click", (e) => {
    if (e.target.closest("[data-usar-sugestao]") && sugestao) {
      estado.espaco.largura = sugestao.largura;
      estado.espaco.comprimento = sugestao.comprimento;
      campo("largura").value = String(sugestao.largura).replace(".", ",");
      campo("comprimento").value = String(sugestao.comprimento).replace(".", ",");
      mudou();
      return;
    }
    const ver = e.target.closest("[data-ver]");
    if (ver && cena) cena.focar(ver.dataset.ver);
  });
  pilula.addEventListener("click", () => caixaResultado.scrollIntoView({ behavior: "smooth", block: "start" }));

  /* ---------------------------------------------------------------- refazer */
  let espera = 0;
  let esperaSugestao = 0;
  function mudou() {
    clearTimeout(espera);
    espera = setTimeout(() => { desenharOpcoes(); refazer(); }, 120);
  }
  function refazer() {
    resultado = arrumar(estado.espaco, escolha(), dados);
    sugestao = null;
    mostrarResultado();
    if (cena) cena.desenhar(resultado, estado);
    if (modo === "cliente") {
      const hash = "#p=" + codificar({ espaco: estado.espaco, ...escolha() });
      if (location.hash !== hash) history.replaceState(null, "", hash);
    }
    // a medida que caberia tudo: só quando algo ficou de fora (por falta de lugar), sem pressa
    clearTimeout(esperaSugestao);
    if (resultado.recusados.some((x) => x.codigo !== "altura")) {
      esperaSugestao = setTimeout(() => {
        sugestao = espacoParaTudo(estado.espaco, escolha(), dados);
        mostrarSugestao();
      }, 450);
    }
  }

  /* ---------------------------------------------------------------- o 3D */
  let cena = null;
  try {
    cena = await criarCena(raiz, dados, geradorMod);
  } catch (erro) {
    console.warn("Monte seu projeto: sem 3D", erro);
    raiz.classList.add("p3d--sem-3d");
  }
  // as fotos do espaço (o projeto dentro delas): só com o 3D de pé
  let fotosApp = null;
  if (cena && raiz.dataset.foto) {
    try {
      fotosApp = await iniciarFotos(raiz, { modo, cena, estado, fotoMod: await import(raiz.dataset.foto) });
    } catch (erro) {
      console.warn("Monte seu projeto: sem as fotos do espaço", erro);
    }
  }
  if (!fotosApp) { const p = $("#p3dFotosPasso", raiz); if (p) p.hidden = true; }
  $("#p3dOutra", raiz)?.addEventListener("click", () => { estado.semente = (estado.semente % 997) + 1; refazer(); });
  $("#p3dVista", raiz)?.addEventListener("click", (e) => {
    if (!cena) return;
    const planta = cena.alternarPlanta();
    e.currentTarget.setAttribute("aria-pressed", String(planta));
    e.currentTarget.querySelector("span").textContent = planta ? "3D" : "Planta";
  });
  $("#p3dNomes", raiz)?.addEventListener("click", (e) => {
    if (!cena) return;
    const ligado = cena.alternarNomes();
    e.currentTarget.setAttribute("aria-pressed", String(ligado));
  });
  $("#p3dImagem", raiz)?.addEventListener("click", () => {
    if (!cena) return;
    const a = document.createElement("a");
    a.href = cena.imagem();
    a.download = `projeto-lazer-sport-${metros(estado.espaco.largura)}x${metros(estado.espaco.comprimento)}m.png`.replace(/,/g, "-");
    a.click();
  });

  desenharModelos();
  desenharAreas();
  desenharOpcoes();
  refazer();
  raiz.classList.add("p3d--pronto");

  /* ---------------------------------------------------------------- o pedido */
  const formulario = $("#p3dPedido", raiz);
  if (formulario && modo === "cliente") {
    const dialogo = $("#p3dDialogo", raiz);
    raiz.querySelectorAll("[data-pedir]").forEach((b) => b.addEventListener("click", () => {
      const nFotos = fotosApp ? fotosApp.total() : 0;
      $("#p3dPedidoResumo", raiz).textContent = `${metros(estado.espaco.largura)} × ${metros(estado.espaco.comprimento)} m · ${resultado.itens.length} no projeto${resultado.recusados.length ? ` · ${resultado.recusados.length} ficaram de fora` : ""}${nFotos ? ` · ${nFotos} ${nFotos === 1 ? "foto" : "fotos"} do espaço` : ""}`;
      $("#p3dPedidoOk", raiz).hidden = true;
      formulario.hidden = false;
      if (dialogo.showModal) dialogo.showModal(); else dialogo.setAttribute("open", "");
    }));
    raiz.querySelectorAll("[data-fechar]").forEach((b) => b.addEventListener("click", () => dialogo.close ? dialogo.close() : dialogo.removeAttribute("open")));
    formulario.addEventListener("submit", async (e) => {
      e.preventDefault();
      const erro = $("#p3dPedidoErro", raiz);
      const botao = $("button[type=submit]", formulario);
      erro.hidden = true;
      botao.disabled = true;
      const f = new FormData(formulario);
      const coube = contarPorNome(resultado.itens).map((i) => ({ nome: nomeComPorte(i), qtd: String(i.qtd) }));
      const fora = contarPorNome(resultado.recusados).map((i) => ({ nome: (i.qtd > 1 ? i.qtd + "× " : "") + i.nome, motivo: i.motivo }));
      const corpo = {
        site: f.get("site") || "",
        contato: { nome: f.get("nome"), whatsapp: f.get("whatsapp"), email: f.get("email"), cidade: f.get("cidade"), mensagem: f.get("mensagem") },
        espaco: estado.espaco,
        escolha: escolha(),
        resumo: { coube, ficou_de_fora: fora, numeros: resultado.numeros, espaco_para_tudo: sugestao },
      };
      try {
        const cabecalhos = { "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || document.querySelector('meta[name="csrf-token"]')?.content || "" };
        // com fotos do espaço, vai em partes (o pedido + as fotos + as montagens); sem, só o pedido
        const anexos = fotosApp ? await fotosApp.paraOPedido() : [];
        let envio;
        if (anexos.length) {
          envio = new FormData();
          envio.append("dados", JSON.stringify(corpo));
          anexos.forEach((a, i) => {
            envio.append(`foto_${i}`, a.foto, `foto-${i + 1}.jpg`);
            envio.append(`cantos_${i}`, JSON.stringify(a.cantos));
            if (a.montagem) envio.append(`montagem_${i}`, a.montagem, `projeto-na-foto-${i + 1}.jpg`);
          });
        } else {
          cabecalhos["Content-Type"] = "application/json";
          envio = JSON.stringify(corpo);
        }
        const resposta = await fetch(raiz.dataset.urlPedido, { method: "POST", headers: cabecalhos, body: envio, credentials: "same-origin" });
        const volta = await resposta.json().catch(() => ({}));
        if (!resposta.ok || volta.status !== "sucesso") {
          erro.innerHTML = escapar(volta.mensagem || "Não deu para mandar agora. Tente de novo.") + (volta.whatsapp ? ` <a href="${escapar(volta.whatsapp)}" target="_blank" rel="noopener">Mandar pelo WhatsApp</a>` : "");
          erro.hidden = false;
          return;
        }
        formulario.hidden = true;
        const ok = $("#p3dPedidoOk", raiz);
        ok.hidden = false;
        $("#p3dPedidoNumero", raiz).textContent = volta.numero ? `nº ${volta.numero}` : "";
        const zap = $("#p3dPedidoZap", raiz);
        if (volta.whatsapp) { zap.href = volta.whatsapp; zap.hidden = false; } else zap.hidden = true;
        const notaFotos = $("#p3dPedidoFotosNota", raiz);
        if (notaFotos) {
          const mandadas = fotosApp ? fotosApp.total() : 0;
          notaFotos.hidden = !mandadas;
          notaFotos.textContent = mandadas && (volta.fotos || 0) < mandadas
            ? "As fotos do espaço não chegaram junto: mande pelo WhatsApp, por favor."
            : `Com ${mandadas} ${mandadas === 1 ? "foto" : "fotos"} do espaço${mandadas ? " e o projeto montado nelas" : ""}.`;
        }
      } catch (_) {
        erro.textContent = "Sem conexão agora. Tente de novo em instantes.";
        erro.hidden = false;
      } finally {
        botao.disabled = false;
      }
    });
  }
}

/* ======================================================================
   VEJA NO SEU ESPAÇO: as fotos do lugar, com o projeto dentro delas
   O cliente sobe as fotos, arrasta quatro pontos até o chão do espaço e o
   3D aparece do ângulo da foto (a conta da câmera: foto3d.js). As fotos e as
   montagens vão junto do pedido. No painel, as fotos que o cliente mandou,
   com os pontos dele, para ver dentro delas o projeto como estiver aqui.
   ====================================================================== */
const MAX_FOTOS = 3;
const LADO_DA_FOTO = 1400; // o bastante para ver o espaço, leve para mandar
const PONTOS_DE_PARTIDA = [[0.26, 0.45], [0.74, 0.45], [0.97, 0.96], [0.03, 0.96]];
const MARGEM_DO_PALCO = { e: 0.12, d: 0.12, c: 0.04, b: 0.18 }; // o espaço em volta da foto, para os cantos que ficam fora dela

function carregarImagem(src) {
  return new Promise((ok, falha) => {
    const img = new Image();
    img.decoding = "async";
    img.onload = () => ok(img);
    img.onerror = falha;
    img.src = src;
  });
}
const paraBlob = (canvas, tipo, qualidade) => new Promise((ok) => canvas.toBlob(ok, tipo, qualidade));

/* A foto no tamanho que basta, em JPEG. Passar pelo canvas também deixa para trás
   os dados do aparelho gravados na foto (o EXIF, com o lugar onde ela foi tirada). */
async function prepararFoto(arquivo) {
  let fonte;
  try {
    fonte = await createImageBitmap(arquivo, { imageOrientation: "from-image" });
  } catch (_) {
    const url = URL.createObjectURL(arquivo);
    try { fonte = await carregarImagem(url); } finally { setTimeout(() => URL.revokeObjectURL(url), 2000); }
  }
  const w0 = fonte.naturalWidth || fonte.width, h0 = fonte.naturalHeight || fonte.height;
  if (!w0 || !h0) throw new Error("foto vazia");
  const k = Math.min(1, LADO_DA_FOTO / Math.max(w0, h0));
  const c = document.createElement("canvas");
  c.width = Math.round(w0 * k);
  c.height = Math.round(h0 * k);
  c.getContext("2d").drawImage(fonte, 0, 0, c.width, c.height);
  if (fonte.close) fonte.close();
  const blob = await paraBlob(c, "image/jpeg", 0.84);
  if (!blob) throw new Error("sem imagem");
  const src = URL.createObjectURL(blob);
  return { blob, src, img: await carregarImagem(src), largura: c.width, altura: c.height };
}

async function iniciarFotos(raiz, { modo, cena, estado, fotoMod }) {
  const passo = $("#p3dFotosPasso", raiz);
  const dialogo = $("#p3dFotoDialogo", raiz);
  if (!passo || !dialogo || !fotoMod) return null;
  const lista = $("#p3dFotos", raiz), erro = $("#p3dFotosErro", raiz), entrada = $("#p3dFotosEntrada", raiz);
  const palco = $("#p3dFotoPalco", raiz), quadro = $("#p3dFotoQuadro", raiz), img = $("#p3dFotoImg", raiz), tela = $("#p3dFotoTela", raiz);
  const svg = $("#p3dFotoLinhas", raiz), aviso = $("#p3dFotoAviso", raiz), dica = $("#p3dFotoDica", raiz), porta = $("#p3dFotoEntrada", raiz);
  const cantos = [...raiz.querySelectorAll(".p3d-canto")];
  const botaoVer = $("#p3dFotoVer", raiz), botaoBaixar = $("#p3dFotoBaixar", raiz);
  const fotos = [];
  let aberta = null;
  let caixa = { x: 0, y: 0, w: 1, h: 1, W: 1, H: 1 };
  let chave = "";
  let projetoVisivel = true;

  const sala = () => ({ largura: Number(estado.espaco.largura), comprimento: Number(estado.espaco.comprimento) });
  const calcular = (f) => (f && f.pontos
    ? fotoMod.cameraDaFoto(f.pontos.map(([x, y]) => [x * f.largura, y * f.altura]), f.largura, f.altura, sala(), { giro: f.giro, frente: f.frente })
    : null);
  const nomeDoPonto = (f, k) => (!f.frente && k >= 2 ? (k === 2 ? "parede dir." : "parede esq.") : fotoMod.NOMES_DOS_CANTOS[(k + f.giro) % 4]);

  // no painel: as fotos que o cliente mandou (com os pontos que ele marcou), sem segurar o 3D
  const doServidor = $("#p3dFotosDados");
  if (doServidor) {
    Promise.all(JSON.parse(doServidor.textContent || "[]").map(async (d) => {
      try {
        const im = await carregarImagem(d.url);
        const c = d.cantos || {};
        const ok = Array.isArray(c.pontos) && c.pontos.length === 4;
        return { src: d.url, img: im, largura: im.naturalWidth, altura: im.naturalHeight, pontos: ok ? c.pontos : null, giro: Number(c.giro) || 0, frente: c.frente !== false };
      } catch (_) {
        return null; // a foto que não abriu fica só no link da ficha
      }
    })).then((lidas) => {
      fotos.push(...lidas.filter(Boolean));
      desenharLista();
      passo.hidden = !fotos.length;
    });
  }

  function desenharLista() {
    lista.innerHTML = fotos.map((f, i) => `<li class="p3d-foto">
        <button type="button" class="p3d-foto-abrir" data-abrir="${i}" aria-label="Ver o projeto na foto ${i + 1}">
          <img src="${escapar(f.src)}" alt="" loading="lazy">
          <span class="p3d-foto-selo${f.pontos ? " p3d-foto-selo--ok" : ""}">${f.pontos ? '<i class="fa-solid fa-check" aria-hidden="true"></i> Projeto na foto' : '<i class="fa-solid fa-crosshairs" aria-hidden="true"></i> Marcar o chão'}</span>
        </button>
        ${modo === "cliente" ? `<button type="button" class="p3d-foto-tirar" data-tirar="${i}" aria-label="Tirar a foto ${i + 1}" title="Tirar esta foto"><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>` : ""}
      </li>`).join("");
    if (entrada) entrada.closest("label").hidden = fotos.length >= MAX_FOTOS;
  }

  entrada?.addEventListener("change", async () => {
    const escolhidas = [...entrada.files];
    entrada.value = "";
    erro.hidden = true;
    const cabem = escolhidas.slice(0, MAX_FOTOS - fotos.length);
    const antes = fotos.length;
    const rotulo = entrada.closest("label");
    rotulo.classList.add("p3d-botao--esperando");
    for (const arquivo of cabem) {
      try {
        fotos.push({ ...(await prepararFoto(arquivo)), pontos: null, giro: 0, frente: true });
      } catch (_) {
        erro.textContent = "Uma das fotos não abriu. Mande em JPG ou PNG (no iPhone: Ajustes › Câmera › Formatos › Mais Compatível).";
        erro.hidden = false;
      }
    }
    rotulo.classList.remove("p3d-botao--esperando");
    if (escolhidas.length > cabem.length && erro.hidden) {
      erro.textContent = `Vão até ${MAX_FOTOS} fotos: ficaram as primeiras.`;
      erro.hidden = false;
    }
    desenharLista();
    if (fotos.length > antes) abrir(antes);
  });

  lista.addEventListener("click", (e) => {
    const a = e.target.closest("[data-abrir]");
    if (a) { abrir(Number(a.dataset.abrir)); return; }
    const t = e.target.closest("[data-tirar]");
    if (t) {
      const [f] = fotos.splice(Number(t.dataset.tirar), 1);
      if (f && f.blob) URL.revokeObjectURL(f.src);
      desenharLista();
    }
  });

  /* ---------------------------------------------------------------- o editor */
  function marcarModo() {
    raiz.querySelectorAll("[data-frente]").forEach((b) => b.setAttribute("aria-pressed", String((b.dataset.frente === "1") === aberta.frente)));
    dica.textContent = aberta.frente
      ? "Arraste os 4 pontos até os cantos do chão do espaço. Canto fora da foto? Leve o ponto para fora dela, até onde ele estaria."
      : "Os 2 pontos de cima vão nos cantos do fundo. Os 2 de baixo ficam em cima da linha do chão das paredes dos lados, na mesma distância do fundo (perto da beira da foto).";
    chave = "";
  }
  function abrir(i) {
    aberta = fotos[i];
    if (!aberta) return;
    if (!aberta.pontos) aberta.pontos = PONTOS_DE_PARTIDA.map((p) => p.slice());
    img.src = aberta.src;
    botaoBaixar.hidden = !aberta.blob; // no painel a montagem do cliente já está na ficha
    marcarModo();
    if (dialogo.showModal) dialogo.showModal(); else dialogo.setAttribute("open", "");
    requestAnimationFrame(() => { medir(); laco(); });
  }
  function fechar() {
    if (dialogo.close) { dialogo.close(); return; }
    // sem <dialog> de verdade (navegador antigo) não vem o "close"
    dialogo.removeAttribute("open");
    aberta = null;
    desenharLista();
  }
  dialogo.addEventListener("close", () => { aberta = null; desenharLista(); });
  raiz.querySelectorAll("[data-fechar-foto]").forEach((b) => b.addEventListener("click", fechar));

  function medir() {
    if (!aberta) return;
    let r = palco.getBoundingClientRect();
    // no celular (tela em pé) a margem é menor e o palco só tem a altura que a foto pede
    const m = r.width < 600 ? { e: 0.08, d: 0.08, c: 0.04, b: 0.14 } : MARGEM_DO_PALCO;
    if (r.width < 600) {
      const pede = (r.width * (1 - m.e - m.d) * (aberta.altura / aberta.largura)) / (1 - m.c - m.b);
      const altura = Math.round(Math.max(240, Math.min(window.innerHeight * 0.62, pede)));
      if (Math.abs(altura - r.height) > 2) {
        palco.style.height = `${altura}px`;
        r = palco.getBoundingClientRect();
      }
    } else if (palco.style.height) {
      palco.style.height = "";
      r = palco.getBoundingClientRect();
    }
    const livreW = r.width * (1 - m.e - m.d), livreH = r.height * (1 - m.c - m.b);
    const k = Math.min(livreW / aberta.largura, livreH / aberta.altura);
    const w = aberta.largura * k, h = aberta.altura * k;
    caixa = { x: r.width * m.e + (livreW - w) / 2, y: r.height * m.c + (livreH - h) / 2, w, h, W: r.width, H: r.height };
    Object.assign(quadro.style, { left: `${caixa.x}px`, top: `${caixa.y}px`, width: `${w}px`, height: `${h}px` });
    svg.setAttribute("viewBox", `0 0 ${r.width} ${r.height}`);
    chave = "";
  }
  new ResizeObserver(() => { if (aberta) medir(); }).observe(palco);

  // os pontos: arrastar (dedo ou mouse) ou as setas do teclado
  let arrasto = null;
  cantos.forEach((botao, k) => {
    botao.addEventListener("pointerdown", (e) => {
      if (!aberta) return;
      e.preventDefault();
      botao.setPointerCapture(e.pointerId);
      const r = palco.getBoundingClientRect();
      const [px, py] = aberta.pontos[k];
      // segura de onde pegou: o ponto não pula para baixo do dedo
      arrasto = { k, id: e.pointerId, dx: caixa.x + px * caixa.w - (e.clientX - r.left), dy: caixa.y + py * caixa.h - (e.clientY - r.top) };
      botao.classList.add("p3d-canto--ativo");
    });
    botao.addEventListener("pointermove", (e) => {
      if (!arrasto || arrasto.id !== e.pointerId || !aberta) return;
      const r = palco.getBoundingClientRect();
      const x = Math.min(r.width, Math.max(0, e.clientX - r.left + arrasto.dx));
      const y = Math.min(r.height, Math.max(0, e.clientY - r.top + arrasto.dy));
      aberta.pontos[arrasto.k] = [(x - caixa.x) / caixa.w, (y - caixa.y) / caixa.h];
    });
    const soltar = () => { arrasto = null; botao.classList.remove("p3d-canto--ativo"); };
    botao.addEventListener("pointerup", soltar);
    botao.addEventListener("pointercancel", soltar);
    botao.addEventListener("keydown", (e) => {
      const d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
      if (!d || !aberta) return;
      e.preventDefault();
      const passoPx = e.shiftKey ? 12 : 2;
      const [px, py] = aberta.pontos[k];
      const x = Math.min(caixa.W, Math.max(0, caixa.x + px * caixa.w + d[0] * passoPx));
      const y = Math.min(caixa.H, Math.max(0, caixa.y + py * caixa.h + d[1] * passoPx));
      aberta.pontos[k] = [(x - caixa.x) / caixa.w, (y - caixa.y) / caixa.h];
    });
  });

  raiz.querySelectorAll("[data-frente]").forEach((b) => b.addEventListener("click", () => {
    if (!aberta) return;
    aberta.frente = b.dataset.frente === "1";
    marcarModo();
  }));
  $("#p3dFotoGirar", raiz)?.addEventListener("click", () => { if (aberta) { aberta.giro = (aberta.giro + 1) % 4; chave = ""; } });
  botaoVer?.addEventListener("click", () => {
    projetoVisivel = !projetoVisivel;
    botaoVer.setAttribute("aria-pressed", String(projetoVisivel));
    botaoVer.querySelector("span").textContent = projetoVisivel ? "Esconder o projeto" : "Mostrar o projeto";
    chave = "";
  });
  botaoBaixar?.addEventListener("click", async () => {
    if (!aberta) return;
    const blob = await montagem(aberta).catch(() => null);
    if (!blob) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `projeto-no-meu-espaco-${metros(estado.espaco.largura)}x${metros(estado.espaco.comprimento)}m.jpg`.replace(/,/g, "-");
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  });

  // do chão do mundo (x, z) para o palco
  const noPalco = (pose, x, y, z) => {
    const [u, v, prof] = fotoMod.projetar(pose, x, y, z);
    return [caixa.x + (u / aberta.largura) * caixa.w, caixa.y + (v / aberta.altura) * caixa.h, prof];
  };
  function linhaNoChao(pose, a, b) {
    // amostrada: o pedaço atrás da câmera fica de fora
    const partes = [];
    let atual = [];
    for (let i = 0; i <= 24; i++) {
      const t = i / 24;
      const [x, y, prof] = noPalco(pose, a[0] + (b[0] - a[0]) * t, 0, a[1] + (b[1] - a[1]) * t);
      if (prof > 0.15 && Math.abs(x) < 1e5 && Math.abs(y) < 1e5) atual.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      else if (atual.length) { partes.push(atual); atual = []; }
    }
    if (atual.length) partes.push(atual);
    return partes.filter((p) => p.length > 1).map((p) => `<polyline points="${p.join(" ")}"/>`).join("");
  }

  function desenharMarcas() {
    const f = aberta;
    const P = f.pontos.map(([x, y]) => [caixa.x + x * caixa.w, caixa.y + y * caixa.h]);
    cantos.forEach((b, k) => {
      b.style.transform = `translate(${P[k][0]}px, ${P[k][1]}px)`;
      const nome = nomeDoPonto(f, k);
      b.querySelector("span").textContent = nome;
      b.setAttribute("aria-label", `Ponto ${nome}: arraste ou use as setas do teclado`);
    });
    const pose = calcular(f);
    const { largura: W, comprimento: D } = sala();
    let grade = "";
    if (pose && pose.ok) {
      // o chão do projeto em quadros de 1 ou 2 m: mostra se a perspectiva bateu
      const passoM = Math.max(W, D) > 24 ? 2 : 1;
      for (let x = -W / 2; x <= W / 2 + 1e-6; x += passoM) grade += linhaNoChao(pose, [x, -D / 2], [x, D / 2]);
      for (let z = -D / 2; z <= D / 2 + 1e-6; z += passoM) grade += linhaNoChao(pose, [-W / 2, z], [W / 2, z]);
    }
    const borda = f.frente
      ? `<polygon class="p3d-foto-marca" points="${P.map((p) => p.join(",")).join(" ")}"/>`
      : `<polyline class="p3d-foto-marca" points="${[P[3], P[0], P[1], P[2]].map((p) => p.join(",")).join(" ")}"/><line class="p3d-foto-marca p3d-foto-marca--corte" x1="${P[2][0]}" y1="${P[2][1]}" x2="${P[3][0]}" y2="${P[3][1]}"/>`;
    svg.innerHTML = `<g class="p3d-foto-grade">${grade}</g>${borda}`;

    // a entrada (o meio da parede da frente), se ela cair na tela
    porta.hidden = true;
    if (pose && pose.ok) {
      const [x, y, prof] = noPalco(pose, 0, 0, D / 2);
      if (prof > 0.15 && x > 0 && x < caixa.W && y > 0 && y < caixa.H) {
        porta.hidden = false;
        porta.style.transform = `translate(${x}px, ${y}px)`;
      }
    }

    // o aviso
    let texto = "", tipo = "";
    if (!pose) texto = "";
    else if (!pose.ok) {
      tipo = "erro";
      texto = {
        invertido: "Os pontos parecem trocados (esquerda com direita, ou fundo com frente). Confira o nome em cada ponto.",
        retangulo: "Esses pontos não fecham um retângulo no chão: os dois de baixo ficam em cima das linhas das paredes, na mesma distância do fundo.",
        pontos: "Os pontos se cruzaram. Deixe cada um no seu canto.",
      }[pose.motivo] || "Não deu para achar o ângulo da foto com esses pontos.";
    } else if (pose.motivo === "torto") {
      tipo = "atencao";
      texto = `Os pontos não fecham com um espaço de ${metros(W)} × ${metros(D)} m. Confira se cada um está no canto certo, ou se as medidas do passo 1 são as do lugar.`;
    } else if (!f.frente && pose.profundidade) {
      const fundo = f.giro % 2 ? D : W;
      texto = `Pela foto, o chão marcado tem uns ${metros(fundo)} × ${metros(Math.round(pose.profundidade * 10) / 10)} m.`;
    }
    aviso.hidden = !texto;
    aviso.textContent = texto;
    aviso.dataset.tipo = tipo;

    if (pose && pose.ok && cena && projetoVisivel) {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      try {
        cena.naFoto(tela, fotoMod.cameraThree(pose), caixa.w * dpr, caixa.h * dpr);
        tela.hidden = false;
      } catch (e) {
        console.warn("Monte seu projeto: o 3D na foto não saiu", e);
        tela.hidden = true;
      }
    } else {
      tela.hidden = true;
    }
  }
  function laco() {
    if (!aberta) return;
    requestAnimationFrame(laco);
    const nova = JSON.stringify([aberta.pontos, aberta.giro, aberta.frente, estado.espaco.largura, estado.espaco.comprimento, caixa.w, caixa.h, cena ? cena.versao() : "", projetoVisivel]);
    if (nova === chave) return;
    chave = nova;
    desenharMarcas();
  }

  /* ---------------------------------------------------------------- a montagem (a foto + o 3D), em JPEG */
  async function montagem(f) {
    const pose = calcular(f);
    if (!pose || !pose.ok || !cena) return null;
    const c = document.createElement("canvas");
    c.width = f.largura;
    c.height = f.altura;
    const g = c.getContext("2d");
    g.drawImage(f.img, 0, 0, c.width, c.height);
    // o mesmo canvas do editor, no tamanho da foto (some no próximo quadro do editor)
    cena.naFoto(tela, fotoMod.cameraThree(pose), c.width, c.height);
    g.drawImage(tela, 0, 0, c.width, c.height);
    chave = "";
    // a legenda
    const fonte = Math.max(12, Math.round(c.height * 0.026));
    const texto = `Lazer & Sport · projeto ilustrativo · ${metros(estado.espaco.largura)} × ${metros(estado.espaco.comprimento)} m`;
    g.font = `700 ${fonte}px system-ui, sans-serif`;
    const largura = g.measureText(texto).width;
    g.fillStyle = "rgba(5, 11, 31, .72)";
    g.fillRect(fonte * 0.6, c.height - fonte * 2.4, largura + fonte * 1.2, fonte * 1.8);
    g.fillStyle = "#ffd23f";
    g.fillText(texto, fonte * 1.2, c.height - fonte * 1.1);
    return paraBlob(c, "image/jpeg", 0.85);
  }

  desenharLista();
  if (modo !== "cliente") passo.hidden = true; // aparece quando as fotos do cliente abrirem
  return {
    total: () => fotos.filter((f) => f.blob).length,
    /** O que vai no pedido: cada foto, o que foi marcado nela e a montagem (quando os pontos fecham). */
    async paraOPedido() {
      const saida = [];
      for (const f of fotos) {
        if (!f.blob) continue;
        const pose = calcular(f);
        saida.push({
          foto: f.blob,
          cantos: f.pontos ? { pontos: f.pontos, giro: f.giro, frente: f.frente } : {},
          montagem: pose && pose.ok ? await montagem(f).catch(() => null) : null,
        });
      }
      return saida;
    },
  };
}

/* ======================================================================
   A CENA
   ====================================================================== */
async function criarCena(raiz, dados, geradorMod) {
  const tela = $("#p3dTela", raiz);
  const pasta = raiz.dataset.three.slice(0, raiz.dataset.three.lastIndexOf("/") + 1);
  const [T, leitorMod, utilidades, pecasMod, maquinasMod] = await Promise.all([
    import(raiz.dataset.three), import(raiz.dataset.gltf), import(pasta + "BufferGeometryUtils.js"),
    import(raiz.dataset.pecas), import(raiz.dataset.maquinas),
  ]);
  const renderer = new T.WebGLRenderer({ canvas: tela, antialias: true, preserveDrawingBuffer: false });
  const celular = window.matchMedia("(max-width: 767.98px)").matches;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, celular ? 1.5 : 2));
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = T.PCFSoftShadowMap;

  const cena = new T.Scene();
  cena.background = new T.Color("#0a1430");
  cena.fog = new T.Fog("#0a1430", 60, 220);
  cena.add(new T.HemisphereLight("#ffffff", "#8a94aa", 1.7));
  const sol = new T.DirectionalLight("#fff6e8", 2.1);
  sol.castShadow = true;
  sol.shadow.mapSize.set(celular ? 1024 : 2048, celular ? 1024 : 2048);
  sol.shadow.bias = -0.0005;
  sol.shadow.normalBias = 0.02;
  cena.add(sol, sol.target);

  // o chão de fora (a mesa da maquete) e o grupo do projeto
  const fora = new T.Mesh(new T.CircleGeometry(400, 64), new T.MeshStandardMaterial({ color: "#16213f", roughness: 0.95 }));
  fora.rotation.x = -Math.PI / 2;
  fora.position.y = -0.02;
  fora.receiveShadow = true;
  cena.add(fora);
  const projeto = new T.Group();
  cena.add(projeto);

  // as peças do projetista (as mesmas do painel) e o mini 3D das máquinas
  const base = pecasMod.desenhosBase(T, utilidades);
  const DESENHOS = base.desenhos;
  Object.assign(DESENHOS, pecasMod.desenhosExtra(T, base.ferramentas));
  const PADROES = Object.assign({}, pecasMod.CATALOGO_BASE, pecasMod.CATALOGO_EXTRA);
  const desenharMaquina = maquinasMod.criarMaquinas(T, () => { sujo = true; });
  const leitor = new leitorMod.GLTFLoader();
  const glbs = new Map();
  const carregarGlb = (url) => { if (!glbs.has(url)) glbs.set(url, leitor.loadAsync(url)); return glbs.get(url); };

  /* ---------------------------------------------------------------- a câmera */
  const camera = new T.PerspectiveCamera(40, 1, 0.1, 600);
  const camFoto = new T.PerspectiveCamera(50, 1, 0.05, 800); // a da foto do cliente
  const fotoRenderers = new Map();
  const vista = { alvo: new T.Vector3(), giro: 0.55, inclinacao: 0.78, distancia: 30 };
  let alvoVista = null; // a vista para onde a câmera desliza (planta, foco)
  let planta = false;
  let sujo = true;
  function posicionarCamera() {
    vista.inclinacao = Math.min(1.53, Math.max(0.12, vista.inclinacao));
    const c = Math.cos(vista.inclinacao);
    camera.position.set(
      vista.alvo.x + vista.distancia * c * Math.sin(vista.giro),
      vista.alvo.y + vista.distancia * Math.sin(vista.inclinacao),
      vista.alvo.z + vista.distancia * c * Math.cos(vista.giro),
    );
    camera.lookAt(vista.alvo);
  }
  function ajustarTamanho() {
    const w = tela.clientWidth || 800, h = tela.clientHeight || 500;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    sujo = true;
  }
  new ResizeObserver(ajustarTamanho).observe(tela);
  ajustarTamanho();

  // girar (arrastar), aproximar (rodinha / pinça), arrastar a vista (botão direito / dois dedos)
  const toques = new Map();
  let arrastou = false;
  tela.addEventListener("pointerdown", (e) => {
    tela.setPointerCapture(e.pointerId);
    toques.set(e.pointerId, { x: e.clientX, y: e.clientY, botao: e.button });
    arrastou = false;
    alvoVista = null;
  });
  tela.addEventListener("pointermove", (e) => {
    const antes = toques.get(e.pointerId);
    if (!antes) return;
    const dx = e.clientX - antes.x, dy = e.clientY - antes.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) arrastou = true;
    if (toques.size === 2) {
      // a pinça aproxima; os dois dedos juntos arrastam a vista
      const outro = [...toques.entries()].find(([id]) => id !== e.pointerId)[1];
      const dAntes = Math.hypot(antes.x - outro.x, antes.y - outro.y);
      const dAgora = Math.hypot(e.clientX - outro.x, e.clientY - outro.y);
      if (dAntes > 0 && dAgora > 0) vista.distancia = Math.min(250, Math.max(3, vista.distancia * (dAntes / dAgora)));
      arrastar(dx / 2, dy / 2);
    } else if (antes.botao === 2 || e.shiftKey) {
      arrastar(dx, dy);
    } else {
      vista.giro -= dx * 0.006;
      vista.inclinacao += dy * 0.005;
    }
    antes.x = e.clientX; antes.y = e.clientY;
    sujo = true;
  });
  const soltar = (e) => toques.delete(e.pointerId);
  tela.addEventListener("pointerup", (e) => { if (!arrastou && toques.size === 1) escolherNoClique(e); soltar(e); });
  tela.addEventListener("pointercancel", soltar);
  tela.addEventListener("contextmenu", (e) => e.preventDefault());
  tela.addEventListener("wheel", (e) => {
    e.preventDefault();
    vista.distancia = Math.min(250, Math.max(3, vista.distancia * Math.exp(e.deltaY * 0.0012)));
    alvoVista = null;
    sujo = true;
  }, { passive: false });
  function arrastar(dx, dy) {
    const k = vista.distancia * 0.0016;
    const frente = new T.Vector3(Math.sin(vista.giro), 0, Math.cos(vista.giro));
    const lado = new T.Vector3(frente.z, 0, -frente.x);
    vista.alvo.addScaledVector(lado, -dx * k).addScaledVector(frente, -dy * k);
  }

  /* ---------------------------------------------------------------- os nomes e a seleção */
  const camadaNomes = $("#p3dNomesCamada", raiz);
  let nomesLigados = true;
  let rotulos = [];
  const selecao = new T.BoxHelper(undefined, "#ffd23f");
  selecao.visible = false;
  cena.add(selecao);
  const ficha = $("#p3dFicha", raiz);
  let objetos = [];
  function selecionar(o) {
    if (!o) { selecao.visible = false; ficha.hidden = true; sujo = true; return; }
    selecao.setFromObject(o.grupo);
    selecao.visible = true;
    const i = o.item;
    ficha.hidden = false;
    ficha.innerHTML = `<b>${escapar(i.nome)}</b><small>${metros(i.w)} × ${metros(i.d)} m${i.h ? ` · ${metros(i.h)} m de altura` : ""}${i.area ? " · sob medida" : ""}</small>`;
    sujo = true;
  }
  const raio = new T.Raycaster();
  function escolherNoClique(e) {
    const r = tela.getBoundingClientRect();
    raio.setFromCamera(new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const acerto = raio.intersectObjects(objetos.map((o) => o.grupo), true)[0];
    selecionar(acerto ? objetos.find((o) => { let p = acerto.object; while (p && p !== o.grupo) p = p.parent; return p === o.grupo; }) : null);
  }

  /* ---------------------------------------------------------------- o chão desenhado */
  function texturaDoChao(r, W, D, cor) {
    const ppm = Math.max(16, Math.min(64, 2048 / Math.max(W, D)));
    const c = document.createElement("canvas");
    c.width = Math.round(W * ppm);
    c.height = Math.round(D * ppm);
    const g = c.getContext("2d");
    const X = (x) => (x - r.sala.x0) * ppm, Z = (z) => (z - r.sala.z0) * ppm;
    g.fillStyle = "#e9e6df";
    g.fillRect(0, 0, c.width, c.height);
    // a grade: metro a metro, e de 5 em 5 mais forte
    for (let m = 0; m <= Math.max(W, D); m++) {
      g.strokeStyle = m % 5 === 0 ? "rgba(30,41,59,.22)" : "rgba(30,41,59,.09)";
      g.lineWidth = m % 5 === 0 ? 2 : 1;
      if (m <= W) { g.beginPath(); g.moveTo(m * ppm, 0); g.lineTo(m * ppm, c.height); g.stroke(); }
      if (m <= D) { g.beginPath(); g.moveTo(0, m * ppm); g.lineTo(c.width, m * ppm); g.stroke(); }
    }
    // o corredor: os centros alcançados, alargados de meio corredor
    const p = r.passagem;
    if (p && p.alcance) {
      const raioCel = Math.max(1, Math.round(p.meio / p.g));
      const faixa = new Uint8Array(p.nx * p.nz);
      const linha = new Uint8Array(p.nx * p.nz);
      for (let k = 0; k < p.nz; k++) for (let i = 0; i < p.nx; i++) {
        if (!p.alcance[k * p.nx + i]) continue;
        for (let di = -raioCel; di <= raioCel; di++) { const ii = i + di; if (ii >= 0 && ii < p.nx) linha[k * p.nx + ii] = 1; }
      }
      for (let k = 0; k < p.nz; k++) for (let i = 0; i < p.nx; i++) {
        if (!linha[k * p.nx + i]) continue;
        for (let dk = -raioCel; dk <= raioCel; dk++) { const kk = k + dk; if (kk >= 0 && kk < p.nz) faixa[kk * p.nx + i] = 1; }
      }
      const pequeno = document.createElement("canvas");
      pequeno.width = p.nx; pequeno.height = p.nz;
      const pg = pequeno.getContext("2d");
      const img = pg.createImageData(p.nx, p.nz);
      for (let n = 0; n < faixa.length; n++) {
        if (!faixa[n]) continue;
        img.data[n * 4] = 147; img.data[n * 4 + 1] = 197; img.data[n * 4 + 2] = 253; img.data[n * 4 + 3] = 120;
      }
      pg.putImageData(img, 0, 0);
      g.imageSmoothingEnabled = true;
      g.drawImage(pequeno, 0, 0, c.width, c.height);
    }
    // as zonas: o lugar de quem joga (máquinas) e a faixa de segurança (brinquedos e áreas)
    for (const i of r.itens) {
      const z = i.zona, b = i.corpo;
      g.fillStyle = i.tipo === "area" ? hexAlfa(cor, 0.16) : i.tipo === "grande" ? "rgba(250,204,21,.22)" : "rgba(249,115,22,.18)";
      g.fillRect(X(z.x0), Z(z.z0), (z.x1 - z.x0) * ppm, (z.z1 - z.z0) * ppm);
      g.setLineDash([ppm * 0.25, ppm * 0.18]);
      g.strokeStyle = i.tipo === "area" ? hexAlfa(cor, 0.7) : "rgba(234,88,12,.55)";
      g.lineWidth = Math.max(1.5, ppm * 0.04);
      g.strokeRect(X(z.x0), Z(z.z0), (z.x1 - z.x0) * ppm, (z.z1 - z.z0) * ppm);
      g.setLineDash([]);
      if (i.tipo !== "area") {
        g.fillStyle = "rgba(15,23,42,.18)";
        g.fillRect(X(b.x0), Z(b.z0), (b.x1 - b.x0) * ppm, (b.z1 - b.z0) * ppm);
      }
    }
    // a entrada
    const h = r.hall;
    g.fillStyle = "rgba(34,197,94,.30)";
    g.fillRect(X(h.x0), Z(h.z0), (h.x1 - h.x0) * ppm, (h.z1 - h.z0) * ppm);
    g.fillStyle = "#15803d";
    g.font = `800 ${Math.max(11, ppm * 0.42)}px system-ui, sans-serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText("ENTRADA", X((h.x0 + h.x1) / 2), Z(h.z1) - ppm * 0.55);
    g.beginPath();
    const ax = X((h.x0 + h.x1) / 2), az = Z(h.z1) - ppm * 1.25;
    g.moveTo(ax, az - ppm * 0.35); g.lineTo(ax - ppm * 0.3, az + ppm * 0.05); g.lineTo(ax + ppm * 0.3, az + ppm * 0.05); g.closePath(); g.fill();
    // as medidas do espaço, junto das paredes
    g.fillStyle = "rgba(15,23,42,.6)";
    g.font = `700 ${Math.max(12, ppm * 0.5)}px system-ui, sans-serif`;
    g.fillText(`${metros(W)} m`, c.width / 2, ppm * 0.45);
    g.save();
    g.translate(ppm * 0.45, c.height / 2);
    g.rotate(-Math.PI / 2);
    g.fillText(`${metros(D)} m`, 0, 0);
    g.restore();
    const tex = new T.CanvasTexture(c);
    tex.colorSpace = T.SRGBColorSpace;
    tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
    return tex;
  }
  function hexAlfa(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  /* ---------------------------------------------------------------- as paredes (somem do lado da câmera) */
  let paredes = [];
  function fazerParedes(r, W, D, H) {
    const vidro = new T.MeshStandardMaterial({ color: "#f8fafc", transparent: true, opacity: 0.32, side: T.DoubleSide, depthWrite: false, roughness: 0.9 });
    const rodape = new T.MeshStandardMaterial({ color: "#cbd5e1", roughness: 0.8 });
    const lista = [];
    const parede = (largura, x, z, giro, normal, xs) => {
      const g = new T.Group();
      const m = new T.Mesh(new T.PlaneGeometry(largura, H), vidro);
      m.position.y = H / 2;
      g.add(m);
      const rp = new T.Mesh(new T.BoxGeometry(largura, 0.12, 0.04), rodape);
      rp.position.y = 0.06;
      g.add(rp);
      g.position.set(x, 0, z);
      g.rotation.y = giro;
      projeto.add(g);
      lista.push({ g, normal: new T.Vector3(...normal), ponto: new T.Vector3(xs ?? x, 0, z) });
    };
    parede(W, 0, -D / 2, 0, [0, 0, 1]);
    parede(D, -W / 2, 0, Math.PI / 2, [1, 0, 0]);
    parede(D, W / 2, 0, -Math.PI / 2, [-1, 0, 0]);
    // a da frente, com o vão da porta
    const porta = r.porta, lado = (W - porta) / 2;
    if (lado > 0.05) {
      parede(lado, -W / 2 + lado / 2, D / 2, Math.PI, [0, 0, -1], 0);
      parede(lado, W / 2 - lado / 2, D / 2, Math.PI, [0, 0, -1], 0);
    }
    // o contorno do alto das paredes, sempre à vista (o desenho da sala)
    const contorno = new T.LineSegments(
      new T.EdgesGeometry(new T.BoxGeometry(W, H, D)),
      new T.LineBasicMaterial({ color: "#94a3b8", transparent: true, opacity: 0.55 }),
    );
    contorno.position.y = H / 2;
    projeto.add(contorno);
    contornoAtual = contorno;
    return lista;
  }
  function esconderParedes() {
    for (const p of paredes) {
      const paraCamera = camera.position.clone().sub(p.ponto);
      p.g.visible = paraCamera.dot(p.normal) > 0;
    }
  }

  /* ---------------------------------------------------------------- desenhar o projeto */
  let versao = 0;
  let carregados = 0; // os .glb que chegaram depois do desenho (a foto do cliente redesenha com eles)
  let ultimoTamanho = "";
  let chaoAtual = null, contornoAtual = null, sombraAtual = null;
  function limpar() {
    projeto.traverse((o) => {
      if (o.isMesh || o.isLineSegments) {
        if (o.userData.doGlb) return;
        o.geometry?.dispose();
        if (o.material && o.material.map && o.material.map.isCanvasTexture) o.material.map.dispose();
      }
    });
    projeto.clear();
    rotulos.forEach((r) => r.el.remove());
    rotulos = [];
    objetos = [];
    selecionar(null);
  }
  function rotular(texto, x, y, z, tipo) {
    const el = document.createElement("span");
    el.className = "p3d-nome p3d-nome--" + tipo;
    el.textContent = texto;
    camadaNomes.appendChild(el);
    rotulos.push({ el, pos: new T.Vector3(x, y, z) });
  }
  function desenhar(r, estado) {
    const minha = ++versao;
    limpar();
    const { largura: W, comprimento: D, pe_direito: H } = r.sala;
    const chao = new T.Mesh(new T.PlaneGeometry(W, D), new T.MeshStandardMaterial({ map: texturaDoChao(r, W, D, estado.cor), roughness: 0.85 }));
    chao.rotation.x = -Math.PI / 2;
    chao.receiveShadow = true;
    projeto.add(chao);
    chaoAtual = chao;
    // na foto do cliente o chão é o dele: fica só a sombra do projeto
    const sombra = new T.Mesh(new T.PlaneGeometry(W, D), new T.ShadowMaterial({ opacity: 0.32 }));
    sombra.rotation.x = -Math.PI / 2;
    sombra.position.y = 0.002;
    sombra.receiveShadow = true;
    sombra.visible = false;
    projeto.add(sombra);
    sombraAtual = sombra;
    paredes = fazerParedes(r, W, D, H);

    // a luz e a sombra cobrem a sala
    const maior = Math.max(W, D);
    sol.position.set(W * 0.35, maior * 1.1 + 8, D * 0.55);
    Object.assign(sol.shadow.camera, { left: -maior * 0.75, right: maior * 0.75, top: maior * 0.75, bottom: -maior * 0.75, near: 1, far: maior * 3 + 30 });
    sol.shadow.camera.updateProjectionMatrix();

    // a câmera recentraliza só quando o tamanho do espaço muda
    const tamanho = `${W}x${D}`;
    if (tamanho !== ultimoTamanho) {
      ultimoTamanho = tamanho;
      vista.alvo.set(0, 0, 0);
      vista.distancia = maior * 1.35 + 4;
    }

    const paleta = geradorMod.paletaDaCor(estado.cor, estado.estilo);
    r.itens.forEach((item, indice) => {
      const grupo = new T.Group();
      grupo.position.set(item.x, 0, item.z);
      projeto.add(grupo);
      objetos.push({ item, grupo });
      if (item.area) {
        const op = (estado.opcoes || {})[item.area.tipo] || {};
        const ideia = geradorMod.gerar(item.area.tipo, { largura: item.area.largura, profundidade: item.area.profundidade, altura: H }, estado.cor, estado.semente, {
          estilo: estado.estilo, porte: op.porte && op.porte !== "auto" ? op.porte : "", sem: op.sem || [],
        });
        const miolo = new T.Group();
        if (item.area.girar) miolo.rotation.y = Math.PI / 2;
        for (const peca of ideia.pecas) {
          const desenho = DESENHOS[peca.tipo];
          if (!desenho) continue;
          const d = Object.assign({}, (PADROES[peca.tipo] || {}).d || {}, peca.d || {});
          const g = new T.Group();
          desenho(d, peca.cor, { cor2: peca.cor2 }).forEach((m) => g.add(m));
          g.position.fromArray(peca.p || [0, 0, 0]);
          g.rotation.y = ((peca.r || 0) * Math.PI) / 180;
          miolo.add(g);
        }
        grupo.add(miolo);
        rotular(item.nome, item.x, Math.min(H, 2.6), item.z, "area");
        return;
      }
      grupo.rotation.y = ((item.r || 0) * Math.PI) / 180;
      const ficha = itensPorIdDaCena.get(item.ref) || {};
      if (ficha.modelo) {
        // o .glb no tamanho real; até chegar (ou se falhar), o mini 3D segura o lugar
        const reserva = desenharMaquina(item.desenho, item.w, item.h, item.d, { capa: ficha.capa, cor: paleta.varias[indice % paleta.varias.length] });
        grupo.add(reserva);
        carregarGlb(ficha.modelo).then((gltf) => {
          if (minha !== versao) return;
          const copia = gltf.scene.clone(true);
          copia.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.userData.doGlb = true; } });
          const caixa = new T.Box3().setFromObject(copia);
          copia.position.x -= (caixa.min.x + caixa.max.x) / 2;
          copia.position.z -= (caixa.min.z + caixa.max.z) / 2;
          copia.position.y -= caixa.min.y;
          grupo.remove(reserva);
          reserva.traverse((o) => o.geometry?.dispose());
          grupo.add(copia);
          carregados++;
          sujo = true;
        }).catch(() => {});
      } else {
        grupo.add(desenharMaquina(item.desenho, item.w, item.h, item.d, { capa: ficha.capa, cor: paleta.varias[indice % paleta.varias.length] }));
      }
      grupo.traverse((o) => { if (o.isMesh) o.castShadow = true; });
      // a fileira da mesma máquina leva um nome só (o da primeira)
      const vizinha = r.itens.slice(0, indice).some((o) => o.ref === item.ref && Math.hypot(o.x - item.x, o.z - item.z) < Math.max(item.w, item.d) + 1.2);
      if (item.tipo === "grande" || item.principal) rotular(item.nome, item.x, item.h + 0.35, item.z, "grande");
      else if (!vizinha) rotular(item.nome, item.x, item.h + 0.25, item.z, "maquina");
    });
    camadaNomes.hidden = !nomesLigados;
    sujo = true;
  }
  const itensPorIdDaCena = new Map(dados.itens.map((i) => [i.id, i]));

  /* ---------------------------------------------------------------- o laço (só quando algo muda) */
  const projetar = new T.Vector3();
  function quadro() {
    requestAnimationFrame(quadro);
    if (alvoVista) {
      const k = 0.14;
      vista.giro += (alvoVista.giro - vista.giro) * k;
      vista.inclinacao += (alvoVista.inclinacao - vista.inclinacao) * k;
      vista.distancia += (alvoVista.distancia - vista.distancia) * k;
      vista.alvo.lerp(alvoVista.alvo, k);
      sujo = true;
      if (Math.abs(alvoVista.inclinacao - vista.inclinacao) < 0.002 && Math.abs(alvoVista.distancia - vista.distancia) < 0.02 && vista.alvo.distanceTo(alvoVista.alvo) < 0.01) alvoVista = null;
    }
    if (!sujo) return;
    sujo = false;
    posicionarCamera();
    esconderParedes();
    renderer.render(cena, camera);
    if (nomesLigados && rotulos.length) {
      const w = tela.clientWidth, h = tela.clientHeight;
      for (const r of rotulos) {
        projetar.copy(r.pos).project(camera);
        const visivel = projetar.z < 1 && Math.abs(projetar.x) < 1.1 && Math.abs(projetar.y) < 1.1;
        r.el.style.display = visivel ? "" : "none";
        if (visivel) r.el.style.transform = `translate(${((projetar.x + 1) / 2) * w}px, ${((1 - projetar.y) / 2) * h}px) translate(-50%, -100%)`;
      }
    }
  }
  requestAnimationFrame(quadro);

  return {
    desenhar,
    alternarPlanta() {
      planta = !planta;
      alvoVista = planta
        ? { giro: 0, inclinacao: 1.5, distancia: vista.distancia, alvo: new T.Vector3(0, 0, 0) }
        : { giro: 0.55, inclinacao: 0.78, distancia: vista.distancia, alvo: new T.Vector3(0, 0, 0) };
      return planta;
    },
    alternarNomes() {
      nomesLigados = !nomesLigados;
      camadaNomes.hidden = !nomesLigados;
      sujo = true;
      return nomesLigados;
    },
    focar(nome) {
      const o = objetos.find((x) => x.item.nome === nome);
      if (!o) return;
      selecionar(o);
      const i = o.item;
      alvoVista = { giro: vista.giro, inclinacao: Math.max(0.5, vista.inclinacao), distancia: Math.max(6, Math.max(i.w, i.d) * 2.2 + 3), alvo: new T.Vector3(i.x, 0, i.z) };
      tela.scrollIntoView({ behavior: "smooth", block: "nearest" });
    },
    imagem() {
      posicionarCamera();
      esconderParedes();
      renderer.render(cena, camera);
      return tela.toDataURL("image/png");
    },
    /** Muda a cada desenho e a cada .glb que chega: a foto do cliente sabe quando redesenhar. */
    versao: () => `${versao}.${carregados}`,
    /**
     * O projeto na foto do cliente: desenha no `canvas` (fundo transparente, para ir por cima da foto)
     * o projeto visto pela câmera da foto (foto3d.cameraThree), em largura × altura pixels.
     * Sem paredes, sem o chão desenhado e sem a mesa: só as peças e a sombra delas no chão de verdade.
     */
    naFoto(canvas, cam, largura, altura) {
      let r = fotoRenderers.get(canvas);
      if (!r) {
        r = new T.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
        r.outputColorSpace = T.SRGBColorSpace;
        r.toneMapping = T.ACESFilmicToneMapping;
        r.toneMappingExposure = 1.05;
        r.shadowMap.enabled = true;
        r.shadowMap.type = T.PCFSoftShadowMap;
        r.setClearColor(0x000000, 0);
        fotoRenderers.set(canvas, r);
      }
      r.setPixelRatio(1);
      r.setSize(Math.max(1, Math.round(largura)), Math.max(1, Math.round(altura)), false);
      camFoto.fov = cam.fov;
      camFoto.aspect = cam.aspecto;
      camFoto.near = 1; // o que está a menos de 1 m da lente fica de fora: é onde o fotógrafo está
      camFoto.far = 800;
      camFoto.position.fromArray(cam.posicao);
      camFoto.quaternion.setFromRotationMatrix(new T.Matrix4().makeBasis(...cam.eixos.map((e) => new T.Vector3(...e))));
      camFoto.updateProjectionMatrix();
      camFoto.updateMatrixWorld();
      const antes = { fundo: cena.background, nevoa: cena.fog, fora: fora.visible, selecao: selecao.visible };
      cena.background = null;
      cena.fog = null;
      fora.visible = false;
      selecao.visible = false;
      for (const p of paredes) p.g.visible = false;
      if (contornoAtual) contornoAtual.visible = false;
      if (chaoAtual) chaoAtual.visible = false;
      if (sombraAtual) sombraAtual.visible = true;
      try {
        r.render(cena, camFoto);
      } finally {
        cena.background = antes.fundo;
        cena.fog = antes.nevoa;
        fora.visible = antes.fora;
        selecao.visible = antes.selecao;
        if (contornoAtual) contornoAtual.visible = true;
        if (chaoAtual) chaoAtual.visible = true;
        if (sombraAtual) sombraAtual.visible = false;
        sujo = true; // as paredes voltam pela câmera do 3D no próximo quadro
      }
      return canvas;
    },
  };
}

const raiz = document.getElementById("p3d");
if (raiz) {
  const comecar = () => iniciar(raiz).catch((erro) => console.error("Monte seu projeto", erro));
  // na Arena 3D o app só acorda perto da tela (a roda 3D já está ocupando a placa de vídeo);
  // o link de um projeto (#p=...) acorda na hora e leva até ele
  const doLink = /^#p=/.test(location.hash);
  if (doLink) requestAnimationFrame(() => raiz.scrollIntoView({ block: "start" }));
  if (raiz.dataset.preguica && !doLink && "IntersectionObserver" in window) {
    const vigia = new IntersectionObserver((vistos) => {
      if (vistos.some((v) => v.isIntersecting)) { vigia.disconnect(); comecar(); }
    }, { rootMargin: "600px 0px" });
    vigia.observe(raiz);
  } else {
    comecar();
  }
}
