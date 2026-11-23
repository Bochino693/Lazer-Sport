"""As telas do cartão de ponto do relógio: enviar o PDF, conferir, importar, cadastrar.

Só quem cuida do RH (a função Gestão; o superusuário tem todas) envia e
importa: as views barram pela função (`funcoes_necessarias`), também em
POST e em URL digitada à mão. O arquivo original sai só pela view
`rh_cartao_arquivo` (sem endereço público, com a trilha). Ver
`importacao_ponto.py` para as regras e LEIA-ME-V10, seção 125.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from sistema_interno.permissoes import GESTAO
from sistema_interno.utils import ErroDeFormulario

from . import arquivos, cartao_ponto, importacao_ponto, ponto, servicos
from .forms import CadastroPeloCartaoForm
from .models import CartaoPonto, Colaborador, ImportacaoPonto, RegistroRH, erro_da_jornada_semana
from .validadores import UFS, formatar_cpf
from .views import BaseRH, sem_cache

#: Arquivos por envio (cada um passa pela conferência e pela leitura).
NO_MAXIMO = 12


def _ids(texto):
    saida = []
    for parte in str(texto or "").split(","):
        parte = parte.strip()
        if parte.isdigit():
            saida.append(int(parte))
    return saida[:NO_MAXIMO]


def url_das_importacoes(importacoes):
    ids = ",".join(str(i.pk) for i in importacoes)
    return reverse("rh_cartoes") + (f"?ids={ids}" if ids else "")


class CartaoEnviarView(BaseRH):
    """Recebe um ou vários PDFs: confere, lê, guarda no privado e mostra a conferência."""

    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request):
        voltar = request.POST.get("voltar") or reverse("rh_ponto_equipe")
        enviados = request.FILES.getlist("arquivos") or request.FILES.getlist("arquivo")
        if not enviados:
            return self.falhou(request, "Escolha o PDF do cartão de ponto (o que o sistema do relógio exporta).",
                               titulo="Nenhum arquivo", campo="arquivos", voltar=voltar)
        if len(enviados) > NO_MAXIMO:
            return self.falhou(request, f"Envie até {NO_MAXIMO} arquivos por vez.", titulo="Arquivos demais",
                               campo="arquivos", voltar=voltar)
        recebidos, ja, problemas = [], [], []
        for enviado in enviados:
            nome = arquivos.nome_seguro(getattr(enviado, "name", ""))
            try:
                conferido = arquivos.conferir(enviado)
                importacao, nova = importacao_ponto.receber(conferido, request)
            except ValidationError as erro:
                problemas.append((nome, "; ".join(erro.messages), "Arquivo recusado"))
                continue
            except cartao_ponto.CartaoIlegivel as erro:
                problemas.append((nome, str(erro), erro.titulo))
                continue
            (recebidos if nova else ja).append(importacao)

        todos = recebidos + ja
        if not todos:
            nome, texto, titulo = problemas[0]
            return self.falhou(
                request, (f"{nome}: {texto}" if len(enviados) > 1 else texto), titulo=titulo, campo="arquivos",
                voltar=voltar, lista=[f"{n}: {t}" for n, t, _ in problemas[1:]] or None,
            )

        cartoes = list(CartaoPonto.objects.filter(importacao__in=todos).select_related("colaborador"))
        pessoas = len(cartoes)
        sem_ficha = sum(1 for c in cartoes if c.colaborador_id is None)
        linhas = [f"{n}: {t}" for n, t, _ in problemas]
        for imp in ja:
            quem = (imp.enviado_por.get_full_name() or imp.enviado_por.get_username()) if imp.enviado_por else "alguém"
            linhas.append(
                f"{imp.nome_original or 'arquivo'}: já recebido em {timezone.localtime(imp.enviado_em):%d/%m/%Y} "
                f"por {quem} — nada foi lido de novo."
            )
        alvo = request.POST.get("colaborador")
        if alvo and alvo.isdigit() and cartoes and not any(c.colaborador_id == int(alvo) for c in cartoes):
            linhas.insert(0, "O cartão enviado pela ficha é de outra pessoa (o CPF não é o desta ficha): "
                             "confira na conferência antes de importar.")
        texto = (
            _n(pessoas, "cartão lido", "cartões lidos") + " em " + _n(len(todos), "arquivo", "arquivos")
            + (f"; {sem_ficha} sem ficha (dá para cadastrar na hora)" if sem_ficha else "")
            + ". Confira e importe."
        )
        janela = None
        if linhas:
            janela = {
                "titulo": "Cartão de ponto lido" if recebidos else "Já recebido",
                "texto": texto, "nivel": "alerta" if problemas else "info", "icone": "arquivo", "lista": linhas,
            }
        return self.ok(request, texto, ir=url_das_importacoes(todos), janela=janela)


class CartoesView(BaseRH):
    """A conferência: cada pessoa do arquivo, o que preenche, o que diverge, e o importar."""

    aba = "ponto_equipe"
    funcoes_necessarias = (GESTAO,)

    def get(self, request):
        ids = _ids(request.GET.get("ids"))
        consulta = ImportacaoPonto.objects.select_related("enviado_por").order_by("-enviado_em", "-id")
        importacoes = list(consulta.filter(pk__in=ids)) if ids else list(consulta[:12])
        if ids and not importacoes:
            raise Http404("Arquivo não encontrado.")
        blocos = []
        for importacao in importacoes:
            cartoes = importacao_ponto.recasar_pendentes(importacao)
            itens = []
            for cartao in cartoes:
                itens.append(self._item(cartao))
            blocos.append({
                "imp": importacao,
                "itens": itens,
                "prontos": sum(1 for i in itens if i["pronto"]),
                "importados": sum(1 for i in itens if i["c"].importado),
                "pode_descartar": not any(i["c"].importado for i in itens),
            })
        return self.responder(
            request, "rh/cartoes.html", blocos=blocos, so_estes=bool(ids), ufs=UFS,
            hoje=timezone.localdate(),
        )

    @staticmethod
    def _item(cartao):
        dados = cartao.dados or {}
        empresa = dados.get("empresa") or {}
        func = dados.get("funcionario") or {}
        item = {
            "c": cartao,
            "resumo": importacao_ponto.resumo_do_cartao(cartao),
            "empresa_confere": empresa.get("confere", True),
            "empresa_cnpj": importacao_ponto.formatar_cnpj(empresa.get("cnpj")),
            "empresa_nome": empresa.get("nome") or "",
            "nome_cartao": importacao_ponto.nome_bonito(func.get("nome") or cartao.nome),
            "cpf_cartao": formatar_cpf(cartao.cpf) if cartao.cpf else "—",
            "semana": importacao_ponto.texto_da_semana(importacao_ponto.semana_do_cartao(dados)),
            "plano": [], "previa": None, "comparacao": None, "form": None, "pronto": False,
        }
        if cartao.colaborador_id and cartao.pendente:
            item["plano"] = importacao_ponto.plano_da_ficha(cartao.colaborador, cartao)
            item["previa"] = importacao_ponto.planejar(cartao.colaborador, cartao)
            item["pronto"] = item["empresa_confere"]
        elif cartao.colaborador_id and cartao.importado:
            item["comparacao"] = importacao_ponto.comparar(cartao)
        elif cartao.pendente:
            item["form"] = CadastroPeloCartaoForm(
                prefix=f"c{cartao.pk}", initial=_inicial_do_cadastro(cartao),
            )
        item["divergentes"] = [linha for linha in item["plano"] if linha["acao"] == "divergente"]
        item["preencher"] = [linha for linha in item["plano"] if linha["acao"] == "preencher"]
        item["ignorados"] = [linha for linha in item["plano"] if linha["acao"] == "ignorado"]
        return item


def _inicial_do_cadastro(cartao):
    func = (cartao.dados or {}).get("funcionario") or {}
    inicial = {"nome": importacao_ponto.nome_bonito(func.get("nome") or cartao.nome), "vinculo": "clt"}
    pis = importacao_ponto.pis_que_vale(func.get("pis"), func.get("cpf"))
    if pis:
        inicial["pis"] = pis
    if func.get("admissao"):
        try:
            inicial["data_admissao"] = date.fromisoformat(func["admissao"])
        except ValueError:
            pass
    return inicial


def _n(quantos, um, varios):
    return f"{quantos} {um if quantos == 1 else varios}"


def _janela_do_resultado(cartao, resultado):
    linhas = [_n(resultado["criadas"], "marcação do relógio lançada", "marcações do relógio lançadas") + " no ponto"]
    if resultado["ja_estavam"]:
        linhas.append(_n(resultado["ja_estavam"], "já estava no ponto", "já estavam no ponto") + " (não entra de novo)")
    if resultado["pedidos_de_ajuste"]:
        linhas.append(_n(resultado["pedidos_de_ajuste"], "hora virou pedido de ajuste", "horas viraram pedidos de ajuste")
                      + ": o dia tinha marcação do painel")
    if resultado["abonos"]:
        linhas.append(_n(resultado["abonos"], "folga ou feriado do relógio lançado", "folgas ou feriados do relógio lançados")
                      + " como abono")
    if resultado["preenchidos"]:
        linhas.append("Na ficha: " + ", ".join(resultado["preenchidos"]))
    if resultado["mantidos"]:
        linhas.append("Ficou como estava na ficha: " + ", ".join(resultado["mantidos"]))
    for pulado in resultado["pulados"][:3]:
        linhas.append(f"{date.fromisoformat(pulado['data']):%d/%m}: sem marcação ({pulado['motivo']})")
    linhas.append("O PDF foi para a pasta de documentos da ficha")
    espelho = reverse("rh_espelho", args=[cartao.colaborador_id]) + f"?de={cartao.inicio:%Y-%m-%d}&ate={cartao.fim:%Y-%m-%d}"
    return {
        "titulo": "Cartão importado",
        "texto": f"{cartao.colaborador.nome} · {cartao.periodo_texto}.",
        "nivel": "sucesso", "icone": "sucesso", "lista": linhas,
        "acao": {"rotulo": "Ver o acompanhamento", "url": espelho},
    }


class CartaoImportarView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        cartao = get_object_or_404(CartaoPonto.objects.select_related("colaborador", "importacao"), pk=pk)
        voltar = url_das_importacoes([cartao.importacao])
        escolhas = {
            chave[len("escolha_"):]: valor for chave, valor in request.POST.items() if chave.startswith("escolha_")
        }
        try:
            resultado = importacao_ponto.importar(
                cartao, request, escolhas=escolhas, forcar_cnpj=request.POST.get("forcar_cnpj") == "1",
            )
        except ErroDeFormulario as erro:
            return self.falhou(request, str(erro), titulo=erro.titulo, campo=erro.campo, acao=erro.acao,
                               voltar=voltar, status=erro.status or 400)
        cartao.refresh_from_db(fields=["situacao"])
        return self.ok(request, f"Cartão de {cartao.colaborador.primeiro_nome} importado.", voltar=voltar,
                       janela=_janela_do_resultado(cartao, resultado))


class CartaoImportarTodosView(BaseRH):
    """Importa de uma vez os cartões prontos do arquivo (com ficha, CNPJ conferido, escolhas padrão)."""

    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        importacao = get_object_or_404(ImportacaoPonto, pk=pk)
        voltar = url_das_importacoes([importacao])
        cartoes = list(importacao.cartoes.filter(situacao=CartaoPonto.Estado.PENDENTE, colaborador__isnull=False)
                       .select_related("colaborador", "importacao"))
        feitos, deixados = [], []
        for cartao in cartoes:
            if not ((cartao.dados or {}).get("empresa") or {}).get("confere", True):
                deixados.append(f"{cartao.colaborador.nome}: CNPJ de outra empresa (importe pelo cartão, conferindo)")
                continue
            try:
                resultado = importacao_ponto.importar(cartao, request)
            except ErroDeFormulario as erro:
                deixados.append(f"{cartao.colaborador.nome}: {erro}")
                continue
            feitos.append(f"{cartao.colaborador.nome}: " + _n(resultado["criadas"], "marcação", "marcações")
                          + (", " + _n(resultado["pedidos_de_ajuste"], "pedido de ajuste", "pedidos de ajuste")
                             if resultado["pedidos_de_ajuste"] else ""))
        if not feitos:
            return self.falhou(request, "Nenhum cartão pronto para importar neste arquivo.",
                               titulo="Nada importado", voltar=voltar, lista=deixados or None, status=409)
        return self.ok(request, _n(len(feitos), "cartão importado.", "cartões importados."), voltar=voltar, janela={
            "titulo": _n(len(feitos), "cartão importado", "cartões importados"),
            "texto": "As marcações do relógio entraram no ponto, os vazios da ficha foram preenchidos e cada PDF foi para a pasta da pessoa.",
            "nivel": "sucesso", "icone": "sucesso", "lista": feitos + deixados,
        })


class CartaoCadastrarView(BaseRH):
    """Cria a ficha com os dados do cartão + o que a equipe completou, e importa."""

    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        cartao = get_object_or_404(CartaoPonto.objects.select_related("importacao"), pk=pk)
        voltar = url_das_importacoes([cartao.importacao])
        if not cartao.pendente:
            return self.falhou(request, "Este cartão já foi importado.", titulo="Já importado", voltar=voltar, status=409)
        if cartao.colaborador_id:
            return self.falhou(request, f"O cartão já está com a ficha de {cartao.colaborador.nome}: é só importar.",
                               titulo="Já tem ficha", voltar=voltar, status=409)
        importacao_ponto.recasar_pendentes(cartao.importacao)
        cartao.refresh_from_db()
        if cartao.colaborador_id:
            return self.falhou(request, "Alguém acabou de cadastrar esta pessoa: a ficha já foi achada pelo CPF.",
                               titulo="Já tem ficha", voltar=voltar, status=409, acao={"rotulo": "Atualizar", "chave": "recarregar"})
        dados = cartao.dados or {}
        func = dados.get("funcionario") or {}
        matricula = (func.get("matricula") or "").strip()
        semana = importacao_ponto.semana_do_cartao(dados)
        # A jornada do relógio que não fecha com a regra da ficha (mais de 10 h
        # num dia, sem intervalo) não entra: a ficha nasce com a jornada simples
        # e a janela diz por quê.
        jornada_recusada = erro_da_jornada_semana(semana) if semana else ""
        novo = Colaborador(
            cpf=cartao.cpf, matricula=matricula[:20] if matricula.strip("0") else "",
            jornada_semana={} if jornada_recusada else semana, criado_por=request.user,
        )
        form = CadastroPeloCartaoForm(request.POST, instance=novo, prefix=f"c{cartao.pk}")
        if not form.is_valid():
            return self.falhou_form(request, form, titulo="Complete a ficha", voltar=voltar, prefixo=f"c{cartao.pk}-")
        try:
            with transaction.atomic():
                colaborador = form.save()
                servicos.ligar_na_producao(colaborador)
                servicos.registrar(request, RegistroRH.Acao.FICHA_CRIADA, colaborador=colaborador,
                                   descricao="Ficha cadastrada a partir do cartão de ponto do relógio")
                CartaoPonto.objects.filter(pk=cartao.pk).update(colaborador=colaborador, casado_por="cpf")
                cartao.colaborador = colaborador
                cartao.casado_por = "cpf"
                resultado = importacao_ponto.importar(
                    cartao, request, forcar_cnpj=request.POST.get("forcar_cnpj") == "1",
                )
        except ErroDeFormulario as erro:
            return self.falhou(request, str(erro), titulo=erro.titulo, campo=erro.campo, acao=erro.acao,
                               voltar=voltar, status=erro.status or 400)
        except IntegrityError:
            return self.falhou(request, "Já existe uma ficha com este CPF ou PIS.", titulo="Ficha repetida",
                               voltar=voltar, status=409)
        cartao.colaborador = colaborador
        janela = _janela_do_resultado(cartao, resultado)
        janela["titulo"] = "Ficha criada e cartão importado"
        janela["lista"].insert(0, "Ficha cadastrada com o nome, o CPF e a admissão do cartão" + (
            f"; a jornada do relógio não entrou ({jornada_recusada}) -- ajuste na ficha" if jornada_recusada
            else " e a jornada de cada dia"))
        janela["lista"].append("Falta o termo de exclusividade: envie na ficha")
        janela["acao"] = {"rotulo": "Abrir a ficha", "url": reverse("rh_ficha", args=[colaborador.pk])}
        return self.ok(request, f"Ficha de {colaborador.primeiro_nome} criada e cartão importado.", voltar=voltar,
                       janela=janela)


class ImportacaoDescartarView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        importacao = get_object_or_404(ImportacaoPonto, pk=pk)
        try:
            with transaction.atomic():
                importacao_ponto.descartar(importacao, request)
        except ErroDeFormulario as erro:
            return self.falhou(request, str(erro), titulo=erro.titulo, voltar=url_das_importacoes([importacao]),
                               status=erro.status or 400)
        return self.ok(request, "Arquivo descartado: nada dele entrou no ponto.", ir=reverse("rh_ponto_equipe"))


class ImportacaoArquivoView(BaseRH):
    """O PDF original (pode ter várias pessoas): só a Gestão, com a trilha."""

    funcoes_necessarias = (GESTAO,)

    def get(self, request, pk):
        importacao = get_object_or_404(ImportacaoPonto, pk=pk)
        try:
            with importacao.arquivo.open("rb") as arquivo:
                dados = arquivo.read()
        except (FileNotFoundError, OSError):
            raise Http404("Arquivo não encontrado no armazenamento.")
        cartoes = list(importacao.cartoes.values_list("colaborador_id", flat=True))
        servicos.registrar(
            request, RegistroRH.Acao.DOC_ABERTO,
            colaborador=Colaborador.objects.filter(pk=cartoes[0]).first() if len(cartoes) == 1 and cartoes[0] else None,
            descricao=f"Cartão de ponto original (arquivo #{importacao.pk})",
        )
        resposta = HttpResponse(dados, content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="cartao-de-ponto-{importacao.pk}.pdf"'
        resposta["X-Content-Type-Options"] = "nosniff"
        resposta["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
        resposta["Referrer-Policy"] = "no-referrer"
        return sem_cache(resposta)
