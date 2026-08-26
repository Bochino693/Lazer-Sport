"""Pontos, metas e a loja de cupons do aplicativo.

O que estes testes protegem:

  * curtir vale ponto, e **descurtir devolve o ponto** -- sem isso,
    curtir e descurtir em sequência seria uma fábrica de pontos e a loja
    viraria piada em uma tarde;
  * meta cumprida não se perde: tirar itens da lista depois não apaga o
    que já foi conquistado;
  * o mesmo fato nunca paga duas vezes;
  * quem curtiu antes de entrar na conta recebe os pontos no login;
  * o resgate exige saldo, respeita estoque e gera um cupom de verdade,
    exclusivo do cliente e com validade;
  * curtir pelo site é recusado: a curtida é o que dá valor ao app.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import pontos
from .favoritos import COOKIE_DISPOSITIVO, migrar_dispositivo_para_conta
from .models import (
    Brinquedos,
    CarteiraPontos,
    Cupom,
    Favorito,
    PontoGanho,
    RecompensaCupom,
    ResgateCupom,
)


DISPOSITIVO = "c" * 32


def brinquedo(nome, valor="300.00"):
    return Brinquedos.objects.create(
        nome_brinquedo=nome,
        descricao=nome,
        valor_brinquedo=Decimal(valor),
        avaliacao=Decimal("5.00"),
        voltz="110",
    )


class PontosBaseTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="cliente",
            password="senha-forte-123",
            email="cliente@example.com",
        )
        perfil = self.user.perfil
        perfil.telefone = "(11) 91234-5678"
        perfil.save(update_fields=["telefone"])

        self.brinquedos = [brinquedo(f"Brinquedo {i}") for i in range(1, 9)]

    def curtir(self, item):
        favorito = Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=item,
            usuario=self.user,
            dispositivo=DISPOSITIVO,
            origem=Favorito.Origem.APP,
        )
        pontos.sincronizar(self.user)
        return favorito

    def desejar(self, item):
        favorito = Favorito.objects.create(
            tipo=Favorito.Tipo.DESEJO,
            brinquedo=item,
            usuario=self.user,
            dispositivo=DISPOSITIVO,
        )
        pontos.sincronizar(self.user)
        return favorito

    def saldo(self):
        return pontos.carteira_de(self.user).saldo


class GanhoDePontosTests(PontosBaseTests):

    def test_curtida_vale_cinco_pontos(self):
        self.curtir(self.brinquedos[0])

        self.assertEqual(self.saldo(), 5)

    def test_tres_curtidas_valem_quinze(self):
        for item in self.brinquedos[:3]:
            self.curtir(item)

        self.assertEqual(self.saldo(), 15)

    def test_descurtir_devolve_o_ponto(self):
        favorito = self.curtir(self.brinquedos[0])
        self.assertEqual(self.saldo(), 5)

        favorito.delete()
        pontos.sincronizar(self.user)

        self.assertEqual(self.saldo(), 0)

    def test_curtir_e_descurtir_em_sequencia_nao_acumula(self):
        """O teste que impede a fábrica de pontos."""
        for _ in range(6):
            favorito = self.curtir(self.brinquedos[0])
            favorito.delete()
            pontos.sincronizar(self.user)

        self.assertEqual(self.saldo(), 0)

    def test_sincronizar_duas_vezes_nao_paga_de_novo(self):
        self.curtir(self.brinquedos[0])
        pontos.sincronizar(self.user)
        pontos.sincronizar(self.user)

        self.assertEqual(self.saldo(), 5)
        self.assertEqual(
            PontoGanho.objects.filter(
                usuario=self.user,
                origem=PontoGanho.Origem.CURTIDA,
            ).count(),
            1,
        )

    def test_cinco_itens_na_lista_liberam_a_meta_de_trinta(self):
        for item in self.brinquedos[:5]:
            self.desejar(item)

        self.assertEqual(self.saldo(), 30)

    def test_lista_com_quatro_itens_ainda_nao_paga(self):
        for item in self.brinquedos[:4]:
            self.desejar(item)

        self.assertEqual(self.saldo(), 0)

    def test_meta_cumprida_nao_e_perdida_ao_tirar_item(self):
        favoritos = [self.desejar(item) for item in self.brinquedos[:5]]
        self.assertEqual(self.saldo(), 30)

        favoritos[0].delete()
        favoritos[1].delete()
        pontos.sincronizar(self.user)

        self.assertEqual(self.saldo(), 30)

    def test_curtidas_e_metas_somam(self):
        for item in self.brinquedos[:5]:
            self.desejar(item)          # 30 pela meta
        for item in self.brinquedos[:2]:
            self.curtir(item)           # 10 pelas curtidas

        self.assertEqual(self.saldo(), 40)

    def test_meta_de_dez_curtidas_entra_junto_das_curtidas(self):
        for item in self.brinquedos[:8]:
            self.curtir(item)
        extras = [brinquedo(f"Extra {i}") for i in range(2)]
        for item in extras:
            self.curtir(item)

        # 10 curtidas x 5 = 50, mais a meta de 10 curtidas = 40.
        self.assertEqual(self.saldo(), 90)

    def test_carteira_guarda_o_total_ja_ganho(self):
        for item in self.brinquedos[:3]:
            self.curtir(item)

        carteira = CarteiraPontos.objects.get(usuario=self.user)
        self.assertEqual(carteira.saldo, 15)
        self.assertEqual(carteira.total_ganho, 15)


class PontosNoLoginTests(PontosBaseTests):

    def test_quem_curtiu_antes_de_entrar_recebe_no_login(self):
        Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=self.brinquedos[0],
            dispositivo=DISPOSITIVO,
            origem=Favorito.Origem.APP,
        )
        Favorito.objects.create(
            tipo=Favorito.Tipo.CURTIDA,
            brinquedo=self.brinquedos[1],
            dispositivo=DISPOSITIVO,
            origem=Favorito.Origem.APP,
        )

        migrar_dispositivo_para_conta(self.user, DISPOSITIVO)

        self.assertEqual(self.saldo(), 10)


class ProgressoTests(PontosBaseTests):

    def test_progresso_mostra_o_que_falta_para_a_proxima_meta(self):
        for item in self.brinquedos[:3]:
            self.desejar(item)

        dados = pontos.progresso(self.user)
        meta = [m for m in dados["metas"] if m["chave"] == "desejo:5"][0]

        self.assertEqual(meta["alcancado"], 3)
        self.assertEqual(meta["falta"], 2)
        self.assertEqual(meta["percentual"], 60)
        self.assertFalse(meta["concluida"])

    def test_meta_concluida_aparece_completa(self):
        for item in self.brinquedos[:5]:
            self.desejar(item)

        dados = pontos.progresso(self.user)
        meta = [m for m in dados["metas"] if m["chave"] == "desejo:5"][0]

        self.assertTrue(meta["concluida"])
        self.assertEqual(meta["percentual"], 100)

    def test_visitante_sem_conta_ve_zero_sem_quebrar(self):
        dados = pontos.progresso(None)

        self.assertEqual(dados["saldo"], 0)
        self.assertFalse(dados["logado"])


class ResgateTests(PontosBaseTests):

    def setUp(self):
        super().setUp()
        self.recompensa = RecompensaCupom.objects.create(
            nome="10% de desconto",
            custo_pontos=50,
            desconto_percentual=Decimal("10.00"),
            validade_dias=30,
        )

    def dar_pontos(self, quantidade):
        PontoGanho.objects.create(
            usuario=self.user,
            origem=PontoGanho.Origem.AJUSTE,
            chave=f"teste:{quantidade}",
            pontos=quantidade,
            descricao="Crédito de teste",
        )
        pontos._recalcular_carteira(self.user)

    def test_resgate_gera_cupom_de_verdade(self):
        self.dar_pontos(60)

        resgate = pontos.resgatar(self.user, self.recompensa.id)

        self.assertIsInstance(resgate, ResgateCupom)
        cupom = Cupom.objects.get(pk=resgate.cupom_id)
        self.assertEqual(cupom.desconto_percentual, Decimal("10.00"))
        self.assertTrue(cupom.codigo.startswith("LS"))
        self.assertGreater(cupom.data_expiracao, timezone.now())

    def test_cupom_resgatado_e_exclusivo_de_quem_resgatou(self):
        self.dar_pontos(60)

        resgate = pontos.resgatar(self.user, self.recompensa.id)

        self.assertFalse(resgate.cupom.todos_usuarios)
        self.assertEqual(
            list(resgate.cupom.cliente.all()),
            [self.user.perfil],
        )

    def test_resgate_desconta_do_saldo(self):
        self.dar_pontos(60)

        pontos.resgatar(self.user, self.recompensa.id)

        self.assertEqual(self.saldo(), 10)

    def test_sem_saldo_nao_resgata(self):
        self.dar_pontos(20)

        with self.assertRaises(pontos.ErroDeResgate) as erro:
            pontos.resgatar(self.user, self.recompensa.id)

        self.assertIn("Faltam 30", str(erro.exception))
        self.assertEqual(Cupom.objects.count(), 0)

    def test_recompensa_esgotada_nao_resgata(self):
        self.recompensa.estoque = 0
        self.recompensa.save(update_fields=["estoque"])
        self.dar_pontos(100)

        with self.assertRaises(pontos.ErroDeResgate):
            pontos.resgatar(self.user, self.recompensa.id)

    def test_resgate_baixa_o_estoque(self):
        self.recompensa.estoque = 2
        self.recompensa.save(update_fields=["estoque"])
        self.dar_pontos(100)

        pontos.resgatar(self.user, self.recompensa.id)

        self.recompensa.refresh_from_db()
        self.assertEqual(self.recompensa.estoque, 1)

    def test_sincronizar_nao_apaga_o_gasto_do_resgate(self):
        """Recalcular os pontos automáticos não pode devolver o que foi gasto."""
        self.dar_pontos(60)
        pontos.resgatar(self.user, self.recompensa.id)

        pontos.sincronizar(self.user)

        self.assertEqual(self.saldo(), 10)

    def test_dois_resgates_gastam_duas_vezes(self):
        self.dar_pontos(120)

        pontos.resgatar(self.user, self.recompensa.id)
        pontos.resgatar(self.user, self.recompensa.id)

        self.assertEqual(self.saldo(), 20)
        self.assertEqual(Cupom.objects.count(), 2)

    def test_codigos_de_cupom_nao_se_repetem(self):
        self.dar_pontos(300)

        codigos = {
            pontos.resgatar(self.user, self.recompensa.id).cupom.codigo
            for _ in range(5)
        }

        self.assertEqual(len(codigos), 5)


class CurtidaSomenteNoAppTests(PontosBaseTests):

    def test_site_recusa_curtida_e_explica(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO

        resposta = self.client.post(
            reverse("alternar_favorito"),
            data={
                "tipo": "curtida",
                "produto": "brinquedo",
                "id": self.brinquedos[0].pk,
            },
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(resposta.json()["somente_app"])
        self.assertIn("aplicativo", resposta.json()["erro"])
        self.assertEqual(Favorito.objects.count(), 0)

    def test_site_continua_guardando_na_lista_de_desejos(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = DISPOSITIVO

        resposta = self.client.post(
            reverse("alternar_favorito"),
            data={
                "tipo": "desejo",
                "produto": "brinquedo",
                "id": self.brinquedos[0].pk,
            },
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["marcado"])

    def test_aplicativo_curte_normalmente(self):
        resposta = self.client.post(
            reverse("api:favoritos_alternar"),
            data={
                "tipo": "curtida",
                "produto": "brinquedo",
                "id": self.brinquedos[0].pk,
            },
            content_type="application/json",
            HTTP_X_DISPOSITIVO=DISPOSITIVO,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["marcado"])


class ApiDoAplicativoTests(PontosBaseTests):

    def setUp(self):
        super().setUp()
        self.recompensa = RecompensaCupom.objects.create(
            nome="15% de desconto",
            custo_pontos=100,
            desconto_percentual=Decimal("15.00"),
        )

    def test_resumo_exige_conta(self):
        resposta = self.client.get(reverse("api:pontos"))

        self.assertEqual(resposta.status_code, 401)

    def test_resumo_traz_saldo_metas_e_extrato(self):
        self.client.force_login(self.user)
        self.curtir(self.brinquedos[0])

        dados = self.client.get(reverse("api:pontos")).json()

        self.assertEqual(dados["saldo"], 5)
        self.assertEqual(dados["pontos_por_curtida"], 5)
        self.assertTrue(dados["metas"])
        self.assertEqual(len(dados["extrato"]), 1)

    def test_loja_abre_sem_login_para_mostrar_o_premio(self):
        resposta = self.client.get(reverse("api:cupons_loja"))

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["saldo"], 0)
        self.assertEqual(dados["recompensas"][0]["faltam"], 100)
        self.assertFalse(dados["recompensas"][0]["pode_resgatar"])

    def test_resgate_pela_api_devolve_o_codigo(self):
        self.client.force_login(self.user)
        PontoGanho.objects.create(
            usuario=self.user,
            origem=PontoGanho.Origem.AJUSTE,
            chave="teste",
            pontos=120,
        )
        pontos._recalcular_carteira(self.user)

        resposta = self.client.post(
            reverse("api:cupons_resgatar"),
            data={"recompensa": self.recompensa.id},
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertTrue(dados["cupom"]["codigo"].startswith("LS"))
        self.assertEqual(dados["saldo"], 20)

    def test_resgate_sem_saldo_explica_o_que_falta(self):
        self.client.force_login(self.user)

        resposta = self.client.post(
            reverse("api:cupons_resgatar"),
            data={"recompensa": self.recompensa.id},
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Faltam", resposta.json()["erro"])

    def test_meus_cupons_lista_o_que_foi_resgatado(self):
        self.client.force_login(self.user)
        PontoGanho.objects.create(
            usuario=self.user,
            origem=PontoGanho.Origem.AJUSTE,
            chave="teste",
            pontos=120,
        )
        pontos._recalcular_carteira(self.user)
        pontos.resgatar(self.user, self.recompensa.id)

        dados = self.client.get(reverse("api:cupons_meus")).json()

        self.assertEqual(len(dados["cupons"]), 1)
        self.assertEqual(dados["cupons"][0]["recompensa"], "15% de desconto")
