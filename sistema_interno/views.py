from django.shortcuts import render
from django.views.generic import View
from .models import (Material, EstoqueMaterial, TipoMaterial,
                     CentralPedidos, CentralVendas, Venda, EnderecoCliente

                     )


class HomeInnerView(View):

    def get(self, request):
        material = Material.objects.all()
        estoque = EstoqueMaterial.objects.all()
        tipo_material = TipoMaterial.objects.all()

        ctx = {
            'materiais': material,

        }

        return render(request, 'home_inner.html', ctx)


class MaterialInnerView(View):

    def get(self, request):
        material = Material.objects.all()

        ctx = {
            'material': material,
        }
        return render(request, 'material_inner.html', ctx)


class EstoqueInnerView(View):
    def get(self, request):
        estoques = (
            EstoqueMaterial.objects
            .select_related('material', 'material__tipo_material')
            .all()
        )

        ctx = {
            'estoques': estoques,
        }
        return render(request, 'estoque_inner.html', ctx)


