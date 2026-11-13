"""Logística: as transportadoras que a equipe recomenda, estado por estado.

O PEDIDO. O frete saiu do site -- o cliente retira na fábrica ou contrata
a transportadora. "Crie objetos de frete, de todos os estados, confiáveis,
com o número e tudo para possível contato, e ponha na área interna a opção
de visualização, chamar no WhatsApp, se tiver Instagram, isso e aquilo."

A TELA RESPONDE UMA PERGUNTA SÓ: "quem leva para este estado?". Escolher a
UF (os 27 botões no alto) mostra as nacionais primeiro, depois as regionais
que entregam ali e, por último, as de mudança e carga especial. Cada cartão
tem os atalhos que o cliente pede na conversa: chamar no WhatsApp com a
cotação já escrita (origem São Paulo/SP, destino no estado escolhido),
ligar, e-mail com assunto, Instagram, site e "Copiar contato" para colar
na conversa com o cliente.

QUEM VÊ E QUEM MEXE. Vendas indica, Produção combina a coleta, Gestão
também vê -- e só Gestão cadastra, corrige e desativa: um número errado
passado ao cliente é responsabilidade da casa, e alguém responde por ela.
Desativar não apaga: a transportadora sai das recomendações e fica guardada
em "Desativadas", com a fonte e a data da conferência.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import View

from . import transportadoras as regras
from .models import Transportadora
from .permissoes import GESTAO, PRODUCAO, VENDAS, capacidades
from .utils import ErroDeFormulario, data, texto
from .views import InternoRequiredMixin, RespostaJSONMixin


def _endereco(valor: str, rotulo: str) -> str:
    """Site e fonte: aceita "www.x.com.br" e completa o https://."""
    valor = (valor or "").strip()
    if not valor:
        return ""
    if "://" not in valor:
        valor = "https://" + valor
    try:
        URLValidator(schemes=("http", "https"))(valor)
    except ValidationError:
        raise ErroDeFormulario(f"{rotulo}: o endereço não parece um link válido.")
    return valor


def texto_de_busca(transportadora) -> str:
    """O que a busca da tela compara: nome, sede, estados e observações."""
    partes = [
        transportadora.nome,
        transportadora.nome_fantasia,
        transportadora.cidade_sede,
        transportadora.uf_sede,
        transportadora.get_tipo_display(),
        transportadora.observacoes,
        "todo o brasil nacional" if transportadora.atende_todo_brasil else "",
        " ".join(
            f"{sigla} {regras.NOME_DA_UF[sigla]}"
            for sigla in regras.ler_ufs(transportadora.estados_atendidos)
        ),
    ]
    return regras.sem_acento(" ".join(p for p in partes if p))


def cartao(transportadora, uf: str) -> dict:
    """Tudo o que o cartão mostra, com os links já montados para a UF."""
    t = transportadora
    return {
        "obj": t,
        "whatsapp": t.link_whatsapp(uf),
        "telefone": t.link_telefone,
        "email": t.link_email(uf),
        "instagram": t.link_instagram,
        "site": t.site,
        "copiar": t.texto_para_copiar(),
        "busca": texto_de_busca(t),
        "ufs": [] if t.atende_todo_brasil else regras.ler_ufs(t.estados_atendidos),
        "fontes_extras": [linha for linha in t.fontes_extras.splitlines() if linha.strip()],
    }


def dados_para_edicao(transportadora) -> dict:
    """O que o formulário de Gestão precisa para abrir já preenchido."""
    t = transportadora
    return {
        "id": t.pk,
        "nome": t.nome,
        "nome_fantasia": t.nome_fantasia,
        "tipo": t.tipo,
        "atende_todo_brasil": t.atende_todo_brasil,
        "estados": regras.ler_ufs(t.estados_atendidos),
        "cidade_sede": t.cidade_sede,
        "uf_sede": t.uf_sede,
        "telefone": t.telefone_formatado,
        "whatsapp": t.whatsapp_formatado,
        "email": t.email,
        "site": t.site,
        "instagram": t.instagram,
        "observacoes": t.observacoes,
        "fonte_url": t.fonte_url,
        "fontes_extras": t.fontes_extras,
        "verificado_em": t.verificado_em.isoformat() if t.verificado_em else "",
        "ordem": t.ordem,
        "ativo": t.ativo,
    }


