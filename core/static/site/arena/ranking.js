/* ======================================================================
   RANKING E PARTIDA GRÁTIS — a parte do simulador que conhece a pessoa.

   O console (console.js) só avisa: "console:abrir" (trocou de jogo),
   "console:jogar" (vai começar, dá para segurar), "console:resultado" (o
   placar final, que vai na hora para o ranking) e "console:fim" (acabou,
   com os pontos). Aqui mora o resto:

   - VISITANTE SEM CONTA tem 2 JOGADAS GRÁTIS NO TOTAL, somando todos os
     jogos do site (aqui, cada partida é uma: perdeu duas, acabou; ou jogou
     dois jogos uma vez cada). A conta é do servidor (/jogos/abriu/ com
     "gastar"), que a página traz ao abrir (jogador.gratis). Ao acabar a
     última partida (ou ao apertar Jogar de novo) vem o convite de cadastro,
     que leva sozinho para a tela de criar conta em poucos segundos. O placar
     vai para o ranking quando a pessoa entra (core/ranking.py), e ela volta
     para o mesmo jogo.
   - CADASTRADO joga à vontade: cada fim de partida grava o recorde e o
     ranking (do jogo e geral) se atualiza na ficha.
   ====================================================================== */

const pagina = document.querySelector("[data-simulador]");
const raiz = pagina && pagina.querySelector("[data-console]");
const dadosDoJogador = document.getElementById("sim-jogador");

const SEGUNDOS_PARA_IR = 8;

