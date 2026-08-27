"""Quem recebe qual aviso no celular, e com que texto.

Separado de `push.py` de propósito: lá mora o transporte (cifrar,
assinar, entregar), aqui mora a REGRA -- quem precisa saber de quê. São
duas coisas que mudam por motivos diferentes, e misturá-las foi o que
espalhou as contagens de aviso por três arquivos antes.

A REGRA GERAL. Só recebe aviso quem poderia abrir a tela do assunto.
Notificar alguém sobre um orçamento que ela não tem permissão de ver
seria vazar o nome do cliente e o valor da proposta pela tela de bloqueio
do celular -- onde a notificação aparece mesmo sem desbloquear.

CUSTO. O envio é feito na mesma requisição de quem agiu, e é por isso que
tudo aqui engole a própria falha: um serviço de push fora do ar não pode
derrubar o salvamento de um orçamento. Se um dia houver fila, é este
módulo que muda -- as telas continuam chamando `avisar_*`.
"""

import logging

from django.contrib.auth.models import User
from django.utils import timezone

from . import push
from .models import InscricaoPush
from .permissoes import GESTAO, VENDAS, tem_funcao

log = logging.getLogger(__name__)


def _entregar(usuarios, dados):
    """Manda para todos os aparelhos das pessoas indicadas."""
    if not push.configurado():
        return 0

    ids = [u.pk for u in usuarios if getattr(u, "pk", None)]
    if not ids:
        return 0

    enviados = 0
    mortas = []
    for inscricao in InscricaoPush.objects.filter(usuario_id__in=ids):
        try:
            if push.enviar(
                inscricao.endpoint, inscricao.p256dh, inscricao.auth, dados
            ):
                enviados += 1
                inscricao.ultimo_aviso = timezone.now()
                inscricao.save(update_fields=["ultimo_aviso"])
        except push.InscricaoMorta:
            # Aplicativo desinstalado, dados do site limpos, telefone
            # trocado. Insistir contra um endereço morto é gastar rede
            # todo dia para sempre.
            mortas.append(inscricao.pk)
        except Exception:
            log.exception("Falha inesperada ao notificar %s", inscricao.pk)

    if mortas:
        InscricaoPush.objects.filter(pk__in=mortas).delete()
    return enviados


def _quem_cuida_de_orcamento(orcamento):
    """Gestão sempre; vendas, quando a proposta é da carteira dela.

    O responsável entra mesmo que não esteja em nenhum dos dois grupos:
    quem montou a proposta é quem o cliente vai cobrar.
    """
    pessoas = {}

    for usuario in User.objects.filter(is_active=True):
        if tem_funcao(usuario, GESTAO) or tem_funcao(usuario, VENDAS):
            pessoas[usuario.pk] = usuario

    responsavel = getattr(orcamento, "responsavel", None)
    if responsavel is not None and responsavel.is_active:
        pessoas[responsavel.pk] = responsavel

    return list(pessoas.values())


def avisar_resposta_do_cliente(orcamento):
    """O cliente aprovou ou recusou pela página pública.

    É O AVISO MAIS IMPORTANTE DO PAINEL. Quem está na estrada montando um
    brinquedo não tem o painel aberto: sem o telefone tocar, um "aprovado"
    fica parado até alguém sentar na bancada -- e nesse meio-tempo a data
    pode ser vendida de novo.
    """
    aprovado = orcamento.status == orcamento.Status.APROVADO
    quem = orcamento.respondido_por or "O cliente"

    return _entregar(
        _quem_cuida_de_orcamento(orcamento),
        {
            "titulo": (
                f"Proposta nº {orcamento.pk} aprovada"
                if aprovado
                else f"Proposta nº {orcamento.pk} recusada"
            ),
            "corpo": f"{quem} respondeu · {orcamento.destinatario}",
            "url": "/orcamentos/?q=" + str(orcamento.pk),
            "marca": f"orcamento-{orcamento.pk}",
            # Aprovação vibra; recusa não. Uma vibração para cada coisa
            # que acontece no dia treina a pessoa a ignorar todas.
            "urgente": aprovado,
        },
    )
