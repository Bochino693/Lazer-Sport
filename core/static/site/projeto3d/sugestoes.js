/* ======================================================================
   AS PROPOSTAS PARA O ESPAÇO DO CLIENTE (o "Monte seu espaço").

   O cliente digita o tamanho do lugar e, antes de escolher qualquer coisa,
   já vê as melhores ideias para AQUELE espaço: o programa monta várias
   combinações (cada modelo de espaço sozinho; com a área baby; com as
   máquinas nas paredes; com um brinquedão...), arruma cada uma de verdade
   (o arrumador: entrada, corredor de 1,20 m, faixas de segurança, o que
   cabe e o que fica de fora) e dá uma nota:

     * o espaço bem usado: perto de 70% com uso (nem vazio, nem apertado);
     * variedade: quantas atividades diferentes;
     * o modelo principal forte: o porte (compacto, médio, grande) e o
       pedaço do espaço que ele ocupa;
     * nada de fora: a combinação que não cabe inteira não entra (a das
       máquinas tenta com menos máquinas antes de desistir).

   As três melhores, de modelos diferentes, viram cartões com a planta em
   miniatura; um toque aplica a proposta e o cliente segue ajustando.

   Só cálculo (nada de three.js nem de página): roda igual no navegador e
   nos testes (core/tests_js/sugestoes.mjs).
   ====================================================================== */

const MAQUINAS_MAX = 10;
// O quanto cada modelo atrai como o principal do espaço (a área baby é melhor de apoio que de atração principal).
const ATRACAO = { trampolim: 1, esportivo: 0.95, ninja: 0.9, brinquedao: 0.9, baby: 0.55 };

/** As máquinas para propor: uma de cada tipo (desenho), as que têm 3D primeiro. */
function maquinasDoCatalogo(catalogo) {
  const vistas = new Set();
  return (catalogo.itens || [])
    .filter((i) => i.tipo === "maquina")
    .sort((a, b) => Number(Boolean(b.modelo)) - Number(Boolean(a.modelo)))
    .filter((i) => {
      const chave = i.desenho || i.id;
      if (vistas.has(chave)) return false;
      vistas.add(chave);
      return true;
    });
}

/** As combinações a experimentar para o espaço (escolhas no formato do arrumador). */
export function combinacoes(espaco, catalogo) {
  const W = Number(espaco.largura) || 0, D = Number(espaco.comprimento) || 0, H = Number(espaco.pe_direito) || 4;
  const area = W * D;
  const areas = catalogo.areas || {};
  const maquinas = maquinasDoCatalogo(catalogo);
  const lista = [];
  const base = (principal) => ({ principal: principal ? { tipo: "area", area: principal } : null, areas: [], itens: [], opcoes: {} });
  const comMaquinas = (escolha, n) => ({
    ...escolha,
    itens: maquinas.slice(0, n).map((m) => ({ id: String(m.id), qtd: 1 })),
  });
  // quantas máquinas o espaço pede além do principal (uma a cada ~18 m² que sobram)
  const nMaq = (sobra) => Math.max(0, Math.min(MAQUINAS_MAX, maquinas.length, Math.round(sobra / 18)));
  for (const [chave, a] of Object.entries(areas)) {
    if (H + 1e-6 < (a.pe_direito_minimo || 0)) continue;
    const so = base(chave);
    lista.push(so);
    const ocupa = Math.min(area * 0.6, (a.max_principal || a.max || a.ideal)[0] * (a.max_principal || a.max || a.ideal)[1]);
    const sobra = area - ocupa;
    if (chave !== "baby" && area >= 110 && H >= (areas.baby || {}).pe_direito_minimo) {
      lista.push({ ...so, areas: ["baby"] });
      if (maquinas.length && sobra >= 60) lista.push(comMaquinas({ ...so, areas: ["baby"] }, nMaq(sobra - 30)));
    }
    if (maquinas.length && sobra >= 25) lista.push(comMaquinas(so, nMaq(sobra)));
    if (["trampolim", "esportivo", "ninja"].includes(chave) && area >= 260 && areas.brinquedao && H >= areas.brinquedao.pe_direito_minimo) {
      lista.push({ ...so, areas: ["brinquedao"] });
      lista.push({ ...so, areas: ["brinquedao", "baby"] });
    }
    if (chave === "brinquedao" && area >= 200 && areas.ninja && H >= areas.ninja.pe_direito_minimo) {
      lista.push({ ...so, areas: ["ninja", "baby"] });
    }
  }
  // o espaço só de máquinas (o que sempre cabe; vale mais em espaço pequeno ou baixo)
  if (maquinas.length) lista.push(comMaquinas(base(""), Math.max(2, nMaq(area * 0.7))));
  return lista;
}

