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
    Painel.fecharAcoesFlutuantes(false);
    Painel.limparModais(true);
    Painel.limparPendurados();
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
  Painel.montarTela = function (raiz) {
    var alvo = raiz || document;
    Painel.aplicarMascaras(alvo);
    Painel.acomodarTextos(alvo);
    Painel.organizarAcoesTabelas(alvo);
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

    m.show();
  };

  Painel.fechar = function (id) {
    var elemento = document.getElementById(id);
    var m = Painel.modal(id);
    if (m) {
      m.hide();
      /* CSS interrompido, navegação suave ou WebView antigo podem impedir
       * o evento final do Bootstrap. O fallback fecha só a janela pedida e
       * devolve o scroll; normalmente não faz nada porque hidden já chegou. */
      global.setTimeout(function () {
        if (!elemento || !elemento.classList.contains("show")) {
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
      paiEl.addEventListener("hidden.bs.modal", mostrarFilho, { once: true });
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
  /* Os tipos que se digitam da direita para a esquerda. Um valor que já
   * existe (vindo do servidor, ou preenchido por JavaScript) é um NÚMERO,
   * não uma sequência de teclas: "80" ali significa oitenta reais, e
   * passá-lo pela máscara de digitação o transformaria em 0,80. Por isso
   * valor existente entra por `moedaFinal`, e só o que a pessoa digita
   * passa pela máscara. */
  var TIPOS_NUMERICOS = ["moeda", "medida", "percentual"];

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
        /* O cursor vai para o fim: em campo que se preenche da direita
           para a esquerda é onde a próxima tecla entra. */
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

  /* Somadas, dão pouco mais de quarenta segundos -- a faixa em que uma
     instância suspensa costuma voltar. */
  var ESPERAS_DO_PULSO = [600, 1400, 3000, 5000, 8000, 11000, 12000];

  function esperarRede(ms) {
    return new Promise(function (resolver) { global.setTimeout(resolver, ms); });
  }

  function pulsoDoServidor(tentativa) {
    var controlador = global.AbortController ? new AbortController() : null;
    var timer = controlador
      ? global.setTimeout(function () { controlador.abort(); }, 9000)
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
      /* A ESPERA PRECISA CABER NUMA PARTIDA A FRIO.

         Eram três tentativas somando cerca de dois segundos -- o
         suficiente para uma oscilação de rede, e muito pouco para o
         caso que motivou tudo isto: a instância suspensa leva de vinte a
         sessenta segundos para voltar. Desistindo aos dois segundos, o
         painel decidia que o servidor não vinha justamente enquanto ele
         estava subindo.

         As esperas crescem para não martelar um servidor que ainda está
         de pé sobre um joelho, e param em doze segundos para o total
         caber na paciência de quem está olhando a tela. */
      if (tentativa < ESPERAS_DO_PULSO.length) {
        return esperarRede(ESPERAS_DO_PULSO[tentativa]).then(function () {
          return pulsoDoServidor(tentativa + 1);
        });
      }
      throw erro;
    }).finally(function () {
      if (timer) global.clearTimeout(timer);
    });
  }

  function acordarServidor(forcar) {
    if (!forcar && Date.now() - redeUltimoSucesso < REDE_OCIOSA_MS) {
      return Promise.resolve(true);
    }
    if (redeAcordando) return redeAcordando;

    redeAcordando = pulsoDoServidor(0).finally(function () {
      redeAcordando = null;
    });
    return redeAcordando;
  }

  Painel.rede = {
    acordar: acordarServidor,

    /* POST único: o preflight GET pode repetir; a gravação nunca. */
    post: function (destino, opcoes) {
      /* NÃO RECUSAR A GRAVAÇÃO PORQUE O DESPERTAR FALHOU.

         Recusar era a escolha segura enquanto a espera era de dois
         segundos: nesse prazo, "não respondeu" quase sempre significava
         mesmo "está fora". Agora que a espera cobre uma partida a frio
         inteira, desistir depois dela e ainda barrar o envio troca uma
         espera por uma parede -- e a pessoa que esperou quarenta
         segundos recebe "tente de novo" sem nada ter sido tentado.

         Além disso, o despertar falhar não prova que o servidor está
         fora: pode ser só aquele endereço. O POST sai uma vez, como
         sempre saiu, e se o servidor realmente não estiver lá ele falha
         com o erro de verdade, que é o que a tela precisa mostrar. */
      return acordarServidor(false).catch(function () {
        return false;
      }).then(function () {
        return fetch(destino, opcoes).then(function (resposta) {
          if (resposta.ok) redeUltimoSucesso = Date.now();
          return resposta;
        });
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
          if (Painel.avisos) Painel.avisos.agora();
          return json;
        });
    });
  };

  /* Liga um formulario de modal ao envio por fetch.
   *
   * opcoes: { form, erro, action, antes, depois, rotuloCarregando }
   * - antes: devolve string com um erro de validacao para barrar o envio
   * - depois: recebe o JSON; por padrao recarrega a pagina
   */
  Painel.ligar = function (opcoes) {
    var form = document.getElementById(opcoes.form);
    if (!form) {
      return;
    }

    var botao = form.querySelector('[type="submit"]');
    var rotulo = botao ? botao.textContent : "";

    function travar(on) {
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
      Painel.erro(opcoes.erro, "");

      if (opcoes.antes) {
        var impedimento = opcoes.antes(form);
        if (impedimento) {
          Painel.erro(opcoes.erro, impedimento);
          return;
        }
      }

      travar(true);

      Painel.enviar(form, opcoes.action ? { action: opcoes.action } : null)
        .then(function (json) {
          if (opcoes.depois) {
            opcoes.depois(json);
            travar(false);
          } else {
            global.location.reload();
          }
        })
        .catch(function (err) {
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

    document.querySelectorAll(opcoes.gatilho || "[data-excluir]").forEach(function (gatilho) {
      gatilho.addEventListener("click", function () {
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
     saída não é um truque, são três caminhos que evitam a navegação:

     1. MESMO CLIENTE, NENHUMA NAVEGAÇÃO. Reenviar para quem já está
        aberto só traz a aba para a frente. Antes isso recarregava o
        WhatsApp inteiro para chegar exatamente onde já estava.

     2. APLICATIVO INSTALADO NUNCA RECARREGA. O programa do computador já
        está rodando: `whatsapp://send` faz ele trocar de conversa na
        hora, sem subir nada. O problema histórico era que ele falha em
        silêncio quando não está instalado -- então aqui a primeira vez
        SONDA: dispara o protocolo e observa se o navegador perdeu o
        foco. Perdeu, o programa atendeu; não perdeu em 1,2s, não existe,
        e a web entra no lugar. O resultado fica guardado naquela
        máquina, e a sondagem não se repete.

     3. CLIENTE DIFERENTE, SEM APLICATIVO. Aí a navegação é inevitável --
        mas só se a pessoa quiser a conversa aberta automaticamente. Quem
        preferir pode copiar a mensagem e trocar a conversa DENTRO do
        WhatsApp, que é instantâneo porque acontece sem sair da página.
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
  var CHAVE_CAMINHO = "ls:whatsapp:caminho";

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
    /* Sem referência viva (o painel recarregou), o nome da aba ainda a
       encontra: abrir "" no mesmo nome foca sem navegar. */
    try {
      var aba = global.open("", NOME_ABA_WHATSAPP);
      if (aba) { abaWhatsappWeb = aba; aba.focus(); return true; }
    } catch (e) {}
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

  /* UMA SONDAGEM POR VEZ, E ELA VALE PELO ÚLTIMO PEDIDO.

     A sondagem leva 1,2s para decidir. Sem esta trava, dois cliques
     nesse intervalo -- um duplo-clique, ou dois clientes em sequência --
     começavam duas sondagens e abriam duas navegações, que é exatamente
     o recarregamento que se quer evitar. Enquanto uma está em curso, os
     pedidos seguintes só atualizam o alvo; quem decide é a primeira. */
  var sondagemEmCurso = false;
  var alvoDaSondagem = null;

  /* Dispara o aplicativo e observa se o navegador perdeu o foco. Só é
     chamada uma vez por máquina: o resultado fica guardado. */
  function sondarAplicativo(endereco, aoDecidir) {
    var atendeu = false;
    function marcar() { atendeu = true; }

    global.addEventListener("blur", marcar, { once: true });
    document.addEventListener("visibilitychange", marcar, { once: true });

    try { global.location.href = endereco; } catch (e) {}

    global.setTimeout(function () {
      global.removeEventListener("blur", marcar);
      document.removeEventListener("visibilitychange", marcar);
      aoDecidir(atendeu || document.hidden || !document.hasFocus());
    }, 1200);
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

    app: function (telefone, mensagem) {
      var digitos = numeroComDdi(telefone);
      if (!digitos) return "";
      return "whatsapp://send?phone=" + digitos
        + "&text=" + encodeURIComponent(mensagem || "");
    },

    noCelular: noCelular,
    alvo: alvoWhatsapp,
    caminho: function () { return guardado(CHAVE_CAMINHO); },

    /* O atalho sem recarregar: a mensagem vai para a área de
       transferência e a aba do WhatsApp vem para a frente. Quem troca a
       conversa por dentro do WhatsApp não paga o carregamento, porque
       nada saiu da página. */
    copiar: function (mensagem) {
      var texto = String(mensagem || "");
      var entregue = Promise.resolve(false);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          entregue = navigator.clipboard.writeText(texto).then(function () {
            return true;
          }).catch(function () { return false; });
        }
      } catch (e) {}
      return entregue.then(function (ok) {
        focarAba();
        return ok;
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
      var caminho = guardado(CHAVE_CAMINHO);

      /* 2. O aplicativo troca de conversa sem subir nada. */
      if (caminho === "aplicativo") {
        try { global.location.href = this.app(telefone, mensagem); } catch (e) {}
        guardar(CHAVE_CONVERSA, digitos);
        return { ok: true, motivo: "aplicativo", web: web };
      }

      /* 1. Mesmo cliente: a conversa já está aberta ali. Navegar de novo
            recarregaria o WhatsApp inteiro para chegar onde já está. */
      var mesmaConversa = digitos && guardado(CHAVE_CONVERSA) === digitos;
      if (caminho === "web" && mesmaConversa && focarAba()) {
        return { ok: true, motivo: "mesma-conversa", web: web, semRecarregar: true };
      }

      /* Primeira vez nesta máquina: descobre se há aplicativo. A web
         entra em seguida se ninguém atender -- ainda dentro da janela de
         ativação do clique, então não é bloqueada como pop-up. */
      if (!caminho) {
        alvoDaSondagem = { web: web, digitos: digitos };
        if (sondagemEmCurso) {
          return { ok: true, motivo: "sondando", web: web };
        }
        sondagemEmCurso = true;
        sondarAplicativo(this.app(telefone, mensagem), function (temApp) {
          sondagemEmCurso = false;
          guardar(CHAVE_CAMINHO, temApp ? "aplicativo" : "web");
          var alvo = alvoDaSondagem || { web: web, digitos: digitos };
          alvoDaSondagem = null;
          guardar(CHAVE_CONVERSA, alvo.digitos);
          if (!temApp) navegarAba(alvo.web);
        });
        return { ok: true, motivo: "sondando", web: web };
      }

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
    intervalo: 30000,
    assinatura: null,
    relogio: null,
    parado: false,
    ligado: false,
    ouvintes: [],
    inicializado: false,
    quantidades: {},
  };

  /* Som curto gerado pelo próprio navegador: não baixa MP3, funciona
     offline e não cria mais uma requisição. Navegadores só liberam áudio
     depois do primeiro toque/clique; até lá a central continua visual. */
  var contextoDeAudio = null;

  function prepararSom() {
    if (contextoDeAudio) return contextoDeAudio;
    var Construtor = global.AudioContext || global.webkitAudioContext;
    if (!Construtor) return null;
    try {
      contextoDeAudio = new Construtor();
      if (contextoDeAudio.state === "suspended") contextoDeAudio.resume();
    } catch (e) {
      contextoDeAudio = null;
    }
    return contextoDeAudio;
  }

  function tocarSomDeAviso() {
    var audio = prepararSom();
    if (!audio || audio.state !== "running") return;
    var inicio = audio.currentTime;
    [0, 0.13].forEach(function (atraso, indice) {
      var oscilador = audio.createOscillator();
      var ganho = audio.createGain();
      oscilador.type = "sine";
      oscilador.frequency.value = indice ? 880 : 660;
      ganho.gain.setValueAtTime(0.0001, inicio + atraso);
      ganho.gain.exponentialRampToValueAtTime(0.09, inicio + atraso + 0.012);
      ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + atraso + 0.11);
      oscilador.connect(ganho);
      ganho.connect(audio.destination);
      oscilador.start(inicio + atraso);
      oscilador.stop(inicio + atraso + 0.12);
    });
  }

  function houveAvisoNovo(dados) {
    var atuais = {};
    var novo = false;
    (dados.avisos || []).forEach(function (item) {
      var quantidade = Number(item.quantidade) || 0;
      atuais[item.chave] = quantidade;
      if (avisos.inicializado && quantidade > (avisos.quantidades[item.chave] || 0)) {
        novo = true;
      }
    });
    avisos.quantidades = atuais;
    if (!avisos.inicializado) avisos.inicializado = true;
    return novo;
  }

  function pintarSelo(elemento, quantidade) {
    if (!elemento) return;
    var numero = Number(quantidade) || 0;
    elemento.textContent = numero;
    elemento.hidden = numero === 0;
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
    document.querySelectorAll('[data-selo="total"]').forEach(function (selo) {
      pintarSelo(selo, dados.total);
      selo.classList.toggle("urgente", (Number(dados.urgentes) || 0) > 0);
    });

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

  function buscarAvisos() {
    if (avisos.parado) return Promise.resolve(null);

    return fetch(avisos.endereco, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      cache: "no-store",
    })
      .then(function (resposta) {
        if (resposta.status === 401 || resposta.status === 403) {
          /* Sessão caída ou conta sem painel: parar é a resposta certa.
             Insistir só encheria o log do servidor. */
          avisos.parado = true;
          return null;
        }
        if (!resposta.ok) return null;
        return resposta.json();
      })
      .then(function (dados) {
        if (!dados) return null;
        if (dados.assinatura && dados.assinatura === avisos.assinatura) {
          /* Nada mudou: não se mexe no DOM. Redesenhar à toa faria a
             central piscar debaixo do dedo de quem está lendo. */
          return dados;
        }
        var avisoNovo = houveAvisoNovo(dados);
        avisos.assinatura = dados.assinatura || null;
        desenharAvisos(dados);
        if (avisoNovo && document.visibilityState === "visible") tocarSomDeAviso();
        avisos.ouvintes.forEach(function (fn) {
          try { fn(dados); } catch (e) {}
        });
        return dados;
      })
      .catch(function () {
        /* Rede oscilando não é motivo para alarme na tela: o próximo
           intervalo tenta de novo. */
        return null;
      });
  }

  Painel.avisos = {
    /* Pede uma atualização imediata. Quem acabou de salvar chama isto. */
    agora: buscarAvisos,

    /* Avisa quando o estado muda -- a lista de orçamentos usa para
       repintar o status de uma proposta que o cliente acabou de
       responder. */
    aoMudar: function (fn) {
      if (typeof fn === "function") avisos.ouvintes.push(fn);
    },

    /* Chamado antes de trocar de tela: ver `Painel.prepararNavegacao`. */
    esquecerOuvintes: function () {
      avisos.ouvintes.length = 0;
    },

    parar: function () {
      avisos.parado = true;
      if (avisos.relogio) global.clearInterval(avisos.relogio);
      avisos.relogio = null;
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
      document.addEventListener(evento, prepararSom, { once: true, passive: true });
    });

    /* A assinatura do que já está na tela: assim a primeira resposta não
       redesenha uma central que já está certa. */
    buscarAvisos();

    avisos.relogio = global.setInterval(function () {
      if (document.visibilityState === "visible") buscarAvisos();
    }, avisos.intervalo);

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
      menu.innerHTML = '<div class="ls-action-fab-head"><span>Ações</span><small>Escolha o que deseja fazer</small></div>';

      function rotuloDaAcao(acao) {
        var rotulo = acao.getAttribute("data-label") || acao.getAttribute("title") || acao.getAttribute("aria-label");
        if (rotulo) return rotulo;
        if (acao.matches("[data-editar], [data-editar-os]")) return "Editar";
        if (acao.matches("[data-enviar], [data-enviar-os]")) return "Enviar";
        if (acao.matches("[data-excluir], [data-excluir-os]")) return "Excluir";
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
})(window);
