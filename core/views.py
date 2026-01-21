from django.views.generic import View
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Count, F, ExpressionWrapper, FloatField, Sum
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from decimal import Decimal

from .forms import UserForm, PerfilForm, ProjetoForm, ManutencaoForm
from django.views.generic.edit import FormView

from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Brinquedos, CategoriasBrinquedos, Projetos, Eventos, ClientePerfil, Combos, Cupom, Promocoes, \
    TagsBrinquedos, ImagensSite, BrinquedosProjeto, Estabelecimentos, Manutencao, ManutencaoImagem

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

        imagens_site = ImagensSite.objects.exclude(imagem="")

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
        paginator = Paginator(brinquedos, 6)  # 8 por página
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        categorias_brinquedos = CategoriasBrinquedos.objects.annotate(
            total_produtos=Count('brinquedos', distinct=True)
        )

        combos = Combos.objects.all()
        promocoes = Promocoes.objects.all()

        estabelecimentos = Estabelecimentos.objects.all()

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
            "projetos": projetos,
            "combos": combos,
            "promocoes": promocoes,
            "estabelecimentos": Estabelecimentos.objects.all(),
            "imagens_site": imagens_site,
        }
        return render(request, 'home.html', context)


from django.shortcuts import render, redirect
from django.views import View
from .forms import ManutencaoForm
from .models import Manutencao
from .models import ClientePerfil


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

        context = {
            "brinquedo": brinquedo
        }

        return render(request, "brinquedo_info.html", context)


class CategoriasInfoView(View):

    def get(self, request, pk):

        # Categoria selecionada
        categoria = get_object_or_404(CategoriasBrinquedos, id=pk)

        # Brinquedos desta categoria
        brinquedos = categoria.brinquedos.all()

        # FILTROS
        ordenar = request.GET.get("ordenar", "az")

        if ordenar == "az":
            brinquedos = brinquedos.order_by("nome_brinquedo")
        elif ordenar == "za":
            brinquedos = brinquedos.order_by("-nome_brinquedo")
        elif ordenar == "melhor-avaliados":
            brinquedos = brinquedos.order_by("-avaliacao")
        elif ordenar == "custo-beneficio":
            brinquedos = brinquedos.order_by("-avaliacao", "valor_brinquedo")

        # PAGINAÇÃO
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
from django.db.models.functions import Cast

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

        # TOTAL ORIGINAL – já é Decimal
        total_original = sum(
            Decimal(b.valor_brinquedo) for b in combo.brinquedos.all()
        )

        # Valor do combo – também Decimal
        valor_combo = Decimal(combo.valor_combo)

        # Economia
        economia = total_original - valor_combo

        # Porcentagem
        porcentagem = (economia / total_original * Decimal(100)) if total_original else Decimal(0)

        # Enviando para o front
        combo.total_original = total_original
        combo.economia = economia
        combo.porcentagem = porcentagem

        context = {
            'combo': combo,
        }

        return render(request, 'combo_info.html', context)


class PromocaoInfoView(View):

    def get(self, request, pk):
        promocao = get_object_or_404(Promocoes, pk=pk)

        context = {
            'promocao': promocao,

        }
        return render(request, 'promocao_info.html', context)


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
        return render(request, 'home.html', context)


class LoginUsuarioView(View):
    def get(self, request):
        return render(request, "login.html")

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Autentica
        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Usuário ou senha incorretos.")
            return render(request, "login.html")  # Recarrega com erro

        # Login OK — exibe tela de "Entrando..."
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


from .models import Combos

from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import Combos


class ComboListView(ListView):
    model = Combos
    template_name = 'combos_adm.html'
    context_object_name = 'combos'

    def get_queryset(self):
        return Combos.objects.prefetch_related('brinquedos')


class ComboCreateView(CreateView):
    model = Combos
    fields = ['descricao', 'imagem_combo', 'brinquedos', 'valor_combo']
    template_name = 'combo_form.html'
    success_url = reverse_lazy('combos_admin')


class ComboUpdateView(UpdateView):
    model = Combos
    fields = ['descricao', 'imagem_combo', 'brinquedos', 'valor_combo']
    template_name = 'combo_form.html'
    success_url = reverse_lazy('combos_admin')


class ComboDeleteView(DeleteView):
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


class PromocaoListView(ListView):
    model = Promocoes
    template_name = "promocoes_adm.html"
    context_object_name = "promocoes"


class PromocaoCreateView(CreateView):
    model = Promocoes
    fields = ['descricao', 'imagem_promocao', 'brinquedos', 'preco_promocao']
    template_name = "partials/promocoes_form.html"
    success_url = reverse_lazy("promocoes_admin")


