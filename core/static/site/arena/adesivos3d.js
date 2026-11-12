/* ======================================================================
   O CONTROLE DOS ADESIVOS NAS ÁREAS 3D (LEIA-ME, seção 72)

   O cliente: "TUDO DEVE AFUNILAR PARA UM OBJETO SÓ, PODENDO VISUALIZAR, EM
   ÁREAS 3D E ETC, TAMBÉM DEVE SER POSSÍVEL MUDAR PARA VER OS ADESIVOS". O
   produto é um só (o Air Game Kids, o Basquete Home), com um 3D para cada
   adesivo (os Astronautas e os Alienígenas). Este controle -- "Adesivo:
   Astronautas · Alienígenas" -- fica sobre o visualizador e troca o .glb
   ali mesmo: o mesmo em toda área 3D (a página do produto: visor3d.js; o
   "Ver em 3D" da proposta: orcamento-3d.js; a Arena: arena3d.js).

     chipsDeAdesivo({ modelos, atual, aoEscolher, onde })

   `modelos`: [{ nome, url }]; `atual`: o índice do que está no visor;
   `aoEscolher(modelo, indice)`: troca o .glb (pode devolver uma promessa:
   o controle espera, com o botão em "carregando"). Devolve o elemento (o
   chamador o põe onde quiser). O estilo vem junto (uma vez por página).
   ====================================================================== */

const ESTILO = `
.adesivos3d {
  display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 6px 8px; border-radius: 999px;
  background: rgba(5, 11, 31, .72); color: #e2e8f0;
  font: 600 13px/1.1 inherit; box-shadow: 0 4px 16px rgba(0, 0, 0, .35);
  -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px);
}
.adesivos3d-rotulo { padding: 0 4px 0 6px; color: #cbd5e1; font-weight: 700; }
.adesivos3d button {
  appearance: none; border: 1px solid rgba(148, 163, 184, .45); border-radius: 999px;
  background: rgba(15, 23, 42, .6); color: #f1f5f9; padding: 6px 12px; min-height: 32px;
  font: inherit; cursor: pointer; transition: background .15s ease, border-color .15s ease;
}
.adesivos3d button:hover { border-color: rgba(96, 165, 250, .9); }
.adesivos3d button[aria-pressed="true"] { background: #2563eb; border-color: #60a5fa; color: #fff; }
.adesivos3d button[aria-busy="true"] { opacity: .65; cursor: progress; }
.adesivos3d button:focus-visible { outline: 3px solid #3fd0ff; outline-offset: 2px; }
.adesivos3d--sobre { position: absolute; left: 12px; top: 12px; z-index: 4; max-width: calc(100% - 24px); }
@media (max-width: 600px) { .adesivos3d { font-size: 12px; } .adesivos3d button { padding: 5px 10px; } }
`;

function estilo() {
  if (document.getElementById("adesivos3d-estilo")) return;
  const tag = document.createElement("style");
  tag.id = "adesivos3d-estilo";
  tag.textContent = ESTILO;
  document.head.appendChild(tag);
}

export function chipsDeAdesivo({ modelos, atual = 0, aoEscolher, onde = "sobre" }) {
  estilo();
  const caixa = document.createElement("div");
  caixa.className = `adesivos3d${onde === "sobre" ? " adesivos3d--sobre" : ""}`;
  caixa.setAttribute("role", "group");
  caixa.setAttribute("aria-label", "Adesivo do 3D");
  caixa.dataset.adesivos3dControle = "";
  const rotulo = document.createElement("span");
  rotulo.className = "adesivos3d-rotulo";
  rotulo.textContent = "Adesivo:";
  caixa.appendChild(rotulo);
  let escolhido = atual;
  let ocupado = false;
  const botoes = modelos.map((modelo, i) => {
    const botao = document.createElement("button");
    botao.type = "button";
    botao.textContent = modelo.nome;
    botao.dataset.adesivo = modelo.nome;
    botao.setAttribute("aria-pressed", i === atual ? "true" : "false");
    botao.addEventListener("click", async (evento) => {
      evento.stopPropagation();
      if (ocupado || i === escolhido) return;
      ocupado = true;
      botao.setAttribute("aria-busy", "true");
      try {
        await aoEscolher(modelo, i);
        escolhido = i;
        botoes.forEach((b, k) => b.setAttribute("aria-pressed", k === i ? "true" : "false"));
      } catch (erro) {
        console.error("Adesivo 3D: não trocou", erro);
      } finally {
        botao.removeAttribute("aria-busy");
        ocupado = false;
      }
    });
    caixa.appendChild(botao);
    return botao;
  });
  // os eventos do arrastar o 3D não passam pelo controle
  ["pointerdown", "pointermove", "wheel", "dblclick"].forEach((tipo) => {
    caixa.addEventListener(tipo, (e) => e.stopPropagation(), { passive: true });
  });
  // quem trocou o adesivo por fora (o seletor da galeria da página) marca o botão aqui
  caixa.marcar = (i) => {
    escolhido = i;
    botoes.forEach((b, k) => b.setAttribute("aria-pressed", k === i ? "true" : "false"));
  };
  return caixa;
}

/** Os modelos do JSON de um <script type="application/json"> (pelo id) ou de um atributo com o JSON. */
export function lerModelos(valor) {
  if (!valor) return [];
  try {
    const tag = document.getElementById(valor);
    return JSON.parse(tag ? tag.textContent : valor) || [];
  } catch (erro) {
    return [];
  }
}
