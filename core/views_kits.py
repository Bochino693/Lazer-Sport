"""Os endereços antigos dos kits eletrônicos: /kits/ e /kits/<id>/ (LEIA-ME seções 105 e 107).

O kit era uma peça com vitrine própria (/kits/) e página própria
(/kits/<id da peça>/). O dono: "vc criou outra sub section e nem sei se outro
objeto, mas eles devem estar junto com os produtos". Agora o kit é um produto
(Brinquedos com `eh_kit`), nas mesmas grades das máquinas, e a categoria
"Kits eletrônicos" junta todos. Os endereços antigos (links, Google, o menu
de quem estava com a página aberta) continuam valendo, para sempre (301):

  * /kits/          -> a página da categoria "Kits eletrônicos" (sem ela, o
                       catálogo de brinquedos);
  * /kits/<número>/ -> a página do produto que a peça-kit virou (o número da
                       peça ficou em `Brinquedos.id_kit_antigo`); o número
                       de uma peça avulsa leva à peça, como antes.
"""

from django.http import Http404
from django.shortcuts import redirect
from django.views import View

from . import kits
from .models import Brinquedos, PecasReposicao


def produto_do_kit_antigo(numero):
    """O produto que a peça-kit `numero` virou, ou None."""
    return Brinquedos.objects.filter(eh_kit=True, id_kit_antigo=numero).order_by("id").only("id").first()


class KitsView(View):
    """/kits/: a vitrine que não existe mais leva à categoria dos kits."""

    def get(self, request):
        categoria = kits.categoria_dos_kits()
        if categoria is not None:
            return redirect("categoria_detalhe", pk=categoria.pk, permanent=True)
        return redirect("brinquedos", permanent=True)


class KitDetalheView(View):
    """/kits/<número>/: a página do kit agora é a do produto."""

    def get(self, request, pk):
        produto = produto_do_kit_antigo(pk)
        if produto is not None:
            return redirect("brinquedo_detalhe", id=produto.pk, permanent=True)
        # o endereço de kit com o número de uma peça avulsa leva à peça (como antes)
        if PecasReposicao.da_vitrine().filter(pk=pk).exists():
            return redirect("reposicao_detalhe", pk=pk, permanent=True)
        raise Http404("Kit não encontrado.")
