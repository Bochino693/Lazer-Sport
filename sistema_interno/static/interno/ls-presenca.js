/* ======================================================================
   QUEM ESTÁ ONLINE AGORA (LEIA-ME-V10, seção 76, AJUSTE)

   O pedido: "vc deve mostrar qual usuário está logado". O painel contava
   "1 online agora" e não dizia quem. Este arquivo é o relógio dessa
   resposta, e mora no base do painel porque serve a dois lugares:

     * a PILHA DE AVATARES da barra de cima (#lsEquipe), em toda tela: a
       equipe que está online, até quatro e "+N"; o toque abre a lista com
       o nome, o papel, onde a pessoa está e desde quando;
     * a faixa "Agora" da tela Usuários (gestao-analises.js), que assina
       este relógio e recebe também os clientes e os contadores.

   UMA PERGUNTA SÓ. Quem pergunta ao servidor é sempre este arquivo, de 45
   em 45 segundos e só com a aba à vista (aba escondida não pergunta; ao
   voltar, pergunta na hora). Se alguém na tela assinou "contas", a mesma
   pergunta leva ?contas=1 -- que só o superadministrador pode fazer; o
   resto do painel recebe só a equipe, e nome de cliente não sai do
   servidor para quem não abre a tela Usuários.

   TEXTO DE FORA ENTRA COMO TEXTO: nome de gente vai por textContent.
   ====================================================================== */
