"""Quem da EQUIPE recebe qual aviso no celular, e com que texto.

DOIS PÚBLICOS, DOIS ARQUIVOS. Este cuida de quem trabalha aqui dentro; o
cliente é atendido por `notificacoes_cliente.py`. A separação não é
arrumação: o objetivo de cada aviso é diferente, e o texto vai atrás.

  * Para a EQUIPE, o aviso diz "isto precisa da sua ação" -- e chega por
    push no aparelho, porque o painel está instalado e a pessoa pode
    estar na estrada, longe da bancada.
  * Para o CLIENTE, o aviso diz "a decisão é sua, e o prazo está
    acabando" -- e chega por e-mail, porque ele não instala nada nem se
    inscreve em nada.

Um texto só para os dois vira ou uma cobrança para o cliente ou um
recado ameno para a equipe.


Separado de `push.py` de propósito: lá mora o transporte (cifrar,
assinar, entregar), aqui mora a REGRA -- quem precisa saber de quê. São
duas coisas que mudam por motivos diferentes, e misturá-las foi o que
espalhou as contagens de aviso por três arquivos antes.

A REGRA GERAL. Só recebe aviso quem poderia abrir a tela do assunto.
Notificar alguém sobre um orçamento que ela não tem permissão de ver
seria vazar o nome do cliente e o valor da proposta pela tela de bloqueio
do celular -- onde a notificação aparece mesmo sem desbloquear.

CUSTO. Respostas do cliente disparam o push imediatamente; novo pedido usa
uma thread curta para o SMTP não segurar o checkout. Em ambos os casos a
falha é isolada: um serviço de aviso fora do ar não pode desfazer a ação
principal. Se um dia houver fila externa, é este módulo que muda -- as
telas continuam chamando `avisar_*`.
"""

import hashlib
import hmac
import logging
import threading

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections
from django.utils.html import escape
from django.utils import timezone

from core.email_utils import remetente, responder_para, smtp_configurado

from . import push
from .models import InscricaoPush
from .permissoes import FINANCEIRO, GESTAO, PRODUCAO, VENDAS, tem_funcao

log = logging.getLogger(__name__)


def _marca(chave):
    """Identificador estável do aviso sem revelar uma chave do banco."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(chave).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]


def _url_interna(caminho):
    return (getattr(settings, "INTERNO_BASE_URL", "") or "").rstrip("/") + caminho


def _enviar_email_individual(usuario, *, assunto, titulo, introducao, linhas, url):
    if not usuario.email or not smtp_configurado():
        return False
    lista = "".join(f"<li>{escape(str(linha))}</li>" for linha in linhas)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#17213a">
      <div style="border-radius:16px 16px 0 0;background:#0b347a;color:white;padding:22px">
        <strong style="font-size:20px">{escape(titulo)}</strong>
      </div>
      <div style="border:1px solid #dce5f4;border-top:0;border-radius:0 0 16px 16px;padding:22px">
        <p>{escape(introducao)}</p><ul>{lista}</ul>
        <p><a href="{escape(url)}" style="display:inline-block;padding:12px 18px;border-radius:10px;background:#0b347a;color:white;text-decoration:none;font-weight:bold">Abrir painel interno</a></p>
        <small>Mensagem automática da Fábrica de brinquedos Lazer Sport.</small>
      </div>
    </div>"""
    texto = titulo + "\n\n" + introducao + "\n" + "\n".join(f"- {x}" for x in linhas) + f"\n\n{url}"
    mensagem = EmailMultiAlternatives(
        subject=assunto,
        body=texto,
        from_email=remetente(),
        to=[usuario.email],
        reply_to=responder_para(),
    )
    mensagem.attach_alternative(html, "text/html")
    return bool(mensagem.send(fail_silently=False))


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
    negociacao = orcamento.status == orcamento.Status.EM_NEGOCIACAO
    # O NÚMERO VAI NO TÍTULO; O NOME E O VALOR, NÃO.
    #
    # A notificação aparece na tela de bloqueio, sem desbloquear: quem
    # estiver perto do aparelho lê. Nome do cliente e valor da proposta
    # ficam do outro lado do login. O número não diz nada a quem está de
    # fora e é tudo para quem está dentro -- sem ele, três respostas na
    # mesma tarde viram três avisos idênticos, e quem está na estrada
    # abre o painel só para descobrir qual delas foi.
    if negociacao:
        titulo = f"Proposta #{orcamento.pk}: cliente pediu ajuste"
        urgente = True
    elif aprovado:
        titulo = f"Proposta #{orcamento.pk} aprovada"
        urgente = True
    else:
        titulo = f"Proposta #{orcamento.pk} recusada"
        urgente = False

    return _entregar(
        _quem_cuida_de_orcamento(orcamento),
        {
            "titulo": titulo,
            "corpo": (
                "Confirme a data com o cliente e gere a O.S."
                if aprovado else
                "Veja o que ele pediu e prepare a nova versão."
                if negociacao else
                "Vale registrar o motivo antes de arquivar."
            ),
            "url": "/orcamentos/",
            "marca": _marca(f"orcamento:{orcamento.pk}:{orcamento.status}"),
            # Aprovação vibra; recusa não. Uma vibração para cada coisa
            # que acontece no dia treina a pessoa a ignorar todas.
            "urgente": urgente,
        },
    )


