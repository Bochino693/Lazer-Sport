from django.views.generic import View
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from decimal import Decimal

from .forms import UserForm, PerfilForm, ProjetoForm, ManutencaoForm, CupomForm
from django.views.generic.edit import FormView

from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Brinquedos, CategoriasBrinquedos, Projetos, Eventos, ClientePerfil, Combos, Cupom, Promocoes, \
    TagsBrinquedos, ImagensSite, BrinquedosProjeto, Estabelecimentos, Manutencao, ManutencaoImagem, EnderecoEntrega, \
    BrinquedoClick, ComboClick, PromocaoClick, CategoriaClick, PecasReposicao

import os
from django.http import FileResponse, Http404
from django.conf import settings


def media_serve(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.isfile(file_path):
        raise Http404("Arquivo não encontrado")

    return FileResponse(open(file_path, 'rb'), content_type='image/jpeg')


def erro_404(request, exception):
    return render(request, "404.html", status=404)


def erro_500(request):
    return render(request, "500.html", status=500)


class HomeView(View):

    def get(self, request):  # ---------------------------
        # 1. Captura do filtro
        # ---------------------------

        imagens_site = ImagensSite.objects.order_by('-id')[:5]

        filtro = request.GET.get("ordenar", "az")  # padrão = A-Z

        brinquedos = Brinquedos.objects.all()

        # ---------------------------
        # 2. Lógica de ordenação
        # ---------------------------
        if filtro == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")

        elif filtro == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")

        elif filtro == "melhor-avaliados":
            brinquedos = brinquedos.order_by("-avaliacao")

        elif filtro == "custo-beneficio":
            # avaliação / preço (menor preço e maior nota)
            brinquedos = brinquedos.annotate(
                score=ExpressionWrapper(
                    F("avaliacao") / (F("valor_brinquedo") + 0.01),
                    output_field=FloatField()
                )
            ).order_by("-score")

        # ---------------------------
        # 3. Paginação
        # ---------------------------
        paginator = Paginator(brinquedos, 9)  # 9 por página
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        categorias_brinquedos = CategoriasBrinquedos.objects.annotate(
            total_produtos=Count('brinquedos', distinct=True)
        )

        combos = Combos.objects.all()
        promocoes = Promocoes.objects.all()

        pecas_count = PecasReposicao.objects.count()
        pecas_reposicao = PecasReposicao.objects.count()

        pecas_preview = (
            PecasReposicao.objects
            .prefetch_related("imagem_peca_reposicao")
            .filter(imagem_peca_reposicao__isnull=False)
            .distinct()[:12]
        )

        eventos = Eventos.objects.all()
        projetos = Projetos.objects.all()

        for combo in combos:
            total_original = sum(
                (b.valor_brinquedo or Decimal('0')) for b in combo.brinquedos.all()
            )

            valor_combo = combo.valor_combo or Decimal('0')

            economia = total_original - valor_combo

            porcentagem = (economia / total_original * 100) if total_original > 0 else 0

            combo.total_original = total_original
            combo.economia = economia
            combo.porcentagem = porcentagem


        context = {
            "categorias_brinquedos": categorias_brinquedos,
            "page_obj": page_obj,
            "ordenar": filtro,
            "eventos": eventos,
            "pecas_reposicao": pecas_reposicao,
            "pecas_count" : pecas_count,
            "pecas_preview": pecas_preview,
            "projetos": projetos,
            "combos": combos,
            "promocoes": promocoes,
            "estabelecimentos": Estabelecimentos.objects.all(),
            "imagens_site": imagens_site,
        }
        return render(request, 'home.html', context)

from .models import PecasReposicao

class ReposicaoView(View):
    def get(self, request):



        ctx = {
            'pecas': PecasReposicao.objects.all(),
        }


        return render(request, 'reposicao.html', ctx)


class ReposicaoDetalheView(View):
    def get(self, request, pk):
        peca = get_object_or_404(PecasReposicao, pk=pk)

        return render(request, 'reposicao_info.html', {
            'peca': peca
        })

from django.shortcuts import render, redirect
from django.views import View


class ManutencaoView(View):
    template_name = 'manutencao.html'

    def get_usuario(self, request):
        if not request.user.is_authenticated:
            return None
        perfil, _ = ClientePerfil.objects.get_or_create(user=request.user)
        return perfil

    def get(self, request):
        usuario = self.get_usuario(request)
        tab_ativa = request.GET.get('tab', 'nova')

        if not usuario:
            return render(request, self.template_name, {
                'form': None,
                'manutencoes': [],
                'brinquedos': [],
                'tab_ativa': tab_ativa,
            })

        form = ManutencaoForm()
        manutencoes = Manutencao.objects.filter(usuario=usuario).order_by('-criado_em')
        brinquedos = Brinquedos.objects.all().order_by('nome_brinquedo')

        return render(request, self.template_name, {
            'form': form,
            'manutencoes': manutencoes,
            'brinquedos': brinquedos,
            'tab_ativa': tab_ativa,
        })

    def post(self, request):
        usuario = self.get_usuario(request)

        if not usuario:
            return redirect('login')

        form = ManutencaoForm(request.POST, request.FILES)

        if not form.is_valid():
            return self.render_form(request, form)

        imagens = request.FILES.getlist('imagens')

        # 🔒 Regras de negócio
        LIMITE_IMAGENS = 5
        TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5MB

        if len(imagens) > LIMITE_IMAGENS:
            messages.error(
                request,
                f"Você pode enviar no máximo {LIMITE_IMAGENS} imagens."
            )
            return self.render_form(request, form)

        for img in imagens:
            if not img.content_type.startswith('image/'):
                messages.error(request, "Apenas arquivos de imagem são permitidos.")
                return self.render_form(request, form)

            if img.size > TAMANHO_MAXIMO:
                messages.error(
                    request,
                    "Cada imagem deve ter no máximo 5MB."
                )
                return self.render_form(request, form)

        # ✅ Salvar manutenção
        manutencao = form.save(commit=False)
        manutencao.usuario = usuario
        manutencao.save()

        # 🖼️ Salvar imagens
        for img in imagens:
            ManutencaoImagem.objects.create(
                manutencao=manutencao,
                imagem=img
            )

        messages.success(request, "Manutenção solicitada com sucesso!")
        return redirect('manutencoes')

    # 🔁 Centraliza renderização do formulário
    def render_form(self, request, form):
        usuario = self.get_usuario(request)

        return render(request, self.template_name, {
            'form': form,
            'manutencoes': Manutencao.objects.filter(
                usuario=usuario
            ).order_by('-criado_em'),
            'brinquedos': Brinquedos.objects.all().order_by('nome_brinquedo'),
            'tab_ativa': 'nova',
        })


from django.views.decorators.http import require_POST
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages


@require_POST
def cancelar_manutencao(request):
    usuario = request.user.perfil

    manutencao = get_object_or_404(
        Manutencao,
        id=request.POST.get("manutencao_id"),
        usuario=usuario
    )

    if manutencao.status in ['P', 'A']:
        manutencao.status = 'X'
        manutencao.save()
        messages.success(request, "Manutenção cancelada com sucesso.")
    else:
        messages.error(request, "Esta manutenção não pode ser cancelada.")

    return redirect('/manutencoes?tab=lista')


class ClientePerfilView(LoginRequiredMixin, View):
    template_name = "profile.html"

    def get_perfil(self, user):
        """Garante que o usuário tenha um perfil"""
        perfil, created = ClientePerfil.objects.get_or_create(user=user)
        return perfil

    def get(self, request):
        perfil = self.get_perfil(request.user)
        user_form = UserForm(instance=request.user)
        perfil_form = PerfilForm(instance=perfil)
        return render(request, self.template_name, {
            'user_form': user_form,
            'perfil_form': perfil_form
        })

    def post(self, request):
        perfil = self.get_perfil(request.user)
        user_form = UserForm(request.POST, instance=request.user)
        perfil_form = PerfilForm(request.POST, instance=perfil)

        if user_form.is_valid() and perfil_form.is_valid():
            user_form.save()
            perfil_form.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect('perfil')

        messages.error(request, "Por favor, corrija os erros abaixo.")
        return render(request, self.template_name, {
            'user_form': user_form,
            'perfil_form': perfil_form
        })


class BrinquedoInfoView(View):

    def get(self, request, id):
        brinquedo = get_object_or_404(Brinquedos, id=id)

        obj, created = BrinquedoClick.objects.get_or_create(
            brinquedo_clicado=brinquedo,
            defaults={'quantidade_click': 1}
        )

        if not created:
            BrinquedoClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        return render(request, "brinquedo_info.html", {"brinquedo": brinquedo})


class CategoriasInfoView(View):

    def get(self, request, pk):

        categoria = get_object_or_404(CategoriasBrinquedos, id=pk)

        # REGISTRA CLICK
        obj, created = CategoriaClick.objects.get_or_create(
            categoria=categoria,
            defaults={
                'nome_categoria': categoria.nome_categoria,
                'quantidade_click': 1
            }
        )

        if not created:
            CategoriaClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        brinquedos = categoria.brinquedos.all()

        ordenar = request.GET.get("ordenar", "az")

        if ordenar == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")
        elif ordenar == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")
        elif ordenar == "melhor-avaliados":
            brinquedos = brinquedos.order_by("-avaliacao")
        elif ordenar == "custo-beneficio":
            brinquedos = brinquedos.order_by("-avaliacao", "valor_brinquedo")

        paginator = Paginator(brinquedos, 12)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        ctx = {
            "categoria": categoria,
            "page_obj": page_obj,
            "ordenar": ordenar,
        }

        return render(request, "categorias_info.html", ctx)


from django.core.paginator import Paginator
from django.db.models import F, FloatField, ExpressionWrapper
from django.db.models import F, FloatField, ExpressionWrapper, DecimalField
from django.db.models.functions import Cast, TruncDate

from django.views.generic import ListView
from .models import Estabelecimentos


class EstabelecimentosListView(ListView):
    model = Estabelecimentos
    template_name = "estabelecimentos_info.html"
    context_object_name = "estabelecimentos"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # brinquedos para o carrossel (limite para não pesar)
        context["brinquedos_carrossel"] = (
            Brinquedos.objects
            .exclude(imagem_brinquedo="")
            [:8]
        )

        return context


class BrinquedosView(View):
    def get(self, request):
        ordenar = request.GET.get('ordenar', 'az')
        # Iniciamos o queryset
        brinquedos_list = Brinquedos.objects.all()

        # ORDENAÇÃO
        if ordenar == 'az':
            brinquedos_list = brinquedos_list.order_by('nome_brinquedo')
        elif ordenar == 'za':
            brinquedos_list = brinquedos_list.order_by('-nome_brinquedo')
        elif ordenar == 'melhor-avaliados':
            brinquedos_list = brinquedos_list.order_by('-avaliacao')
        elif ordenar == 'custo-beneficio':
            # Garantimos que o valor seja tratado como Float para o cálculo
            # E adicionamos um valor mínimo para evitar divisão por zero absoluta
            brinquedos_list = brinquedos_list.annotate(
                score=ExpressionWrapper(
                    Cast(F('avaliacao'), FloatField()) / (Cast(F('valor_brinquedo'), FloatField()) + 0.1),
                    output_field=FloatField()
                )
            ).order_by('-score')

        # PAGINAÇÃO
        paginator = Paginator(brinquedos_list, 12)
        page_number = request.GET.get('page')

        try:
            page_obj = paginator.get_page(page_number)
        except Exception:
            # Caso o número da página seja inválido, volta para a 1
            page_obj = paginator.get_page(1)

        context = {
            'brinquedos': page_obj,
            'page_obj': page_obj,
            'ordenar': ordenar,
        }

        return render(request, 'brinquedos.html', context)


class ComboInfoView(View):

    def get(self, request, pk):
        combo = get_object_or_404(Combos, id=pk)

        # REGISTRA O CLICK
        obj, created = ComboClick.objects.get_or_create(
            combo_clicado=combo,
            defaults={
                'descricao_combo': combo.descricao,
                'valor_combo': combo.valor_combo,
                'quantidade_click': 1
            }
        )

        if not created:
            ComboClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        # ===== CÁLCULOS =====
        total_original = sum(
            Decimal(b.valor_brinquedo) for b in combo.brinquedos.all()
        )

        valor_combo = Decimal(combo.valor_combo)
        economia = total_original - valor_combo
        porcentagem = (economia / total_original * Decimal(100)) if total_original else Decimal(0)

        combo.total_original = total_original
        combo.economia = economia
        combo.porcentagem = porcentagem

        return render(request, 'combo_info.html', {'combo': combo})


class PromocaoInfoView(View):

    def get(self, request, pk):
        promocao = get_object_or_404(Promocoes, pk=pk)

        obj, created = PromocaoClick.objects.get_or_create(
            promocao=promocao,
            defaults={
                'descricao_promocao': promocao.descricao,
                'preco_promocao': promocao.preco_promocao,
                'quantidade_click': 1
            }
        )

        if not created:
            PromocaoClick.objects.filter(id=obj.id).update(
                quantidade_click=F('quantidade_click') + 1
            )

        return render(request, 'promocao_info.html', {
            'promocao': promocao
        })


class EstabelecimentoInfoView(View):
    def get(self, request, pk):
        estabelecimento = get_object_or_404(Estabelecimentos, pk=pk)

        order = request.GET.get("order", "")

        brinquedos = estabelecimento.brinquedos.all()

        if order == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")
        elif order == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")
        elif order == "avaliacao":
            brinquedos = brinquedos.order_by("-avaliacao")
        elif order == "custo":
            brinquedos = brinquedos.order_by("valor_brinquedo")

        return render(request, "estabelecimento_info.html", {
            "estabelecimento": estabelecimento,
            "brinquedos": brinquedos,
            "order": order
        })


class SobreView(View):

    def get(self, request):
        context = {
            'brinquedos': Brinquedos.object.all()
        }
        return render(request, 'home_inner.html', context)


class LoginUsuarioView(View):
    def get(self, request):
        return render(request, "login.html")

    def post(self, request):
        login_input = request.POST.get("username")  # pode ser username ou email
        password = request.POST.get("password")

        # Se for email, busca o username
        if "@" in login_input:
            try:
                user_obj = User.objects.get(email=login_input)
                username = user_obj.username
            except User.DoesNotExist:
                username = None
        else:
            username = login_input

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Usuário/E-mail ou senha incorretos.")
            return render(request, "login.html")

        login(request, user)
        return render(request, "login_sucesso.html", {"user": user})


class EventosView(View):

    def get(self, request):
        context = {
            'eventos': Eventos.objects.all(),
        }
        return render(request, "eventos.html", context)


class ProjetosView(View):
    def get(self, request):
        context = {
            'projetos': Projetos.objects.all(),
        }
        return render(request, 'projetos.html', context)


from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Combos

from django.core.cache import cache
import time


class AdminLoginView(View):
    template_name = 'admin_login.html'

    MAX_ATTEMPTS = 3
    BLOCK_TIME = 600  # 10 minutos (em segundos)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff and request.user.is_superuser:
            return redirect('/adm/banners/')

        ip = self.get_client_ip(request)
        cache_key = f'admin_login:{ip}'
        data = cache.get(cache_key)

        # ⛔ IP bloqueado
        if data and data.get('blocked_until', 0) > time.time():
            return redirect('acesso_negado')

        return render(request, self.template_name)

    def post(self, request):
        ip = self.get_client_ip(request)
        cache_key = f'admin_login:{ip}'

        data = cache.get(cache_key, {
            'attempts': 0,
            'blocked_until': 0
        })

        # ⛔ Ainda bloqueado
        if data['blocked_until'] > time.time():
            return redirect('acesso_negado')

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        # ❌ Login inválido
        if not user or not (user.is_staff and user.is_superuser):
            data['attempts'] += 1

            # 🔒 Estourou limite
            if data['attempts'] >= self.MAX_ATTEMPTS:
                data['blocked_until'] = time.time() + self.BLOCK_TIME
                cache.set(cache_key, data, timeout=self.BLOCK_TIME)
                return redirect('acesso_negado')

            cache.set(cache_key, data, timeout=self.BLOCK_TIME)

            return render(request, self.template_name, {
                'error': 'Usuário ou senha inválidos.'
            })

        # ✅ Login OK → limpa tudo
        cache.delete(cache_key)
        login(request, user)

        return redirect('/adm/banners/')


class AcessoNegadoView(View):
    def get(self, request):
        return render(request, 'acesso_negado.html', {
            'bloqueio': True
        })


class AdminOnlyMixin(View):
    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('acesso_negado')

        if not (request.user.is_superuser and request.user.is_staff):
            return redirect('acesso_negado')

        return super().dispatch(request, *args, **kwargs)


class ComboListView(AdminOnlyMixin, ListView):
    model = Combos
    template_name = 'combos_adm.html'
    context_object_name = 'combos'

    def get_queryset(self):
        return Combos.objects.prefetch_related('brinquedos')


class ComboCreateView(AdminOnlyMixin, CreateView):
    model = Combos
    fields = ['descricao', 'imagem_combo', 'brinquedos', 'valor_combo']
    template_name = 'combo_form.html'
    success_url = reverse_lazy('combos_admin')


class ComboUpdateView(UpdateView):
    model = Combos
    fields = ['descricao', 'imagem_combo', 'brinquedos', 'valor_combo']
    template_name = 'combo_form.html'
    success_url = reverse_lazy('combos_admin')


class ComboDeleteView(AdminOnlyMixin, DeleteView):
    model = Combos
    template_name = 'combo_confirm_delete.html'
    success_url = reverse_lazy('combos_admin')


from django.contrib.auth import logout


class LogoutUsuarioView(View):

    def get(self, request):
        # Desloga primeiro
        logout(request)

        # Mostra página bonita com delay
        return render(request, "logout_sucesso.html")


from .models import Promocoes

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from .models import Promocoes, Brinquedos  # Certifique-se dos nomes dos modelos


class PromocaoAdminView(AdminOnlyMixin, View):
    template_name = "promocoes_adm.html"

    def get(self, request, *args, **kwargs):
        # Dados para preencher a página e o modal
        context = {
            "promocoes": Promocoes.objects.all().order_by('-id'),
            "brinquedos": Brinquedos.objects.all().order_by('nome_brinquedo'),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Captura os dados do formulário do modal
        promo_id = request.POST.get('promo_id')  # Para o caso de edição
        descricao = request.POST.get('descricao')
        preco = request.POST.get('preco_promocao')
        brinquedo_id = request.POST.get('brinquedos')
        imagem = request.FILES.get('imagem_promocao')

        # Busca a instância para editar ou cria uma nova
        if promo_id:
            promocao = get_object_or_404(Promocoes, id=promo_id)
        else:
            promocao = Promocoes()

        # Atualiza os campos
        promocao.descricao = descricao
        promocao.preco_promocao = preco
        promocao.brinquedos_id = brinquedo_id  # Django usa _id para chaves estrangeiras via ID direto

        if imagem:
            promocao.imagem_promocao = imagem

        promocao.save()
        return redirect('promocoes_admin')  # Nome da sua URL de listagem


class PromocaoDeleteView(AdminOnlyMixin, View):
    def post(self, request, pk, *args, **kwargs):
        promocao = get_object_or_404(Promocoes, pk=pk)
        try:
            promocao.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CupomAdminView(AdminOnlyMixin, View):

    def get(self, request):
        cupons = Cupom.objects.all()
        return render(request, "cupons_adm.html", {
            "cupons": cupons
        })

    def post(self, request):
        codigo = request.POST.get("codigo")
        desconto = request.POST.get("desconto_percentual")

        if not codigo or not desconto:
            return JsonResponse({
                "success": False,
                "html": self.render_form(error="Preencha todos os campos")
            })

        Cupom.objects.create(
            codigo=codigo,
            desconto_percentual=desconto
        )

        return JsonResponse({"success": True})

    def delete(self, request, cupom_id):
        cupom = get_object_or_404(Cupom, id=cupom_id)
        cupom.delete()
        return JsonResponse({"success": True})

    def render_form(self, error=None):
        return f"""
        <form id="formCupom" method="post" action="/adm/cupons/">
            <input type="hidden" name="csrfmiddlewaretoken" value="{{{{ csrf_token }}}}">

            <label>Código</label>
            <input type="text" name="codigo" required>

            <label>Desconto (%)</label>
            <input type="number" step="0.01" name="desconto_percentual" required>

            {"<p style='color:red'>" + error + "</p>" if error else ""}

            <button type="submit" class="btn-novo-cupom">
                💾 Salvar
            </button>
        </form>
        """


class ProjetoAdminView(AdminOnlyMixin, View):
    template_name = "projetos/projetos_adm.html"

    def get(self, request):
        context = {
            "projetos": Projetos.objects.select_related('brinquedo_projetado').all(),
            "brinquedos_disponiveis": BrinquedosProjeto.objects.all(),
            "form": ProjetoForm()
        }
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get("action")

        # 1. CRIAR APENAS O BRINQUEDO (Via Modal 2)
        if action == "create_brinquedo":
            nome = request.POST.get("nome_brinquedo")
            desc = request.POST.get("desc_brinquedo")
            if nome:
                brinquedo = BrinquedosProjeto.objects.create(
                    nome_brinquedo_projeto=nome,
                    descricao=desc
                )
                return JsonResponse({
                    "success": True,
                    "id": brinquedo.id,
                    "nome": brinquedo.nome_brinquedo_projeto
                })

        # 2. SALVAR PROJETO COMPLETO
        if action == "save_projeto":
            projeto_id = request.POST.get("id")
            if projeto_id:  # Update
                projeto = get_object_or_404(Projetos, id=projeto_id)
                form = ProjetoForm(request.POST, instance=projeto)
            else:  # Create
                form = ProjetoForm(request.POST)

            if form.is_valid():
                projeto = form.save()
                return JsonResponse({"success": True})

            return JsonResponse({"success": False, "errors": form.errors})

        # 3. EXCLUIR
        if action == "delete":
            projeto = get_object_or_404(Projetos, id=request.POST.get("id"))
            projeto.delete()
            return JsonResponse({"success": True})

        return JsonResponse({"success": False})


from django.forms import modelform_factory

EventoForm = modelform_factory(
    Eventos,
    fields=["titulo", "descricao", "brinquedos"]
)


class EventoAdminView(AdminOnlyMixin, View):
    template_name = "eventos/eventos_adm.html"

    def get(self, request):
        # Use prefetch_related para otimizar a busca das imagens também
        eventos = Eventos.objects.prefetch_related('brinquedos', 'imagens_evento')
        form = EventoForm()
        brinquedos = Brinquedos.objects.all()

        eventos_data = []
        for evento in eventos:
            eventos_data.append({
                "id": evento.id,
                "titulo": evento.titulo,
                "descricao": evento.descricao,
                "brinquedos": list(evento.brinquedos.values_list('id', flat=True)),
                # Adicione esta linha para extrair as URLs das imagens:
                "imagens_list": [img.imagem.url for img in evento.imagens_evento.all()]
            })

        return render(request, self.template_name, {
            "eventos": eventos_data,
            "form": form,
            "brinquedos": brinquedos
        })

    def post(self, request):
        action = request.POST.get("action")

        # ===== CREATE =====
        if action == "create":
            form = EventoForm(request.POST)
            if form.is_valid():
                form.save()
                return JsonResponse({"success": True})
            return JsonResponse({
                "success": False,
                "errors": form.errors
            })

        # ===== UPDATE =====
        if action == "update":
            evento = get_object_or_404(Eventos, pk=request.POST.get("id"))
            form = EventoForm(request.POST, instance=evento)
            if form.is_valid():
                form.save()
                return JsonResponse({"success": True})
            return JsonResponse({
                "success": False,
                "errors": form.errors
            })

        # ===== DELETE =====
        if action == "delete":
            evento = get_object_or_404(Eventos, pk=request.POST.get("id"))
            evento.delete()
            return JsonResponse({"success": True})

        return JsonResponse({"success": False})


class PedidoAdminView(AdminOnlyMixin, View):

    def get(self, request):
        pedidos = Pedido.objects.all()

        ctx = {
            'pedidos': pedidos,
        }
        return render(request, 'pedidos_adm.html', ctx)


class RegistrarView(View):
    template_name = "register.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not all([first_name, last_name, username, email, password]):
            messages.error(request, "Preencha todos os campos.")
            return render(request, self.template_name)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Nome de usuário já está em uso.")
            return render(request, self.template_name)

        if User.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está registrado.")
            return render(request, self.template_name)

        from django.contrib.auth import authenticate, login

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user:
            login(request, user)

        messages.success(
            request,
            f"Conta criada com sucesso! Bem-vindo(a), {first_name}."
        )
        return redirect("login")


class BrinquedoAdmin(AdminOnlyMixin, View):

    def get(self, request):
        categoria = request.GET.get("categoria", "todas")

        # FILTRAGEM
        if categoria == "todas":
            brinquedos = Brinquedos.objects.all()
        else:
            brinquedos = Brinquedos.objects.filter(
                categorias_brinquedos__nome_categoria=categoria
            ).distinct()

        # PAGINAÇÃO
        paginator = Paginator(brinquedos, 50)
        page = request.GET.get("page")
        brinquedos_page = paginator.get_page(page)

        # LISTA DE CATEGORIAS
        categorias = CategoriasBrinquedos.objects.all()
        tags = TagsBrinquedos.objects.all()

        context = {
            "brinquedos": brinquedos_page,
            "categorias": categorias,
            "tags": tags,
            "categoria_ativa": categoria,
            "page_obj": brinquedos_page,
        }

        return render(request, "brinquedos_adm.html", context)

    def post(self, request):
        try:
            acao = request.POST.get("acao")  # <-- identifica qual botão apertou

            nome = request.POST.get("nome_brinquedo")
            imagem = request.FILES.get("imagem_brinquedo")
            descricao = request.POST.get("descricao")
            preco = request.POST.get("valor_brinquedo")
            avaliacao = request.POST.get("avaliacao")
            voltz = request.POST.get("voltz")

            categorias_ids = request.POST.getlist("categorias_brinquedos")
            tags_ids = request.POST.getlist("tags")

            altura = request.POST.get("altura_m")
            largura = request.POST.get("largura_m")
            profundidade = request.POST.get("profundidade_m")

            # VALIDAÇÃO
            if not nome or not descricao:
                messages.error(request, "Preencha todos os campos obrigatórios.")
                return redirect("/adm/brinquedos/?modal_aberto=1")

            if acao == "salvar" and not imagem:
                messages.error(request, "Selecione uma imagem!")
                return redirect("/adm/brinquedos/?modal_aberto=1")

            # Parse valores
            def parse_decimal(v):
                return v.replace(",", ".") if v else None

            preco = parse_decimal(preco)
            avaliacao = parse_decimal(avaliacao)
            altura = parse_decimal(altura)
            largura = parse_decimal(largura)
            profundidade = parse_decimal(profundidade)

            # CRIA O BRINQUEDO
            novo = Brinquedos.objects.create(
                nome_brinquedo=nome,
                imagem_brinquedo=imagem,
                descricao=descricao,
                valor_brinquedo=preco,
                avaliacao=avaliacao,
                voltz=voltz,
                altura_m=altura,
                largura_m=largura,
                profundidade_m=profundidade
            )

            # 🔥 ADICIONA CATEGORIAS
            if categorias_ids:
                novo.categorias_brinquedos.set(categorias_ids)

            # 🔥 ADICIONA TAGS
            if tags_ids:
                novo.tags.set(tags_ids)

            messages.success(request, f"Brinquedo '{novo.nome_brinquedo}' salvo com sucesso!")

            # Se for "Salvar e adicionar outro"
            if acao == "salvar_adicionar":
                return redirect("/brinquedos/admin/?modal_aberto=1&limpar=1")

            # Caso seja salvar normal → fecha modal
            return redirect("/brinquedos/admin/")

        except Exception as e:
            messages.error(request, f"Erro ao salvar: {str(e)}")
            return redirect("/brinquedos/admin/?modal_aberto=1")


from django.http import JsonResponse
from django.db import IntegrityError


class NovaCategoria(AdminOnlyMixin, View):

    def post(self, request):
        try:
            nome = request.POST.get("nome_categoria")
            img = request.FILES.get("imagem_categoria")

            if not nome or not img:
                return JsonResponse({"status": "erro", "msg": "Preencha todos os campos."})

            try:
                nova = CategoriasBrinquedos.objects.create(
                    nome_categoria=nome,
                    imagem_categoria=img
                )
            except IntegrityError:
                # Captura o erro de UNIQUE
                return JsonResponse({
                    "status": "erro",
                    "msg": f"Já existe uma categoria com o nome '{nome}'"
                })

            return JsonResponse({
                "status": "sucesso",
                "msg": "Categoria adicionada!",
                "id": nova.id,
                "nome": nova.nome_categoria
            })

        except Exception as e:
            return JsonResponse({"status": "erro", "msg": f"Erro inesperado: {str(e)}"})


class NovaTag(AdminOnlyMixin, View):
    def post(self, request):
        nome = request.POST.get("nome_tag")

        TagsBrinquedos.objects.create(nome_tag=nome)

        messages.success(request, "Tag criada com sucesso!")

        return redirect("/brinquedos/admin/?modal_aberto=1")


from django.utils.timesince import timesince
from django.utils import timezone

from .forms import ImagensSiteForm

MAX_BANNERS = 5


class BannerAdminView(LoginRequiredMixin, View):

    def get(self, request):
        imagens_site = ImagensSite.objects.all()
        total = imagens_site.count()
        limite_restante = max(0, MAX_BANNERS - total)

        for banner in imagens_site:
            if banner.atualizado and banner.atualizado != banner.criacao:
                dias = timesince(banner.atualizado, timezone.now())
                banner.status_atualizacao = f'Atualizado há {dias}'
            else:
                banner.status_atualizacao = 'Nunca foi alterado'

        form = ImagensSiteForm()

        return render(request, 'banner_adm.html', {
            'imagens_site': imagens_site,
            'form': form,
            'limite_restante': limite_restante,
            'max_banners': MAX_BANNERS,
        })

    def post(self, request):
        # =============================
        # ATUALIZAÇÃO DE BANNER
        # =============================
        update_id = request.POST.get('update_id')
        imagem_update = request.FILES.get('imagem')

        if update_id and imagem_update:
            banner = get_object_or_404(ImagensSite, pk=update_id)
            banner.imagem = imagem_update
            banner.atualizado = timezone.now()
            banner.save()

            messages.success(request, 'Banner atualizado com sucesso.')
            return redirect('banner_adm')

        # =============================
        # UPLOAD DE NOVOS BANNERS
        # =============================
        imagens = request.FILES.getlist('imagens')

        if not imagens:
            messages.warning(request, 'Nenhuma imagem selecionada.')
            return redirect('banner_adm')

        total_atual = ImagensSite.objects.count()
        restante = MAX_BANNERS - total_atual

        if restante <= 0:
            messages.error(
                request,
                f'Limite máximo de {MAX_BANNERS} banners atingido.'
            )
            return redirect('banner_adm')

        if len(imagens) > restante:
            messages.error(
                request,
                f'Você só pode adicionar mais {restante} banner(s).'
            )
            return redirect('banner_adm')

        for imagem in imagens:
            ImagensSite.objects.create(imagem=imagem)

        messages.success(request, 'Banner(s) adicionados com sucesso.')
        return redirect('banner_adm')


class BannerDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk):
        banner = get_object_or_404(ImagensSite, pk=pk)
        banner.delete()
        messages.success(request, 'Banner removido com sucesso.')
        return redirect('banner_adm')


from .models import ClientePerfil, Pedido  # ⚠️ muito importante
from datetime import timedelta
from django.db.models.functions import TruncDay, TruncMonth


class DashboardAdminView(View):
    def get(self, request):
        filtro = request.GET.get('filtro', 'geral')
        agora = timezone.now()

        # Definir data inicial para filtro
        if filtro == '7dias':
            data_inicio = agora - timedelta(days=7)
        elif filtro == '30dias':
            data_inicio = agora - timedelta(days=30)
        elif filtro == 'ano':
            data_inicio = agora.replace(month=1, day=1, hour=0, minute=0, second=0)
        else:  # geral
            data_inicio = None

        # Filtrar clientes
        # Filtrar clientes (somente usuários "clientes")
        clientes_qs = ClientePerfil.objects.select_related('user').all()
        if data_inicio:
            clientes_qs = clientes_qs.filter(criado_em__gte=data_inicio)

        # Filtrar apenas usuários que não são staff nem superusers
        clientes_qs = clientes_qs.filter(user__is_staff=False, user__is_superuser=False)
        total_clientes = clientes_qs.count()

        # Filtrar pedidos
        pedidos_qs = Pedido.objects.all()
        if data_inicio:
            pedidos_qs = pedidos_qs.filter(criacao__gte=data_inicio)

        total_pedidos = pedidos_qs.count()
        pedidos_finalizados = pedidos_qs.filter(status='finalizado').count()
        taxa_conversao = (pedidos_finalizados / total_pedidos * 100) if total_pedidos else 0

        # Total de vendas
        vendas_total = pedidos_qs.filter(status='finalizado').aggregate(
            total=Sum('total_liquido')
        )['total'] or 0
        vendas_total_formatado = f"R$ {vendas_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        # ---------------------------
        # Preparar dados do gráfico
        # ---------------------------
        # ----------------------------
        # Preparar dados do gráfico
        # ----------------------------
        labels = []
        vendas_data = []

        if filtro == 'geral' or filtro == 'ano':
            # Agrupar por mês usando TruncDate
            vendas_qs = pedidos_qs.filter(status='finalizado').exclude(criacao__isnull=True)
            vendas_agrupadas = vendas_qs.annotate(data=TruncDate('criacao')) \
                .values('data') \
                .annotate(total=Sum('total_liquido')) \
                .order_by('data')

            # Criar dicionário para somar por mês
            from collections import defaultdict
            mes_dict = defaultdict(float)
            for item in vendas_agrupadas:
                mes_label = item['data'].strftime('%b/%Y')  # formato: Jan/2026
                mes_dict[mes_label] += float(item['total'])

            labels = list(mes_dict.keys())
            vendas_data = list(mes_dict.values())

        elif filtro == '7dias':
            vendas_por_dia = pedidos_qs.filter(status='finalizado').annotate(
                dia=TruncDate('criacao')
            ).values('dia').annotate(total=Sum('total_liquido')).order_by('dia')

            for item in vendas_por_dia:
                labels.append(item['dia'].strftime('%d/%m'))
                vendas_data.append(float(item['total']))

        elif filtro == '30dias':
            # Dois blocos de 15 dias cada
            vendas_por_15 = pedidos_qs.filter(status='finalizado').order_by('criacao')
            first_half = vendas_por_15[:15]
            second_half = vendas_por_15[15:30]

            labels = ['Dias 1-15', 'Dias 16-30']
            total_first = sum(p.total_liquido for p in first_half)
            total_second = sum(p.total_liquido for p in second_half)
            vendas_data = [float(total_first), float(total_second)]

        top_brinquedos = BrinquedoClick.objects.order_by('-quantidade_click')[:3]
        top_combos = ComboClick.objects.order_by('-quantidade_click')[:3]
        top_promocoes = PromocaoClick.objects.order_by('-quantidade_click')[:3]
        top_categorias = CategoriaClick.objects.order_by('-quantidade_click')[:3]

        ctx = {
            'filtro': filtro,
            'total_clientes': total_clientes,
            'total_pedidos': total_pedidos,
            'pedidos_finalizados': pedidos_finalizados,
            'taxa_conversao': f"{taxa_conversao:.1f}%",
            'vendas_total': vendas_total_formatado,
            'chart_labels': labels,
            'chart_data': vendas_data,
            'top_brinquedos': top_brinquedos,
            'top_combos': top_combos,
            'top_promocoes': top_promocoes,
            'top_categorias': top_categorias,
        }

        return render(request, 'dashboard.html', ctx)


from django.http import HttpResponseForbidden
from django.db.models.functions import TruncDate


class EstatisticasGeraisView(View):
    def get(self, request):
        filtro = request.GET.get('filtro', 'geral')
        agora = timezone.now()

        if filtro == '7dias':
            data_inicio = agora - timedelta(days=7)
        elif filtro == '30dias':
            data_inicio = agora - timedelta(days=30)
        elif filtro == 'ano':
            data_inicio = agora.replace(month=1, day=1, hour=0, minute=0, second=0)
        else:
            data_inicio = None

        # -----------------------------
        # BRINQUEDOS
        # -----------------------------
        brinquedos = BrinquedoClick.objects.all()
        if data_inicio:
            brinquedos = brinquedos.filter(criacao__gte=data_inicio)

        top_brinquedos = (
            brinquedos
            .values('brinquedo_clicado__nome_brinquedo')
            .annotate(total=Sum('quantidade_click'))
            .order_by('-total')[:20]
        )

        # -----------------------------
        # COMBOS
        # -----------------------------
        combos = ComboClick.objects.all()
        if data_inicio:
            combos = combos.filter(criacao__gte=data_inicio)

        top_combos = (
            combos
            .values('descricao_combo')
            .annotate(total=Sum('quantidade_click'))
            .order_by('-total')[:20]
        )

        # -----------------------------
        # PROMOÇÕES
        # -----------------------------
        promocoes = PromocaoClick.objects.all()
        if data_inicio:
            promocoes = promocoes.filter(criacao__gte=data_inicio)

        top_promocoes = (
            promocoes
            .values('descricao_promocao')
            .annotate(total=Sum('quantidade_click'))
            .order_by('-total')[:20]
        )

        # -----------------------------
        # CATEGORIAS
        # -----------------------------
        categorias = CategoriaClick.objects.all()
        if data_inicio:
            categorias = categorias.filter(criacao__gte=data_inicio)

        top_categorias = (
            categorias
            .values('nome_categoria')
            .annotate(total=Sum('quantidade_click'))
            .order_by('-total')[:20]
        )

        total_brinquedo_clicks = brinquedos.aggregate(
            total=Sum('quantidade_click')
        )['total'] or 0

        total_combo_clicks = combos.aggregate(
            total=Sum('quantidade_click')
        )['total'] or 0

        total_promocao_clicks = promocoes.aggregate(
            total=Sum('quantidade_click')
        )['total'] or 0

        total_categoria_clicks = categorias.aggregate(
            total=Sum('quantidade_click')
        )['total'] or 0

        total_geral = (
                total_brinquedo_clicks +
                total_combo_clicks +
                total_promocao_clicks +
                total_categoria_clicks
        )

        crescimento_diario = (
            BrinquedoClick.objects
            .values(dia=TruncDate('criacao'))
            .annotate(total=Sum('quantidade_click'))
            .order_by('-dia')[:15]
        )

        ctx = {
            'crescimento_diario': crescimento_diario,
            'filtro': filtro,
            'top_brinquedos': top_brinquedos,
            'top_combos': top_combos,
            'top_promocoes': top_promocoes,
            'top_categorias': top_categorias,

            'total_brinquedo_clicks': total_brinquedo_clicks,
            'total_combo_clicks': total_combo_clicks,
            'total_promocao_clicks': total_promocao_clicks,
            'total_categoria_clicks': total_categoria_clicks,
            'total_geral': total_geral,
        }

        return render(request, 'estatisticas_gerais.html', ctx)


class ManutencaoAdminView(LoginRequiredMixin, View):

    def get(self, request):
        manutencoes = Manutencao.objects.all()

        ctx = {
            'manutencoes': manutencoes,
        }
        return render(request, 'manutencao_adm.html', ctx)


class UserAdminView(LoginRequiredMixin, View):
    login_url = '/adm/login/'  # redireciona se não estiver logado

    def get(self, request):
        # Pegamos todos os perfis de clientes
        perfis_clientes = ClientePerfil.objects.select_related('user').all().order_by('user__id')

        # Alternativamente, se quiser todos os usuários (admins, staff e clientes):
        # perfis_clientes = ClientePerfil.objects.select_related('user').all()
        # Para usuários sem perfil (apenas User):
        # usuarios_sem_perfil = User.objects.exclude(perfil__isnull=False)
        # aí você poderia combinar no template ou na view

        context = {
            'perfis_clientes': perfis_clientes
        }
        return render(request, 'users_adm.html', context)


from django.views.generic import TemplateView
from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import datetime

from .models import Venda


class RelatorioVendasView(LoginRequiredMixin, TemplateView):
    template_name = 'relatoriov_adm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        vendas = Venda.objects.filter(confirmado=True)

        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        forma_pagamento = self.request.GET.get('forma_pagamento')

        if data_inicio:
            vendas = vendas.filter(criacao__date__gte=data_inicio)

        if data_fim:
            vendas = vendas.filter(criacao__date__lte=data_fim)

        if forma_pagamento:
            vendas = vendas.filter(forma_pagamento=forma_pagamento)

        context['total_vendas'] = vendas.count()
        context['total_valor'] = vendas.aggregate(
            total=Sum('valor_pago')
        )['total'] or 0

        context['vendas'] = vendas.select_related('pedido').order_by('-criacao')

        context['formas_pagamento'] = [
            ('pix', 'PIX'),
            ('cartao', 'Cartão'),
            ('dinheiro', 'Dinheiro'),
            ('whatsapp', 'WhatsApp'),
        ]

        context['filtros'] = {
            'data_inicio': data_inicio or '',
            'data_fim': data_fim or '',
            'forma_pagamento': forma_pagamento or '',
        }

        return context


from .forms import ManutencaoForm
from .models import Manutencao

from django.contrib.auth.decorators import login_required
from .models import ItemCarrinho, Carrinho


def adicionar_ao_carrinho(request, tipo, object_id):
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Você precisa fazer login'}, status=403)

    if not hasattr(request.user, 'perfil'):
        return JsonResponse({'erro': 'Usuário inválido'}, status=403)

    cliente = request.user.perfil
    carrinho, _ = Carrinho.objects.get_or_create(cliente=cliente)

    modelos = {
        'brinquedo': Brinquedos,
        'combo': Combos,
        'promocao': Promocoes,
    }

    model = modelos.get(tipo)
    if not model:
        return JsonResponse({'erro': 'Tipo inválido'}, status=400)

    objeto = get_object_or_404(model, id=object_id)
    content_type = ContentType.objects.get_for_model(objeto)

    item, created = ItemCarrinho.objects.get_or_create(
        carrinho=carrinho,
        content_type=content_type,
        object_id=objeto.id,
        defaults={'quantidade': 1}
    )

    if not created:
        item.quantidade += 1
        item.save()

    total_itens = carrinho.itens.aggregate(total=Sum('quantidade'))['total'] or 0

    return JsonResponse({
        'sucesso': True,
        'total_itens': total_itens
    })


from django.views.decorators.http import require_POST


@login_required
@require_POST
def remover_item_carrinho(request):
    item_id = request.POST.get('item_id')

    try:
        item = ItemCarrinho.objects.get(
            id=item_id,
            carrinho__cliente=request.user.perfil
        )
        item.delete()
        return JsonResponse({'status': 'success'})
    except ItemCarrinho.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item não encontrado'}, status=404)


@login_required
@require_POST
def limpar_carrinho(request):
    carrinho = Carrinho.objects.get(cliente=request.user.perfil)
    carrinho.itens.all().delete()
    carrinho.cupom = None
    carrinho.save()

    return JsonResponse({'status': 'success'})


@login_required
def carrinho_view(request):
    if not hasattr(request.user, 'perfil'):
        return redirect('home')

    cliente = request.user.perfil

    carrinho = Carrinho.objects.select_related('cupom').get(cliente=cliente)

    itens = (
        ItemCarrinho.objects
        .filter(carrinho=carrinho)
        .select_related('content_type')
    )

    context = {
        'carrinho': carrinho,
        'itens': itens,
    }

    return render(request, 'carrinho.html', context)


import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Pedido, ItemPedido


@login_required
@require_POST
def aplicar_cupom(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'title': 'Erro',
            'message': 'Dados inválidos enviados'
        }, status=400)

    codigo = data.get('codigo', '').strip()

    if not codigo:
        return JsonResponse({
            'status': 'warning',
            'title': 'Cupom vazio',
            'message': 'Digite um código de cupom'
        })

    if not hasattr(request.user, 'perfil'):
        return JsonResponse({
            'status': 'error',
            'title': 'Erro',
            'message': 'Perfil do cliente não encontrado'
        }, status=400)

    carrinho = Carrinho.objects.filter(cliente=request.user.perfil).first()

    if not carrinho:
        return JsonResponse({
            'status': 'error',
            'title': 'Carrinho vazio',
            'message': 'Crie um carrinho antes de aplicar o cupom'
        })

    try:
        cupom = Cupom.objects.get(codigo__iexact=codigo)
    except Cupom.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'title': 'Cupom inválido',
            'message': 'Este cupom não existe ou é inválido'
        })

    # 🔮 FUTURA REGRA: cupom primeira compra
    if codigo.lower() == 'newuser10':
        ja_comprou = Pedido.objects.filter(cliente=request.user.perfil).exists()
        if ja_comprou:
            return JsonResponse({
                'status': 'warning',
                'title': 'Cupom indisponível',
                'message': 'Este cupom é válido apenas na primeira compra'
            })

    carrinho.cupom = cupom
    carrinho.save(update_fields=['cupom'])

    return JsonResponse({
        'status': 'success',
        'title': 'Cupom aplicado 🎉',
        'message': f'Você economizou {cupom.desconto_percentual}% com o cupom {cupom.codigo}'
    })