class TransportadorasInnerView(RespostaJSONMixin, InternoRequiredMixin, View):
    template_name = "transportadoras_inner.html"
    rota_padrao = "transportadoras_inner"

    #: Cobrado no dispatch: vale para o GET e para toda ação.
    funcoes_necessarias = (VENDAS, GESTAO, PRODUCAO)

    # ------------------------------------------------------------ leitura
    def get(self, request):
        acesso = capacidades(request.user)
        uf = regras.uf_valida(request.GET.get("uf"))
        busca = (request.GET.get("q") or "").strip()[:80]

        ativas = Transportadora.objects.ativas()
        contagem = dict.fromkeys(regras.SIGLAS, 0)
        for todo_brasil, lista in ativas.values_list("atende_todo_brasil", "estados_atendidos"):
            for sigla in (regras.SIGLAS if todo_brasil else regras.ler_ufs(lista)):
                contagem[sigla] += 1

        escolhidas = ativas.atendem(uf) if uf else ativas
        cartoes = [cartao(t, uf) for t in escolhidas]
        termos = regras.termos_de_busca(busca)
        if termos:
            cartoes = [c for c in cartoes if all(t in c["busca"] for t in termos)]

        secoes = []
        for tipo, rotulo in Transportadora.Tipo.choices:
            da_secao = [c for c in cartoes if c["obj"].tipo == tipo]
            secoes.append({
                "tipo": tipo,
                "rotulo": rotulo,
                "nota": self.NOTAS_DAS_SECOES[tipo],
                "cartoes": da_secao,
            })

        editar = acesso["transportadoras_editar"]
        desativadas = (
            [cartao(t, uf) for t in Transportadora.objects.filter(ativo=False)]
            if editar else []
        )

        return render(request, self.template_name, {
            "uf": uf,
            "uf_nome": regras.NOME_DA_UF.get(uf, ""),
            "busca": busca,
            "estados": [
                {"sigla": sigla, "nome": nome, "regiao": regiao, "total": contagem[sigla]}
                for sigla, nome, regiao in regras.UFS
            ],
            "regioes": regras.REGIOES,
            "secoes": secoes,
            "total": len(cartoes),
            "desativadas": desativadas,
            "pode_editar": editar,
            "mensagem_cotacao": regras.mensagem_cotacao(uf),
            "tipos": Transportadora.Tipo.choices,
            "ufs_sede": regras.UF_CHOICES,
            "ufs_por_regiao": [
                (regiao, [(s, n) for s, n, r in regras.UFS if r == regiao])
                for regiao in regras.REGIOES
            ],
            "hoje": timezone.localdate().isoformat(),
            "dados_edicao": (
                [dados_para_edicao(c["obj"]) for c in cartoes + desativadas]
                if editar else []
            ),
        })

    NOTAS_DAS_SECOES = {
        Transportadora.Tipo.NACIONAL: "Atendem todo o Brasil.",
        Transportadora.Tipo.REGIONAL: "Especialistas da região: costumam sair mais em conta.",
        Transportadora.Tipo.MUDANCAS: "Embalam, carregam e cuidam de peça grande ou frágil.",
    }

    # ------------------------------------------------------------ escrita
    def post(self, request, *args, **kwargs):
        if not capacidades(request.user)["transportadoras_editar"]:
            # Recusada antes de abrir a transação: não há o que desfazer.
            self._acao_sem_transacao = True
            return self.erro(
                request,
                "Só a Gestão cadastra, corrige ou desativa transportadoras.",
                status=403,
            )
        return super().post(request, *args, **kwargs)

    def _transportadora(self, request):
        ident = (request.POST.get("id") or "").strip()
        return get_object_or_404(Transportadora, pk=ident) if ident.isdigit() else None

    def acao_salvar(self, request):
        t = self._transportadora(request) or Transportadora()

        t.nome = texto(request, "nome", obrigatorio=True, rotulo="o nome", limite=120)
        t.nome_fantasia = texto(request, "nome_fantasia", rotulo="Nome curto", limite=80)

        tipo = (request.POST.get("tipo") or "").strip()
        if tipo not in Transportadora.Tipo.values:
            raise ErroDeFormulario("Escolha o tipo: nacional, regional ou mudanças.")
        t.tipo = tipo

        t.atende_todo_brasil = request.POST.get("atende_todo_brasil") in ("1", "on", "true")
        try:
            t.estados_atendidos = regras.gravar_ufs(request.POST.getlist("estados"))
        except ValidationError as exc:
            raise ErroDeFormulario(" ".join(exc.messages))
        if t.atende_todo_brasil:
            t.estados_atendidos = ""
        elif not t.estados_atendidos:
            raise ErroDeFormulario(
                "Marque os estados que ela atende, ou “Atende todo o Brasil”."
            )

        t.cidade_sede = texto(request, "cidade_sede", rotulo="Cidade-sede", limite=80)
        uf_sede = (request.POST.get("uf_sede") or "").strip()
        if uf_sede and not regras.uf_valida(uf_sede):
            raise ErroDeFormulario("UF da sede desconhecida.")
        t.uf_sede = regras.uf_valida(uf_sede)

        t.telefone = regras.normalizar_telefone(request.POST.get("telefone"))
        t.whatsapp = regras.normalizar_telefone(request.POST.get("whatsapp"))
        t.email = texto(request, "email", rotulo="E-mail", limite=254)
        if t.email:
            try:
                validate_email(t.email)
            except ValidationError:
                raise ErroDeFormulario("E-mail: o endereço não parece válido.")
        t.site = _endereco(request.POST.get("site"), "Site")
        t.instagram = regras.normalizar_instagram(request.POST.get("instagram"))
        t.observacoes = texto(request, "observacoes", rotulo="Observações", limite=2000)
        t.fonte_url = _endereco(request.POST.get("fonte_url"), "Fonte")
        t.fontes_extras = texto(request, "fontes_extras", rotulo="Outras fontes", limite=3000)

        # Contato sem fonte não entra: é a regra que mantém a lista confiável.
        if t.tem_contato and not t.fonte_url:
            raise ErroDeFormulario(
                "Informe a fonte: o link da página onde telefone, WhatsApp, "
                "e-mail ou Instagram foram conferidos. Contato sem fonte não "
                "entra na lista."
            )
        t.verificado_em = data(request.POST.get("verificado_em"), "Conferido em")
        if t.tem_contato and not t.verificado_em:
            t.verificado_em = timezone.localdate()

        ordem = (request.POST.get("ordem") or "").strip()
        t.ordem = int(ordem) if ordem.isdigit() and int(ordem) <= 999 else 100
        if not t.pk:
            t.ativo = True

        try:
            t.full_clean()
        except ValidationError as exc:
            raise ErroDeFormulario(" ".join(exc.messages))
        t.save()
        return self.sucesso(
            request, f"“{t.nome_exibicao}” salva.", transportadora=dados_para_edicao(t),
        )

    def acao_desativar(self, request):
        t = self._transportadora(request)
        if t is None:
            raise ErroDeFormulario("Transportadora não encontrada.")
        t.ativo = False
        t.save(update_fields=["ativo", "atualizado"])
        return self.sucesso(
            request,
            f"“{t.nome_exibicao}” saiu das recomendações. Ela fica guardada em "
            "Desativadas e pode voltar.",
        )

    def acao_reativar(self, request):
        t = self._transportadora(request)
        if t is None:
            raise ErroDeFormulario("Transportadora não encontrada.")
        t.ativo = True
        t.save(update_fields=["ativo", "atualizado"])
        return self.sucesso(request, f"“{t.nome_exibicao}” voltou para a lista.")
