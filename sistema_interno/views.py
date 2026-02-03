from django.shortcuts import render, redirect
from django.views.generic import View
from .models import (Material, EstoqueMaterial, TipoMaterial,
                     CentralPedidos, CentralVendas, Venda, EnderecoCliente

                     )

from django.contrib.auth import authenticate, login

class InternoRequiredMixin(View):
    def dispatch(self, request, *args, **kwargs):
        host = request.get_host()

        if not host.startswith('interno.'):
            return redirect('/')

        if not request.user.is_authenticated:
            return redirect('login_interno')

        if not (request.user.is_staff or hasattr(request.user, 'gerente')):
            return redirect('login_interno')

        return super().dispatch(request, *args, **kwargs)


class LoginInternoView(View):
    template_name = 'login_inner.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home_inner')  # ajuste
        return render(request, self.template_name)

    def post(self, request):
        login_input = request.POST.get('login')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=login_input,
            password=password
        )

        if not user:
            return render(request, self.template_name, {
                'error': 'Usuário ou senha inválidos.'
            })

        if not (user.is_staff or hasattr(user, 'gerente')):
            return render(request, self.template_name, {
                'error': 'Usuário sem permissão para acesso interno.'
            })

        login(request, user)
        return redirect('home_inner')


class HomeInnerView(InternoRequiredMixin, View):

    def get(self, request):
        material = Material.objects.all()
        estoque = EstoqueMaterial.objects.all()
        tipo_material = TipoMaterial.objects.all()

        ctx = {
            'materiais': material,

        }

        return render(request, 'home_inner.html', ctx)


class MaterialInnerView(InternoRequiredMixin, View):

    def get(self, request):
        material = Material.objects.all()

        ctx = {
            'material': material,
        }
        return render(request, 'material_inner.html', ctx)


class EstoqueInnerView(InternoRequiredMixin, View):
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