from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages


class PaymentView(View):

    def get(self, request, carrinho_id):
        carrinho = get_object_or_404(Carrinho, id=carrinho_id)

        itens = carrinho.itens.all()
        carrinho_vazio = not itens.exists()

        somente_pix = (
                not request.user.is_authenticated or carrinho_vazio
        )

        context = {
            'carrinho': carrinho,
            'itens': itens,
            'carrinho_vazio': carrinho_vazio,
            'total_bruto': carrinho.total_bruto,
            'valor_desconto': carrinho.valor_desconto,
            'total_liquido': carrinho.total_liquido,
            'total_itens': itens.count(),
            'somente_pix': somente_pix,
        }

        return render(request, 'payment.html', context)


from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def processar_cartao(request):
    if request.method != "POST":
        return JsonResponse({"sucesso": False, "mensagem": "Método inválido."})

    dados = json.loads(request.body)
    numero = dados.get("numero")
    validade = dados.get("validade")
    cvv = dados.get("cvv")
    nome = dados.get("nome")
    cpf = dados.get("cpf")

    # Simulação: aqui você chamaria a API de pagamento do seu gateway
    saldo_disponivel = Decimal("1000.00")  # Exemplo
    valor_compra = Decimal("123.45")  # Pegar do carrinho/pedido atual

    if saldo_disponivel < valor_compra:
        return JsonResponse({"sucesso": False, "mensagem": "Saldo insuficiente."})

    # Se passou, cria o pedido
    from .models import Pedido

    pedido = Pedido.objects.create(
        cliente=request.user.clienteperfil,
        status="pago",
        total_bruto=valor_compra,
        total_liquido=valor_compra,
        forma_pagamento="credito",
        observacoes=f"CPF: {cpf}"
    )

    # Aqui você pode registrar venda, itens, etc.
    return JsonResponse({"sucesso": True, "pedido_id": pedido.id})


