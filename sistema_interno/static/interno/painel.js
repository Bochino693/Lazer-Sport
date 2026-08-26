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
    var m = Painel.modal(id);
    if (m) {
      m.hide();
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
      var numero = digitos(valor, 14);
      if (numero.length <= 11) {
        return numero
          .replace(/^(\d{3})(\d)/, "$1.$2")
          .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
          .replace(/\.(\d{3})(\d)/, ".$1-$2");
      }
      return numero
        .replace(/^(\d{2})(\d)/, "$1.$2")
        .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d)/, ".$1/$2")
        .replace(/(\d{4})(\d)/, "$1-$2");
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

  Painel.aplicarMascaras = function (raiz) {
    raiz = raiz || document;

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

  Painel.enviar = function (form, extras) {
    var dados = new FormData(form);

    Object.keys(extras || {}).forEach(function (chave) {
      dados.set(chave, extras[chave]);
    });

    // getAttribute, nao form.action: o proprio formulario tem um
    // <input name="action">, e o acesso por propriedade devolve esse
    // input em vez da URL -- o POST ia parar em /stock/[object HTMLInputElement].
    var destino = form.getAttribute("action") || global.location.pathname;

    return fetch(destino, {
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
          return json;
        });
    });
  };

  /* Liga um formulario de modal ao envio por fetch.
   *
   * opcoes: { form, erro, action, antes, depois }
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
      botao.textContent = on ? "Salvando..." : rotulo;
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

  function ligarMedidaDeTela() {
    medirTela();
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

  global.Painel = Painel;
  document.addEventListener("DOMContentLoaded", function () {
    Painel.aplicarMascaras(document);
    Painel.acomodarTextos(document);
    ligarMedidaDeTela();
    document.querySelectorAll(".modal").forEach(normalizarJanela);
  });

  /* Janelas criadas depois (ou trocadas por JavaScript) entram no mesmo
     contrato no momento em que aparecem. */
  document.addEventListener("show.bs.modal", function (evento) {
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
