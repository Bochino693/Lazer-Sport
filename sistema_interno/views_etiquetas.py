"""Etiquetas de transporte impressas pelo próprio painel.

O QUE ISTO SUBSTITUI. As caixas saíam com "FRÁGIL" escrito a caneta no
papelão, quando saíam com alguma coisa. Uma etiqueta escrita à mão não
diz de quem é a carga, não diz para onde vai, e some no meio da fita
quando a caixa é reembalada -- e brinquedo inflável, tobogã e cama
elástica viajam em carga fracionada, onde quem carrega nunca é quem
vendeu.

A etiqueta daqui responde as três perguntas que faltavam, na ordem em que
alguém as faz no galpão: o que fazer com esta caixa (os avisos de manuseio,
grandes o bastante para se ler de longe), de quem ela é (o cliente, com
endereço quando há), e de onde veio (a empresa, com telefone -- se algo se
perder, é para cá que ligam).

NENHUMA ETIQUETA É GRAVADA. Ela é papel: nasce da tela, vai para a
impressora e acabou. Guardar o histórico de cada etiqueta impressa seria
criar uma tabela que ninguém consulta para responder uma pergunta que
ninguém faz.
"""

from django.conf import settings
from django.shortcuts import render
from django.views.generic import View

from core.email_utils import cnpj_empresa, nome_empresa
from core.models import EnderecoEmpresa

from . import clientes as svc
from .models import Cliente
from .rotas import texto_endereco
from .views import InternoRequiredMixin


def identidade_da_empresa() -> dict:
    """Quem imprimiu, para quem achar a caixa saber a quem ligar.

    Sai das mesmas configurações que assinam a proposta e a Ordem de
    Serviço: um contato só para a casa inteira. Se o telefone mudar num
    lugar, muda na etiqueta junto.
    """
    endereco = EnderecoEmpresa.objects.order_by("id").first()
    return {
        "nome": nome_empresa(),
        "cnpj": cnpj_empresa(),
        "telefone": getattr(settings, "EMPRESA_TELEFONE", ""),
        "email": getattr(settings, "EMPRESA_EMAIL", ""),
        "instagram": getattr(settings, "EMPRESA_INSTAGRAM", ""),
        "endereco": texto_endereco(endereco),
    }


class EtiquetasInnerView(InternoRequiredMixin, View):
    """Monta e imprime etiquetas de frágil; nada é salvo."""

    template_name = "etiquetas_inner.html"

    #: Os avisos que fazem sentido para o que esta fábrica despacha.
    #
    # A lista é curta de propósito. Etiqueta com sete selos não é lida:
    # quem carrega a caixa olha um segundo e decide. Cada aviso aqui muda
    # alguma coisa no que a pessoa faz com o volume.
    AVISOS = (
        ("fragil", "Frágil", "bi-exclamation-triangle-fill", True),
        ("nao_empilhar", "Não empilhar", "bi-box-seam", False),
        ("este_lado", "Este lado para cima", "bi-arrow-up-circle-fill", False),
        ("seco", "Proteger de chuva", "bi-umbrella-fill", False),
        ("nao_rolar", "Não rolar", "bi-arrow-repeat", False),
        ("peso", "Volume pesado", "bi-arrows-vertical", False),
    )

    def get(self, request):
        clientes = (
            Cliente.objects
            .select_related("parceiro")
            .prefetch_related("enderecos")
            .order_by("nome_cliente", "id")
        )

        return render(request, self.template_name, {
            "empresa": identidade_da_empresa(),
            "avisos": [
                {"chave": chave, "rotulo": rotulo, "icone": icone, "padrao": padrao}
                for chave, rotulo, icone, padrao in self.AVISOS
            ],
            # O cliente sai da lista OU é digitado na hora: a etiqueta de
            # uma entrega avulsa não pode exigir cadastro antes.
            "opcoes_clientes": [svc.opcao_de_busca(c) for c in clientes],
        })
