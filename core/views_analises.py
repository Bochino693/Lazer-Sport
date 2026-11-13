"""Os endereços JSON das análises e das fichas das telas de gestão.

    GET /analises/<tipo>/?periodo=mes[&id=7][&de=2026-01-01&ate=2026-01-31]
    GET /detalhes/<tipo>/<id>/
    GET /detalhes/<tipo>/<id>/atividade/?pagina=2
    GET /presenca/agora/[?contas=1]

Só no subdomínio interno, só para a equipe, e cada tipo com a MESMA
permissão da tela em que aparece (core/analises_tipos.py). Quem não abre a
tela de cupons recebe 403 aqui também -- o endereço JSON não é uma porta
dos fundos para os números de uma tela que a pessoa não vê.

/presenca/agora/ é o "quem está online" (core/presenca.py): sem parâmetro,
só a EQUIPE online, para qualquer pessoa da equipe (a pilha de avatares da
barra de cima); com `contas=1`, todas as contas -- e aí a permissão é a da
tela Usuários (só o superadministrador). Nome de cliente não sai para quem
não abre aquela tela.
"""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.views import View

from . import analises, detalhes, presenca
from .analises_tipos import tipo as tipo_por_codigo


log = logging.getLogger(__name__)

#: O que a tela diz quando algo inesperado falha (o erro inteiro vai para o log do
#: servidor): frase de gente, e não "O servidor respondeu 500".
FALHA_INESPERADA = "Não deu para montar estes números agora. O erro foi registrado; tente de novo em instantes."


def _erro(mensagem, status):
    resposta = JsonResponse({"erro": mensagem}, status=status)
    resposta["Cache-Control"] = "no-store"
    return resposta


class _JsonDaEquipe(View):
    http_method_names = ["get"]

    def autorizar_equipe(self, request):
        """None quando a conta é da equipe e está no painel; senão, a resposta de erro."""
        from sistema_interno.permissoes import faz_parte_da_equipe

        if not getattr(request, "is_interno", False):
            return _erro("Endereço do painel interno.", 404)
        if not request.user.is_authenticated:
            return _erro("Entre no painel para ver os números.", 401)
        if not faz_parte_da_equipe(request.user):
            return _erro("Conta sem acesso ao painel.", 403)
        return None

    def autorizar(self, request, codigo):
        from sistema_interno.permissoes import tem_funcao

        erro = self.autorizar_equipe(request)
        if erro:
            return None, erro
        tipo = tipo_por_codigo(codigo)
        if tipo is None:
            return None, _erro("Tipo desconhecido.", 404)
        if tipo.somente_super and not request.user.is_superuser:
            return None, _erro("Só o superadministrador vê estes números.", 403)
        if tipo.funcoes and not tem_funcao(request.user, *tipo.funcoes):
            return None, _erro("Sua função não abre esta tela.", 403)
        return tipo, None

    @staticmethod
    def responder(dados):
        resposta = JsonResponse(dados, json_dumps_params={"ensure_ascii": False})
        # o servidor já guarda as análises por dois minutos; o navegador não guarda nada
        resposta["Cache-Control"] = "private, no-store"
        return resposta


class AnalisesView(_JsonDaEquipe):
    def get(self, request, tipo):
        tipo, erro = self.autorizar(request, tipo)
        if erro:
            return erro
        objeto_id = None
        bruto = (request.GET.get("id") or "").strip()
        if bruto:
            if not bruto.isdigit() or not tipo.tem_objeto:
                return _erro("Objeto inválido.", 400)
            objeto_id = int(bruto)
            if not tipo.modelo.objects.filter(pk=objeto_id).exists():
                return _erro("Não encontrado.", 404)
        try:
            janela = analises.janela(
                request.GET.get("periodo") or analises.PERIODO_PADRAO,
                de=request.GET.get("de"),
                ate=request.GET.get("ate"),
            )
        except analises.PeriodoInvalido as erro_periodo:
            return _erro(str(erro_periodo), 400)
        try:
            dados = analises.calcular(tipo, janela, objeto_id=objeto_id)
            if objeto_id is not None:
                nome = (tipo.nomes({objeto_id}) if tipo.nomes else {}).get(objeto_id)
                if isinstance(nome, dict):
                    nome = nome.get("nome")
                dados = {**dados, "objeto": {"id": objeto_id, "nome": nome or f"#{objeto_id}"}}
        except Exception:  # noqa: BLE001 -- a última rede: nada de página de erro crua no painel
            log.exception("analises: falhou (tipo=%s objeto=%s periodo=%s)", tipo.codigo, objeto_id, janela.codigo)
            return _erro(FALHA_INESPERADA, 500)
        return self.responder(dados)


class DetalheView(_JsonDaEquipe):
    so_atividade = False

    def get(self, request, tipo, pk):
        tipo, erro = self.autorizar(request, tipo)
        if erro:
            return erro
        try:
            pagina = int(request.GET.get("pagina") or 1)
        except ValueError:
            pagina = 1
        try:
            ficha = detalhes.montar(tipo.codigo, pk, request.user, pagina=pagina, so_atividade=self.so_atividade)
        except detalhes.NaoEncontrado:
            return _erro("Não encontrado.", 404)
        except Exception:  # noqa: BLE001 -- a última rede da ficha
            log.exception("detalhes: falhou (tipo=%s id=%s pagina=%s)", tipo.codigo, pk, pagina)
            return _erro(FALHA_INESPERADA, 500)
        if not self.so_atividade:
            ficha["tem_graficos"] = tipo.tem_objeto
            ficha["tipo_rotulo"] = tipo.singular
        return self.responder(ficha)


class AtividadeView(DetalheView):
    so_atividade = True


class PresencaAgoraView(_JsonDaEquipe):
    """Quem está online agora. A tela pergunta de novo sozinha (a cada ~45 s)."""

    def get(self, request):
        contas = request.GET.get("contas") == "1"
        if contas:
            # as contas todas (clientes inclusive): a permissão da tela Usuários
            _tipo, erro = self.autorizar(request, "usuario")
        else:
            erro = self.autorizar_equipe(request)
        if erro:
            return erro
        try:
            dados = presenca.agora_mesmo(eu=request.user, contas=contas)
        except Exception:  # noqa: BLE001 -- a última rede: a faixa fica com o último retrato e tenta de novo
            log.exception("presenca: falhou ao montar quem está online (contas=%s)", contas)
            return _erro(FALHA_INESPERADA, 500)
        return self.responder(dados)