class PromocaoUpdateView(UpdateView):
    model = Promocoes
    fields = ['descricao', 'imagem_promocao', 'brinquedos', 'preco_promocao']
    template_name = "promocoes_form.html"
    success_url = reverse_lazy("promocoes_admin")


class PromocaoDeleteView(DeleteView):
    model = Promocoes
    template_name = "promocao_confirm_delete.html"
    success_url = reverse_lazy("promocoes_admin")


class CupomListView(ListView):
    model = Cupom
    template_name = "cupons/cupons_adm.html"
    context_object_name = "cupons"


class CupomCreateView(CreateView):
    model = Cupom
    fields = ["codigo", "desconto_percentual"]
    template_name = "cupons/partials/cupom_modal.html"
    success_url = reverse_lazy("cupons_admin")


class CupomUpdateView(UpdateView):
    model = Cupom
    fields = ["codigo", "desconto_percentual"]
    template_name = "cupons/cupons_form.html"
    success_url = reverse_lazy("cupons_admin")


class CupomDeleteView(DeleteView):
    model = Cupom
    template_name = "cupons/cupons_confirm_delete.html"
    success_url = reverse_lazy("cupons_admin")


class BrinquedoProjetoListView(ListView):
    model = BrinquedosProjeto
    template_name = "projeto_adm.html"
    context_object_name = "brinquedos"


class ProjetoListView(ListView):
    model = Projetos
    template_name = "projetos/projetos_adm.html"
    context_object_name = "projetos"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ProjetoForm()
        return context


class ProjetoCreateView(View):

    def post(self, request):
        form = ProjetoForm(request.POST)

        if form.is_valid():
            projeto = form.save(commit=False)

            nome = request.POST.get("novo_brinquedo_nome")
            descricao = request.POST.get("novo_brinquedo_descricao")

            if nome:
                brinquedo = BrinquedosProjeto.objects.create(
                    nome_brinquedo_projeto=nome,
                    descricao=descricao
                )
                projeto.brinquedo_projetado = brinquedo

            projeto.save()

        return redirect("projetos_admin")


class ProjetoUpdateView(UpdateView):
    model = Projetos
    fields = ["titulo", "descricao", "brinquedo_projetado"]
    template_name = "projetos/projetos_form.html"
    success_url = reverse_lazy("projetos_admin")


class ProjetoDeleteView(DeleteView):
    model = Projetos
    template_name = "projetos/projetos_confirm_delete.html"
    success_url = reverse_lazy("projetos_admin")


class EventoListView(ListView):
    model = Eventos
    template_name = "eventos/eventos_adm.html"
    context_object_name = "eventos"


class EventoCreateView(CreateView):
    model = Eventos
    fields = ["titulo", "descricao", "brinquedos"]
    template_name = "eventos/partials/evento_modal.html"
    success_url = reverse_lazy("eventos_admin")


class EventoUpdateView(UpdateView):
    model = Eventos
    fields = ["titulo", "descricao", "brinquedos"]
    template_name = "eventos/eventos_form.html"
    success_url = reverse_lazy("eventos_admin")


class EventoDeleteView(DeleteView):
    model = Eventos
    template_name = "eventos/eventos_confirm_delete.html"
    success_url = reverse_lazy("eventos_admin")


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

        # Verificar se username já existe
        if User.objects.filter(username=username).exists():
            messages.error(request, "Nome de usuário já está em uso.")
            return render(request, self.template_name)

        # Verificar se email já existe
        if User.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está registrado.")
            return render(request, self.template_name)

        # Criar usuário
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Fazer login automático após cadastro
        login(request, user)

        messages.success(request, f"Conta criada com sucesso! Bem-vindo(a), {first_name}.")
        return redirect("home")  # ajuste para sua rota principal


class BrinquedoAdmin(View):

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


class NovaCategoria(View):

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


class NovaTag(View):
    def post(self, request):
        nome = request.POST.get("nome_tag")

        TagsBrinquedos.objects.create(nome_tag=nome)

        messages.success(request, "Tag criada com sucesso!")

        return redirect("/brinquedos/admin/?modal_aberto=1")


from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import FormView
from .forms import ManutencaoForm
from .models import Manutencao

from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy



from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import ItemCarrinho, Carrinho

from django.http import JsonResponse


@login_required
def adicionar_ao_carrinho(request, tipo, object_id):
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

    total_itens = carrinho.itens.aggregate(
        total=Sum('quantidade')
    )['total'] or 0

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


from django.contrib.contenttypes.models import ContentType
from django.db import transaction


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


class PaymentView(View):

    def get(self, request):
        return request, render('paymente.html')
