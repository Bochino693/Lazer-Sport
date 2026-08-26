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

    /* Enquanto digita: tira letra e símbolo, deixa uma vírgula só. O
       arredondamento para duas casas fica para o blur -- formatar no meio
       da digitação empurra o cursor e faz a pessoa errar o número. */
    moeda: function (valor) {
      var limpo = String(valor || "").replace(/[^\d.,]/g, "");
      var virgula = limpo.lastIndexOf(",");
      if (virgula >= 0) {
        limpo = limpo.slice(0, virgula).replace(/,/g, "") + limpo.slice(virgula);
      }
      return limpo.slice(0, 18);
    }
  };

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
  Painel.valor = function (id, v) {
    var el = document.getElementById(id);
    if (!el) return;

    var bruto = v === null || v === undefined ? "" : String(v);
    var tipo = el.dataset ? el.dataset.mascara : "";

    if (!bruto) {
      el.value = "";
      return;
    }

    if (tipo === "moeda") el.value = moedaFinal(bruto) || bruto;
    else if (tipo) el.value = Painel.mascarar(tipo, bruto);
    else el.value = bruto;
  };

  Painel.aplicarMascaras = function (raiz) {
    raiz = raiz || document;

    raiz.querySelectorAll("[data-mascara]").forEach(function (campo) {
      if (campo.dataset.mascaraLigada === "1") {
        /* Já ligado, mas o valor pode ter sido trocado por JavaScript
           desde então: reformata e sai. */
        if (campo.value) campo.value = Painel.mascarar(campo.dataset.mascara, campo.value);
        return;
      }

      campo.dataset.mascaraLigada = "1";
      var tipo = campo.dataset.mascara;

      function formatarEntrada() {
        campo.value = Painel.mascarar(tipo, campo.value);
      }

      campo.addEventListener("input", formatarEntrada);

      if (tipo === "moeda") {
        /* Ao sair do campo o número ganha as duas casas: "80" vira
           "80,00" e "1234,5" vira "1.234,50". */
        campo.addEventListener("blur", function () {
          campo.value = moedaFinal(campo.value);
        });
      }

      formatarEntrada();
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

  global.Painel = Painel;
  document.addEventListener("DOMContentLoaded", function () {
    Painel.aplicarMascaras(document);
  });
})(window);
