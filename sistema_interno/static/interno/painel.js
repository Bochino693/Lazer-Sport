/* Utilidades do painel interno: modal + envio por fetch.
 *
 * Toda tela de cadastro daqui segue o mesmo contrato com o servidor:
 * POST com um campo "action" e resposta JSON {status, msg}. Assim um
 * erro de validacao volta pro proprio modal, com o que foi digitado
 * ainda na tela, em vez de recarregar a pagina e perder tudo.
 */
(function (global) {
  "use strict";

  var Painel = {};
  var cliquesDaTela = [];

  // A tabela troca de nós ao filtrar; o menu de ações vive no body.
  // Delegar no documento atende ambos e a navegação descarta os ouvintes.
  Painel.aoClicar = function (seletor, tratar) {
    function ouvir(evento) {
      var alvo = evento.target.closest ? evento.target.closest(seletor) : null;
      if (alvo && !alvo.disabled) tratar(alvo, evento);
    }
    document.addEventListener("click", ouvir);
    cliquesDaTela.push(ouvir);
  };

  function haModalVisivel() {
    return Boolean(document.querySelector(".modal.show"));
  }

  function limparEstadoDoCorpo() {
    if (haModalVisivel()) return;
    document.querySelectorAll(".modal-backdrop").forEach(function (fundo) {
      fundo.remove();
    });
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
  }

  Painel.limparModais = function (imediato) {
    document.querySelectorAll(".modal").forEach(function (elemento) {
      var instancia = global.bootstrap && global.bootstrap.Modal
        ? global.bootstrap.Modal.getInstance(elemento)
        : null;
      if (instancia && !imediato) {
        instancia.hide();
        return;
      }
      if (instancia) instancia.dispose();
      elemento.classList.remove("show");
      elemento.style.display = "none";
      elemento.setAttribute("aria-hidden", "true");
      elemento.removeAttribute("aria-modal");
      elemento.removeAttribute("role");
    });
    limparEstadoDoCorpo();
  };

  /* ====================================================================
     O QUE A TELA DEIXA FORA DELA MESMA

     Três coisas do painel nascem penduradas no `<body>`, e não dentro da
     área de conteúdo: o menu flutuante de ações das tabelas, o painel de
     resultados da busca e o aviso de falha de rede. Todos usam
     `position:fixed` de propósito -- dentro da tabela ficariam cortados
     pelo scroll e empurrariam a altura da linha.

     Isso tem um preço na troca de tela: como a troca substitui a área de
     conteúdo, o botão que abre cada menu morre junto, mas o MENU não --
     ele fica órfão no corpo da página. Sem esta limpeza, voltar duas
     vezes à mesma lista deixava sete botões "Editar" para três
     orçamentos, e o primeiro da fila pertencia a uma tela que já não
     existia: clicar nele não fazia nada.

     Quem sai apaga o que pendurou. É por isso que esta função existe e é
     chamada imediatamente antes de a área de conteúdo ser trocada.
     ==================================================================== */
  Painel.limparPendurados = function () {
    document.querySelectorAll(
      "body > .ls-action-fab-menu, body > .ls-busca-painel, body > #lsNavRecovery"
    ).forEach(function (solto) { solto.remove(); });
    Painel._acoesAbertas = null;
  };

  Painel.prepararNavegacao = function () {
    cliquesDaTela.forEach(function (ouvir) {
      document.removeEventListener("click", ouvir);
    });
    cliquesDaTela = [];
    Painel.fecharAcoesFlutuantes(false);
    Painel.limparModais(true);
    Painel.limparPendurados();
    /* O sino mora na barra do topo, que não é trocada na navegação
       suave: aberto, ele atravessava a troca e ficava por cima da tela
       nova. Fechar aqui é o que faz a mudança de tela ser visível.
       Definido em `base_inner.html`, junto do botão. */
    if (global.LSFecharAvisos) global.LSFecharAvisos();
    /* Os ouvintes de aviso registrados pela TELA que está saindo apontam
       para elementos que vão deixar de existir. Guardá-los seria segurar
       a tela velha na memória e chamar função sobre nó solto a cada
       atualização. Os do próprio painel não passam por aqui. */
    Painel.avisos.esquecerOuvintes();
  };

  /* ====================================================================
     MONTAGEM DE UMA TELA

     Tudo o que precisa acontecer para uma tela recém-chegada funcionar:
     máscara nos campos, textarea que cresce, ações de tabela agrupadas e
     janelas com o rodapé no lugar. Fica separado do que se liga UMA vez
     por aba (relógio dos avisos, medida do teclado) porque a navegação
     suave troca a tela sem recarregar a página: chamar de novo o que é
     de tela é obrigatório, e chamar de novo o que é de aba duplicaria
     relógio e ouvinte a cada clique no menu.
     ==================================================================== */
  Painel.organizarSecoesMenu = function () {
    var secoes = document.querySelectorAll('.ls-nav > .ls-nav-section');
    secoes.forEach(function (secao, indice) {
      if (secao.dataset.acordeao === '1') return;
      var titulo = secao.querySelector('.ls-nav-caption');
      if (!titulo) return;
      secao.dataset.acordeao = '1';
      var botao = document.createElement('button');
      botao.type = 'button';
      botao.className = 'ls-nav-caption ls-nav-section-toggle';
      botao.textContent = titulo.textContent;
      var links = document.createElement('div');
      links.className = 'ls-nav-links';
      links.id = 'ls-nav-grupo-' + indice;
      botao.setAttribute('aria-controls', links.id);
      titulo.replaceWith(botao);
      Array.from(secao.children).forEach(function (filho) {
        if (filho !== botao) links.appendChild(filho);
      });
      secao.appendChild(links);
      function mudar(aberto) {
        links.hidden = !aberto;
        botao.setAttribute('aria-expanded', String(aberto));
      }
      mudar(Boolean(links.querySelector('.active')));
      botao.addEventListener('click', function () {
        var abrir = links.hidden;
        secoes.forEach(function (outra) {
          var grupo = outra.querySelector('.ls-nav-links');
          var controle = outra.querySelector('.ls-nav-section-toggle');
          if (grupo && controle) { grupo.hidden = true; controle.setAttribute('aria-expanded', 'false'); }
        });
        mudar(abrir);
      });
    });
  };

  Painel.montarTela = function (raiz) {
    var alvo = raiz || document;
    if (avisos && avisos.ultimoEstado) desenharAvisos(avisos.ultimoEstado);
    Painel.aplicarMascaras(alvo);
    Painel.acomodarTextos(alvo);
    Painel.organizarAcoesTabelas(alvo);
    Painel.organizarSecoesMenu();
    alvo.querySelectorAll(".modal").forEach(normalizarJanela);
    /* O filtro instantâneo das listas entra aqui, e não por conta
       própria: o módulo é carregado uma vez e a tela troca muitas. Sem
       este ponto, o campo de busca da segunda tela em diante voltaria a
       recarregar a página. */
    if (global.LSFiltroLocal) global.LSFiltroLocal.ligar(alvo);
  };

  Painel.fecharAcoesFlutuantes = function (devolverFoco) {
    if (Painel._acoesAbertas && Painel._acoesAbertas._lsFechar) {
      Painel._acoesAbertas._lsFechar(Boolean(devolverFoco));
    }
  };

  ["show", "shown", "hide", "hidden"].forEach(function (estado) {
    document.addEventListener(estado + ".bs.modal", function (evento) {
      if (evento.target.matches(".modal")) evento.target.dataset.lsModalEstado = estado;
    }, true);
  });

  Painel.modal = function (id) {
    var el = document.getElementById(id);
    if (!el) {
      return null;
    }
    return global.bootstrap.Modal.getOrCreateInstance(el);
  };

  Painel.abrir = function (id) {
    var m = Painel.modal(id);
    if (!m) return;

    /* Toda janela do painel entra na tela com as máscaras ligadas.
     *
     * Antes cada tela precisava lembrar de chamar `aplicarMascaras`, e as
     * que esqueceram mostravam telefone e dinheiro crus -- "11999998888"
     * no lugar de "(11) 99999-8888". Ligar aqui resolve para as janelas
     * que existem e para as próximas, que é o ponto. */
    var elemento = document.getElementById(id);
    if (elemento) Painel.aplicarMascaras(elemento);

    if (elemento.dataset.lsModalEstado === "hide" || elemento._lsFechamentoPendente) {
      elemento.addEventListener("hidden.bs.modal", function () { m.show(); }, { once: true });
    } else {
      m.show();
    }
  };

  Painel.fechar = function (id) {
    var elemento = document.getElementById(id);
    var m = Painel.modal(id);
    if (m) {
      if (!elemento.classList.contains("show")
          && elemento.dataset.lsModalEstado !== "show"
          && elemento.dataset.lsModalEstado !== "hide") {
        limparEstadoDoCorpo();
        return;
      }
      elemento._lsFechamentoPendente = true;
      var finalizado = false;
      var fallback = null;
      function fecharAoTerminarAbertura() { m.hide(); }
      elemento.addEventListener("shown.bs.modal", fecharAoTerminarAbertura, { once: true });
      elemento.addEventListener("hidden.bs.modal", function () {
        finalizado = true;
        elemento._lsFechamentoPendente = false;
        elemento.removeEventListener("shown.bs.modal", fecharAoTerminarAbertura);
        if (fallback) global.clearTimeout(fallback);
      }, { once: true });
      m.hide();
      /* CSS interrompido, navegação suave ou WebView antigo podem impedir
       * o evento final do Bootstrap. O fallback fecha só a janela pedida e
       * devolve o scroll; normalmente não faz nada porque hidden já chegou. */
      fallback = global.setTimeout(function () {
        if (finalizado) return;
        if (!elemento || !elemento.classList.contains("show")) {
          if (elemento) elemento._lsFechamentoPendente = false;
          limparEstadoDoCorpo();
          return;
        }
        elemento.classList.remove("show");
        elemento.style.display = "none";
        elemento.setAttribute("aria-hidden", "true");
        elemento.removeAttribute("aria-modal");
        elemento.dispatchEvent(new Event("hidden.bs.modal", { bubbles: true }));
        limparEstadoDoCorpo();
      }, 480);
    }
  };

  /* Bootstrap não suporta dois modais abertos ao mesmo tempo. Cliente,
   * brinquedo e peça são cadastros-filhos do orçamento: esconder o pai
   * antes de abrir o filho evita duas barras de rolagem, backdrop preso e
   * formulário cortado no iPad. Ao fechar o filho, a proposta volta com
   * tudo o que já estava digitado. */
  Painel.abrirFilho = function (filhoId, paiId) {
    var filhoEl = document.getElementById(filhoId);
    var paiEl = document.getElementById(paiId);
    if (!filhoEl || !paiEl) {
      Painel.abrir(filhoId);
      return;
    }

    var filho = Painel.modal(filhoId);
    var pai = Painel.modal(paiId);

    function mostrarFilho() {
      filhoEl.addEventListener("hidden.bs.modal", function restaurarPai() {
        global.setTimeout(function () { pai.show(); }, 0);
      }, { once: true });
      filho.show();
    }

    if (paiEl.classList.contains("show")) {
      // Bootstrap ignora hide durante a animação de abertura.
      function esconderPai() { pai.hide(); }
      paiEl.addEventListener("shown.bs.modal", esconderPai, { once: true });
      paiEl.addEventListener("hidden.bs.modal", function () {
        paiEl.removeEventListener("shown.bs.modal", esconderPai);
        mostrarFilho();
      }, { once: true });
      pai.hide();
    } else {
      mostrarFilho();
    }
  };

  Painel.erro = function (id, texto) {
    var caixa = document.getElementById(id);
    if (!caixa) {
      return;
    }
    caixa.textContent = texto || "";
    caixa.classList.toggle("d-none", !texto);
    if (texto) {
      caixa.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  };

  document.addEventListener("hidden.bs.modal", function () {
    global.setTimeout(limparEstadoDoCorpo, 0);
  });

  global.addEventListener("pageshow", limparEstadoDoCorpo);

  /* Máscaras do aplicativo interno.
   *
   * type="number" é bom para quantidade inteira, mas ruim para dinheiro
   * brasileiro: vários navegadores recusam a vírgula e apagam o valor ao
   * enviar. Valores monetários continuam como texto com inputmode
   * decimal, recebem teclado numérico no tablet e têm qualquer letra
   * removida na digitação.
   *
   * As funções vivem aqui fora, e não dentro de `aplicarMascaras`, porque
   * quem preenche um campo por JavaScript também precisa delas -- ver
   * `Painel.valor`.
   */
  function digitos(valor, limite) {
    return String(valor || "").replace(/\D/g, "").slice(0, limite || 99);
  }

  var mascaras = {
    telefone: function (valor) {
      var numero = digitos(valor, 13);
      var pais = numero.length > 11 && numero.indexOf("55") === 0;
      var local = pais ? numero.slice(2) : numero;
      var prefixo = pais ? "+55 " : "";

      if (!local) return prefixo.trim();
      if (local.length < 3) return prefixo + "(" + local;

      var ddd = local.slice(0, 2);
      var corpo = local.slice(2);
      if (corpo.length <= 4) return prefixo + "(" + ddd + ") " + corpo;

      var corte = corpo.length > 8 ? 5 : 4;
      return prefixo + "(" + ddd + ") " + corpo.slice(0, corte) + "-" + corpo.slice(corte, 9);
    },

    cep: function (valor) {
      var numero = digitos(valor, 8);
      return numero.length > 5
        ? numero.slice(0, 5) + "-" + numero.slice(5)
        : numero;
    },

    documento: function (valor) {
      var documento = String(valor || "")
        .toUpperCase()
        .replace(/[^0-9A-Z]/g, "")
        .slice(0, 14);
      var ehCnpj = /[A-Z]/.test(documento) || documento.length > 11;
      if (!ehCnpj) {
        return documento
          .replace(/^(\d{3})(\d)/, "$1.$2")
          .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
          .replace(/\.(\d{3})(\d)/, ".$1-$2");
      }
      var base = documento.slice(0, 12);
      var dv = documento.slice(12).replace(/\D/g, "");
      var partes = [];
      if (base.slice(0, 2)) partes.push(base.slice(0, 2));
      var formatado = partes[0] || "";
      if (base.length > 2) formatado += "." + base.slice(2, 5);
      if (base.length > 5) formatado += "." + base.slice(5, 8);
      if (base.length > 8) formatado += "/" + base.slice(8, 12);
      if (dv) formatado += "-" + dv;
      return formatado;
    },

    /* DINHEIRO SE DIGITA DA DIREITA PARA A ESQUERDA.
     *
     * É como toda maquininha e todo caixa funcionam, e é o que a equipe
     * espera: 1 vira 0,01; 10 vira 0,10; 100 vira 1,00; 123456 vira
     * 1.234,56. Só dígitos importam -- vírgula, ponto e letra são
     * ignorados na digitação, então não há como escrever "80,0,0" nem
     * mandar letra para o servidor.
     *
     * A versão anterior deixava o campo cru até sair dele. Quem digitava
     * "80" via "80" e só descobria no blur que virou "80,00"; quem
     * digitava "8,5" via "8,5" e mandava oito e meio achando que eram
     * oito e cinquenta. Formatando a cada tecla, o valor na tela é
     * sempre o valor real. */
    moeda: function (valor) {
      var centavos = digitos(valor, 15);
      if (!centavos) return "";

      // Zeros à esquerda não têm valor: "007" é 0,07, não 007,00.
      centavos = centavos.replace(/^0+(?=\d{3})/, "");
      while (centavos.length < 3) centavos = "0" + centavos;

      var inteiros = centavos.slice(0, -2);
      var resto = centavos.slice(-2);
      return agrupar(inteiros) + "," + resto;
    },

    /* Valor monetário digitado por inteiro.
     *
     * Algumas tabelas, como os itens da O.S., são preenchidas a partir
     * de uma cotação: quem escreve 400 quer registrar quatrocentos reais,
     * não R$ 4,00. Este modo deixa a parte inteira exatamente como foi
     * digitada, aceita a vírgula opcional e entrega a formatação completa
     * no blur. O placeholder continua ensinando o formato sem virar valor. */
    "moeda-valor": function (valor) {
      var texto = String(valor || "").replace(/[^\d.,]/g, "");
      if (!texto) return "";

      var ultimaVirgula = texto.lastIndexOf(",");
      var ultimoPonto = texto.lastIndexOf(".");
      var separador = Math.max(ultimaVirgula, ultimoPonto);

      if (separador < 0) return digitos(texto, 13);

      /* Em valor colado, pontos anteriores ao último separador são apenas
         agrupadores: R$ 1.234,56 vira 1234,56. */
      var inteiros = texto.slice(0, separador).replace(/\D/g, "") || "0";
      var centavos = texto.slice(separador + 1).replace(/\D/g, "").slice(0, 2);
      return inteiros.slice(0, 13) + "," + centavos;
    },

    /* Metragem: mesma digitação da direita para a esquerda, em metros.
     * 350 vira 3,50 -- e não 350 metros de brinquedo. */
    medida: function (valor) {
      return mascaras.moeda(valor);
    },

    /* Percentual de 0 a 100, com duas casas: 5 vira 0,05 e 1000 vira
     * 10,00. Passar de cem por cento não é desconto, é engano. */
    percentual: function (valor) {
      var texto = mascaras.moeda(valor);
      if (!texto) return "";
      return numeroMoeda(texto) > 100 ? "100,00" : texto;
    }
  };

  /* Ponto de milhar, que é o que separa "1.234,56" de "123456". */
  function agrupar(inteiros) {
    return inteiros.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function numeroMoeda(valor) {
    var limpo = String(valor || "").replace(/[^\d.,]/g, "");
    if (!limpo) return null;
    if (limpo.indexOf(",") >= 0) {
      limpo = limpo.replace(/\./g, "").replace(",", ".");
    } else if ((limpo.match(/\./g) || []).length > 1) {
      limpo = limpo.replace(/\./g, "");
    }
    var numero = Number(limpo);
    return Number.isFinite(numero) ? numero : null;
  }

  function moedaFinal(valor) {
    var numero = numeroMoeda(valor);
    return numero === null ? "" : numero.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  Painel.mascarar = function (tipo, valor) {
    var formatar = mascaras[tipo];
    return formatar ? formatar(valor) : valor;
  };

  Painel.valorNumerico = numeroMoeda;

  /* Preenche um campo pelo id.
   *
   * APLICA A MÁSCARA. Reabrir um cadastro salvo jogava o valor cru na
   * tela -- "11999998888" no lugar de "(11) 99999-8888" -- e, pior, o
   * primeiro salvamento depois disso gravava o cru de volta. Formatar
   * aqui conserta os dois de uma vez, porque toda tela do painel enche
   * modal por esta função.
   */
  /* Tipos numéricos recebem normalização final ao sair do campo. Um valor
   * que já existe (vindo do servidor ou preenchido por JavaScript) é um
   * NÚMERO, não uma sequência de teclas: "80" significa oitenta reais.
   * Por isso o valor existente entra por `moedaFinal`; durante a digitação,
   * cada tipo mantém o comportamento adequado ao seu contexto. */
  var TIPOS_NUMERICOS = ["moeda", "moeda-valor", "medida", "percentual"];

  function ehNumerico(tipo) {
    return TIPOS_NUMERICOS.indexOf(tipo) >= 0;
  }

  Painel.valor = function (id, v) {
    var el = document.getElementById(id);
    if (!el) return;

    var bruto = v === null || v === undefined ? "" : String(v);
    var tipo = el.dataset ? el.dataset.mascara : "";

    if (!bruto) {
      el.value = "";
      return;
    }

    if (ehNumerico(tipo)) el.value = moedaFinal(bruto) || bruto;
    else if (tipo) el.value = Painel.mascarar(tipo, bruto);
    else el.value = bruto;

    if (el.tagName === "TEXTAREA" && Painel.acomodarTextos) {
      Painel.acomodarTextos(el.parentNode || document);
    }
  };

  /* Datas sem deslocamento de fuso.
   *
   * `toISOString()` sempre converte para UTC. Em aparelhos do Brasil,
   * datas próximas da meia-noite podiam voltar como o dia anterior e o
   * datetime-local aparecia algumas horas adiantado. Estes helpers usam
   * os componentes locais do próprio aparelho e mantêm o valor que a
   * pessoa realmente escolheu. */
  function dois(numero) {
    return String(numero).padStart(2, "0");
  }

  Painel.datas = {
    paraDataLocal: function (data) {
      data = data instanceof Date ? data : new Date(data);
      if (Number.isNaN(data.getTime())) return "";
      return [data.getFullYear(), dois(data.getMonth() + 1), dois(data.getDate())].join("-");
    },

    paraDataHoraLocal: function (data) {
      data = data instanceof Date ? data : new Date(data);
      if (Number.isNaN(data.getTime())) return "";
      return Painel.datas.paraDataLocal(data) + "T" + dois(data.getHours()) + ":" + dois(data.getMinutes());
    },

    agoraArredondado: function (minutos) {
      var passo = Math.max(1, Number(minutos) || 15);
      var data = new Date();
      data.setSeconds(0, 0);
      data.setMinutes(Math.ceil(data.getMinutes() / passo) * passo);
      return data;
    },

    fusoDoAparelho: function () {
      try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || "horário local";
      } catch (e) {
        return "horário local";
      }
    },

    aprimorar: function (raiz) {
      var escopo = raiz || document;

      escopo.querySelectorAll('input[type="datetime-local"]').forEach(function (campo) {
        if (!campo.step || campo.step === "60") campo.step = "300";
        campo.setAttribute("title", "Horário local do aparelho · " + Painel.datas.fusoDoAparelho());
      });

      /* CAMPO QUE NÃO OLHA PARA TRÁS.

         `data-nao-passado` põe o piso do calendário em hoje. Não substitui
         a conferência do servidor -- atributo de HTML qualquer um tira --,
         mas muda o momento em que a pessoa descobre o problema: o
         calendário simplesmente não deixa escolher o dia errado, em vez de
         aceitar, mandar, e devolver um erro depois de tudo preenchido.

         O piso é recalculado a cada montagem de tela porque o painel fica
         aberto a semana inteira na bancada: com o valor preso na abertura,
         na terça-feira ele ainda estaria travando na segunda. */
      escopo.querySelectorAll("[data-nao-passado]").forEach(function (campo) {
        var agora = new Date();
        campo.min = campo.type === "datetime-local"
          ? Painel.datas.paraDataHoraLocal(agora)
          : Painel.datas.paraDataLocal(agora);
      });
    },

    /* Hoje + N dias, no calendário do próprio aparelho.
       O meio-dia evita que horário de verão empurre a data um dia. */
    emDias: function (dias) {
      var dia = new Date();
      dia.setHours(12, 0, 0, 0);
      dia.setDate(dia.getDate() + (Number(dias) || 0));
      return Painel.datas.paraDataLocal(dia);
    }
  };

  Painel.aplicarMascaras = function (raiz) {
    raiz = raiz || document;

    Painel.datas.aprimorar(raiz);

    raiz.querySelectorAll("[data-mascara]").forEach(function (campo) {
      var tipo = campo.dataset.mascara;

      /* Valor que já estava no campo é número, não digitação. */
      function normalizarExistente() {
        if (!campo.value) return;
        campo.value = ehNumerico(tipo)
          ? (moedaFinal(campo.value) || campo.value)
          : Painel.mascarar(tipo, campo.value);
      }

      if (campo.dataset.mascaraLigada === "1") {
        /* Já ligado, mas o valor pode ter sido trocado por JavaScript
           desde então: reformata e sai. */
        normalizarExistente();
        return;
      }

      campo.dataset.mascaraLigada = "1";

      campo.addEventListener("input", function () {
        campo.value = Painel.mascarar(tipo, campo.value);
        /* O cursor vai para o fim, onde a próxima tecla deve entrar. */
        if (ehNumerico(tipo) && campo.setSelectionRange) {
          try {
            campo.setSelectionRange(campo.value.length, campo.value.length);
          } catch (e) { /* type=email e afins não aceitam seleção */ }
        }
      });

      if (ehNumerico(tipo)) {
        /* Colar "1234.5" ou "R$ 80" continua funcionando: ao sair do
           campo o texto vira número de verdade. */
        campo.addEventListener("blur", function () {
          if (campo.value) campo.value = moedaFinal(campo.value) || campo.value;
        });
      }

      normalizarExistente();
    });
  };

  /* CEP compartilhado por qualquer formulário do painel. O resultado fica
   * sete dias no sessionStorage do aparelho: abrir cliente, orçamento e
   * entrega com o mesmo CEP reaproveita os dados e não cobra outra consulta
   * do servidor. */
  Painel.ligarCep = function (opcoes) {
    var campoCep = document.getElementById(opcoes.cep);
    if (!campoCep || !opcoes.url) return;

    var status = opcoes.status ? document.getElementById(opcoes.status) : null;
    var ultimo = "";
    var emAndamento = null;
    var validade = 7 * 24 * 60 * 60 * 1000;
    var timer = null;

    function informar(texto, classe) {
      if (!status) return;
      status.textContent = texto || "";
      status.className = "ls-cep-status" + (classe ? " " + classe : "");
    }

    function aplicar(dados) {
      Object.keys(opcoes.campos || {}).forEach(function (chave) {
        var campo = document.getElementById(opcoes.campos[chave]);
        if (campo && dados[chave] !== undefined) campo.value = dados[chave] || "";
      });
      Object.keys(opcoes.coordenadas || {}).forEach(function (chave) {
        var campo = document.getElementById(opcoes.coordenadas[chave]);
        if (campo) campo.value = dados[chave] == null ? "" : dados[chave];
      });
      if (dados.cep) campoCep.value = String(dados.cep).replace(/\D/g, "")
        .replace(/^(\d{5})(\d{1,3})$/, "$1-$2");
      informar(
        dados.bairro ? "Endereço completo encontrado" : "Confira e complete o bairro",
        dados.bairro ? "sucesso" : "erro"
      );
    }

    function lerCache(cep) {
      try {
        var bruto = global.sessionStorage.getItem("ls:cep:v2:" + cep);
        var salvo = bruto ? JSON.parse(bruto) : null;
        if (salvo && Date.now() - salvo.em < validade) return salvo.dados;
      } catch (e) {
        return null;
      }
      return null;
    }

    function guardarCache(cep, dados) {
      try {
        global.sessionStorage.setItem(
          "ls:cep:v2:" + cep,
          JSON.stringify({ em: Date.now(), dados: dados })
        );
      } catch (e) {
        /* Navegação privada pode negar armazenamento; o formulário segue. */
      }
    }

    function consultar() {
      var cep = String(campoCep.value || "").replace(/\D/g, "");
      if (!cep) {
        informar("");
        ultimo = "";
        return;
      }
      if (cep.length !== 8) {
        informar("CEP incompleto", "erro");
        ultimo = "";
        return;
      }
      if (cep === ultimo) return;
      ultimo = cep;

      var cacheado = lerCache(cep);
      if (cacheado) {
        aplicar(cacheado);
        return;
      }

      if (emAndamento && emAndamento.abort) emAndamento.abort();
      emAndamento = global.AbortController ? new AbortController() : null;
      informar("Consultando CEP…", "carregando");
      campoCep.setAttribute("aria-busy", "true");

      fetch(opcoes.url + "?cep=" + encodeURIComponent(cep), {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: emAndamento ? emAndamento.signal : undefined
      })
        .then(function (resposta) {
          return resposta.json().catch(function () { return null; }).then(function (json) {
            if (!resposta.ok || !json || json.status !== "sucesso") {
              throw new Error((json && json.msg) || "Não consegui consultar o CEP.");
            }
            return json.endereco;
          });
        })
        .then(function (dados) {
          guardarCache(cep, dados);
          aplicar(dados);
        })
        .catch(function (erro) {
          if (erro && erro.name === "AbortError") return;
          informar(erro.message || "Não consegui consultar o CEP.", "erro");
          ultimo = "";
        })
        .finally(function () {
          campoCep.removeAttribute("aria-busy");
        });
    }

    campoCep.addEventListener("blur", consultar);
    campoCep.addEventListener("change", consultar);
    campoCep.addEventListener("input", function () {
      if (timer) global.clearTimeout(timer);
      var completo = String(campoCep.value || "").replace(/\D/g, "").length === 8;
      if (!completo) {
        ultimo = "";
        if (campoCep.value) informar("CEP incompleto", "erro");
        else informar("");
        return;
      }
      timer = global.setTimeout(consultar, 180);
    });
  };

  /* ====================================================================
     SERVIDOR PRONTO DEPOIS DE MUITO TEMPO SEM USO

     A hospedagem pode suspender o processo ou encerrar uma conexão ociosa.
     Repetir automaticamente um POST seria perigoso (dois pagamentos, duas
     versões, duas exclusões). A estratégia segura é acordar o servidor com
     GET /healthz/ ANTES da gravação e enviar o POST uma única vez.

     Enquanto o painel estiver aberto e visível, um pulso barato mantém o
     processo pronto. Ao voltar para uma aba antiga, o pulso começa antes do
     primeiro clique e todas as gravações compartilham a mesma promessa.
     ==================================================================== */
  var redeUltimoSucesso = Date.now();
  var redeAcordando = null;
  var REDE_OCIOSA_MS = 2 * 60 * 1000;
  var REDE_PULSO_MS = 4 * 60 * 1000;

  /* UMA SONDAGEM CURTA, DEPOIS UMA ESPERA LONGA.

     Eram sete tentativas de nove segundos cada, com pausas crescentes
     entre elas. A duração total estava certa -- cobria uma partida a
     frio --, mas o FORMATO estava errado: cada tentativa que estoura o
     prazo é um `abort`, e cada `abort` joga fora o pedido que já estava
     na fila do servidor. Contra uma instância que está subindo, isso
     significa recomeçar a conta sete vezes e nunca receber a resposta
     que estava a caminho.

     Agora são duas, com trabalhos diferentes: a primeira sonda em seis
     segundos (rede lenta, servidor de pé), e a segunda espera cinquenta
     -- UM pedido, aberto, atendido no instante em que o processo sobe.

     E as duas avisam. Quarenta segundos de tela parada sem uma palavra
     são indistinguíveis de um sistema travado, e é isso que faz a pessoa
     tocar de novo -- cancelando justamente o pedido que ia responder. */
  var PRAZOS_DO_PULSO = [6000, 50000];
  var ESPERAS_DO_PULSO = [500];
  var ouvintesDePulso = [];

  /* Quem quiser mostrar "acordando o servidor" na tela se inscreve aqui.
     Vale para qualquer espera de rede do painel, não só para a gravação. */
  Painel.aoEsperarRede = function (fn) {
    if (typeof fn === "function") ouvintesDePulso.push(fn);
  };

  function avisarEspera(estado, decorridoMs) {
    ouvintesDePulso.forEach(function (fn) {
      try { fn(estado, decorridoMs); } catch (e) {}
    });
  }

  function esperarRede(ms) {
    return new Promise(function (resolver) { global.setTimeout(resolver, ms); });
  }

  function pulsoDoServidor(tentativa, anunciar) {
    var controlador = global.AbortController ? new AbortController() : null;
    var prazo = PRAZOS_DO_PULSO[Math.min(tentativa, PRAZOS_DO_PULSO.length - 1)];
    var timer = controlador
      ? global.setTimeout(function () { controlador.abort(); }, prazo)
      : null;

    /* `/pronto/`, e não `/healthz/`.

       O `healthz` responde sem tocar o banco -- é o health check da
       hospedagem, e ele PRECISA ser assim: se dependesse do Supabase,
       uma oscilação do banco passaria a derrubar o processo web inteiro.

       Só que acordar apenas o processo resolve metade do problema. O
       primeiro clique de quem volta ao painel vai consultar o banco, e
       abrir conexão nova com o Supabase custa segundos -- trocaríamos
       uma espera longa por uma espera média. `/pronto/` faz um
       `SELECT 1`: o bastante para a conexão existir e estar quente
       quando a gravação de verdade chegar. Ver `core.views.pronto`. */
    return fetch("/pronto/?painel=1", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      signal: controlador ? controlador.signal : undefined,
    }).then(function (resposta) {
      if (!resposta.ok) throw new Error("health-" + resposta.status);
      redeUltimoSucesso = Date.now();
      return true;
    }).catch(function (erro) {
      /* A pausa entre a sondagem e a espera longa é curta de propósito:
         o que se ganha esperando aqui é nada, e o que se perde é tempo
         da paciência de quem está olhando a tela. */
      if (tentativa < ESPERAS_DO_PULSO.length) {
        if (anunciar && anunciar()) avisarEspera("acordando", tentativa);
        return esperarRede(ESPERAS_DO_PULSO[tentativa]).then(function () {
          return pulsoDoServidor(tentativa + 1, anunciar);
        });
      }
      if (anunciar && anunciar()) avisarEspera("desistiu", tentativa);
      throw erro;
    }).finally(function () {
      if (timer) global.clearTimeout(timer);
    });
  }

  /* SÓ FALA QUEM TEM ALGUÉM ESPERANDO.

     O despertar acontece em quatro momentos, e só um deles tem uma
     pessoa parada olhando: a gravação. Os outros três -- o pulso de
     quatro em quatro minutos, a volta para a aba, e o toque depois de um
     tempo parado -- são aquecimento especulativo, feito por precaução,
     sem ninguém esperando por eles.

     Enquanto todos anunciavam, um aquecimento que falhasse escrevia
     "Servidor acordando…" numa tela que já estava carregada e
     funcionando. A pessoa via um aviso de espera sem estar esperando por
     nada -- e sem nada para fazer a respeito.

     Agora a regra é: quem foi chamado por uma ação da pessoa fala; quem
     foi chamado por precaução, cala. */
  var anuncioPendente = false;

  function acordarServidor(forcar, anunciar) {
    if (!forcar && Date.now() - redeUltimoSucesso < REDE_OCIOSA_MS) {
      return Promise.resolve(true);
    }
    if (redeAcordando) {
      /* Uma gravação que chega no meio de um aquecimento mudo passa a
         ter alguém esperando: daí em diante ele fala. */
      if (anunciar) anuncioPendente = true;
      return redeAcordando;
    }

    anuncioPendente = Boolean(anunciar);
    redeAcordando = pulsoDoServidor(0, function () {
      return anuncioPendente;
    }).finally(function () {
      redeAcordando = null;
      anuncioPendente = false;
    });
    return redeAcordando;
  }

  Painel.rede = {
    acordar: acordarServidor,

    /* Navegação e central de avisos também atravessam o Django e o banco.
       Se uma delas acabou de responder, esperar outro /pronto/ antes de
       salvar seria uma viagem redundante pela rede. */
    marcarSucesso: function () {
      redeUltimoSucesso = Date.now();
    },

    /* POST único: o preflight GET pode repetir; a gravação nunca. */
    post: function (destino, opcoes) {
      // Uma gravação não espera o GET de aquecimento. O próprio POST
      // acorda o servidor e nunca é repetido automaticamente.
      return fetch(destino, opcoes).then(function (resposta) {
        if (resposta.ok) redeUltimoSucesso = Date.now();
        return resposta;
      });
    },
  };

  /* Mantém a instância pronta somente enquanto o painel está realmente em
     uso. Aba escondida não gera tráfego; ao voltar, acorda imediatamente. */
  global.setInterval(function () {
    if (document.visibilityState === "visible") acordarServidor(true).catch(function () {});
  }, REDE_PULSO_MS);

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") acordarServidor(false).catch(function () {});
  });
  global.addEventListener("pageshow", function () {
    acordarServidor(false).catch(function () {});
  });
  document.addEventListener("pointerdown", function () {
    if (Date.now() - redeUltimoSucesso >= REDE_OCIOSA_MS) {
      acordarServidor(false).catch(function () {});
    }
  }, { capture: true, passive: true });

  /* ======================================================================
     "ESTÁ ACONTECENDO ALGUMA COISA" — o que faltava em salvar e excluir

     Gravar mostrava só o rótulo do botão virando "Salvando…", dentro de
     uma janela que fecha logo em seguida; depois disso a tela ficava
     parada enquanto a lista era rebuscada. Em rede de galpão ou com a
     instância voltando do sono isso é meio minuto sem nada na tela --
     e meio minuto sem resposta é indistinguível de travamento. Quem
     estava usando clicava de novo.

     Esta é a camada que faltava: uma tarja fixa, no alto e no centro,
     que diz o que está sendo feito e permanece até o fim do ciclo
     inteiro -- gravação MAIS a atualização da lista. Ela também se
     inscreve nas esperas de rede, então "Salvando…" vira "Servidor
     acordando… (12s)" quando é isso que está acontecendo, em vez de
     continuar mentindo que ainda está gravando.
     ====================================================================== */
  var caixaOcupado = null;
  var relogioOcupado = null;
  var tetoOcupado = null;
  var inicioOcupado = 0;
  var textoOcupado = "";

  /* TETO DE VIDA DA TARJA.

     Ela informa uma espera; se a espera acaba sem ninguém avisar, ela
     tem de sair sozinha. Sem isso, qualquer caminho que a mostre e não
     a esconda a deixa presa na tela contando segundos -- foi o que
     aconteceu com a busca de fundo, que a acendia e nunca a apagava
     porque ninguém tinha navegado.

     Setenta segundos: um pouco mais que a maior espera legítima (a
     sondagem de 8s mais a janela de despertar de 50s). Passou disso,
     ou a resposta chegou por outro caminho, ou ela não vem mais -- e nos
     dois casos a tarja está mentindo. */
  var TETO_DA_TARJA = 70000;

  function montarOcupado() {
    if (caixaOcupado && document.body.contains(caixaOcupado)) return caixaOcupado;
    caixaOcupado = document.createElement("div");
    caixaOcupado.className = "ls-ocupado";
    caixaOcupado.setAttribute("role", "status");
    caixaOcupado.setAttribute("aria-live", "polite");
    caixaOcupado.innerHTML =
      '<span class="ls-ocupado-giro" aria-hidden="true"></span>' +
      '<span class="ls-ocupado-texto"></span>';
    document.body.appendChild(caixaOcupado);
    return caixaOcupado;
  }

  function pintarOcupado(sufixo) {
    if (!caixaOcupado) return;
    caixaOcupado.querySelector(".ls-ocupado-texto").textContent =
      textoOcupado + (sufixo || "");
  }

  /* Mostra a tarja. Enquanto ela estiver de pé, o relógio acrescenta os
     segundos decorridos depois do quinto -- antes disso a conta na tela
     só chamaria atenção para uma espera que já terminou. */
  Painel.ocupado = function (mensagem) {
    montarOcupado();
    textoOcupado = mensagem || "Salvando…";
    inicioOcupado = Date.now();
    pintarOcupado("");
    caixaOcupado.classList.add("aparece");

    if (relogioOcupado) global.clearInterval(relogioOcupado);
    relogioOcupado = global.setInterval(function () {
      var segundos = Math.round((Date.now() - inicioOcupado) / 1000);
      pintarOcupado(segundos >= 5 ? " (" + segundos + "s)" : "");
    }, 1000);

    if (tetoOcupado) global.clearTimeout(tetoOcupado);
    tetoOcupado = global.setTimeout(Painel.pronto, TETO_DA_TARJA);
  };

  Painel.pronto = function () {
    if (relogioOcupado) {
      global.clearInterval(relogioOcupado);
      relogioOcupado = null;
    }
    if (tetoOcupado) {
      global.clearTimeout(tetoOcupado);
      tetoOcupado = null;
    }
    if (caixaOcupado) caixaOcupado.classList.remove("aparece");
    if (global.LSLoader && global.LSLoader.hide) global.LSLoader.hide();
  };

  /* Confirmação curta do que acabou de acontecer. Sem ela, uma gravação
     bem-sucedida e uma janela que fecha sozinha por engano têm a mesma
     aparência. */
  Painel.aviso = function (mensagem, tipo, tema) {
    if (!mensagem) return;
    var tarja = document.createElement("div");
    tarja.className = "ls-tarja" + (tipo ? " " + tipo : "");
    tarja.setAttribute("role", "status");
    tarja.textContent = mensagem;
    if (["sol", "lua", "eclipse"].indexOf(tema) !== -1) {
      document.querySelectorAll(".ls-tarja-tema").forEach(function (anterior) { anterior.remove(); });
      tarja.className = "ls-tarja ls-tarja-tema";
      tarja.dataset.temaAviso = tema;
      var origem = document.querySelector("#lsTemaIconeAtual svg");
      if (origem) {
        var icone = origem.cloneNode(true);
        icone.querySelectorAll("[id]").forEach(function (definicao) {
          var anterior = definicao.id;
          definicao.id = anterior + "Aviso";
          icone.querySelectorAll("[fill]").forEach(function (parte) {
            if (parte.getAttribute("fill") === "url(#" + anterior + ")") {
              parte.setAttribute("fill", "url(#" + definicao.id + ")");
            }
          });
        });
        tarja.prepend(icone);
      }
    }
    document.body.appendChild(tarja);
    global.requestAnimationFrame(function () { tarja.classList.add("aparece"); });
    global.setTimeout(function () {
      tarja.classList.remove("aparece");
      global.setTimeout(function () { tarja.remove(); }, 260);
    }, 2600);
  };

  /* A espera de rede reescreve a tarja: quem está olhando passa a saber
     que a demora é o servidor voltando, e não a gravação emperrada. */
  Painel.aoEsperarRede(function (estado) {
    if (!caixaOcupado || !caixaOcupado.classList.contains("aparece")) return;
    if (estado === "acordando") {
      textoOcupado = "Servidor acordando…";
      pintarOcupado("");
    }
  });

  Painel.fotoMaterial = function (form) {
    var editor = form.querySelector("[data-foto-editor]");
    var campo = editor.querySelector("[data-foto-input]");
    var previa = editor.querySelector("[data-foto-previa]");
    var vazio = editor.querySelector("[data-foto-vazia]");
    var remover = editor.querySelector("[data-foto-remover]");
    var erro = editor.querySelector("[data-foto-erro]");
    var objeto = null, original = "";
    function limparObjeto() {
      if (objeto) URL.revokeObjectURL(objeto);
      objeto = null;
    }
    function mostrar(url) {
      previa.hidden = !url;
      vazio.hidden = !!url;
      if (url) previa.src = url; else previa.removeAttribute("src");
    }
    campo.addEventListener("change", function () {
      limparObjeto();
      erro.textContent = "";
      var arquivo = campo.files[0];
      if (!arquivo) { mostrar(remover.checked ? "" : original); return; }
      if (arquivo.size > 5 * 1024 * 1024 || !/^image\/(jpeg|png|webp)$/.test(arquivo.type)) {
        erro.textContent = "Escolha JPG, PNG ou WebP de até 5 MB.";
        campo.value = "";
        mostrar(remover.checked ? "" : original);
        return;
      }
      remover.checked = false;
      objeto = URL.createObjectURL(arquivo);
      mostrar(objeto);
    });
    remover.addEventListener("change", function () {
      limparObjeto(); campo.value = "";
      mostrar(remover.checked ? "" : original);
    });
    previa.addEventListener("error", function () {
      erro.textContent = "Não foi possível exibir esta foto.";
      mostrar("");
    });
    var modal = form.closest(".modal");
    if (modal) modal.addEventListener("hidden.bs.modal", function () { limparObjeto(); mostrar(""); });
    return function (url) {
      limparObjeto(); original = url || "";
      campo.value = ""; remover.checked = false; erro.textContent = "";
      mostrar(original);
    };
  };

  Painel.enviar = function (form, extras) {
    var dados = new FormData(form);

    Object.keys(extras || {}).forEach(function (chave) {
      dados.set(chave, extras[chave]);
    });

    // getAttribute, nao form.action: o proprio formulario tem um
    // <input name="action">, e o acesso por propriedade devolve esse
    // input em vez da URL -- o POST ia parar em /stock/[object HTMLInputElement].
    var destino = form.getAttribute("action") || global.location.pathname;

    return Painel.rede.post(destino, {
      method: "POST",
      body: dados,
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    }).then(function (resposta) {
      return resposta
        .json()
        .catch(function () {
          return null;
        })
        .then(function (json) {
          if (!resposta.ok || !json || json.status !== "sucesso") {
            throw new Error(
              (json && json.msg) ||
                "Não foi possível salvar. Tente novamente em instantes."
            );
          }
          /* Salvou: os avisos podem ter mudado agora mesmo -- um pedido
             que virou produção, um orçamento que saiu. Perguntar aqui faz
             a bolinha acompanhar a ação de quem está na tela, sem esperar
             o próximo intervalo. */
          Painel.confirmarGravacao();
          return json;
        });
    });
  };

  /* Liga um formulario de modal ao envio por fetch.
   *
   * opcoes: { form, erro, action, antes, depois, rotuloCarregando }
   * - antes: devolve string com um erro de validacao para barrar o envio
   * - depois: recebe o JSON; por padrão atualiza somente a tela
   */
  Painel.ligar = function (opcoes) {
    var form = document.getElementById(opcoes.form);
    if (!form) {
      return;
    }

    var botao = form.querySelector('[type="submit"]');
    var rotulo = botao ? botao.textContent : "";
    var enviando = false;

    function travar(on) {
      enviando = on;
      if (!botao) {
        return;
      }
      botao.disabled = on;
      botao.textContent = on ? (opcoes.rotuloCarregando || "Salvando...") : rotulo;
    }

    // A validacao nativa nao bubbla e o balaozinho some quando o modal
    // rola; o motivo tambem vai pro banner fixo do modal.
    form.addEventListener(
      "invalid",
      function (e) {
        travar(false);
        Painel.erro(
          opcoes.erro,
          "Confira o campo " +
            (e.target.getAttribute("data-rotulo") || e.target.name) +
            ": " +
            e.target.validationMessage
        );
      },
      true
    );

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (enviando) return;
      Painel.erro(opcoes.erro, "");

      if (opcoes.antes) {
        var impedimento = opcoes.antes(form);
        if (impedimento) {
          Painel.erro(opcoes.erro, impedimento);
          return;
        }
      }

      travar(true);
      /* A tarja cobre o CICLO INTEIRO -- gravar e depois rebuscar a
         lista. Antes, a janela fechava assim que o POST voltava e a
         atualização acontecia em silêncio: a tela antiga continuava na
         frente, com os dados antigos, e parecia que nada tinha sido
         salvo. */
      Painel.ocupado(opcoes.rotuloCarregando || "Salvando…");

      Painel.enviar(form, opcoes.action ? { action: opcoes.action } : null)
        .then(function (json) {
          if (opcoes.depois) {
            opcoes.depois(json);
            travar(false);
            Painel.pronto();
            Painel.aviso(opcoes.mensagemPronta || "Salvo.", "ok");
          } else {
            /* A gravação já terminou. Fecha a janela imediatamente para
               que o clique pareça concluído e atualiza só o conteúdo;
               recarregar o documento inteiro repetia CSS, scripts e menu. */
            var modal = form.closest(".modal");
            if (modal && modal.id) Painel.fechar(modal.id);
            textoOcupado = "Atualizando a lista…";
            pintarOcupado("");

            var atualizacao =
              typeof global.LSAtualizarTela === "function"
                ? global.LSAtualizarTela({ partes: opcoes.partes === true })
                : null;

            function encerrar() {
              travar(false);
              Painel.pronto();
              Painel.aviso(opcoes.mensagemPronta || "Salvo.", "ok");
            }

            if (atualizacao && typeof atualizacao.then === "function") {
              atualizacao.then(encerrar, encerrar);
            } else if (typeof global.LSAtualizarTela === "function") {
              /* Versão antiga do módulo de navegação, que não devolve
                 promessa: a tarja sai por tempo, e não por evento. */
              global.setTimeout(encerrar, 1200);
            } else {
              global.location.reload();
            }
          }
        })
        .catch(function (err) {
          Painel.pronto();
          Painel.erro(opcoes.erro, err.message);
          travar(false);
        });
    });
  };

  /* Exclusão permanente com confirmação escrita.
   *
   * O botão só habilita quando a palavra está certa, mas isto é apenas a
   * orientação da interface. O servidor repete a validação e a permissão;
   * assim um POST manual nunca contorna a proteção. Uma função única atende
   * clientes e orçamentos e mantém o comportamento igual nas duas telas. */
  Painel.ligarExclusao = function (opcoes) {
    opcoes = opcoes || {};

    var formId = opcoes.form || "formExcluir";
    var erroId = opcoes.erro || "excluirErro";
    var modalId = opcoes.modal || "modalExcluir";
    var form = document.getElementById(formId);
    if (!form) return;

    var campo = form.querySelector('[name="confirmacao_exclusao"]');
    var botao = form.querySelector('[type="submit"]');
    var nome = document.getElementById(opcoes.nome || "excluirNome");
    var id = document.getElementById(opcoes.id || "excluirId");
    var palavra = String(opcoes.palavra || "CONFIRMAR");

    function normalizar(valor) {
      return String(valor || "").trim().toLocaleUpperCase("pt-BR");
    }

    function confirmacaoCorreta() {
      return campo && normalizar(campo.value) === normalizar(palavra);
    }

    function atualizarConfirmacao() {
      var correta = confirmacaoCorreta();
      if (botao) botao.disabled = !correta;
      if (campo) {
        campo.classList.toggle("is-valid", correta);
        campo.classList.remove("is-invalid");
        campo.setAttribute("aria-invalid", "false");
      }
    }

    if (campo) campo.addEventListener("input", atualizarConfirmacao);

    Painel.aoClicar(opcoes.gatilho || "[data-excluir]", function (gatilho) {
        form.reset();
        Painel.erro(erroId, "");
        if (id) id.value = gatilho.dataset.excluir || "";
        if (nome) nome.textContent = gatilho.dataset.nome || "Registro selecionado";

        /* EXCLUSÃO COMUM OU EXCLUSÃO POR CIMA DA REGRA?

           O botão diz, pelo `data-protegido`, se aquele registro é dos
           que as regras normais protegem -- proposta já enviada, O.S.
           concluída, cliente com histórico. Nesse caso o superusuário
           continua podendo excluir, mas precisa saber que está passando
           por cima de uma proteção e que isso vai ficar registrado com o
           nome dele. Sem o aviso, apagar histórico teria a mesma cara de
           apagar um rascunho -- e é justamente o que não pode. */
        var forcada = document.getElementById("excluirForcada");
        if (forcada) {
          forcada.hidden = gatilho.dataset.protegido !== "1";
          var detalhe = gatilho.dataset.protegidoMotivo;
          var vao = document.getElementById("excluirForcadaDetalhe");
          if (detalhe && vao) vao.textContent = detalhe;
        }

        atualizarConfirmacao();
        Painel.abrir(modalId);

        /* No celular, abrir o teclado imediatamente esconde a explicação.
         * No desktop, foco direto economiza um clique. */
        if (campo && global.matchMedia("(min-width: 901px)").matches) {
          global.setTimeout(function () { campo.focus(); }, 180);
        }
    });

    Painel.ligar({
      form: formId,
      erro: erroId,
      rotuloCarregando: "Excluindo...",
      antes: function () {
        if (confirmacaoCorreta()) return null;
        if (campo) {
          campo.classList.add("is-invalid");
          campo.setAttribute("aria-invalid", "true");
          campo.focus();
        }
        return "Digite " + palavra + " para autorizar a exclusão.";
      }
    });
  };

  /* ==================================================================
     A JANELA CABE NA TELA -- SEMPRE, INCLUSIVE COM O TECLADO ABERTO.

     Este é o bug que mais atrapalhou o dia a dia: no tablet, ao tocar
     num campo, o teclado sobe e cobre a parte de baixo da tela. Só que
     `100dvh` NÃO enxerga o teclado -- para o CSS a janela continua com a
     altura inteira, e "Salvar" e "Cancelar" ficam atrás do teclado, sem
     rolagem que os alcance. A pessoa digita e não tem como salvar.

     Quem enxerga o teclado é o `visualViewport`. Copiamos a altura dele
     para `--ls-vh` e o CSS usa essa medida no lugar de `100dvh`: quando
     o teclado sobe, a janela encolhe junto e o rodapé continua visível.
     ================================================================== */
  function medirTela() {
    var vv = global.visualViewport;
    var altura = vv ? vv.height : global.innerHeight;
    document.documentElement.style.setProperty("--ls-vh", Math.round(altura) + "px");
  }

  var medidaLigada = false;

  function ligarMedidaDeTela() {
    medirTela();
    /* Os ouvintes abaixo são de janela, não de tela: sobrevivem à troca
       e não podem ser registrados de novo a cada navegação. */
    if (medidaLigada) return;
    medidaLigada = true;
    if (global.visualViewport) {
      global.visualViewport.addEventListener("resize", medirTela);
      global.visualViewport.addEventListener("scroll", medirTela);
    }
    global.addEventListener("resize", medirTela);
    global.addEventListener("orientationchange", function () {
      setTimeout(medirTela, 220);
    });
  }

  /* Toda janela do painel tem a mesma estrutura: cabeçalho fixo, corpo
     que rola, rodapé fixo. Marcar isso aqui, e não em cada template,
     é o que garante que a próxima janela nasça certa -- metade delas
     estava sem a marca e dependia de sorte para o rodapé aparecer. */
  function normalizarJanela(modal) {
    var dialogo = modal.querySelector(".modal-dialog");
    if (!dialogo) return;
    dialogo.classList.add("modal-dialog-scrollable", "modal-dialog-centered");
  }

  /* Campo focado atrás do teclado: o navegador rola a PÁGINA, que no
     modal não rola nada. Rolamos o corpo da janela, que é quem rola. */
  function trazerCampoParaVista(campo) {
    var corpo = campo.closest(".modal-body");
    if (!corpo) return;

    var c = corpo.getBoundingClientRect();
    var e = campo.getBoundingClientRect();
    if (e.top >= c.top + 8 && e.bottom <= c.bottom - 8) return;

    corpo.scrollTop += e.top - c.top - (c.height - e.height) / 2;
  }

  /* ==================================================================
     ESCREVER SEM APERTO.

     Campo de observação com três linhas fixas obriga a rolar por dentro
     de uma caixinha para reler o que se escreveu -- no tablet, com o
     teclado ocupando metade da tela, é quase impossível conferir o
     texto antes de salvar. O campo cresce com o que se digita, até um
     limite, e aí sim começa a rolar.
     ================================================================== */
  var ALTURA_MAXIMA_TEXTO = 320;

  function acomodarTexto(campo) {
    campo.style.height = "auto";
    var preciso = campo.scrollHeight + 2;
    campo.style.height = Math.min(preciso, ALTURA_MAXIMA_TEXTO) + "px";
    campo.style.overflowY = preciso > ALTURA_MAXIMA_TEXTO ? "auto" : "hidden";
  }

  Painel.acomodarTextos = function (raiz) {
    (raiz || document).querySelectorAll("textarea").forEach(function (campo) {
      if (campo.dataset.crescer !== "1") {
        campo.dataset.crescer = "1";
        campo.addEventListener("input", function () { acomodarTexto(campo); });
      }
      acomodarTexto(campo);
    });
  };

  /* ====================================================================
     WHATSAPP: TROCAR DE CONVERSA SEM RECARREGAR O APLICATIVO
     --------------------------------------------------------------------
     O QUE AINDA DOÍA. A aba única resolveu o acúmulo de abas, mas não o
     tempo: cada envio chamava `window.open` com
     `web.whatsapp.com/send?phone=...`, e isso é uma NAVEGAÇÃO DE
     DOCUMENTO. O WhatsApp Web é um aplicativo de página única -- navegar
     a aba o derruba e o obriga a subir de novo: reconectar, decifrar e
     redesenhar todas as conversas. É o "carregando as mensagens" que
     aparecia a cada cliente.

     Não dá para trocar a conversa por dentro: a página é de outro
     domínio e nenhum script daqui alcança o que acontece lá. Então a
     saída não é um truque, são dois caminhos previsíveis:

     1. MESMO CLIENTE, NENHUMA NAVEGAÇÃO. Reenviar para quem já está
        aberto só traz a aba para a frente. Antes isso recarregava o
        WhatsApp inteiro para chegar exatamente onde já estava.

     2. CLIENTE DIFERENTE. Abrir automaticamente a conversa navega a aba
        Web nomeada. Quem quer evitar esse carregamento copia a mensagem
        e troca a conversa DENTRO do WhatsApp, que é instantâneo porque
        acontece sem sair da página. No computador não sondamos protocolo
        nativo: ele pode falhar em silêncio e perder a ativação do clique.
        Ver `Painel.whatsapp.copiar`.
     ==================================================================== */
  function numeroComDdi(telefone) {
    var digitos = String(telefone || "").replace(/\D/g, "");
    if (digitos.length < 10) return "";
    /* 10 ou 11 dígitos é número brasileiro sem DDI. Acima disso a pessoa
       já digitou o país -- inclusive para cliente de fora. */
    if (digitos.length === 10 || digitos.length === 11) digitos = "55" + digitos;
    return digitos;
  }

  function noCelular() {
    /* `maxTouchPoints` pega o iPad, que se anuncia como Mac há anos. */
    return (
      /Android|iPhone|iPad|iPod|Windows Phone/i.test(navigator.userAgent) ||
      (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))
    );
  }

  /* Um nome estável faz o próprio navegador encontrar a aba mesmo depois
     de o painel ser recarregado. A referência acelera o caso comum; o nome
     resolve também o caso em que a referência JavaScript foi perdida. */
  var NOME_ABA_WHATSAPP = "ls-whatsapp-web";
  var abaWhatsappWeb = null;
  /* Para quem a aba está aberta agora. Guardado também no navegador
     porque a aba sobrevive ao recarregamento do painel, e sem isso o
     primeiro envio depois de um F5 recarregaria o WhatsApp à toa. */
  var CHAVE_CONVERSA = "ls:whatsapp:conversa";

  function guardado(chave) {
    try { return global.localStorage.getItem(chave) || ""; } catch (e) { return ""; }
  }

  function guardar(chave, valor) {
    try { global.localStorage.setItem(chave, valor); } catch (e) {}
  }

  function alvoWhatsapp() {
    return noCelular() ? "_blank" : NOME_ABA_WHATSAPP;
  }

  function focarAba() {
    if (abaWhatsappWeb && !abaWhatsappWeb.closed) {
      try { abaWhatsappWeb.focus(); return true; } catch (e) {}
    }
    /* Nunca tente recuperar uma referência com window.open("", nome).
       Quando a aba não existe, isso cria about:blank -- exatamente a
       página vazia que aparecia no botão Copiar mensagem. */
    return false;
  }

  function navegarAba(endereco) {
    var aba = global.open(endereco, alvoWhatsapp());
    if (aba) {
      abaWhatsappWeb = aba;
      /* Alguns navegadores navegam a aba nomeada, mas deixam o painel
         por cima. O foco torna a troca de cliente imediatamente visível. */
      try { aba.focus(); } catch (e) {}
    }
    return aba;
  }

  Painel.whatsapp = {
    numero: numeroComDdi,

    /* No PC vai explicitamente ao WhatsApp Web; no celular conserva wa.me. */
    web: function (telefone, mensagem) {
      var digitos = numeroComDdi(telefone);
      if (!digitos) return "";
      var base = noCelular()
        ? "https://wa.me/" + digitos
        : "https://web.whatsapp.com/send?phone=" + digitos;
      return base + (noCelular() ? "?text=" : "&text=")
        + encodeURIComponent(mensagem || "");
    },

    noCelular: noCelular,
    alvo: alvoWhatsapp,

    /* O atalho sem recarregar: a mensagem vai para a área de
       transferência e a aba do WhatsApp vem para a frente. Quem troca a
       conversa por dentro do WhatsApp não paga o carregamento, porque
       nada saiu da página. */
    copiar: function (mensagem, telefone) {
      var texto = String(mensagem || "");
      var entregue = Promise.resolve(false);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          entregue = navigator.clipboard.writeText(texto).then(function () {
            return true;
          }).catch(function () { return false; });
        }
      } catch (e) {}

      /* Abrir/focar precisa acontecer no mesmo ciclo do clique. Dentro do
         .then da área de transferência vários navegadores já consideram
         pop-up tardio e bloqueiam. Se ainda não existe referência viva,
         abre uma URL REAL; nunca uma string vazia/about:blank. */
      var abriu = focarAba();
      if (!abriu) {
        var destino = noCelular()
          ? this.web(telefone, "")
          : "https://web.whatsapp.com/";
        var aba = navegarAba(destino || "https://web.whatsapp.com/");
        abriu = Boolean(aba);
      }

      return entregue.then(function (ok) {
        return { copiou: ok, abriu: abriu };
      });
    },

    /* Abre a conversa e devolve o que aconteceu, para a tela explicar.
       Precisa ser chamado DENTRO do clique: fora do gesto da pessoa o
       navegador trata como pop-up e bloqueia. */
    abrir: function (telefone, mensagem) {
      var web = this.web(telefone, mensagem);
      if (!web) return { ok: false, motivo: "numero", web: "" };

      if (noCelular()) {
        var aba = global.open(web, "_blank");
        if (aba) { try { aba.opener = null; } catch (e) {} }
        return { ok: !!aba, motivo: aba ? "web" : "bloqueado", web: web };
      }

      var digitos = numeroComDdi(telefone);

      /* 1. Mesmo cliente: a conversa já está aberta ali. Navegar de novo
            recarregaria o WhatsApp inteiro para chegar onde já está. */
      var mesmaConversa = digitos && guardado(CHAVE_CONVERSA) === digitos;
      if (mesmaConversa && focarAba()) {
        return { ok: true, motivo: "mesma-conversa", web: web, semRecarregar: true };
      }

      /* No computador o contrato é WhatsApp Web. A navegação ocorre já
         dentro do clique, numa única aba nomeada, sem sondagem de protocolo
         que possa falhar em silêncio ou deixar uma página vazia. */
      guardar(CHAVE_CONVERSA, digitos);
      var novaAba = navegarAba(web);
      return {
        ok: !!novaAba,
        motivo: novaAba ? "web" : "bloqueado",
        web: web,
      };
    },
  };

  /* Links antigos em wa.me também entram na Web no computador. */
  document.addEventListener("click", function (evento) {
    var link = evento.target.closest
      ? evento.target.closest('a[href^="https://wa.me/"]')
      : null;
    if (!link || link.hasAttribute("data-whatsapp-web")) return;
    if (noCelular()) return;

    var endereco = new URL(link.href);
    var telefone = endereco.pathname.replace(/\//g, "");
    if (!telefone) return;

    evento.preventDefault();
    var destino = Painel.whatsapp.web(
      telefone,
      endereco.searchParams.get("text") || ""
    );
    var aba = window.open(destino, alvoWhatsapp());
    if (aba) {
      abaWhatsappWeb = aba;
      try { aba.focus(); } catch (e) {}
    }
  });

  /* ====================================================================
     AVISOS AO VIVO
     --------------------------------------------------------------------
     As bolinhas do menu e a central eram desenhadas uma vez, no HTML. Um
     pedido que entrava com o painel aberto na bancada só aparecia depois
     de recarregar -- e como a sessão dura o dia inteiro, na prática só
     depois de sair e entrar de novo. Aviso que chega tarde é o mesmo que
     aviso que não chega.

     Agora a tela pergunta ao servidor de tempos em tempos. Regras que
     mantêm isso barato:

       * só pergunta com a aba VISÍVEL -- dez abas de fundo não custam
         nada, e ao voltar para a aba a resposta é imediata;
       * o servidor devolve uma `assinatura` do estado; enquanto ela não
         muda, nada é redesenhado;
       * quem acabou de salvar alguma coisa pede uma atualização na hora
         (`Painel.avisos.agora()`), sem esperar o próximo intervalo.

     Sessão caída devolve 401, e aí a tela PARA de perguntar: insistir
     contra o login é gastar rede para nada.
     ==================================================================== */
  var avisos = {
    endereco: "",
    /* O PASSO DE QUEM ESTÁ TRABALHANDO.

       É este número que decide quanto tempo passa entre um colega salvar
       alguma coisa e o sino tocar aqui. Um painel parado tem passo
       próprio, mais lento, em `PASSO_PARADO`.

       Uma pergunta que não encontra novidade custa duas consultas curtas
       e uma resposta de duzentos bytes (304, ver o ETag em
       views_avisos.py). Quatro segundos de espera são baratos; um colega
       esperando para descobrir que existe um cliente novo, não.

       E este passo só é pago por quem está MEXENDO na tela: passados
       setenta e cinco segundos sem toque, o relógio cai para
       `PASSO_PARADO`. Foi por isso que dobrar a velocidade aqui não
       dobrou o tráfego -- o tempo em que a aba fica no passo rápido
       encurtou junto. */
    intervalo: 4000,
    assinatura: null,
    relogio: null,
    parado: false,
    ligado: false,
    lendo: false,
    ouvintes: [],
    inicializado: false,
    quantidades: {},
    /* O que o SERVIDOR lembra de já ter anunciado para esta conta. Chega
       na primeira resposta e é o que faz o sino falar com quem volta.
       Ver `PREFIXO_VISTO` em avisos.py. */
    vistos: null,
    confirmandoVistos: false,
    relogioDeVistos: null,
    ultimoSomEm: 0,
    /* Aviso que chegou antes de o navegador liberar áudio. Ver
       `despertarSom`. */
    somPendenteAte: 0,
    atividadeAte: 0,
    emVoo: null, repetir: false, ultimoEstado: null, etag: null,
    falhas: 0, proximaTentativa: 0,
    relogioDaAnimacao: null,
  };

  /* Som curto gerado pelo próprio navegador: não baixa MP3, funciona
     offline e não cria mais uma requisição. Navegadores só liberam áudio
     depois do primeiro toque/clique; até lá a central continua visual. */
  var contextoDeAudio = null;
  function prepararSom() {
    if (contextoDeAudio) {
      if (contextoDeAudio.state === "suspended") contextoDeAudio.resume().catch(function () {});
      return contextoDeAudio;
    }
    var Construtor = global.AudioContext || global.webkitAudioContext;
    if (!Construtor) return null;
    try {
      contextoDeAudio = new Construtor();
      if (contextoDeAudio.state === "suspended") contextoDeAudio.resume().catch(function () {});
    } catch (e) {
      contextoDeAudio = null;
    }
    return contextoDeAudio;
  }

  /* ====================================================================
     O AVISO QUE CHEGOU ANTES DO PRIMEIRO TOQUE

     Navegador nenhum toca som numa aba que a pessoa ainda não tocou. E é
     exatamente essa a hora do aviso mais importante: a pessoa acabou de
     abrir o painel e há uma movimentação nova esperando por ela. O som
     era simplesmente perdido.

     Agora ele fica guardado e sai no primeiro toque ou tecla -- desde
     que dentro de um minuto e meio. Passado isso, a novidade já não é
     novidade e um som do nada só assusta. A animação do sino, essa,
     acontece na hora: ela não depende de permissão nenhuma.
     ==================================================================== */
  var VALIDADE_DO_SOM_ADIADO = 90000;

  function despertarSom() {
    var audio = prepararSom();
    if (!audio || audio.state !== "running") return;
    if (!avisos.somPendenteAte) return;
    var vencido = Date.now() > avisos.somPendenteAte;
    avisos.somPendenteAte = 0;
    if (!vencido) tocarSomDeAviso();
  }

  function tocarSomDeAviso() {
    var audio = prepararSom();
    if (!audio || audio.state !== "running") {
      avisos.somPendenteAte = Date.now() + VALIDADE_DO_SOM_ADIADO;
      return;
    }
    var agora = Date.now();
    if (agora - avisos.ultimoSomEm < 1800) return;
    avisos.ultimoSomEm = agora;

    var inicio = audio.currentTime;

    /* ==================================================================
       ALTO O BASTANTE PARA UM GALPÃO

       O aviso era três senoides de volume 0,055 a 0,075 -- perto do
       silêncio. Numa sala quieta dava para ouvir; ao lado de uma
       compressor de ar, de um rádio ligado ou com o tablet na bancada a
       um metro de distância, não existia. Um aviso que não se ouve é um
       aviso que não foi dado.

       O que mudou, e por quê:

         * VOLUME quatro vezes maior. Continua longe de assustar --
           som de aviso, não de alarme;
         * DUAS VOZES por nota: uma senoide dá o corpo e um triângulo
           uma oitava acima dá o brilho. É o brilho que atravessa o
           ruído de fundo, porque ruído de galpão é grave;
         * NOTAS MAIS LONGAS (0,26s contra 0,18s) e um acorde ao fim.
           Som curto demais some no meio de qualquer barulho.

       Continua gerado aqui: não baixa arquivo, funciona sem rede e não
       gasta banda -- que, no mês em que isto foi escrito, era o assunto.
       ================================================================== */
    var VOLUME = 0.28;

    function voz(frequencia, atraso, duracao, forca, tipo) {
      var oscilador = audio.createOscillator();
      var ganho = audio.createGain();
      oscilador.type = tipo;
      oscilador.frequency.value = frequencia;

      var em = inicio + atraso;
      /* Rampa exponencial não pode partir de zero, e a subida em 12ms
         evita o "clique" de um corte seco. */
      ganho.gain.setValueAtTime(0.0001, em);
      ganho.gain.exponentialRampToValueAtTime(VOLUME * forca, em + 0.012);
      ganho.gain.exponentialRampToValueAtTime(0.0001, em + duracao);

      oscilador.connect(ganho);
      ganho.connect(audio.destination);
      oscilador.start(em);
      oscilador.stop(em + duracao + 0.02);
    }

    /* Mi, sol, si -- as três notas subindo, como antes. O acorde no fim
       é o que faz o aviso soar terminado em vez de interrompido. */
    [
      { atraso: 0, frequencia: 659.25, forca: 0.85 },
      { atraso: 0.11, frequencia: 783.99, forca: 0.95 },
      { atraso: 0.23, frequencia: 987.77, forca: 1 },
    ].forEach(function (nota) {
      voz(nota.frequencia, nota.atraso, 0.26, nota.forca, "sine");
      voz(nota.frequencia * 2, nota.atraso, 0.20, nota.forca * 0.45, "triangle");
    });
    voz(1318.51, 0.35, 0.34, 0.55, "sine");
  }

  /* ====================================================================
     CONTRA O QUE SE COMPARA PARA SABER SE CHEGOU COISA NOVA

     Com o painel aberto, contra o que está na tela: o número era 3,
     virou 4, tocou. Isso sempre funcionou.

     Na PRIMEIRA resposta depois de abrir o painel, não havia contra o
     que comparar, e o código simplesmente engolia a diferença -- quem
     saía com dez pendências e voltava com onze não via nada. Agora a
     comparação é contra `vistos`: o que o servidor lembra de já ter
     anunciado para esta conta, guardado no banco e não na aba. Sair,
     fechar o navegador, voltar no dia seguinte de outro computador: a
     décima primeira movimentação continua sendo anunciada.

     Servidor antigo, ou resposta sem o campo, cai no comportamento de
     antes -- calado -- em vez de anunciar tudo de uma vez.
     ==================================================================== */
  function houveAvisoNovo(dados) {
    var atuais = {};
    var referencia = avisos.inicializado ? avisos.quantidades : avisos.vistos;
    var novo = false;
    (dados.avisos || []).forEach(function (item) {
      var quantidade = Number(item.quantidade) || 0;
      atuais[item.chave] = quantidade;
      if (referencia && quantidade > (referencia[item.chave] || 0)) {
        novo = true;
      }
    });
    avisos.quantidades = atuais;
    if (!avisos.inicializado) avisos.inicializado = true;
    return novo;
  }

  function mesmasQuantidades(a, b) {
    if (!a || !b) return false;
    var chaves = Object.keys(a).concat(Object.keys(b));
    for (var i = 0; i < chaves.length; i += 1) {
      if ((a[chaves[i]] || 0) !== (b[chaves[i]] || 0)) return false;
    }
    return true;
  }

  /* ====================================================================
     "MOSTREI ISTO PARA ELA"

     Quem grava a memória do sino é o painel, e não o GET do servidor:
     só o navegador sabe se o número chegou de fato a uma tela. Sai um
     POST curto por MUDANÇA REAL de estado -- não por pulso -- e com um
     respiro de dois segundos, para uma sequência de gravações rápidas
     virar uma confirmação só.

     A cópia local é atualizada na hora, antes da resposta: sem isso o
     pulso seguinte compararia com a memória velha e anunciaria a mesma
     novidade de novo.
     ==================================================================== */
  function confirmarVistos() {
    if (!avisos.endereco || avisos.parado) return;
    if (mesmasQuantidades(avisos.vistos, avisos.quantidades)) return;

    var enviar = {};
    Object.keys(avisos.quantidades).forEach(function (chave) {
      if (avisos.quantidades[chave] > 0) enviar[chave] = avisos.quantidades[chave];
    });
    avisos.vistos = enviar;

    global.clearTimeout(avisos.relogioDeVistos);
    avisos.relogioDeVistos = global.setTimeout(function () {
      if (avisos.confirmandoVistos || avisos.parado) return;
      avisos.confirmandoVistos = true;
      var corpo = new FormData();
      corpo.set("acao", "avisos_vistos");
      corpo.set("vistos", JSON.stringify(avisos.vistos || {}));
      var campo = document.querySelector("[name=csrfmiddlewaretoken]");
      if (campo) corpo.set("csrfmiddlewaretoken", campo.value);
      fetch(avisos.endereco, {
        method: "POST",
        body: corpo,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": campo ? campo.value : "",
        },
        credentials: "same-origin",
        cache: "no-store",
      }).catch(function () {
        /* Falhou: a memória do servidor continua a antiga e o pior que
           acontece é o sino anunciar de novo na próxima abertura. Nunca
           o contrário -- perder um aviso seria o erro grave. */
      }).finally(function () {
        avisos.confirmandoVistos = false;
      });
    }, 2000);
  }

  /* ====================================================================
     O SINO SE MEXE QUANDO CHEGA COISA NOVA

     A pulsação sozinha não dava conta: quem está com o painel de avisos
     ABERTO olha para a lista, e o número no canto trocava de 3 para 4
     sem nada acontecer na tela -- ninguém percebia que tinha chegado
     mais uma. Agora o sino chacoalha, o número SOME, é reescrito
     escondido e volta já atualizado. O movimento é o que conta a
     novidade; o número volta com a resposta.

     Chamada ANTES de `desenharAvisos`: é isso que faz a troca acontecer
     com o selo invisível, em vez de o número piscar o valor velho.
     ==================================================================== */
  function anunciarNoSino(chegada) {
    var botao = document.getElementById("avisosBotao");
    if (!botao) return;

    /* CHEGADA: a novidade aconteceu enquanto a pessoa não estava aqui.
       Se a aba abriu no fundo (link novo, restauração de sessão), o sino
       espera ela aparecer -- balançar para uma tela que ninguém está
       olhando é o mesmo que não balançar. */
    if (chegada && document.visibilityState !== "visible") {
      document.addEventListener("visibilitychange", function aoAparecer() {
        if (document.visibilityState !== "visible") return;
        document.removeEventListener("visibilitychange", aoAparecer);
        anunciarNoSino(true);
      });
      return;
    }

    var selos = document.querySelectorAll('[data-selo="total"]');
    /* Tirar e repor a classe reinicia a animação: sem a leitura de
       `offsetWidth` no meio, o navegador junta as duas mudanças num
       quadro só e o segundo aviso seguido não chacoalha nada. */
    botao.classList.remove("chacoalha");
    botao.classList.remove("chegada");
    void botao.offsetWidth;
    botao.classList.add("chacoalha");
    /* Quem volta ao painel não está olhando para o sino: os olhos estão
       procurando a tela carregar. Uma batida de seis décimos passa
       despercebida, então na chegada ele bate três vezes. */
    if (chegada) botao.classList.add("chegada");
    selos.forEach(function (selo) { selo.classList.add("trocando"); });

    global.clearTimeout(avisos.relogioDaAnimacao);
    avisos.relogioDaAnimacao = global.setTimeout(function () {
      botao.classList.remove("chacoalha");
      botao.classList.remove("chegada");
      document.querySelectorAll('[data-selo="total"]').forEach(
        function (selo) { selo.classList.remove("trocando"); }
      );
    }, chegada ? 1900 : 620);
  }

  function pintarSelo(elemento, quantidade) {
    if (!elemento) return;
    var numero = Number(quantidade) || 0;
    elemento.textContent = numero;
    elemento.hidden = numero === 0 && elemento.dataset.mostrarZero !== "1";
  }

  function desenharAvisos(dados) {
    var contagens = dados.contagens || {};
    Object.keys(contagens).forEach(function (chave) {
      document.querySelectorAll('[data-selo="' + chave + '"]').forEach(
        function (selo) { pintarSelo(selo, contagens[chave]); }
      );
    });

    document.querySelectorAll('[data-selo="urgentes"]').forEach(function (selo) {
      pintarSelo(selo, dados.urgentes);
    });
    var pendentes = Number(dados.total) || 0;
    var urgentes = Number(dados.urgentes) || 0;
    document.querySelectorAll('[data-selo="total"]').forEach(function (selo) {
      pintarSelo(selo, dados.total);
      selo.classList.toggle("urgente", urgentes > 0);
    });

    /* QUEM CHAMA É O BOTÃO, NÃO O NÚMERO.

       A onda e o clarão do sino são pseudo-elementos do botão (ver
       `.ls-avisos-botao::before/::after`), e CSS não sabe olhar para o
       selo que está dentro dele -- `:has()` saberia, mas o tablet da
       fábrica nem sempre tem. Então quem conta ao botão o que o selo
       está mostrando é esta linha. */
    var botao = document.getElementById("avisosBotao");
    if (botao) {
      botao.classList.toggle("tem-aviso", pendentes > 0);
      botao.classList.toggle("urgente", urgentes > 0);
    }

    var texto = document.querySelector('[data-selo="urgentes-texto"]');
    if (texto) {
      var quantos = Number(dados.urgentes) || 0;
      texto.textContent = quantos + " urgente" + (quantos === 1 ? "" : "s");
      texto.hidden = quantos === 0;
    }

    var lista = document.getElementById("avisosLista");
    if (lista) lista.innerHTML = montarLista(dados.avisos || []);
  }

  function escapar(texto) {
    var caixa = document.createElement("span");
    caixa.textContent = texto == null ? "" : String(texto);
    return caixa.innerHTML;
  }

  function montarLista(itens) {
    if (!itens.length) {
      return (
        '<div class="ls-avisos-vazio">' +
        '<i class="bi bi-check2-circle"></i> Nada pendente agora.</div>'
      );
    }
    return itens.map(function (aviso) {
      return (
        '<a class="ls-aviso ' + escapar(aviso.nivel) + '" href="' + escapar(aviso.url) + '">' +
        '<span class="ls-aviso-icone"><i class="bi ' + escapar(aviso.icone) + '"></i></span>' +
        '<span class="ls-aviso-corpo">' +
        '<span class="ls-aviso-titulo">' + escapar(aviso.titulo) +
        '<span class="ls-aviso-quantidade">' + escapar(aviso.quantidade) + "</span></span>" +
        '<span class="ls-aviso-detalhe">' + escapar(aviso.detalhe) + "</span>" +
        "</span></a>"
      );
    }).join("");
  }

  function mostrarEstadoDaSincronia(texto) {
    var estado = document.getElementById("lsSincroniaEstado");
    if (estado) { estado.textContent = texto || ""; estado.hidden = !texto; }
  }

  function buscarAvisos(forcar) {
    if (avisos.parado || !avisos.endereco) return Promise.resolve(null);
    if (avisos.emVoo) {
      if (forcar) avisos.repetir = true;
      return avisos.emVoo;
    }
    if (!forcar && Date.now() < avisos.proximaTentativa) return Promise.resolve(null);
    var controle = new AbortController();
    var prazo = global.setTimeout(function () { controle.abort(); }, 12000);
    var headers = { "X-Requested-With": "XMLHttpRequest" };
    if (avisos.etag && !forcar) headers["If-None-Match"] = avisos.etag;
    avisos.emVoo = fetch(avisos.endereco, {
      headers: headers, credentials: "same-origin", cache: "no-store", signal: controle.signal,
    }).then(function (resposta) {
      if (resposta.status === 401 || resposta.status === 403) {
        avisos.parado = true;
        mostrarEstadoDaSincronia("Entre novamente para atualizar os avisos.");
        return null;
      }
      if (!resposta.ok && resposta.status !== 304) throw new Error("Avisos indisponíveis");
      Painel.rede.marcarSucesso();
      avisos.falhas = 0;
      avisos.proximaTentativa = 0;
      mostrarEstadoDaSincronia("");
      if (resposta.status === 304) return avisos.ultimoEstado;
      avisos.etag = resposta.headers.get("ETag");
      return resposta.json();
    }).then(function (dados) {
      // Uma gravação durante o GET exige uma leitura posterior à gravação.
      if (!dados || avisos.repetir) return null;
      avisos.atividadeAte = Number(dados.atividade_ate) || 0;
      avisos.ultimoEstado = dados;
      var mudou = dados.assinatura !== avisos.assinatura;
      if (mudou && avisos.assinatura && global.LSNavigation) global.LSNavigation.clear();
      /* Esta é a primeira resposta desde que o painel abriu? Então a
         comparação é contra a memória da conta, e a novidade é uma
         CHEGADA: aconteceu com a pessoa fora. */
      var chegada = !avisos.inicializado;
      if (chegada && dados.vistos) avisos.vistos = dados.vistos;
      var novo = houveAvisoNovo(dados);
      avisos.assinatura = dados.assinatura || null;
      if (novo) anunciarNoSino(chegada);
      if (mudou) desenharAvisos(dados);
      if (novo) {
        /* Aba de fundo não toca som na cara de ninguém -- mas também não
           perde o aviso: ele fica guardado para o primeiro toque de quem
           voltar para esta aba. */
        if (document.visibilityState === "visible") tocarSomDeAviso();
        else avisos.somPendenteAte = Date.now() + VALIDADE_DO_SOM_ADIADO;
      }
      /* Depois de desenhar: a memória guarda o que está NA TELA. */
      confirmarVistos();
      if (mudou) avisos.ouvintes.forEach(function (fn) { try { fn(dados); } catch (e) {} });
      document.dispatchEvent(new CustomEvent("ls:estado", { detail: dados }));
      return dados;
    }).catch(function () {
      mostrarEstadoDaSincronia("Não foi possível atualizar os números. Tentando novamente…");
      avisos.falhas += 1;
      avisos.proximaTentativa = Date.now() + Math.min(60000, 3000 * Math.pow(2, avisos.falhas));
      return null;
    }).finally(function () {
      global.clearTimeout(prazo);
      avisos.emVoo = null;
      if (avisos.repetir) {
        avisos.repetir = false;
        return buscarAvisos(true);
      }
    });
    return avisos.emVoo;
  }

  var canalSincronia = null;
  try {
    if (global.BroadcastChannel) {
      canalSincronia = new global.BroadcastChannel("ls-painel-atualizado");
      canalSincronia.onmessage = function () {
        if (global.LSNavigation) global.LSNavigation.clear();
        if (document.visibilityState === "visible") buscarAvisos(true);
      };
    }
  } catch (e) {}

  Painel.confirmarGravacao = function () {
    if (global.LSNavigation) global.LSNavigation.clear();
    // Gravar atualiza o estado; apenas novos avisos do sino geram áudio.
    buscarAvisos(true);
    if (canalSincronia) canalSincronia.postMessage({ mudou: true });
  };

  Painel.avisos = {
    /* Pede uma atualização imediata. Quem acabou de salvar chama isto. */
    agora: function () { return buscarAvisos(true); },
    estado: function () { return avisos.ultimoEstado; },

    /* Avisa quando o estado muda -- a lista de orçamentos usa para
       repintar o status de uma proposta que o cliente acabou de
       responder. */
    aoMudar: function (fn) {
      if (typeof fn === "function") avisos.ouvintes.push(fn);
    },

    /* Abrir o sino confirma somente as movimentações de colegas que já
       estavam visíveis. Pendências reais (vencido, estoque, pagamento...)
       permanecem até serem resolvidas. */
    lerAtividades: function () {
      if (avisos.lendo || !avisos.endereco) return Promise.resolve(null);
      avisos.lendo = true;
      var dados = new FormData();
      dados.set("acao", "ler_atividades");
      dados.set("atividade_ate", String(avisos.atividadeAte || 0));
      var campo = document.querySelector("[name=csrfmiddlewaretoken]");
      if (campo) dados.set("csrfmiddlewaretoken", campo.value);

      return fetch(avisos.endereco, {
        method: "POST",
        body: dados,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": campo ? campo.value : "",
        },
        credentials: "same-origin",
        cache: "no-store",
      }).then(function (resposta) {
        if (!resposta.ok) return null;
        /* A leitura já foi gravada; busca de novo para o número sumir no
           mesmo clique, sem deixar o usuário esperando o próximo pulso. */
        avisos.assinatura = null;
        avisos.etag = null;
        return buscarAvisos(true);
      }).catch(function () {
        return null;
      }).finally(function () {
        avisos.lendo = false;
      });
    },

    /* Chamado antes de trocar de tela: ver `Painel.prepararNavegacao`. */
    esquecerOuvintes: function () {
      avisos.ouvintes.length = 0;
    },

    parar: function () {
      avisos.parado = true;
      /* clearTimeout, e não clearInterval: o relógio virou uma corrente
         de setTimeout para poder mudar de passo entre uma batida e
         outra (ver `bater`). */
      if (avisos.relogio) global.clearTimeout(avisos.relogio);
      avisos.relogio = null;
      global.clearTimeout(avisos.relogioDeVistos);
      avisos.relogioDeVistos = null;
    },
  };

  function ligarAvisosAoVivo() {
    /* Uma vez por aba. Com a navegação suave esta função é alcançada a
       cada tela; sem a trava, cada troca somava mais um setInterval e o
       painel passava a perguntar o estado várias vezes por segundo. */
    if (avisos.ligado) return;

    var sino = document.querySelector('[data-selo="total"]');
    if (!sino) return;  /* Fora do painel (ou sem equipe): nada a fazer. */
    avisos.ligado = true;

    /* A rota vem do HTML (que a montou com {% url %}), e não escrita à
       mão aqui: quem manda no endereço é o urls.py. */
    avisos.endereco = document.body.getAttribute("data-avisos") || "";
    if (!avisos.endereco) return;

    ["pointerdown", "keydown"].forEach(function (evento) {
      document.addEventListener(evento, despertarSom, { passive: true });
    });

    global.addEventListener("online", function () { buscarAvisos(true); });

    /* A assinatura do que já está na tela: assim a primeira resposta não
       redesenha uma central que já está certa. */
    buscarAvisos();

    /* ==================================================================
       O RELÓGIO ACOMPANHA QUEM ESTÁ TRABALHANDO

       Perguntar de doze em doze segundos faz sentido enquanto alguém
       mexe no painel: é o tempo entre um colega salvar um orçamento e a
       bolinha aparecer aqui. Não faz sentido nenhum na quarta hora de
       uma aba esquecida aberta na bancada -- e era isso que acontecia,
       o dia inteiro, em toda aba de todo mundo.

       Agora o intervalo respira. Enquanto há toque, teclado ou rolagem,
       são doze segundos. Passados três minutos sem sinal de vida, o
       relógio recua para um minuto; qualquer toque o traz de volta na
       hora, junto com uma pergunta imediata -- então quem volta para o
       painel nunca olha para um número velho.

       Com a economia de dados ligada, o passo lento é o dobro: dois
       minutos. Ver `ECONOMIA_DE_DADOS` em settings.
       ================================================================== */
    /* Quanto tempo sem toque, tecla ou rolagem até o painel ser
       considerado esquecido. Três minutos deixavam uma aba parada
       perguntando depressa por muito tempo à toa; setenta e cinco
       segundos são mais que suficientes para a pausa de quem está
       lendo a tela, e qualquer toque traz o passo rápido de volta na
       hora, junto com uma pergunta imediata. */
    var OCIOSO_APOS = 75000;
    /* Passo do painel esquecido aberto na bancada: um minuto. Escrito em
       milissegundos, e não como múltiplo do passo ativo, porque são duas
       decisões diferentes -- acelerar quem está trabalhando não pode
       acelerar junto quem não está. Com a economia de dados, dois. */
    var PASSO_PARADO = 60000;
    var ultimoSinalDeVida = Date.now();

    function economiaLigada() {
      return document.body
        && document.body.getAttribute("data-ls-economia") === "1";
    }

    function passoDoRelogio() {
      var parado = Date.now() - ultimoSinalDeVida > OCIOSO_APOS;
      if (!parado) return avisos.intervalo;
      return economiaLigada() ? PASSO_PARADO * 2 : PASSO_PARADO;
    }

    function bater() {
      if (avisos.parado) return;
      avisos.relogio = global.setTimeout(function () {
        if (document.visibilityState === "visible") buscarAvisos();
        bater();
      }, passoDoRelogio());
    }
    bater();

    /* Qualquer sinal de que há gente ali. `passive` porque nenhum deles
       cancela nada -- e sem isso a rolagem no tablet engasga. */
    ["pointerdown", "keydown", "scroll", "focusin"].forEach(function (evento) {
      document.addEventListener(evento, function () {
        var estavaParado = Date.now() - ultimoSinalDeVida > OCIOSO_APOS;
        ultimoSinalDeVida = Date.now();
        /* Voltou depois de um tempo parado: o número na tela pode estar
           velho, e esperar o próximo pulso seria mostrar o passado a
           quem acabou de chegar. */
        if (estavaParado) buscarAvisos(true);
      }, { passive: true });
    });

    document.addEventListener("visibilitychange", function () {
      /* Voltar para a aba é o momento em que a pessoa QUER ver o estado
         de agora -- e é quando o intervalo tem mais chance de estar no
         meio de uma espera. */
      if (document.visibilityState === "visible") buscarAvisos();
    });
  }

  /* ====================================================================
     AVISO NO CELULAR (Web Push)
     --------------------------------------------------------------------
     As bolinhas resolvem para quem está com o painel aberto. Quem está na
     estrada montando um brinquedo não está -- e para essa pessoa o aviso
     só existe se o telefone tocar. É o caso do orçamento aprovado, que
     precisa virar agenda antes de a data ser vendida de novo.

     TRÊS COISAS PRECISAM SER VERDADE, e cada uma esconde o botão quando
     não é:

       1. a hospedagem tem a chave da aplicação configurada;
       2. o navegador tem Push -- todo Android moderno tem;
       3. no IPHONE, o painel precisa estar ADICIONADO À TELA DE INÍCIO.
          A Apple não entrega notificação para site aberto no Safari, e
          essa é a diferença que mais confunde: a pessoa acha que o
          aplicativo está com defeito. Por isso, no iPhone fora da tela de
          início, o texto explica o que fazer em vez de sumir calado.

     A permissão do navegador só pode ser pedida dentro de um clique. É
     por isso que existe um botão, e não um pedido automático ao abrir --
     que aliás o navegador recusaria, e alguns bloqueiam o site depois.
     ==================================================================== */
  function ehIphone() {
    return (
      /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.maxTouchPoints > 1 && /Macintosh/.test(navigator.userAgent))
    );
  }

  function instaladoNaTelaDeInicio() {
    return (
      global.navigator.standalone === true ||
      (global.matchMedia &&
        global.matchMedia("(display-mode: standalone)").matches)
    );
  }

  function bytesDaChave(base64) {
    /* A chave chega em base64url; `atob` só entende base64 comum. */
    var preenchido = (base64 + "===").slice(0, base64.length + (4 - (base64.length % 4)) % 4);
    var normal = preenchido.replace(/-/g, "+").replace(/_/g, "/");
    var cru = global.atob(normal);
    var saida = new Uint8Array(cru.length);
    for (var i = 0; i < cru.length; i += 1) saida[i] = cru.charCodeAt(i);
    return saida;
  }

  function chaveEmTexto(inscricao, nome) {
    var bruto = inscricao.getKey(nome);
    if (!bruto) return "";
    var bytes = new Uint8Array(bruto);
    var texto = "";
    for (var i = 0; i < bytes.length; i += 1) texto += String.fromCharCode(bytes[i]);
    return global.btoa(texto).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function ligarAvisoNoCelular() {
    var caixa = document.getElementById("avisosAparelho");
    var botao = document.getElementById("avisosAparelhoBotao");
    var rotulo = document.getElementById("avisosAparelhoRotulo");
    var nota = document.getElementById("avisosAparelhoNota");
    var rota = document.body.getAttribute("data-aparelho") || "";
    if (!caixa || !botao || !rota) return;

    function dizer(texto) {
      if (!nota) return;
      nota.textContent = texto || "";
      nota.hidden = !texto;
    }

    /* iPhone fora da tela de início: explicar, não esconder. A pessoa
       precisa saber que o caminho existe -- e qual é. */
    if (ehIphone() && !instaladoNaTelaDeInicio()) {
      caixa.hidden = false;
      botao.disabled = true;
      rotulo.textContent = "Avisos no iPhone";
      dizer(
        "No iPhone o aviso só chega com o painel adicionado à tela de " +
        "início: toque em Compartilhar e depois em “Adicionar à Tela de Início”."
      );
      return;
    }

    var temSuporte =
      "serviceWorker" in navigator &&
      "PushManager" in global &&
      "Notification" in global &&
      global.isSecureContext;
    if (!temSuporte) return;

    var chaveDoServidor = "";

    fetch(rota, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (dados) {
        /* Sem chave na hospedagem o botão não aparece: oferecer um aviso
           que nunca sairia é pior do que não oferecer. */
        if (!dados || !dados.configurado || !dados.chave) return;
        chaveDoServidor = dados.chave;
        caixa.hidden = false;
        return navigator.serviceWorker.ready;
      })
      .then(function (registro) {
        if (!registro) return null;
        return registro.pushManager.getSubscription();
      })
      .then(function (inscricao) {
        mostrarEstado(!!inscricao);
      })
      .catch(function () {});

    function mostrarEstado(inscrito) {
      rotulo.textContent = inscrito
        ? "Avisos ligados neste aparelho"
        : "Avisar no meu celular";
      botao.classList.toggle("ligado", inscrito);
      botao.disabled = false;
      dizer(
        inscrito
          ? "Toque de novo para desligar só neste aparelho."
          : ""
      );
    }

    function guardar(inscricao, acao) {
      var dados = new FormData();
      dados.set("endpoint", inscricao.endpoint);
      dados.set("aparelho", navigator.userAgent.slice(0, 120));
      if (acao) dados.set("acao", acao);
      if (!acao) {
        dados.set("p256dh", chaveEmTexto(inscricao, "p256dh"));
        dados.set("auth", chaveEmTexto(inscricao, "auth"));
      }
      var campo = document.querySelector("[name=csrfmiddlewaretoken]");
      if (campo) dados.set("csrfmiddlewaretoken", campo.value);
      return fetch(rota, {
        method: "POST",
        body: dados,
        credentials: "same-origin",
        headers: { "X-CSRFToken": campo ? campo.value : "" },
      });
    }

    botao.addEventListener("click", function () {
      botao.disabled = true;
      dizer("");

      navigator.serviceWorker.ready
        .then(function (registro) {
          return registro.pushManager.getSubscription().then(function (atual) {
            if (atual) {
              /* Já ligado: este clique desliga -- e desliga NESTE
                 aparelho só, não no celular da pessoa também. */
              return guardar(atual, "cancelar")
                .then(function () { return atual.unsubscribe(); })
                .then(function () { mostrarEstado(false); });
            }

            return global.Notification.requestPermission().then(function (resposta) {
              if (resposta !== "granted") {
                botao.disabled = false;
                dizer(
                  resposta === "denied"
                    ? "O navegador está bloqueando avisos deste site. Libere nas configurações do site e toque de novo."
                    : "Permissão não concedida."
                );
                return null;
              }
              return registro.pushManager
                .subscribe({
                  userVisibleOnly: true,
                  applicationServerKey: bytesDaChave(chaveDoServidor),
                })
                .then(function (nova) {
                  return guardar(nova).then(function () { mostrarEstado(true); });
                });
            });
          });
        })
        .catch(function () {
          botao.disabled = false;
          dizer("Não consegui ligar os avisos neste aparelho. Tente de novo.");
        });
    });
  }

  /* Um único botão por registro abre um painel flutuante. O painel usa
     position:fixed e, por isso, não aumenta a altura da linha nem fica
     recortado pelo scroll da tabela. Os nós originais (forms, CSRF e
     listeners) são apenas reorganizados: nenhuma ação é clonada. */
  Painel.organizarAcoesTabelas = function (raiz) {
    var escopo = raiz || document;

    /* Telas mais antigas já identificam a célula como `ls-actions`, mas
       ainda não possuem o agrupador novo. Normalizamos esse contrato aqui
       para que o ganho alcance a área interna inteira de forma gradual. */
    escopo.querySelectorAll(".ls-actions, .ls-commercial-actions").forEach(function (celula) {
      var grupoExistente = Array.prototype.find.call(celula.children, function (filho) {
        return filho.classList.contains("ls-row-actions");
      });
      if (grupoExistente) return;
      if (celula.querySelectorAll("a, button, form").length < 2) return;

      if (celula.children.length === 1 && celula.firstElementChild) {
        celula.firstElementChild.classList.add("ls-row-actions");
        return;
      }
      var agrupador = document.createElement("div");
      agrupador.className = "ls-row-actions";
      while (celula.firstChild) agrupador.appendChild(celula.firstChild);
      celula.appendChild(agrupador);
    });

    escopo.querySelectorAll(".ls-row-actions").forEach(function (grupo) {
      if (grupo.dataset.lsActionsReady === "1") return;

      var filhos = Array.prototype.filter.call(grupo.children, function (filho) {
        return !filho.classList.contains("ls-action-fab");
      });
      if (filhos.length < 2) {
        grupo.dataset.lsActionsReady = "1";
        return;
      }

      Painel._sequenciaAcoes = (Painel._sequenciaAcoes || 0) + 1;
      var instancia = String(Painel._sequenciaAcoes);
      var envoltorio = document.createElement("div");
      envoltorio.className = "ls-action-fab";

      var gatilho = document.createElement("button");
      gatilho.type = "button";
      gatilho.className = "ls-action-fab-trigger";
      gatilho.setAttribute("aria-label", "Abrir ações deste registro");
      gatilho.setAttribute("aria-expanded", "false");
      gatilho.setAttribute("aria-controls", "ls-action-menu-" + instancia);
      gatilho.innerHTML = '<i class="bi bi-three-dots-vertical" aria-hidden="true"></i>';

      var menu = document.createElement("div");
      menu.id = "ls-action-menu-" + instancia;
      menu.className = "ls-action-fab-menu";
      menu.setAttribute("role", "menu");
      menu.setAttribute("aria-hidden", "true");
      menu.hidden = true;
      menu.innerHTML = '<div class="ls-action-fab-head"><span>Ações</span></div>';

      function rotuloDaAcao(acao) {
        var rotulo = acao.getAttribute("data-label") || acao.getAttribute("title") || acao.getAttribute("aria-label");
        if (rotulo) return rotulo;
        if (acao.matches("[data-editar], [data-editar-os]")) return "Editar";
        if (acao.matches("[data-enviar], [data-enviar-os]")) return "Enviar";
        if (acao.matches("[data-excluir], [data-excluir-os], [data-excluir-material], [data-excluir-tipo], [data-excluir-fornecedor]")) return "Excluir";
        return (acao.textContent || "Ação").trim() || "Ação";
      }

      filhos.forEach(function (filho) {
        var acao = filho.matches("a,button") ? filho : filho.querySelector("a,button");
        if (acao) {
          var rotulo = rotuloDaAcao(acao);
          acao.classList.add("ls-action-fab-item");
          acao.setAttribute("role", "menuitem");
          if (!acao.getAttribute("aria-label")) acao.setAttribute("aria-label", rotulo);
          if (!acao.querySelector(".ls-action-label")) {
            var spanExistente = Array.prototype.find.call(acao.children, function (no) {
              return no.tagName === "SPAN" && !no.classList.contains("spinner-border");
            });
            if (spanExistente) {
              spanExistente.classList.add("ls-action-label");
            } else {
              var textosDiretos = Array.prototype.filter.call(acao.childNodes, function (no) {
                return no.nodeType === 3 && no.textContent.trim();
              });
              var texto = document.createElement("span");
              texto.className = "ls-action-label";
              texto.textContent = textosDiretos.length
                ? textosDiretos.map(function (no) { return no.textContent.trim(); }).join(" ")
                : rotulo;
              textosDiretos.forEach(function (no) { no.remove(); });
              acao.appendChild(texto);
            }
          }
        }
        menu.appendChild(filho);
      });

      function posicionar() {
        if (!envoltorio.classList.contains("is-open")) return;
        var ancora = gatilho.getBoundingClientRect();
        var caixa = menu.getBoundingClientRect();
        var margem = 10;
        var esquerda = Math.min(
          Math.max(margem, ancora.right - caixa.width),
          global.innerWidth - caixa.width - margem
        );
        var topo = ancora.bottom + 8;
        if (topo + caixa.height > global.innerHeight - margem) {
          topo = Math.max(margem, ancora.top - caixa.height - 8);
          menu.classList.add("abre-acima");
        } else {
          menu.classList.remove("abre-acima");
        }
        menu.style.left = Math.round(esquerda) + "px";
        menu.style.top = Math.round(topo) + "px";
      }

      function fechar(devolverFoco) {
        if (!envoltorio.classList.contains("is-open")) return;
        envoltorio.classList.remove("is-open");
        menu.classList.remove("is-open");
        gatilho.setAttribute("aria-expanded", "false");
        menu.setAttribute("aria-hidden", "true");
        menu.hidden = true;
        menu.style.removeProperty("left");
        menu.style.removeProperty("top");
        if (Painel._acoesAbertas === envoltorio) Painel._acoesAbertas = null;
        if (devolverFoco) gatilho.focus({ preventScroll: true });
      }

      function abrir() {
        if (Painel._acoesAbertas && Painel._acoesAbertas !== envoltorio) {
          Painel._acoesAbertas._lsFechar(false);
        }
        /* O menu vive diretamente no body. Assim nenhum overflow, transform
           ou contain da tabela consegue recortá-lo no PC, tablet ou celular. */
        menu.hidden = false;
        envoltorio.classList.add("is-open");
        menu.classList.add("is-open");
        gatilho.setAttribute("aria-expanded", "true");
        menu.setAttribute("aria-hidden", "false");
        Painel._acoesAbertas = envoltorio;
        global.requestAnimationFrame(posicionar);
      }

      envoltorio._lsFechar = fechar;
      envoltorio._lsPosicionar = posicionar;
      envoltorio._lsMenu = menu;
      gatilho.addEventListener("click", function () {
        if (envoltorio.classList.contains("is-open")) fechar(false);
        else abrir();
      });
      menu.addEventListener("click", function (evento) {
        if (evento.target.closest("a, button")) fechar(false);
      });
      menu.addEventListener("keydown", function (evento) {
        var itens = Array.prototype.slice.call(menu.querySelectorAll("a:not([disabled]),button:not([disabled])"));
        var atual = itens.indexOf(document.activeElement);
        if (evento.key === "Escape") {
          evento.preventDefault();
          fechar(true);
        } else if (evento.key === "ArrowDown" && itens.length) {
          evento.preventDefault();
          itens[(atual + 1 + itens.length) % itens.length].focus();
        } else if (evento.key === "ArrowUp" && itens.length) {
          evento.preventDefault();
          itens[(atual - 1 + itens.length) % itens.length].focus();
        }
      });

      envoltorio.appendChild(gatilho);
      grupo.appendChild(envoltorio);
      document.body.appendChild(menu);
      grupo.dataset.lsActionsReady = "1";
    });

    if (!Painel._acoesGlobaisLigadas) {
      document.addEventListener("pointerdown", function (evento) {
        var abertas = Painel._acoesAbertas;
        var clicouNoMenu = abertas && abertas._lsMenu && abertas._lsMenu.contains(evento.target);
        if (abertas && !abertas.contains(evento.target) && !clicouNoMenu) {
          Painel._acoesAbertas._lsFechar(false);
        }
      });
      document.addEventListener("keydown", function (evento) {
        if (evento.key === "Escape" && Painel._acoesAbertas) Painel._acoesAbertas._lsFechar(true);
      });
      global.addEventListener("resize", function () {
        if (Painel._acoesAbertas) Painel._acoesAbertas._lsPosicionar();
      }, { passive: true });
      document.addEventListener("scroll", function () {
        if (Painel._acoesAbertas) Painel._acoesAbertas._lsPosicionar();
      }, true);
      Painel._acoesGlobaisLigadas = true;
    }
  };

  global.Painel = Painel;

  /* O que roda a cada tela que chega -- inclusive as que chegam por
     navegação suave, sem recarregar a página. As três primeiras chamadas
     têm trava própria e só valem na primeira vez. */
  Painel.iniciar = function () {
    ligarAvisosAoVivo();
    ligarAvisoNoCelular();
    ligarMedidaDeTela();
    Painel.montarTela(document);
  };

  /* `readyState` em vez de esperar o evento: numa troca de tela o
     documento já está pronto e o DOMContentLoaded não acontece de novo.
     Assim o mesmo arquivo serve para a primeira abertura e para as
     seguintes, sem o painel depender de qual das duas foi. */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", Painel.iniciar);
  } else {
    Painel.iniciar();
  }

  /* Janelas criadas depois (ou trocadas por JavaScript) entram no mesmo
     contrato no momento em que aparecem. */
  document.addEventListener("show.bs.modal", function (evento) {
    Painel.fecharAcoesFlutuantes(false);
    normalizarJanela(evento.target);
    medirTela();
  });

  /* A altura só pode ser medida com a janela na tela: `scrollHeight` de
     um campo escondido é zero, e o campo abria espremido. */
  document.addEventListener("shown.bs.modal", function (evento) {
    Painel.acomodarTextos(evento.target);
  });

  document.addEventListener("focusin", function (evento) {
    var campo = evento.target;
    if (!campo.matches || !campo.matches("input, select, textarea")) return;
    /* Espera o teclado terminar de subir antes de medir. */
    setTimeout(function () { trazerCampoParaVista(campo); }, 320);
  });

  /* ====================================================================
     A PRÉVIA LEVA JUNTO DE ONDE VEIO

     As prévias de orçamento e de O.S. abrem em outra aba -- e o painel
     mora num subdomínio (`interno.`) diferente do site. Quem terminava
     de conferir o documento ficava sem caminho de volta: o botão do
     navegador não serve numa aba recém-aberta, e fechar não devolve a
     tela em que a pessoa estava.

     O endereço da tela atual entra no link no momento do toque, e não
     escrito no HTML: a lista tem filtro, página e busca na URL, e o que
     interessa é voltar para o que a pessoa estava vendo -- inclusive
     quando a tela chegou por navegação suave, em que o servidor nem
     sabe onde ela parou. O servidor confere o endereço antes de
     desenhar o botão (ver `destino_de_retorno`, em utils.py).
     ==================================================================== */
  ["click", "auxclick"].forEach(function (evento) {
    document.addEventListener(evento, function (toque) {
      var link = toque.target.closest ? toque.target.closest("a[href]") : null;
      if (!link) return;

      var destino;
      try {
        destino = new URL(link.getAttribute("href") || "", global.location.href);
      } catch (erro) {
        return;
      }
      if (destino.origin !== global.location.origin) return;
      if (!/\/previa\/$/.test(destino.pathname)) return;

      destino.searchParams.set("voltar", global.location.href);
      link.setAttribute("href", destino.href);
    }, true);
  });
})(window);