def avisar_ciencia_ordem_servico(ordem):
    """Cliente confirmou o recebimento de uma O.S. concluída."""
    pessoas = {}
    for usuario in User.objects.filter(is_active=True):
        if (
            tem_funcao(usuario, PRODUCAO)
            or tem_funcao(usuario, FINANCEIRO)
            or tem_funcao(usuario, GESTAO)
        ):
            pessoas[usuario.pk] = usuario
    for usuario in (ordem.responsavel, ordem.tecnico):
        if usuario is not None and usuario.is_active:
            pessoas[usuario.pk] = usuario

    return _entregar(
        pessoas.values(),
        {
            "titulo": f"O.S. {ordem.numero_documento} confirmada pelo cliente",
            "corpo": "Serviço aceito. Falta fechar o pagamento.",
            "url": "/ordens-servico/",
            "marca": _marca(f"ordem-servico:{ordem.pk}:confirmada"),
            "urgente": False,
        },
    )


def enviar_pendencias_urgentes(usuario, avisos):
    """Resumo individual usado pelo observador; levanta erro para poder repetir."""
    linhas = [f"{aviso.titulo}: {aviso.quantidade} — {aviso.detalhe}" for aviso in avisos]
    if not linhas:
        return False
    return _enviar_email_individual(
        usuario,
        assunto="Pendências urgentes no painel Lazer & Sport",
        titulo="Há pendências que precisam de atenção",
        introducao="O observador identificou uma mudança nas pendências urgentes da sua área.",
        linhas=linhas,
        url=_url_interna("/"),
    )


def _avisar_novo_pedido_agora(pedido_id):
    from core.models import Pedido

    try:
        pedido = Pedido.objects.filter(pk=pedido_id).first()
        if not pedido:
            return False
        superusuarios = list(User.objects.filter(is_active=True, is_superuser=True))
        _entregar(
            superusuarios,
            {
                "titulo": "Novo pedido recebido",
                "corpo": "Abra o painel para conferir pagamento, itens e entrega.",
                "url": "/pedidos/inner/",
                "marca": _marca(f"pedido:{pedido.pk}:novo"),
                "urgente": True,
            },
        )
        total = pedido.total_final if pedido.total_final is not None else pedido.total_liquido
        linhas = ["Um novo pedido entrou na operação."]
        if total is not None:
            linhas.append(f"Valor informado: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        enviados = 0
        for usuario in superusuarios:
            try:
                enviados += int(_enviar_email_individual(
                    usuario,
                    assunto="Novo pedido recebido — Lazer & Sport",
                    titulo="Novo pedido recebido",
                    introducao="Confira os dados no painel interno antes de iniciar a separação.",
                    linhas=linhas,
                    url=_url_interna("/pedidos/inner/"),
                ))
            except Exception:
                log.exception("Falha ao enviar aviso de novo pedido ao usuário %s", usuario.pk)
        return enviados
    except Exception:
        log.exception("Falha ao notificar novo pedido.")
        return False
    finally:
        close_old_connections()


def avisar_novo_pedido_id(pedido_id, *, bloqueante=False):
    """Sempre sinaliza superusuários, sem segurar a criação do pedido no SMTP."""
    if bloqueante:
        return _avisar_novo_pedido_agora(pedido_id)
    thread = threading.Thread(
        target=_avisar_novo_pedido_agora,
        args=(pedido_id,),
        name="aviso-novo-pedido",
        daemon=True,
    )
    thread.start()
    return True