(function (window, document) {
  "use strict";

  if (window.LSPresenca) return;

  var INTERVALO = 45000;
  var assinantes = [];
  var ultimo = null;
  var relogio = null;
  var emVoo = false;
  var parado = false;
  var semContas = false;
  var pedidoEm = 0;

  function endereco() {
    return (document.body && document.body.getAttribute("data-presenca")) || "";
  }

  function passo() {
    var economia = document.body && document.body.getAttribute("data-ls-economia") === "1";
    return economia ? INTERVALO * 2 : INTERVALO;
  }

  function el(tag, classe, texto) {
    var no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto !== undefined && texto !== null) no.textContent = String(texto);
    return no;
  }

  /* Assinante cuja peça saiu da tela (a navegação suave trocou o miolo)
     deixa de contar: sem isto, sair de Usuários continuaria pedindo as
     contas todas em cada tela seguinte. */
  function vivos() {
    assinantes = assinantes.filter(function (assinante) {
      return !assinante.no || document.contains(assinante.no);
    });
    return assinantes;
  }

  function querContas() {
    return !semContas && vivos().some(function (assinante) { return assinante.contas; });
  }

  function avisar(dados, erro) {
    vivos().forEach(function (assinante) {
      try { assinante.fn(dados, erro); } catch (falha) { /* um assinante quebrado não cala os outros */ }
    });
  }

  function agendar() {
    window.clearTimeout(relogio);
    if (parado) return;
    relogio = window.setTimeout(function () {
      if (document.visibilityState === "visible") buscar();
      else agendar();
    }, passo());
  }

  function buscar() {
    var url = endereco();
    if (!url || emVoo || parado || !window.fetch) return;
    var contas = querContas();
    var repetir = false;
    emVoo = true;
    pedidoEm = Date.now();
    window.fetch(url + (contas ? "?contas=1" : ""), {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" }
    }).then(function (resposta) {
      if (resposta.status === 403 && contas) {
        /* a conta não abre a tela Usuários: fica só com a equipe */
        semContas = true;
        throw new Error("sem-contas");
      }
      if (resposta.status === 401 || resposta.status === 403 || resposta.status === 404) {
        parado = true;  /* saiu do painel ou não é da equipe: nada a mostrar */
        throw new Error("fora");
      }
      if (!resposta.ok) throw new Error("O servidor respondeu " + resposta.status + ".");
      return resposta.json();
    }).then(function (dados) {
      dados.comContas = contas;
      ultimo = dados;
      pintarEquipe(dados);
      avisar(dados, null);
    }).catch(function (erro) {
      if (erro && erro.message === "sem-contas") {
        repetir = true;
        return;
      }
      if (parado) esconderEquipe();
      avisar(null, erro || new Error("Sem conexão."));
    }).then(function () {
      emVoo = false;
      if (repetir) buscar();
      else agendar();
    });
  }

  /* ------------------------------------------------------------------
     a pilha de avatares da barra de cima
     ------------------------------------------------------------------ */
  function caixa() { return document.getElementById("lsEquipe"); }

  function esconderEquipe() {
    var raiz = caixa();
    if (raiz) raiz.hidden = true;
  }

  function avatar(pessoa, classe) {
    var no = el("span", (classe || "ls-equipe-avatar") + " is-c" + (Number(pessoa.cor) || 0), pessoa.iniciais || "?");
    no.setAttribute("aria-hidden", "true");
    return no;
  }

  function onde(pessoa) {
    var partes = [pessoa.papel_rotulo];
    if (pessoa.onde_rotulo) partes.push(pessoa.onde_rotulo);
    if (pessoa.desde) partes.push("hoje desde " + pessoa.desde);
    return partes.filter(Boolean).join(" · ");
  }

  /* Quantos avatares cabem na barra: quatro no computador, três no tablet,
     dois no celular e um no celular estreito. O resto vira "+N". */
  function maximoNaPilha() {
    var largura = window.innerWidth || 1366;
    return largura <= 400 ? 1 : (largura <= 760 ? 2 : (largura <= 1100 ? 3 : 4));
  }

  function pintarEquipe(dados) {
    var raiz = caixa();
    if (!raiz) return;
    var equipe = (dados && dados.equipe) || [];
    if (!equipe.length) { raiz.hidden = true; return; }
    raiz.hidden = false;

    var pilha = document.getElementById("lsEquipePilha");
    var maximo = maximoNaPilha();
    pilha.textContent = "";
    equipe.slice(0, maximo).forEach(function (pessoa) { pilha.appendChild(avatar(pessoa)); });
    if (equipe.length > maximo) {
      pilha.appendChild(el("span", "ls-equipe-avatar ls-equipe-mais", "+" + (equipe.length - maximo)));
    }

    var nomes = equipe.map(function (pessoa) { return pessoa.nome + (pessoa.voce ? " (você)" : ""); });
    var frase = equipe.length === 1 ? "1 pessoa da equipe online agora" : equipe.length + " pessoas da equipe online agora";
    var botao = document.getElementById("lsEquipeBotao");
    botao.setAttribute("aria-label", frase + ": " + nomes.join(", ") + ". Ver onde cada uma está");
    botao.title = "Equipe online agora: " + nomes.join(", ");
    document.getElementById("lsEquipeTitulo").textContent = frase;

    var lista = document.getElementById("lsEquipeLista");
    lista.textContent = "";
    equipe.forEach(function (pessoa) {
      var item = el("li", "ls-equipe-pessoa");
      item.appendChild(avatar(pessoa, "ls-equipe-avatar is-grande"));
      var texto = el("span", "ls-equipe-texto");
      var nome = el("strong", "", pessoa.nome);
      if (pessoa.voce) nome.appendChild(el("span", "ls-equipe-voce", "Você"));
      texto.appendChild(nome);
      texto.appendChild(el("small", "", onde(pessoa)));
      item.appendChild(texto);
      item.appendChild(el("span", "ls-equipe-quando", pessoa.quando === "agora" ? "agora" : pessoa.quando));
      lista.appendChild(item);
    });
    document.getElementById("lsEquipeNota").textContent =
      "Online é quem usou o painel, o site ou o aplicativo nos últimos " + (dados.online_minutos || 5) + " minutos. Atualiza sozinho.";
  }

  function fecharEquipe(devolverFoco) {
    var painel = document.getElementById("lsEquipePainel");
    var botao = document.getElementById("lsEquipeBotao");
    if (!painel || painel.hidden) return;
    painel.hidden = true;
    botao.setAttribute("aria-expanded", "false");
    if (devolverFoco) botao.focus();
  }

  function ligarEquipe() {
    var botao = document.getElementById("lsEquipeBotao");
    var painel = document.getElementById("lsEquipePainel");
    if (!botao || !painel) return;
    botao.addEventListener("click", function () {
      var abrir = painel.hidden;
      painel.hidden = !abrir;
      botao.setAttribute("aria-expanded", String(abrir));
      if (abrir && window.LSFecharAvisos) window.LSFecharAvisos();
    });
    document.addEventListener("click", function (evento) {
      if (!evento.target.closest || !evento.target.closest("#lsEquipe")) fecharEquipe(false);
    });
    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && !painel.hidden) {
        evento.preventDefault();
        fecharEquipe(true);
      }
    });
    document.addEventListener("focusin", function (evento) {
      if (!evento.target.closest || !evento.target.closest("#lsEquipe")) fecharEquipe(false);
    });
    document.addEventListener("ls:tela", function () { fecharEquipe(false); });
    /* girou o tablet, encolheu a janela: a pilha conta de novo quantos cabem */
    var espera = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(espera);
      espera = window.setTimeout(function () { if (ultimo) pintarEquipe(ultimo); }, 200);
    });
  }

  /* ------------------------------------------------------------------
     o que as telas usam
     ------------------------------------------------------------------ */
  window.LSPresenca = {
    /* fn(dados, erro) a cada resposta. `contas`: quer as contas todas
       (tela Usuários); `no`: a peça que desenha -- saiu da tela, a
       assinatura acaba sozinha. */
    assinar: function (fn, opcoes) {
      opcoes = opcoes || {};
      assinantes.push({ fn: fn, contas: !!opcoes.contas, no: opcoes.no || null });
      var serve = ultimo && (!opcoes.contas || ultimo.comContas);
      if (serve) fn(ultimo, null);
      else if (!emVoo) buscar();
      else if (opcoes.contas) {
        /* a pergunta que está no ar não pediu as contas: outra em seguida */
        window.setTimeout(function () { if (!ultimo || !ultimo.comContas) buscar(); }, 400);
      }
    },
    atualizar: function () { buscar(); },
    ultimo: function () { return ultimo; }
  };

  function iniciar() {
    if (!endereco() || !caixa()) return;
    ligarEquipe();
    /* um instante depois: a tela (script com defer) assina antes, e a
       primeira pergunta já sai sabendo se alguém quer as contas */
    window.setTimeout(function () { if (!ultimo) buscar(); }, 60);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible" && Date.now() - pedidoEm > 10000) buscar();
    });
    window.addEventListener("online", function () { buscar(); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})(window, document);
