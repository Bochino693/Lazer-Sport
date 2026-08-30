"""A página de orçamento que o cliente abre, e a resposta que ele dá.

O que estes testes protegem, em ordem de importância:

  * um orçamento não vaza por outro — o token é a única chave;
  * rascunho não tem página, porque a equipe ainda está montando;
  * a resposta é registrada UMA vez: aprovada, a proposta vira comprovante
    e para de aceitar mudança, inclusive por quem tem o link;
  * proposta vencida não vira venda por descuido.

São as regras que sustentam a decisão de a página ser aberta por link, sem
login. Se alguma cair, o link deixa de ser seguro.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from sistema_interno.models import (
    AceiteOrcamento,
    Cliente,
    EnderecoCliente,
    ItemOrcamento,
    Orcamento,
)

from .models import Brinquedos, CategoriasBrinquedos


class OrcamentoPublicoTests(TestCase):

    def setUp(self):
        self.categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Infláveis",
        )
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Tobogã inflável",
            descricao="Tobogã de 6 metros",
            valor_brinquedo=Decimal("520.00"),
            avaliacao=Decimal("5.00"),
            voltz="220",
        )
        self.brinquedo.categorias_brinquedos.add(self.categoria)

        self.orcamento = Orcamento.objects.create(
            nome_cliente="Fulano de Tal",
            contato="11 90000-0000",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() + timedelta(days=7),
            frete=Decimal("100.00"),
            desconto=Decimal("50.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            descricao="Tobogã inflável",
            brinquedo=self.brinquedo,
            quantidade=2,
            valor_unitario=Decimal("520.00"),
        )

    def url(self, orcamento=None):
        alvo = orcamento or self.orcamento
        return reverse("orcamento_publico", args=[alvo.token])

    def aprovar(self, nome="Fulano", **extras):
        dados = {
            "decisao": "aprovar",
            "nome": nome,
            "documento_assinante": "529.982.247-25",
            "consentimento_aceite": "1",
        }
        dados.update(extras)
        return self.client.post(self.url(), dados)

    # ------------------------------------------------------------ leitura
    def test_pagina_mostra_itens_e_total(self):
        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tobogã inflável")
        self.assertContains(resposta, "Fulano de Tal")
        # 2 x 520 = 1040, + 100 de frete, - 50 de desconto = 1.090,00
        self.assertContains(resposta, "1.090,00")

    def test_link_chega_ao_whatsapp_como_cartao_e_nao_endereco_cru(self):
        """No WhatsApp o link vira cartão com foto, número e total.

        Link cru numa conversa parece golpe, e o cliente não abre. As
        marcas Open Graph são o mais perto de "mandar a imagem junto"
        que uma conversa aberta pelo próprio atendente permite -- o
        WhatsApp desenha a prévia sozinho, a partir da página.
        """
        resposta = self.client.get(self.url())
        html = resposta.content.decode()

        self.assertIn('property="og:title"', html)
        self.assertIn(f"Proposta nº {self.orcamento.pk}", html)
        self.assertIn('property="og:image"', html)
        # Sem foto no item, entra a logo: cartão sem imagem nenhuma some
        # na conversa.
        self.assertIn('property="og:url"', html)
        self.assertIn(self.orcamento.token, html)
        # A prévia não desfaz o noindex: quem não tem o link continua
        # sem chegar à proposta por busca.
        self.assertIn('content="noindex, nofollow"', html)

    def test_o_link_nao_tem_caractere_que_o_whatsapp_come(self):
        """O token só usa letra e número, e isso é o conserto de um bug real.

        O link chegava quebrado do outro lado. `secrets.token_urlsafe`
        sorteia também "_", e o WhatsApp lê "_texto_" como itálico: um
        token com dois sublinhados era entregue em itálico e SEM eles, o
        cliente clicava e caía num 404. Não é só o WhatsApp -- qualquer
        conversa que formate texto faz o mesmo.
        """
        for _ in range(60):
            token = Orcamento.objects.create(
                nome_cliente="Teste do alfabeto",
            ).token
            self.assertEqual(len(token), 32)
            self.assertTrue(
                token.isalnum() and token.isascii(),
                f"token com caractere que o WhatsApp formata: {token!r}",
            )

    def test_tokens_antigos_continuam_abrindo(self):
        """Trocar o alfabeto não invalida proposta já enviada.

        Existem links com "_" e "-" em conversas de clientes. O campo só
        guarda texto: o que mudou foi como se sorteia um token novo.
        """
        self.orcamento.token = "_uYepJ8hBAuIU2MpPjdVlgR4j5tPBTrD"
        self.orcamento.save(update_fields=["token"])

        self.assertEqual(self.client.get(self.url()).status_code, 200)

    @override_settings(DEBUG=False, SITE_URL="https://www.lazersport.com.br")
    def test_o_cartao_aponta_para_o_endereco_canonico(self):
        """og:url é o endereço publicado, não o host de quem abriu.

        O WhatsApp guarda o cartão pela og:url. Com o host da vez ali,
        a mesma proposta virava dois cartões -- um deles apontando para
        um endereço que o servidor de prévia do aplicativo não alcança.
        """
        html = self.client.get(
            self.url(), HTTP_HOST="lazersport.onrender.com",
        ).content.decode()

        esperado = (
            f"https://www.lazersport.com.br{self.orcamento.caminho_publico}"
        )
        self.assertIn(f'property="og:url" content="{esperado}"', html)
        self.assertIn(f'rel="canonical" href="{esperado}"', html)
        self.assertNotIn("lazersport.onrender.com", html)
        # A imagem do cartão também precisa ser absoluta: caminho
        # relativo o WhatsApp não busca.
        self.assertIn(
            'property="og:image" content="https://www.lazersport.com.br/', html,
        )

    def test_o_contato_do_documento_e_o_da_empresa(self):
        """A proposta leva o contato da EMPRESA, nunca o pessoal.

        Um documento comercial com o telefone errado manda o cliente
        ligar para a pessoa errada, e quem atende não sabe de qual
        proposta se trata. O padrão é o mesmo número e o mesmo e-mail que
        o site inteiro mostra; a hospedagem pode trocar por variável de
        ambiente.
        """
        from django.conf import settings

        resposta = self.client.get(self.url())
        html = resposta.content.decode()

        self.assertEqual(settings.ORCAMENTO_TELEFONE, settings.EMPRESA_TELEFONE)
        self.assertEqual(settings.ORCAMENTO_EMAIL, settings.EMPRESA_EMAIL)
        self.assertIn(settings.EMPRESA_TELEFONE, html)
        self.assertIn(settings.EMPRESA_EMAIL, html)
        # E a dúvida vira conversa no WhatsApp da empresa.
        self.assertIn(f"wa.me/{settings.EMPRESA_WHATSAPP}", html)

    @override_settings(
        ORCAMENTO_TELEFONE="(11) 4000-1000",
        ORCAMENTO_EMAIL="vendas@lazersport.com",
    )
    def test_cadastro_antigo_nao_sobrepoe_o_contato_configurado(self):
        """Era o contrário: um telefone gravado no cadastro de endereço
        ganhava da configuração, e a proposta saía com ele."""
        from core.models import EnderecoEmpresa

        EnderecoEmpresa.objects.create(
            telefone="(11) 95388-7201", ativo=True,
        )

        html = self.client.get(self.url()).content.decode()

        self.assertIn("(11) 4000-1000", html)
        self.assertNotIn("95388-7201", html)

    def test_documento_mostra_cliente_pagamento_envio_e_decisao(self):
        cliente = Cliente.objects.create(
            nome_cliente="R3 Boteco Original Ltda",
            tipo=Cliente.Tipo.COMERCIAL,
            documento="48.646.647/0001-11",
            telefone="(11) 95388-7201",
            email="compras@example.com",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="300",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )
        self.orcamento.cliente = cliente
        self.orcamento.forma_pagamento = "Pix"
        self.orcamento.forma_envio = "Transportadora"
        self.orcamento.save(update_fields=[
            "cliente", "forma_pagamento", "forma_envio",
        ])

        resposta = self.client.get(self.url())

        self.assertContains(resposta, "Dados do cliente")
        self.assertContains(resposta, "48.646.647/0001-11")
        self.assertContains(resposta, "Praça da Sé")
        self.assertContains(resposta, "Pix")
        self.assertContains(resposta, "Transportadora")
        self.assertContains(resposta, "Aprovar proposta")
        self.assertContains(resposta, "Recusar")

    def test_token_desconhecido_nao_existe(self):
        resposta = self.client.get(
            reverse("orcamento_publico", args=["token-que-nunca-foi-gerado"])
        )
        self.assertEqual(resposta.status_code, 404)

    def test_rascunho_nao_tem_pagina(self):
        """A equipe ainda está montando: para quem tem o link, não existe."""
        self.orcamento.status = Orcamento.Status.RASCUNHO
        self.orcamento.save(update_fields=["status"])

        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_cada_orcamento_tem_token_proprio(self):
        outro = Orcamento.objects.create(
            nome_cliente="Sicrano",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
        )
        self.assertNotEqual(outro.token, self.orcamento.token)

        # e um não abre a página do outro
        resposta = self.client.get(self.url(outro))
        self.assertNotContains(resposta, "Fulano de Tal")

    # ----------------------------------------------------------- resposta
    def test_aprovar_registra_nome_e_muda_situacao(self):
        resposta = self.aprovar("Fulano de Tal")

        self.assertEqual(resposta.status_code, 302)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)
        self.assertEqual(self.orcamento.respondido_por, "Fulano de Tal")
        self.assertIsNotNone(self.orcamento.respondido_em)
        aceite = AceiteOrcamento.objects.get(orcamento=self.orcamento)
        self.assertEqual(aceite.assinante_documento, "52998224725")
        self.assertEqual(len(aceite.proposta_hash), 64)

    def test_aprovacao_exige_documento_valido_e_consentimento(self):
        resposta = self.client.post(self.url(), {
            "decisao": "aprovar",
            "nome": "Fulano",
            "documento_assinante": "111.111.111-11",
        })
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(AceiteOrcamento.objects.exists())
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_aprovacao_do_cliente_publica_o_cadastro_no_mapa(self):
        """Aprovar a proposta liga a chave do mapa no próprio cliente.

        Nada de rede aqui: publicar deixou de copiar o cadastro para uma
        segunda tabela, e por isso não passa mais por geocodificação.
        """
        cliente = Cliente.objects.create(
            nome_cliente="Colégio Sol",
            telefone="(11) 99999-1111",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="20",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )
        self.orcamento.cliente = cliente
        self.orcamento.save(update_fields=["cliente"])

        self.aprovar("Responsável do colégio")

        cliente.refresh_from_db()
        self.assertTrue(cliente.publicar_no_mapa)
        self.assertEqual(cliente.endereco_principal.cidade, "São Paulo")

    def test_recusar_guarda_o_motivo(self):
        self.client.post(
            self.url(),
            {
                "decisao": "recusar",
                "nome": "Fulano de Tal",
                "motivo": "Ficou acima do orçamento da festa.",
            },
        )

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.RECUSADO)
        self.assertEqual(
            self.orcamento.motivo_recusa,
            "Ficou acima do orçamento da festa.",
        )

    def test_aprovar_nao_guarda_motivo_de_recusa(self):
        """Motivo é da recusa. Aprovando, some — senão fica pendurado."""
        self.orcamento.motivo_recusa = "sobra de uma recusa anterior"
        self.orcamento.save(update_fields=["motivo_recusa"])

        self.aprovar("Fulano", motivo="qualquer coisa")

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.motivo_recusa, "")

    def test_sem_nome_nao_registra(self):
        resposta = self.client.post(self.url(), {"decisao": "aprovar", "nome": "  "})

        self.assertEqual(resposta.status_code, 400)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_decisao_invalida_nao_registra(self):
        resposta = self.client.post(
            self.url(),
            {"decisao": "talvez", "nome": "Fulano"},
        )

        self.assertEqual(resposta.status_code, 400)
        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_resposta_e_definitiva(self):
        """Aprovada, a proposta não vira recusada por um segundo clique."""
        self.aprovar()
        self.client.post(self.url(), {"decisao": "recusar", "nome": "Fulano"})

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.APROVADO)

    def test_vencido_nao_aceita_resposta(self):
        self.orcamento.validade = timezone.localdate() - timedelta(days=1)
        self.orcamento.save(update_fields=["validade"])

        self.aprovar()

        self.orcamento.refresh_from_db()
        self.assertEqual(self.orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)

    def test_vencido_ainda_pode_ser_consultado(self):
        """Vencer tira o botão, não a proposta: o cliente ainda quer ver."""
        self.orcamento.validade = timezone.localdate() - timedelta(days=1)
        self.orcamento.save(update_fields=["validade"])

        resposta = self.client.get(self.url())

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Tobogã inflável")
        self.assertContains(resposta, "validade desta proposta terminou")

    def test_pagina_respondida_nao_mostra_botao(self):
        self.aprovar()

        resposta = self.client.get(self.url())

        self.assertContains(resposta, "Resposta registrada")
        self.assertContains(resposta, "Comprovante")
        self.assertContains(resposta, "529.***.***-25")
        self.assertNotContains(resposta, "Aprovar proposta")

    def test_pagina_nao_e_indexada(self):
        """Proposta comercial no Google seria vazamento de preço."""
        resposta = self.client.get(self.url())
        self.assertContains(resposta, "noindex")


class OrcamentoModeloTests(TestCase):
    """Regras que vivem no modelo, sem passar pela página."""

    def test_marcar_enviado_carimba_uma_vez(self):
        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)

        orcamento.marcar_enviado()
        primeira = orcamento.enviado_em

        self.assertEqual(orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertIsNotNone(primeira)

        # reenviar não reescreve a data: o que interessa é quando a
        # proposta saiu pela primeira vez
        orcamento.marcar_enviado()
        self.assertEqual(orcamento.enviado_em, primeira)

    def test_dias_para_vencer_distingue_sem_validade_de_vence_hoje(self):
        sem = Orcamento.objects.create(nome_cliente="Sem validade")
        hoje = Orcamento.objects.create(
            nome_cliente="Vence hoje",
            validade=timezone.localdate(),
        )

        self.assertIsNone(sem.dias_para_vencer)
        self.assertEqual(hoje.dias_para_vencer, 0)

    def test_desconto_maior_que_tudo_nao_deixa_total_negativo(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Fulano",
            desconto=Decimal("9999.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Cama elástica",
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )

        self.assertEqual(orcamento.total, Decimal("0.00"))

    def test_item_nao_vem_do_catalogo_e_da_producao_ao_mesmo_tempo(self):
        from django.core.exceptions import ValidationError

        from sistema_interno.models import ProdutoInterno

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Piscina de bolinhas",
            descricao="3x3",
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        produto = ProdutoInterno.objects.create(nome="Piscina — versão fábrica")

        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        item = ItemOrcamento(
            orcamento=orcamento,
            descricao="Piscina",
            brinquedo=brinquedo,
            produto=produto,
            quantidade=1,
            valor_unitario=Decimal("340.00"),
        )

        with self.assertRaises(ValidationError):
            item.clean()