from django.urls import reverse


@login_required
@require_POST
def criar_pedido_pix(request):
    cliente = request.user.perfil
    carrinho = Carrinho.objects.filter(cliente=cliente).first()

    if not carrinho or not carrinho.itens.exists():
        return JsonResponse({'error': 'Carrinho vazio'}, status=400)

    with transaction.atomic():
        pedido = Pedido.objects.create(
            cliente=cliente,
            status='criado',  # 👈 ainda NÃO pago
            forma_pagamento='pix',
            total_bruto=carrinho.total_bruto,
            valor_desconto=carrinho.valor_desconto,
            total_liquido=carrinho.total_liquido,
            cupom_codigo=carrinho.cupom.codigo if carrinho.cupom else None,
            cupom_percentual=carrinho.cupom.desconto_percentual if carrinho.cupom else None
        )

        for item in carrinho.itens.all():
            ItemPedido.objects.create(
                pedido=pedido,
                content_type=item.content_type,
                object_id=item.object_id,
                nome_item=str(item.item),
                tipo_item=item.item.__class__.__name__.lower(),
                preco_unitario=item.preco_unitario,
                quantidade=item.quantidade,
                subtotal=item.subtotal
            )

        carrinho.itens.all().delete()

    return JsonResponse({
        'success': True,
        'redirect_url': reverse('payment_finally', args=[pedido.id])
    })


