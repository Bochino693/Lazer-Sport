from django.views.generic import View
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Count, F, ExpressionWrapper, FloatField
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login
from decimal import Decimal

from .forms import UserForm, PerfilForm

from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Brinquedos, CategoriasBrinquedos, Projetos, Eventos, ClientePerfil, Combos, Cupom, Promocoes, \
    TagsBrinquedos, ImagensSite

import os
from django.http import FileResponse, Http404
from django.conf import settings


def media_serve(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.isfile(file_path):
        raise Http404("Arquivo não encontrado")

    return FileResponse(open(file_path, 'rb'), content_type='image/jpeg')


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
            "imagens_site": imagens_site,
        }
        return render(request, 'home.html', context)


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
        paginator = Paginator(brinquedos_list, 9)
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


from django.views.generic import ListView
from .models import Combos

class ComboListView(ListView):
    model = Combos
    template_name = "combos_adm.html"
    context_object_name = "combos"



from django.contrib.auth import logout


class LogoutUsuarioView(View):

    def get(self, request):
        # Desloga primeiro
        logout(request)

        # Mostra página bonita com delay
        return render(request, "logout_sucesso.html")


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
