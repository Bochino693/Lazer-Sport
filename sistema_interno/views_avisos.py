"""O estado dos avisos, servido para a tela se atualizar sozinha.

POR QUE ISSO EXISTE. As bolinhas do menu e a central de avisos eram
desenhadas uma vez, no HTML da página. Quem deixava Orçamentos aberto na
bancada só via um pedido novo depois de recarregar -- e como a sessão do
painel dura o dia inteiro, na prática só depois de sair e entrar de novo.
O aviso chegava tarde, que é o mesmo que não chegar.

Aqui o painel pergunta "mudou alguma coisa?" de tempos em tempos e o
servidor responde com os MESMOS números que o context processor usa para
desenhar o HTML. Uma fonte só (`avisos.coletar`), dois caminhos de
entrega: o primeiro desenho e a atualização.

CUSTO. É uma consulta de leitura repetida por cada aba aberta, então:

  * só responde a quem é da equipe;
  * reaproveita o cache curto que o context processor já mantém, de modo
    que perguntar de novo dentro da janela não toca o banco;
  * a tela pergunta só quando está VISÍVEL -- aba de fundo não custa
    nada, e é o padrão de quem deixa dez abas abertas.

O corpo carrega uma `assinatura`: um resumo do estado. Enquanto ela não
muda, a tela não redesenha nada.
"""

import hashlib
import json

from django.http import JsonResponse
from django.views.generic import View

from . import push
from .context_processors import _apurar_com_cache
from .models import InscricaoPush
from .permissoes import faz_parte_da_equipe


def assinatura_do_estado(dados):
    """Resumo curto do que está na tela, para comparar sem redesenhar."""
    cru = json.dumps(dados, sort_keys=True, default=str)
    return hashlib.sha1(cru.encode("utf-8")).hexdigest()[:16]


class EstadoAvisosView(View):
    """GET /avisos/estado/ -> contagens e avisos, em JSON."""

    def get(self, request):
        usuario = getattr(request, "user", None)
        if not getattr(usuario, "is_authenticated", False):
            # 401 e não 403: para a tela isso significa "a sessão caiu",
            # e o JavaScript para de perguntar em vez de insistir contra
            # uma tela de login.
            return JsonResponse({"erro": "sessao"}, status=401)
        if not faz_parte_da_equipe(usuario):
            return JsonResponse({"erro": "sem_acesso"}, status=403)

        apurado = _apurar_com_cache(usuario)

        contagens = {
            chave: apurado[chave]
            for chave in (
                "count_vendas",
                "count_pedidos",
                "count_manutencao",
                "count_producao",
                "count_orcamentos",
                "count_ordens_servico",
                "count_clientes_incompletos",
            )
        }
        corpo = {
            "contagens": contagens,
            "urgentes": apurado["avisos_urgentes"],
            "total": apurado["total_avisos"],
            "avisos": [
                {
                    "chave": aviso.chave,
                    "titulo": aviso.titulo,
                    "detalhe": aviso.detalhe,
                    "quantidade": aviso.quantidade,
                    "url": aviso.url,
                    "nivel": aviso.nivel,
                    "icone": aviso.icone,
                    "urgente": aviso.urgente,
                }
                for aviso in apurado["avisos"]
            ],
        }
        corpo["assinatura"] = assinatura_do_estado(corpo)

        resposta = JsonResponse(corpo)
        # Resposta de usuário, curta e pessoal: nenhum intermediário pode
        # guardá-la e servir o painel de um colega.
        resposta["Cache-Control"] = "no-store, private"
        return resposta


class InscricaoPushView(View):
    """O aparelho pede (ou desiste de) receber aviso.

    GET  -> a chave pública da aplicação, que o navegador precisa para se
            inscrever, e se a hospedagem tem isso configurado.
    POST -> guarda a inscrição que o navegador acabou de criar.
    POST com acao=cancelar -> apaga.

    O endereço da inscrição É a credencial: quem o tem manda notificação
    para aquele aparelho. Por isso a linha é sempre presa ao usuário
    autenticado -- e uma inscrição que reaparece em outra conta (aparelho
    emprestado, conta trocada no mesmo tablet) troca de dono em vez de
    duplicar, senão o dono antigo continuaria recebendo os avisos dele.
    """

    def get(self, request):
        if not self._da_equipe(request):
            return JsonResponse({"erro": "sem_acesso"}, status=403)

        return JsonResponse({
            "configurado": push.configurado(),
            "chave": push.chave_publica(),
            "inscritos": InscricaoPush.objects.filter(
                usuario=request.user
            ).count(),
        })

    def post(self, request):
        if not self._da_equipe(request):
            return JsonResponse({"erro": "sem_acesso"}, status=403)

        endpoint = (request.POST.get("endpoint") or "").strip()
        if not endpoint or len(endpoint) > 600:
            return JsonResponse({"erro": "endpoint"}, status=400)

        if (request.POST.get("acao") or "") == "cancelar":
            InscricaoPush.objects.filter(
                usuario=request.user, endpoint=endpoint
            ).delete()
            return JsonResponse({"status": "sucesso", "inscrito": False})

        p256dh = (request.POST.get("p256dh") or "").strip()
        auth = (request.POST.get("auth") or "").strip()
        if not p256dh or not auth:
            return JsonResponse({"erro": "chaves"}, status=400)

        InscricaoPush.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "usuario": request.user,
                "p256dh": p256dh[:200],
                "auth": auth[:100],
                "aparelho": (request.POST.get("aparelho") or "")[:120],
            },
        )
        return JsonResponse({"status": "sucesso", "inscrito": True})

    @staticmethod
    def _da_equipe(request):
        usuario = getattr(request, "user", None)
        return (
            getattr(usuario, "is_authenticated", False)
            and faz_parte_da_equipe(usuario)
        )