def criar_pedido_do_carrinho(carrinho):
    with transaction.atomic():
        pedido = Pedido.objects.create(
            cliente=carrinho.cliente,
            total_bruto=carrinho.total_bruto,
            valor_desconto=carrinho.valor_desconto,
            total_liquido=carrinho.total_liquido,
            cupom_codigo=carrinho.cupom.codigo if carrinho.cupom else None,
            cupom_percentual=carrinho.cupom.desconto_percentual if carrinho.cupom else None,
        )

        for item in carrinho.itens.all():
            ItemPedido.objects.create(
                pedido=pedido,
                content_type=item.content_type,
                object_id=item.object_id,
                nome_item=str(item.item),
                tipo_item=item.content_type.model,
                preco_unitario=item.preco_unitario,
                quantidade=item.quantidade,
                subtotal=item.subtotal
            )

        # opcional: limpar carrinho
        carrinho.itens.all().delete()
        carrinho.cupom = None
        carrinho.save()

        return pedido


@require_POST
def confirmar_cartao(request, carrinho_id):
    carrinho = get_object_or_404(Carrinho, id=carrinho_id)

    numero = request.POST.get('numero_cartao', '')

    # regra simples
    if numero.startswith('6'):
        forma = 'debito'
    else:
        forma = 'credito'

    pedido = Pedido.objects.create(
        cliente=carrinho.cliente,
        status='pago',
        forma_pagamento=forma,
        total_bruto=carrinho.total_bruto,
        valor_desconto=carrinho.valor_desconto,
        total_liquido=carrinho.total_liquido,
        observacoes='Pagamento via cartão'
    )

    for item in carrinho.itens.all():
        ItemPedido.objects.create(
            pedido=pedido,
            nome_item=str(item.item),
            tipo_item=item.item.__class__.__name__.lower(),
            preco_unitario=item.preco_unitario,
            quantidade=item.quantidade,
            subtotal=item.subtotal
        )

    carrinho.delete()
    return redirect('meus_pedidos')