/** A nota de uma combinação já arrumada (maior é melhor); null se algo ficou de fora. */
export function nota(r, escolha, gerador) {
  if (r.recusados.length) return null;
  const n = r.numeros;
  const ocup = n.ocupacao;
  let pontos = 100 - Math.abs(ocup - 70) * 1.4;
  const areas = r.itens.filter((i) => i.area);
  const maquinas = r.itens.filter((i) => !i.area);
  const tipos = new Set(areas.map((i) => i.area.tipo));
  pontos += tipos.size * 7 + Math.min(4, new Set(maquinas.map((i) => i.desenho || i.ref)).size) * 3;
  const principal = areas.find((i) => i.principal);
  if (principal) {
    const porte = gerador && gerador.porteQueCabe ? gerador.porteQueCabe(principal.area.tipo, principal.area.largura, principal.area.profundidade) : null;
    if (porte) pontos += porte.chave === "grande" ? 16 : porte.chave === "medio" ? 10 : 0;
    // o modelo do espaço tem de ser o forte: pelo menos um terço do espaço
    const parte = (principal.w * principal.d) / n.area;
    pontos += Math.min(parte, 0.6) * 30 - (parte < 0.25 ? 15 : 0);
    // o que atrai mais, e o que aproveita o pé-direito (um salão de 6 m pede trampolim, não só área baby)
    const tipo = principal.area.tipo;
    pontos += (ATRACAO[tipo] ?? 0.8) * 18;
    const pedeAltura = (gerador && gerador.PE_DIREITO ? gerador.PE_DIREITO[tipo] : 0) || { trampolim: 4, esportivo: 3, ninja: 3, brinquedao: 2.6, baby: 2.2 }[tipo] || 3;
    const H = Number(r.sala.pe_direito) || 4;
    pontos += Math.min(1, pedeAltura / H) * 10;
  } else {
    pontos -= 18; // só máquinas é a última ideia (a não ser que nada mais caiba)
  }
  if (ocup > 90) pontos -= 20;
  return pontos;
}

/**
 * As melhores propostas para o espaço: [{escolha, resultado, nota, titulo, linhas}], até `limite`,
 * de modelos diferentes. `arrumar` é o do arrumador; `gerador` (opcional) dá o porte.
 */
export function sugerir(espaco, catalogo, arrumar, gerador, { limite = 3 } = {}) {
  const avaliadas = [];
  for (const escolha of combinacoes(espaco, catalogo)) {
    let atual = escolha;
    let r = arrumar(espaco, { ...atual, estilo: "colorido", cor: "#2563eb", semente: 1 }, catalogo);
    // com máquinas demais: tira duas de cada vez até caber (ou ficar sem nenhuma)
    while (r.recusados.length && atual.itens.length && r.recusados.every((x) => !x.principal && x.tipo !== "area")) {
      atual = { ...atual, itens: atual.itens.slice(0, Math.max(0, atual.itens.length - 2)) };
      r = arrumar(espaco, { ...atual, estilo: "colorido", cor: "#2563eb", semente: 1 }, catalogo);
    }
    const pontos = nota(r, atual, gerador);
    if (pontos === null) continue;
    avaliadas.push({ escolha: atual, resultado: r, nota: pontos });
  }
  avaliadas.sort((a, b) => b.nota - a.nota);
  // uma por modelo principal (variedade), na ordem da nota
  const escolhidas = [];
  const vistos = new Set();
  for (const a of avaliadas) {
    const chave = a.escolha.principal ? a.escolha.principal.area : "maquinas";
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    escolhidas.push(a);
    if (escolhidas.length >= limite) break;
  }
  return escolhidas.map((a) => ({ ...a, ...descrever(a.resultado, catalogo, gerador) }));
}

const m2 = (v) => (Math.round(v * 100) / 100).toFixed(2).replace(".", ",").replace(",00", "").replace(/(,\d)0$/, "$1");

/** O título e as linhas do cartão: o modelo (com o porte), as outras áreas, as máquinas e o uso. */
export function descrever(r, catalogo, gerador) {
  const areas = r.itens.filter((i) => i.area);
  const maquinas = r.itens.filter((i) => !i.area);
  const nomeDaArea = (i) => {
    const a = (catalogo.areas || {})[i.area.tipo] || {};
    const porte = gerador && gerador.porteQueCabe ? gerador.porteQueCabe(i.area.tipo, i.area.largura, i.area.profundidade) : null;
    const nomePorte = porte && (a.portes || []).length ? ((a.portes.find((p) => p.chave === porte.chave) || {}).nome || "") : "";
    return `${a.nome || i.nome}${nomePorte ? ` ${nomePorte.toLowerCase()}` : ""}`;
  };
  const principal = areas.find((i) => i.principal);
  const outras = areas.filter((i) => !i.principal);
  const partes = [];
  if (outras.length) partes.push(outras.map((i) => ((catalogo.areas || {})[i.area.tipo] || {}).nome || i.nome).join(" e ").toLowerCase());
  if (maquinas.length) partes.push(`${maquinas.length} ${maquinas.length === 1 ? "máquina" : "máquinas"}`);
  const titulo = principal
    ? `${nomeDaArea(principal)}${partes.length ? ` + ${partes.join(" + ")}` : ""}`
    : `Só máquinas: ${maquinas.length} jogos`;
  const linhas = areas.map((i) => `${nomeDaArea(i)} de ${m2(i.area.largura)} × ${m2(i.area.profundidade)} m`);
  if (maquinas.length) {
    const nomes = [...new Set(maquinas.map((i) => i.nome))];
    linhas.push(`${maquinas.length} ${maquinas.length === 1 ? "máquina" : "máquinas"}: ${nomes.slice(0, 4).join(", ")}${nomes.length > 4 ? "…" : ""}`);
  }
  linhas.push(`${r.numeros.ocupacao}% do espaço em uso, com corredor de 1,20 m até tudo`);
  return { titulo, linhas };
}