if (raiz && dadosDoJogador) {
  const jogador = JSON.parse(dadosDoJogador.textContent);
  const logado = !!jogador.logado;
  let jogoAtual = jogador.jogo;
  let aba = "jogo";

  // as jogadas grátis (de todos os jogos): o servidor diz quantas já foram ao abrir a página;
  // as desta página entram na conta na hora (o Jogar não pode esperar a resposta)
  const gratis = jogador.gratis || null;
  const LIMITE = gratis ? gratis.limite : 2;
  let usadas = gratis ? gratis.usadas : 0;
  const restantes = () => Math.max(0, LIMITE - usadas);

  const csrf = () => {
    const achado = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return achado ? decodeURIComponent(achado[1]) : "";
  };
  const numero = (valor) => Number(valor || 0).toLocaleString("pt-BR");

  /* ---------- o ranking da ficha ---------- */
  const caixa = pagina.querySelector("[data-sim-ranking]");
  const listas = {
    jogo: caixa.querySelector('[data-ranking-lista="jogo"]'),
    geral: caixa.querySelector('[data-ranking-lista="geral"]'),
  };
  const nota = caixa.querySelector("[data-ranking-nota]");
  const linhaEu = caixa.querySelector("[data-ranking-eu]");
  const VAZIO = {
    jogo: "Ninguém no ranking deste jogo ainda. Seja o primeiro!",
    geral: "O ranking geral começa com a primeira partida de um cadastrado.",
  };

  const preencher = (qual, linhas) => {
    if (!linhas.length) {
      const item = document.createElement("li");
      item.className = "sim-ranking-vazio";
      item.textContent = VAZIO[qual];
      listas[qual].replaceChildren(item);
      return;
    }
    listas[qual].replaceChildren(...linhas.map((linha) => {
      const item = document.createElement("li");
      const posicao = document.createElement("b");
      posicao.textContent = `${linha.posicao}º`;
      const nome = document.createElement("span");
      nome.textContent = linha.nome;
      const pontos = document.createElement("strong");
      pontos.textContent = numero(linha.pontos);
      item.append(posicao, nome, pontos);
      return item;
    }));
  };

  const mostrarEu = (eu) => {
    if (!logado || !eu) return;
    const partes = [];
    partes.push(eu.jogo ? `${eu.jogo.posicao}º neste jogo, com ${numero(eu.jogo.pontos)} pontos` : "jogue uma partida para entrar no ranking deste jogo");
    if (eu.geral) partes.push(`${eu.geral.posicao}º no geral`);
    linhaEu.textContent = `Você: ${partes.join(" · ")}.`;
  };

  let pedido = 0;
  const atualizar = (slug) => {
    const meu = ++pedido;
    return fetch(`${jogador.rankingUrl}?jogo=${encodeURIComponent(slug)}`, { credentials: "same-origin" })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => {
        if (!dados || meu !== pedido) return dados;
        preencher("jogo", dados.rankingJogo || []);
        preencher("geral", dados.rankingGeral || []);
        mostrarEu(dados.eu);
        return dados;
      })
      .catch(() => null);
  };

  caixa.querySelectorAll("[data-ranking-aba]").forEach((botao) => {
    botao.addEventListener("click", () => {
      aba = botao.dataset.rankingAba;
      caixa.querySelectorAll("[data-ranking-aba]").forEach((b) => {
        const ativa = b === botao;
        b.setAttribute("aria-selected", ativa ? "true" : "false");
        b.tabIndex = ativa ? 0 : -1;
      });
      listas.jogo.hidden = aba !== "jogo";
      listas.geral.hidden = aba !== "geral";
      nota.hidden = aba !== "geral";
    });
  });

  /* ---------- o convite de cadastro (por cima da tela do jogo) ---------- */
  const portao = raiz.querySelector("[data-console-cadastro]");
  const selo = portao.querySelector("[data-cadastro-selo]");
  const titulo = portao.querySelector("[data-cadastro-titulo]");
  const texto = portao.querySelector("[data-cadastro-texto]");
  const passos = portao.querySelector("[data-cadastro-passos]");
  const contagem = portao.querySelector("[data-cadastro-contagem]");
  let relogio = 0;

  // os links de cadastro e login voltam para o jogo da vez
  const apontarLinks = (slug) => {
    const volta = `/jogos/${slug}/`;
    pagina.querySelectorAll("[data-cadastro-criar]").forEach((link) => { link.href = `${jogador.cadastroUrl}?next=${encodeURIComponent(volta)}`; });
    pagina.querySelectorAll("[data-cadastro-entrar]").forEach((link) => { link.href = `${jogador.entrarUrl}?next=${encodeURIComponent(volta)}`; });
  };

  const fecharPortao = () => {
    window.clearInterval(relogio);
    relogio = 0;
    portao.hidden = true;
  };

  // Onde a pontuação cairia no ranking deste jogo que está na ficha.
  const lugarNoRanking = (pontos) => {
    const linhas = listas.jogo.querySelectorAll("li:not(.sim-ranking-vazio) strong");
    const valores = Array.from(linhas, (el) => Number(el.textContent.replace(/\D/g, "")) || 0);
    const lugar = 1 + valores.filter((v) => v >= pontos).length;
    return lugar <= 10 ? lugar : null;
  };

  const abrirPortao = ({ pontos = null } = {}) => {
    window.clearInterval(relogio);
    apontarLinks(jogoAtual);
    const temResultado = pontos !== null && pontos > 0;
    const lugar = temResultado ? lugarNoRanking(pontos) : null;
    selo.hidden = !temResultado;
    passos.hidden = !temResultado;
    if (!temResultado) {
      titulo.textContent = `Você já usou as suas ${LIMITE} jogadas grátis`;
      texto.textContent = "Crie a conta grátis ou entre para jogar à vontade e disputar o ranking.";
    } else if (lugar === 1) {
      // bateu o recorde do jogo: o primeiro lugar espera só o cadastro
      selo.textContent = "Novo recorde do jogo!";
      titulo.textContent = `${numero(pontos)} pontos: ninguém fez mais`;
      texto.textContent = "Crie a conta ou entre e o 1º lugar fica no seu nome.";
    } else if (lugar) {
      selo.textContent = `Dá ${lugar}º lugar no ranking!`;
      titulo.textContent = `Você fez ${numero(pontos)} pontos`;
      texto.textContent = "Crie a conta ou entre para salvar no ranking e jogar de novo.";
    } else {
      selo.textContent = "Boa partida!";
      titulo.textContent = `Você fez ${numero(pontos)} pontos`;
      texto.textContent = "Crie a conta ou entre para salvar e continuar jogando.";
    }
    portao.classList.toggle("console-cadastro--recorde", lugar === 1);
    portao.hidden = false;
    let falta = temResultado ? SEGUNDOS_PARA_IR + 4 : SEGUNDOS_PARA_IR;
    const criar = portao.querySelector("[data-cadastro-criar]");
    const passo = () => {
      contagem.textContent = `Cadastro em ${falta} s…`;
      if (falta <= 0) {
        window.clearInterval(relogio);
        window.location.href = criar.href;
      }
      falta -= 1;
    };
    passo();
    relogio = window.setInterval(passo, 1000);
    criar.focus({ preventScroll: true });
  };

  portao.querySelector("[data-cadastro-fechar]").addEventListener("click", fecharPortao);

  /* ---------- o que o console avisa ---------- */
  raiz.addEventListener("console:abrir", (evento) => {
    const slug = evento.detail.slug;
    fecharPortao();
    if (slug === jogoAtual) return;
    jogoAtual = slug;
    apontarLinks(slug);
    atualizar(slug);
  });

  // conta a partida no "Mais jogados" do portal (/jogos/: no máximo uma vez a cada meia
  // hora por visitante e jogo) e, do visitante, gasta uma jogada grátis. Se o servidor
  // disser que não havia mais (gastou noutra aba), a partida para e vem o convite.
  // Falhar aqui nunca segura o jogo.
  const contar = (slug) => {
    if (!jogador.abriuUrl) return;
    fetch(jogador.abriuUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({ jogo: slug, gastar: !logado }),
    })
      .then((resposta) => (resposta.ok ? resposta.json() : null))
      .then((dados) => {
        if (!dados || logado || !dados.visitante) return;
        if (dados.liberado === false) {
          usadas = LIMITE;
          if (raiz.lsConsole) raiz.lsConsole.pausar();
          abrirPortao();
          return;
        }
        usadas = LIMITE - dados.restantes;
      })
      .catch(() => {});
  };

  // "Jogados recentemente", na biblioteca (/jogos/): o aparelho anota quando cada jogo abriu
  const lembrarNaBiblioteca = (slug) => {
    try {
      const lista = JSON.parse(window.localStorage.getItem("ls-biblioteca-recentes") || "{}") || {};
      lista[slug] = Date.now();
      const curta = {};
      Object.keys(lista).sort((a, b) => lista[b] - lista[a]).slice(0, 30).forEach((s) => { curta[s] = lista[s]; });
      window.localStorage.setItem("ls-biblioteca-recentes", JSON.stringify(curta));
    } catch (erro) { /* sem armazenamento: a biblioteca só não mostra */ }
  };

  raiz.addEventListener("console:jogar", (evento) => {
    const slug = evento.detail.slug;
    lembrarNaBiblioteca(slug);
    if (!logado && restantes() <= 0) {
      evento.preventDefault();
      abrirPortao();
      return;
    }
    // a partida grátis começou (recomeçar no meio também conta)
    if (!logado) usadas += 1;
    contar(slug);
  });

  /* O RESULTADO vai para o ranking assim que o jogo sabe o placar final
     ("console:resultado", uma vez por partida) -- não no fim da animação da
     máquina. Antes, quem rolava a página para ver o ranking pausava o jogo
     na tela final e o recorde nunca chegava. `keepalive`: sair da página
     logo depois não corta o envio. Sem resposta, tenta de novo uma vez. */
  let lugarDaPartida = null;
  const enviarResultado = (slug, pontos, tentativa = 0) => fetch(jogador.partidaUrl, {
    method: "POST",
    credentials: "same-origin",
    keepalive: true,
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: JSON.stringify({ jogo: slug, pontos }),
  })
    .then((resposta) => (resposta.ok ? resposta.json() : null))
    .catch(() => {
      if (tentativa < 1) return new Promise((pronto) => window.setTimeout(pronto, 2500)).then(() => enviarResultado(slug, pontos, 1));
      return null;
    });

  raiz.addEventListener("console:resultado", (evento) => {
    const { slug, pontos } = evento.detail;
    lugarDaPartida = null;
    enviarResultado(slug, pontos).then((dados) => {
      if (!dados || !logado || slug !== jogoAtual) return;
      atualizar(slug).then((painel) => {
        lugarDaPartida = painel && painel.eu && painel.eu.jogo;
        mostrarLugar();
      });
    });
  });

  // o lugar no ranking, no cartão de fim da partida (que pode abrir antes ou depois da resposta)
  const mostrarLugar = () => {
    const caixaRecorde = raiz.querySelector("[data-console-fim-recorde]");
    if (lugarDaPartida && caixaRecorde) {
      caixaRecorde.textContent = `Ranking: ${lugarDaPartida.posicao}º lugar neste jogo, com ${numero(lugarDaPartida.pontos)} pontos.`;
    }
  };

  raiz.addEventListener("console:fim", (evento) => {
    const { slug, pontos } = evento.detail;
    mostrarLugar();
    if (!logado) {
      if (restantes() > 0) {
        // ainda tem jogada: o cartão do fim diz quantas
        const caixaRecorde = raiz.querySelector("[data-console-fim-recorde]");
        if (caixaRecorde) caixaRecorde.textContent = `Sobra ${restantes()} jogada grátis. Com a conta grátis você joga à vontade.`;
        return;
      }
      // a última: um instante para ver o placar, e o convite vem por cima
      window.setTimeout(() => { if (slug === jogoAtual) abrirPortao({ pontos }); }, 1600);
    }
  });

  apontarLinks(jogoAtual);

  /* ---------- voltou do cadastro: "salvo no seu nome" ---------- */
  const salvo = pagina.querySelector("[data-sim-salvo]");
  if (salvo) {
    const fechar = () => { salvo.classList.add("sim-salvo--saindo"); window.setTimeout(() => salvo.remove(), 400); };
    salvo.querySelector("[data-sim-salvo-fechar]").addEventListener("click", fechar);
    window.setTimeout(fechar, 9000);
  }
}