from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Pedido, EnderecoEntrega, EnderecoEmpresa
from .utils import calcular_distancia_km, estimar_tempo_minutos


class PaymentFinallyView(LoginRequiredMixin, View):
    template_name = 'payment_finally.html'

    def get_pedido(self, pedido_id, user):
        return get_object_or_404(
            Pedido,
            id=pedido_id,
            cliente=user.perfil
        )

    def get(self, request, pedido_id):
        pedido = self.get_pedido(pedido_id, request.user)
        return render(request, self.template_name, {
            "pedido": pedido,
            "endereco": getattr(pedido, 'endereco', None),
        })

    def post(self, request, pedido_id):
        pedido = self.get_pedido(pedido_id, request.user)

        if pedido.status not in ['criado', 'aguardando_pagamento']:
            return redirect('meus_pedidos')

        with transaction.atomic():
            # Cria ou atualiza o endereço de entrega
            endereco, _ = EnderecoEntrega.objects.update_or_create(
                pedido=pedido,
                defaults={
                    'cep': request.POST.get('cep'),
                    'rua': request.POST.get('rua'),
                    'numero': request.POST.get('numero'),
                    'complemento': request.POST.get('complemento'),
                    'bairro': request.POST.get('bairro'),
                    'cidade': request.POST.get('cidade'),
                    'estado': request.POST.get('estado'),
                    'telefone': request.POST.get('telefone'),
                }
            )

            # Geocodifica endereço do cliente
            lat_entrega, lon_entrega = endereco.geocodificar()
            if lat_entrega is not None and lon_entrega is not None:
                endereco.latitude = round(lat_entrega, 6)
                endereco.longitude = round(lon_entrega, 6)
                endereco.save(update_fields=['latitude', 'longitude'])

            # Atualiza status do pedido
            if pedido.status != 'aguardando_pagamento':
                pedido.status = 'aguardando_pagamento'
                pedido.save(update_fields=['status'])

        return redirect('meus_pedidos')


