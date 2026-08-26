"""Curtidas e lista de desejos.

O que estes testes protegem:

  * curtir não exige login — quem chegou agora consegue marcar;
  * sem conta, vale uma curtida por aparelho: recarregar a página ou
    clicar de novo não infla o número;
  * com conta, vale uma por conta, mesmo trocando de aparelho;
  * o que a pessoa marcou antes de entrar não some no login: migra;
  * o app e o site compartilham exatamente as mesmas regras.

Se alguma dessas cair, ou a contagem vira ficção, ou o cliente perde a
lista que montou.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .favoritos import COOKIE_DISPOSITIVO, migrar_dispositivo_para_conta
from .models import Brinquedos, Favorito, PecasReposicao


DISPOSITIVO_A = "a" * 32
DISPOSITIVO_B = "b" * 32


class FavoritoBaseTests(TestCase):

    def setUp(self):
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica 3m",
            descricao="Cama elástica com rede de proteção",
            valor_brinquedo=Decimal("2500.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        self.peca = PecasReposicao.objects.create(
            nome="Rede de proteção 3m",
            descricao_peca="Rede para cama elástica de 3 metros",
            preco_venda=Decimal("180.00"),
        )
        self.url = reverse("alternar_favorito")

    def alternar(self, tipo="curtida", produto="brinquedo", produto_id=None):
        """Marca pelo caminho de quem realmente faz aquilo.

        Curtir é exclusivo do aplicativo, então a curtida vai pela API,
        levando a chave do aparelho no cabeçalho -- é assim que o app
        conversa com o servidor. A lista de desejos continua valendo em
        qualquer lugar e usa a rota do site.
        """
        corpo = {
            "tipo": tipo,
            "produto": produto,
            "id": produto_id or self.brinquedo.pk,
        }

        if tipo == "curtida":
            return self.client.post(
                reverse("api:favoritos_alternar"),
                data=corpo,
                content_type="application/json",
                **self.cabecalho_do_aparelho(),
            )

        return self.client.post(
            self.url,
            data=corpo,
            content_type="application/json",
        )

    def cabecalho_do_aparelho(self):
        """O app manda a chave no cabeçalho; o site, em cookie.

        Sem cookie definido pelo teste, vale a chave padrão: o aparelho
        de verdade gera a dele uma vez, na instalação, e repete sempre --
        chave nova a cada chamada faria toda curtida parecer de um
        aparelho diferente.
        """
        chave = self.client.cookies.get(COOKIE_DISPOSITIVO)
        return {"HTTP_X_DISPOSITIVO": chave.value if chave else DISPOSITIVO_A}


class CurtidaSemLoginTests(FavoritoBaseTests):

    def test_visitante_curte_sem_estar_logado(self):
        resposta = self.alternar()

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertTrue(dados["marcado"])
        self.assertEqual(dados["curtidas"], 1)
        self.assertFalse(dados["logado"])
        self.assertEqual(Favorito.objects.count(), 1)

    def test_primeira_marcacao_no_site_grava_o_cookie_do_aparelho(self):
        resposta = self.alternar(tipo="desejo")

        self.assertIn(COOKIE_DISPOSITIVO, resposta.cookies)
        self.assertEqual(len(resposta.cookies[COOKIE_DISPOSITIVO].value), 32)

    def test_aplicativo_recebe_a_chave_do_aparelho_na_resposta(self):
        """O app guarda a chave e a repete; não há cookie para ele."""
        resposta = self.alternar()

        self.assertEqual(resposta.json()["dispositivo"], DISPOSITIVO_A)

    def test_curtir_de_novo_desfaz(self):
        self.alternar()
        dados = self.alternar().json()

        self.assertFalse(dados["marcado"])
        self.assertEqual(dados["curtidas"], 0)
        self.assertEqual(Favorito.objects.count(), 0)

    def test_um_por_aparelho_mesmo_com_varias_chamadas(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A

        self.alternar()   # marca
        self.alternar()   # desmarca
        self.alternar()   # marca de novo

        self.assertEqual(
            Favorito.objects.filter(tipo=Favorito.Tipo.CURTIDA).count(),
            1,
        )

    def test_aparelhos_diferentes_contam_separado(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar()

        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_B
        dados = self.alternar().json()

        self.assertEqual(dados["curtidas"], 2)

    def test_produto_inexistente_nao_cria_registro(self):
        resposta = self.alternar(produto_id=99999)

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(Favorito.objects.count(), 0)

    def test_tipo_invalido_e_recusado(self):
        resposta = self.alternar(tipo="cutucada")

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Favorito.objects.count(), 0)

    def test_peca_de_reposicao_tambem_recebe_curtida(self):
        dados = self.alternar(
            produto="peca",
            produto_id=self.peca.pk,
        ).json()

        self.assertTrue(dados["marcado"])
        self.assertEqual(
            Favorito.objects.filter(peca=self.peca).count(),
            1,
        )


class CurtidaComContaTests(FavoritoBaseTests):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="cliente",
            password="senha-forte-123",
            first_name="Marina",
        )
        # Sem telefone o middleware manda completar o perfil e nenhuma
        # rota do site responde -- inclusive a de curtida.
        perfil = self.user.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])

    def test_conta_vale_uma_curtida_em_qualquer_aparelho(self):
        self.client.force_login(self.user)

        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar()

        # Mesma conta, outro celular: continua sendo uma curtida só.
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_B
        dados = self.alternar().json()

        self.assertFalse(dados["marcado"])
        self.assertEqual(dados["curtidas"], 0)

    def test_login_leva_o_que_estava_no_aparelho(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar()
        self.alternar(tipo="desejo")

        migrados = migrar_dispositivo_para_conta(self.user, DISPOSITIVO_A)

        self.assertEqual(migrados, 2)
        self.assertEqual(
            Favorito.objects.filter(usuario=self.user).count(),
            2,
        )
        self.assertFalse(
            Favorito.objects.filter(usuario__isnull=True).exists()
        )

    def test_migracao_nao_duplica_o_que_a_conta_ja_tinha(self):
        Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=self.brinquedo,
            usuario=self.user,
            dispositivo=DISPOSITIVO_B,
        )
        Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=self.brinquedo,
            dispositivo=DISPOSITIVO_A,
        )

        migrar_dispositivo_para_conta(self.user, DISPOSITIVO_A)

        self.assertEqual(
            Favorito.objects.filter(brinquedo=self.brinquedo).count(),
            1,
        )

    def test_entrar_pelo_formulario_de_login_migra_sozinho(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")

        self.client.post(
            reverse("login"),
            {"username": "cliente", "password": "senha-forte-123"},
        )

        self.assertEqual(
            Favorito.objects.filter(usuario=self.user).count(),
            1,
        )


class ListaDesejosTests(FavoritoBaseTests):

    def test_pagina_abre_para_visitante_e_mostra_o_que_ele_guardou(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")
        self.alternar(tipo="desejo", produto="peca", produto_id=self.peca.pk)

        resposta = self.client.get(reverse("lista_desejos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Cama elástica 3m")
        self.assertContains(resposta, "Rede de proteção 3m")
        self.assertEqual(resposta.context["total_desejos"], 2)

    def test_lista_de_outro_aparelho_nao_aparece(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")

        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_B
        resposta = self.client.get(reverse("lista_desejos"))

        self.assertEqual(resposta.context["total_desejos"], 0)

    def test_curtir_nao_enche_a_lista_de_desejos(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="curtida")

        resposta = self.client.get(reverse("lista_desejos"))

        self.assertEqual(resposta.context["total_desejos"], 0)
        self.assertEqual(resposta.context["total_curtidas"], 1)


class CatalogoTests(FavoritoBaseTests):
    """Os corações do catálogo vêm pintados do servidor."""

    def test_catalogo_mostra_curtidas_do_app_e_o_botao_de_desejo(self):
        """No site a curtida é número; a ação disponível é guardar."""
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="curtida")

        resposta = self.client.get(reverse("brinquedos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(self.brinquedo.pk, resposta.context["fav_curtidos"])
        self.assertNotIn(self.brinquedo.pk, resposta.context["fav_desejados"])

        # Coração: só leitura, com o total do aplicativo.
        self.assertContains(
            resposta,
            f'data-favorito-total="brinquedo-{self.brinquedo.pk}"',
        )
        self.assertNotContains(resposta, 'data-favorito="curtida"')
        # Guardar continua sendo uma ação do site.
        self.assertContains(resposta, 'data-favorito="desejo"')

    def test_catalogo_de_pecas_mostra_o_total_de_curtidas(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(produto="peca", produto_id=self.peca.pk)

        resposta = self.client.get(reverse("pecas_reposicao"))

        cartao = resposta.context["cartoes_pecas"][0]
        self.assertTrue(cartao["curtido"])
        self.assertEqual(cartao["curtidas"], 1)

    def test_detalhe_do_brinquedo_traz_o_estado_do_visitante(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")

        resposta = self.client.get(
            reverse("brinquedo_detalhe", args=[self.brinquedo.pk])
        )

        self.assertTrue(resposta.context["favorito"]["desejado"])
        self.assertFalse(resposta.context["favorito"]["curtido"])


class FavoritoAppTests(FavoritoBaseTests):
    """O aplicativo manda a chave no cabeçalho, não em cookie."""

    def test_app_curte_pelo_cabecalho_do_aparelho(self):
        resposta = self.client.post(
            reverse("api:favoritos_alternar"),
            data={
                "tipo": "curtida",
                "produto": "brinquedo",
                "id": self.brinquedo.pk,
            },
            content_type="application/json",
            HTTP_X_DISPOSITIVO=DISPOSITIVO_A,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["marcado"])
        self.assertEqual(resposta.json()["dispositivo"], DISPOSITIVO_A)

        favorito = Favorito.objects.get()
        self.assertEqual(favorito.dispositivo, DISPOSITIVO_A)
        self.assertEqual(favorito.origem, Favorito.Origem.APP)

    def test_app_lista_o_que_o_aparelho_guardou(self):
        self.client.post(
            reverse("api:favoritos_alternar"),
            data={"tipo": "desejo", "produto": "peca", "id": self.peca.pk},
            content_type="application/json",
            HTTP_X_DISPOSITIVO=DISPOSITIVO_A,
        )

        resposta = self.client.get(
            reverse("api:favoritos"),
            HTTP_X_DISPOSITIVO=DISPOSITIVO_A,
        )

        dados = resposta.json()
        self.assertEqual(dados["total_desejos"], 1)
        self.assertEqual(
            dados["lista_desejos"]["pecas"][0]["nome"],
            "Rede de proteção 3m",
        )

    def test_catalogo_do_app_devolve_o_total_de_curtidas(self):
        self.client.post(
            reverse("api:favoritos_alternar"),
            data={
                "tipo": "curtida",
                "produto": "brinquedo",
                "id": self.brinquedo.pk,
            },
            content_type="application/json",
            HTTP_X_DISPOSITIVO=DISPOSITIVO_A,
        )

        resposta = self.client.get(
            reverse("api:brinquedo_detalhe", args=[self.brinquedo.pk])
        )

        self.assertEqual(resposta.json()["curtidas"], 1)


class EstadoDoVisitanteTests(FavoritoBaseTests):
    """A home é cacheada: o card sai neutro e o JS pergunta o estado.

    Sem este endereço, marcar o card no servidor faria a lista de uma
    pessoa aparecer para as outras, que é o preço de um HTML compartilhado
    entre todos os visitantes.
    """

    def test_devolve_o_que_o_aparelho_guardou(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")
        self.alternar(tipo="desejo", produto="peca", produto_id=self.peca.pk)

        dados = self.client.get(reverse("meus_favoritos")).json()

        self.assertTrue(dados["ok"])
        self.assertEqual(dados["desejo"]["brinquedo"], [self.brinquedo.pk])
        self.assertEqual(dados["desejo"]["peca"], [self.peca.pk])
        self.assertEqual(dados["total_desejos"], 2)

    def test_visitante_novo_recebe_lista_vazia_sem_ganhar_cookie(self):
        """Quem só passou pela home não precisa sair com chave de aparelho."""
        resposta = self.client.get(reverse("meus_favoritos"))

        self.assertEqual(resposta.json()["total_desejos"], 0)
        self.assertNotIn(COOKIE_DISPOSITIVO, resposta.cookies)

    def test_lista_de_outro_aparelho_nao_vaza(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")

        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_B
        dados = self.client.get(reverse("meus_favoritos")).json()

        self.assertEqual(dados["desejo"]["brinquedo"], [])


class CardsDoSiteTests(FavoritoBaseTests):
    """O coração e o marcador aparecem onde o cliente escolhe produto."""

    def test_vitrine_da_loja_traz_curtidas_e_marcador(self):
        self.brinquedo.exibir_na_loja = True
        self.brinquedo.save(update_fields=["exibir_na_loja"])
        self.alternar(tipo="curtida")

        resposta = self.client.get(reverse("loja"))

        self.assertEqual(resposta.status_code, 200)
        cartao = [
            item for item in resposta.context["itens_loja"]
            if item["tipo"] == "brinquedo"
        ][0]
        self.assertEqual(cartao["fav_curtidas"], 1)
        self.assertContains(resposta, 'data-favorito="desejo"')

    def test_pagina_da_categoria_traz_o_total_de_curtidas(self):
        from .models import CategoriasBrinquedos

        categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Infláveis",
        )
        self.brinquedo.categorias_brinquedos.add(categoria)
        self.alternar(tipo="curtida")

        resposta = self.client.get(
            reverse("categoria_detalhe", args=[categoria.pk])
        )

        item = resposta.context["page_obj"].object_list[0]
        self.assertEqual(item.total_curtidas, 1)
        self.assertContains(
            resposta,
            f'data-favorito-total="brinquedo-{self.brinquedo.pk}"',
        )


class ProgramaDePontosNaListaTests(FavoritoBaseTests):

    def test_lista_mostra_a_meta_e_o_que_falta(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO_A
        self.alternar(tipo="desejo")

        resposta = self.client.get(reverse("lista_desejos"))

        self.assertContains(resposta, "Programa de pontos")
        self.assertContains(resposta, "Baixar o aplicativo")

    def test_cliente_logado_ve_o_saldo(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(
            username="cliente-pontos",
            password="senha-forte-123",
        )
        perfil = user.perfil
        perfil.telefone = "(11) 91234-5678"
        perfil.save(update_fields=["telefone"])
        self.client.force_login(user)

        resposta = self.client.get(reverse("lista_desejos"))

        self.assertTrue(resposta.context["pontos"]["logado"])
        self.assertContains(resposta, "Você tem 0 pontos")