#-23.453403648643707, -46.66151816239609  -23.472997309863196, -46.63041992925325

class MeusPedidosView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        perfil = request.user.perfil
        empresa = EnderecoEmpresa.objects.first()  # único endereço da empresa

        pedidos = (
            Pedido.objects
            .filter(cliente=perfil)
            .prefetch_related('itens', 'endereco')
            .order_by('-criacao')
        )

        # Atualiza distância e tempo para pedidos que têm endereço e empresa
        for pedido in pedidos:
            endereco = getattr(pedido, 'endereco', None)
            if endereco and endereco.latitude and endereco.longitude:
                if empresa and empresa.latitude and empresa.longitude:
                    # Evita recalcular se já estiver salvo
                    if pedido.distancia_km is None or pedido.tempo_estimado_min is None:
                        distancia = calcular_distancia_km(
                            round(empresa.latitude, 6),
                            round(empresa.longitude, 6),
                            round(endereco.latitude, 6),
                            round(endereco.longitude, 6)
                        )
                        tempo = estimar_tempo_minutos(distancia)

                        pedido.distancia_km = round(distancia, 2)
                        pedido.tempo_estimado_min = tempo
                        pedido.save(update_fields=['distancia_km', 'tempo_estimado_min'])

        return render(request, 'meus_pedidos.html', {
            'pedidos': pedidos,
            'empresa': empresa
        })


from django.shortcuts import redirect
from django.urls import reverse


def redirecionar_loja(request):
    return redirect(reverse('brinquedos') + '#grid-cards')


def redirecionar_lancamentos(request):
    return redirect(reverse('brinquedos') + '#grid-cards')


def redirecionar_showroom(request):
    return redirect(reverse('eventos') + '#todos-eventos')


def redirecionar_contato(request):
    return redirect(reverse('home') + '#contato')


def redirecionar_categoria_brinquedos(request):
    return redirect(reverse('brinquedo_detalhe', args=[12]))


def redirecionar_categoria_aventura(request):
    return redirect(reverse('categoria_detalhe', args=[12]))
