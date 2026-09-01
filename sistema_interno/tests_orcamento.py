"""Orçamento visto de dentro: catálogo, cadastro na hora e envio.

O painel responde no subdomínio interno, então todo teste aqui usa
HTTP_HOST="interno.testserver" — sem isso o SubdomainURLMiddleware não
liga `is_interno` e a view devolve um desvio para a loja, que é o mesmo
que o usuário veria.
"""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Brinquedos, CategoriaPeca, CategoriasBrinquedos, PecasReposicao

from .models import (
    AtividadeOrcamento,
    AvaliacaoBlocoOrcamento,
    Cliente,
    ItemOrcamento,
    Orcamento,
    ProdutoInterno,
)
from .permissoes import atribuir_funcoes


def aprovar_blocos(orcamento, avaliador):
    AvaliacaoBlocoOrcamento.objects.bulk_create([
        AvaliacaoBlocoOrcamento(
            orcamento=orcamento,
            bloco=bloco,
            status=AvaliacaoBlocoOrcamento.Status.APROVADO,
            avaliador=avaliador,
            avaliado_em=timezone.now(),
        )
        for bloco in AvaliacaoBlocoOrcamento.Bloco.values
    ])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class OrcamentoInternoTests(TestCase):

    URL = "/orcamentos/"
    #: Espelha `OrcamentosInnerView.POR_PAGINA`; conferido logo abaixo.
    POR_PAGINA_ESPERADA = 25

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Infláveis",
        )
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica",
            imagem_brinquedo="imagens_brinquedos/cama-elastica.jpg",
            descricao="Cama elástica 3m",
            valor_brinquedo=Decimal("280.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # ------------------------------------------------------- paginação
    def test_lista_vem_por_pagina(self):
        """A tela não era paginada e a resposta crescia com o histórico.

        Cada linha carrega os itens, o texto pronto do WhatsApp e a
        proposta inteira em JSON para o modal -- com algumas centenas de
        propostas virava megabytes de HTML, e no servidor a resposta
        estourava o tempo do gunicorn (o 502 ao abrir Orçamentos).
        """
        for i in range(OrcamentoInternoTests.POR_PAGINA_ESPERADA + 7):
            Orcamento.objects.create(
                nome_cliente=f"Cliente {i}",
                contato="(11) 90000-0000",
            )

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        pagina = resposta.context["page_obj"]

        self.assertEqual(
            len(pagina.object_list), OrcamentoInternoTests.POR_PAGINA_ESPERADA
        )
        self.assertTrue(pagina.has_next())

    def test_os_numeros_do_topo_somam_o_filtro_inteiro(self):
        """Se mudassem ao virar de página, não responderiam nada.

        A soma sai de uma subconsulta em SQL; este teste compara com o
        cálculo em Python (`Orcamento.total`), que é a definição.
        """
        aprovados = []
        for i in range(OrcamentoInternoTests.POR_PAGINA_ESPERADA + 5):
            orcamento = Orcamento.objects.create(
                nome_cliente=f"Fechado {i}",
                contato="(11) 90000-0000",
                status=Orcamento.Status.APROVADO,
                frete=Decimal("120.00"),
                desconto=Decimal("30.00"),
            )
            ItemOrcamento.objects.create(
                orcamento=orcamento,
                descricao="Locação",
                quantidade=2,
                valor_unitario=Decimal("310.50"),
            )
            aprovados.append(orcamento)

        esperado = sum((o.total for o in aprovados), Decimal("0.00"))

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.context["total_aprovado"], esperado)
        self.assertEqual(resposta.context["quantidade_aprovado"], len(aprovados))
        # E a página mostra menos linhas do que o número somado.
        self.assertLess(
            len(resposta.context["page_obj"].object_list), len(aprovados)
        )

    def test_o_desconto_maior_que_o_total_nao_vira_numero_negativo(self):
        """`Orcamento.total` trava em zero; a soma em SQL precisa travar também."""
        orcamento = Orcamento.objects.create(
            nome_cliente="Desconto grande",
            contato="(11) 90000-0000",
            status=Orcamento.Status.APROVADO,
            desconto=Decimal("900.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Locação",
            quantidade=1,
            valor_unitario=Decimal("100.00"),
        )

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(orcamento.total, Decimal("0.00"))
        self.assertEqual(resposta.context["total_aprovado"], Decimal("0.00"))

    def test_a_busca_por_texto_de_item_nao_infla_o_total(self):
        """Buscar por item entra por join, e join multiplica linha.

        Somar por cima desse join contaria o mesmo item várias vezes -- o
        total apareceria inflado justamente quando alguém filtrasse.
        """
        orcamento = Orcamento.objects.create(
            nome_cliente="Com três itens",
            contato="(11) 90000-0000",
            status=Orcamento.Status.APROVADO,
        )
        for i in range(3):
            ItemOrcamento.objects.create(
                orcamento=orcamento,
                descricao=f"Cama elástica {i}",
                quantidade=1,
                valor_unitario=Decimal("100.00"),
            )

        resposta = self.client.get(
            self.URL, {"q": "Cama elástica"}, HTTP_HOST="interno.testserver"
        )

        self.assertEqual(resposta.context["total_aprovado"], orcamento.total)
        self.assertEqual(resposta.context["total_orcamentos"], 1)

    def test_a_pagina_do_teste_acompanha_a_da_view(self):
        """Se a view mudar o tamanho da página, os testes acima sabem."""
        from .views_gestao import OrcamentosInnerView

        self.assertEqual(
            OrcamentosInnerView.POR_PAGINA, self.POR_PAGINA_ESPERADA
        )

    # ------------------------------------------------ situação ao vivo
    def test_a_situacao_da_proposta_pode_ser_lida_sem_recarregar(self):
        """O cliente responde na página pública; o painel precisa ver.

        Antes a mudança só aparecia ao recarregar -- e como a sessão dura
        o dia inteiro, na prática só ao sair e entrar de novo. Um
        "aprovado" que demora meia hora para aparecer é um cliente
        esperando meia hora por um retorno que já podia ter saído.
        """
        orcamento = Orcamento.objects.create(
            nome_cliente="Festa da Ana",
            contato="(11) 90000-0000",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
        )

        # O cliente responde, como responderia pela página pública.
        orcamento.status = Orcamento.Status.APROVADO
        orcamento.respondido_por = "Ana"
        orcamento.respondido_em = timezone.now()
        orcamento.save()

        resposta = self.client.get(
            "/orcamentos/estados/",
            {"ids": str(orcamento.pk)},
            HTTP_HOST="interno.testserver",
        )
        estado = resposta.json()["orcamentos"][str(orcamento.pk)]

        self.assertEqual(estado["status"], Orcamento.Status.APROVADO)
        self.assertEqual(estado["rotulo"], "Aprovado")
        # A cor é a MESMA que o template usa: se divergirem, a linha muda
        # de cor ao atualizar e ninguém entende por quê.
        self.assertEqual(estado["cor"], "success")
        self.assertEqual(estado["respondido_por"], "Ana")
        self.assertTrue(estado["respondido_em"])

    def test_a_lista_de_situacoes_ignora_lixo_e_nao_estoura(self):
        """Os ids vêm de um endereço, então chegam como qualquer coisa."""
        resposta = self.client.get(
            "/orcamentos/estados/",
            {"ids": "abc, ,-1, 9' OR 1=1,"},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["orcamentos"], {})

    def test_a_situacao_respeita_quem_ve_o_que(self):
        """Quem só enxerga a própria carteira não descobre a do colega.

        Sem `limitar_orcamentos` aqui, bastaria pedir a situação por id
        para contornar a regra que a lista aplica.
        """
        alheio = Orcamento.objects.create(
            nome_cliente="Do colega",
            status=Orcamento.Status.APROVADO,
            origem=Orcamento.Origem.AMBULANTE,
        )
        vendedor = User.objects.create_user(
            username="ambulante", password="senha-segura", is_staff=True
        )
        atribuir_funcoes(vendedor, ["vendas"])
        self.client.force_login(vendedor)

        visiveis = self.client.get(
            "/orcamentos/estados/",
            {"ids": str(alheio.pk)},
            HTTP_HOST="interno.testserver",
        ).json()["orcamentos"]

        from .permissoes import limitar_orcamentos
        esperado = limitar_orcamentos(
            vendedor, Orcamento.objects.filter(pk=alheio.pk)
        ).exists()

        self.assertEqual(str(alheio.pk) in visiveis, esperado)

    # -------------------------------------------------------- catálogo
    def test_tela_busca_catalogo_sob_demanda(self):
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 200)
        # O catálogo inteiro não é embutido na página: mil itens continuam
        # sendo uma tela leve. O navegador consulta somente quando digita.
        self.assertNotContains(resposta, "opcoesItens")
        self.assertContains(resposta, "Novo brinquedo")

        busca = self.client.get(
            "/orcamentos/itens/buscar/",
            {"q": "cama elastica"},
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(busca.status_code, 200)
        opcoes = busca.json()["opcoes"]
        self.assertEqual(opcoes[0]["valor"], f"b:{self.brinquedo.id}")
        self.assertEqual(opcoes[0]["rotulo"], "Cama elástica")
        self.assertTrue(opcoes[0]["imagem"])

    def test_busca_nunca_devolve_catalogo_inteiro(self):
        Brinquedos.objects.bulk_create([
            Brinquedos(
                nome_brinquedo=f"Brinquedo festa {numero:03d}",
                descricao="Item para festa",
                avaliacao=Decimal("0.00"),
                voltz="bivolt",
            )
            for numero in range(40)
        ])

        resposta = self.client.get(
            "/orcamentos/itens/buscar/",
            {"q": "festa"},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertLessEqual(len(resposta.json()["opcoes"]), 24)

    def test_clientes_tambem_sao_buscados_sob_demanda(self):
        cliente = Cliente.objects.create(
            nome_cliente="Escola Girassol",
            telefone="(11) 95555-4444",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
        )

        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertNotContains(pagina, "opcoesClientes")

        resposta = self.client.get(
            "/orcamentos/clientes/buscar/",
            {"q": "Girassol"},
            HTTP_HOST="interno.testserver",
        )
        opcoes = resposta.json()["opcoes"]
        self.assertEqual(opcoes[0]["valor"], str(cliente.id))

    def test_catalogo_inclui_o_que_nao_esta_na_loja(self):
        """A vitrine é um recorte; orçamento alcança o cadastro inteiro."""
        fora = Brinquedos.objects.create(
            nome_brinquedo="Tobogã antigo",
            descricao="Fora da vitrine",
            avaliacao=Decimal("0.00"),
            voltz="220",
            exibir_na_loja=False,
        )
        resposta = self.client.get(
            "/orcamentos/itens/buscar/",
            {"q": "Tobogã antigo"},
            HTTP_HOST="interno.testserver",
        )
        valores = [item["valor"] for item in resposta.json()["opcoes"]]
        self.assertIn(f"b:{fora.id}", valores)

    def test_item_salvo_fica_ligado_ao_brinquedo(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Cama elástica","brinquedo":"%s",'
                '"quantidade":"2","valor_unitario":"280,00"}]' % self.brinquedo.id
            ),
        })

        self.assertEqual(resposta.status_code, 200)
        item = ItemOrcamento.objects.get()
        self.assertEqual(item.brinquedo, self.brinquedo)
        self.assertIsNone(item.produto)
        self.assertEqual(item.subtotal, Decimal("560.00"))

    def test_salvar_orcamento_registra_novidade_para_os_colegas(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Cliente compartilhado",
            "itens": (
                '[{"descricao":"Cama elástica","brinquedo":"%s",'
                '"quantidade":"1","valor_unitario":"280,00"}]'
                % self.brinquedo.id
            ),
        })

        self.assertEqual(resposta.status_code, 200)
        atividade = AtividadeOrcamento.objects.get()
        self.assertEqual(atividade.autor, self.gestor)
        self.assertEqual(atividade.tipo, AtividadeOrcamento.Tipo.CRIADO)
        self.assertEqual(atividade.cliente, "Cliente compartilhado")

    def test_tabela_do_pc_agrupa_dados_sem_esmagar_data_e_revisao(self):
        from pathlib import Path

        template = Path(
            "sistema_interno/templates/orcamentos_inner.html"
        ).read_text(encoding="utf-8")
        css = Path(
            "sistema_interno/static/interno/interno_modern.css"
        ).read_text(encoding="utf-8")

        self.assertIn("<th>Proposta</th>", template)
        self.assertIn("<th>Acompanhamento</th>", template)
        self.assertIn('class="ls-review-item', template)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", css)
        self.assertIn("white-space:nowrap", css)

    def test_salva_valores_e_condicoes_no_formato_brasileiro(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "frete": "1.250,90",
            "desconto": "50,00",
            "forma_pagamento": "50% na entrada e 50% na entrega",
            "forma_envio": "Transportadora",
            "itens": (
                '[{"descricao":"Cama elástica","brinquedo":"%s",'
                '"quantidade":"2","valor_unitario":"280,00"}]'
                % self.brinquedo.id
            ),
        })

        self.assertEqual(resposta.status_code, 200)
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.frete, Decimal("1250.90"))
        self.assertEqual(orcamento.desconto, Decimal("50.00"))
        self.assertEqual(orcamento.forma_envio, "Transportadora")

    def test_tela_declara_mascaras_e_quantidade_numerica(self):
        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertContains(resposta, 'data-mascara="cep"')
        self.assertContains(resposta, 'data-mascara="telefone"')
        self.assertContains(resposta, 'data-mascara="moeda"')
        self.assertContains(resposta, 'type="number" class="form-control form-control-sm text-end ls-item-quantidade"')

    def test_aceite_eletronico_tem_uma_unica_classe_de_modelo(self):
        """Duas declarações registravam o modelo duas vezes no Django."""
        codigo = Path("sistema_interno/models.py").read_text(encoding="utf-8")
        self.assertEqual(codigo.count("class AceiteOrcamento(models.Model):"), 1)

    def test_linha_com_catalogo_e_producao_fica_so_com_o_catalogo(self):
        """São origens exclusivas: gravar as duas criaria item inválido."""
        produto = ProdutoInterno.objects.create(nome="Cama — versão fábrica")

        self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Cama","brinquedo":"%s","produto":"%s",'
                '"quantidade":"1","valor_unitario":"280,00"}]'
                % (self.brinquedo.id, produto.id)
            ),
        })

        item = ItemOrcamento.objects.get()
        self.assertEqual(item.brinquedo, self.brinquedo)
        self.assertIsNone(item.produto)

    def test_item_sem_catalogo_ainda_aceita_produto_de_producao(self):
        produto = ProdutoInterno.objects.create(nome="Máquina de algodão doce")

        self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Algodão doce","produto":"%s",'
                '"quantidade":"1","valor_unitario":"150,00"}]' % produto.id
            ),
        })

        item = ItemOrcamento.objects.get()
        self.assertEqual(item.produto, produto)
        self.assertIsNone(item.brinquedo)

    def test_item_pode_vir_das_pecas_de_reposicao(self):
        peca = PecasReposicao.objects.create(
            nome="Mola de cama elástica",
            descricao_peca="Mola galvanizada",
            preco_venda=Decimal("12.50"),
        )

        resposta = self.post({
            "action": "save",
            "nome_cliente": "Fulano",
            "status": Orcamento.Status.RASCUNHO,
            "itens": (
                '[{"descricao":"Mola galvanizada","peca":"%s",'
                '"quantidade":"8","valor_unitario":"12,50"}]' % peca.id
            ),
        })

        self.assertEqual(resposta.status_code, 200)
        item = ItemOrcamento.objects.get()
        self.assertEqual(item.peca, peca)
        self.assertIsNone(item.brinquedo)
        self.assertIsNone(item.produto)

    # ------------------------------------------- cadastrar sem sair daqui
    def test_cadastra_brinquedo_novo_e_devolve_para_a_linha(self):
        resposta = self.post({
            "action": "brinquedo_novo",
            "nome": "Piscina de bolinhas",
            "valor": "340,00",
            "categoria": self.categoria.id,
        })

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")

        novo = Brinquedos.objects.get(nome_brinquedo="Piscina de bolinhas")
        self.assertEqual(dados["brinquedo"]["id"], novo.id)
        self.assertEqual(dados["brinquedo"]["valor"], "340,00")
        self.assertEqual(novo.valor_brinquedo, Decimal("340.00"))
        self.assertIn(self.categoria, novo.categorias_brinquedos.all())

    def test_brinquedo_novo_nasce_fora_da_vitrine(self):
        """Publicar é decisão de quem cuida do site, com foto e texto."""
        self.post({"action": "brinquedo_novo", "nome": "Touro mecânico"})

        novo = Brinquedos.objects.get(nome_brinquedo="Touro mecânico")
        self.assertFalse(novo.ativo)
        self.assertFalse(novo.exibir_na_loja)

    def test_nao_duplica_brinquedo_existente(self):
        # A diferença de caixa é só em letra ASCII de propósito. O SQLite
        # destes testes dobra maiúscula/minúscula apenas em ASCII, então
        # "ELÁSTICA" x "elástica" não casaria aqui -- no PostgreSQL da
        # produção casa. Testar com "C"/"c" verifica a regra sem depender
        # de qual banco está rodando.
        resposta = self.post({"action": "brinquedo_novo", "nome": "cama elástica"})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_brinquedo_novo_exige_nome(self):
        resposta = self.post({"action": "brinquedo_novo", "nome": "   "})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_cadastra_peca_nova_e_devolve_para_a_linha(self):
        categoria = CategoriaPeca.objects.create(nome_categoria_peca="Cama elástica")
        resposta = self.post({
            "action": "peca_nova",
            "nome": "Rede de proteção",
            "preco_venda": "89,90",
            "preco_fornecedor": "50,00",
            "categoria": categoria.id,
            "descricao": "Rede preta para 3,05 m",
        })

        self.assertEqual(resposta.status_code, 200)
        peca = PecasReposicao.objects.get(nome="Rede de proteção")
        self.assertEqual(resposta.json()["peca"]["id"], peca.id)
        self.assertEqual(peca.preco_venda, Decimal("89.90"))
        self.assertFalse(peca.ativo)
        self.assertIn(categoria, peca.categoria_peca.all())

    # -------------------------------------------------------- envio
    def _orcamento_com_item(self):
        orcamento = Orcamento.objects.create(nome_cliente="Fulano")
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Cama elástica",
            brinquedo=self.brinquedo,
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )
        aprovar_blocos(orcamento, self.gestor)
        return orcamento

    def test_avaliacoes_pendentes_nao_bloqueiam_o_envio_ao_cliente(self):
        orcamento = Orcamento.objects.create(nome_cliente="Aguardando revisão")
        ItemOrcamento.objects.create(
            orcamento=orcamento,
            descricao="Cama elástica",
            brinquedo=self.brinquedo,
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )
        AvaliacaoBlocoOrcamento.objects.create(
            orcamento=orcamento,
            bloco=AvaliacaoBlocoOrcamento.Bloco.COMERCIAL,
            status=AvaliacaoBlocoOrcamento.Status.APROVADO,
            avaliador=self.gestor,
        )

        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertContains(pagina, f'data-enviar="{orcamento.id}"')
        self.assertNotContains(pagina, f'value="{orcamento.id}" disabled')

        resposta = self.post({"action": "enviar", "id": orcamento.id})

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(orcamento.token, resposta.json()["link"])
        self.assertFalse(
            orcamento.avaliacoes_blocos.filter(bloco="financeiro").exists()
        )

    # -------------------------------------------------------- exclusão
    def test_exclusao_de_rascunho_exige_confirmacao_escrita(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Rascunho duplicado",
            responsavel=self.gestor,
        )

        sem_confirmar = self.post({"action": "delete", "id": orcamento.id})

        self.assertEqual(sem_confirmar.status_code, 400)
        self.assertIn("CONFIRMAR", sem_confirmar.json()["msg"])
        self.assertTrue(Orcamento.objects.filter(pk=orcamento.pk).exists())

        confirmado = self.post({
            "action": "delete",
            "id": orcamento.id,
            "confirmacao_exclusao": "confirmar",
        })

        self.assertEqual(confirmado.status_code, 200)
        self.assertFalse(Orcamento.objects.filter(pk=orcamento.pk).exists())

    def test_vendas_so_exclui_o_proprio_rascunho(self):
        vendedor = User.objects.create_user(
            username="vendedor-orcamento",
            password="senha-segura",
        )
        atribuir_funcoes(vendedor, ["vendas"])
        proprio = Orcamento.objects.create(
            nome_cliente="Meu rascunho",
            responsavel=vendedor,
        )
        alheio = Orcamento.objects.create(
            nome_cliente="Rascunho de outra pessoa",
            responsavel=self.gestor,
        )
        self.client.force_login(vendedor)

        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertContains(pagina, f'data-excluir="{proprio.id}"')
        self.assertNotContains(pagina, f'data-excluir="{alheio.id}"')
        self.assertContains(pagina, 'name="confirmacao_exclusao"')

        proprio_resposta = self.post({
            "action": "delete",
            "id": proprio.id,
            "confirmacao_exclusao": "ConFiRmAr",
        })
        alheio_resposta = self.post({
            "action": "delete",
            "id": alheio.id,
            "confirmacao_exclusao": "CONFIRMAR",
        })

        self.assertEqual(proprio_resposta.status_code, 200)
        self.assertEqual(alheio_resposta.status_code, 403)
        self.assertFalse(Orcamento.objects.filter(pk=proprio.pk).exists())
        self.assertTrue(Orcamento.objects.filter(pk=alheio.pk).exists())

    ESTADOS_DE_HISTORICO = (
        Orcamento.Status.AGUARDANDO_RESPOSTA,
        Orcamento.Status.APROVADO,
        Orcamento.Status.RECUSADO,
        Orcamento.Status.EXPIRADO,
    )

    def _propostas_de_historico(self, responsavel=None):
        return [
            Orcamento.objects.create(
                nome_cliente=f"Histórico {status}",
                status=status,
                responsavel=responsavel or self.gestor,
            )
            for status in self.ESTADOS_DE_HISTORICO
        ]

    def test_propostas_fora_do_rascunho_ficam_no_historico(self):
        """A regra do dia a dia: proposta enviada não some da linha do tempo.

        Conferida com quem a regra protege -- uma pessoa do Comercial. O
        superusuário tem a palavra final e é o teste seguinte; se este
        rodasse com ele, mediria a exceção achando que media a regra.
        """
        comercial = User.objects.create_user(
            username="vendas-hist", password="x", email="c@example.com",
        )
        atribuir_funcoes(comercial, ["vendas"])
        self.client.force_login(comercial)

        protegidos = self._propostas_de_historico(responsavel=comercial)

        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        for orcamento in protegidos:
            with self.subTest(status=orcamento.status):
                self.assertNotContains(
                    pagina,
                    f'data-excluir="{orcamento.id}"',
                )
                resposta = self.post({
                    "action": "delete",
                    "id": orcamento.id,
                    "confirmacao_exclusao": "CONFIRMAR",
                })
                self.assertEqual(resposta.status_code, 403)
                self.assertTrue(
                    Orcamento.objects.filter(pk=orcamento.pk).exists()
                )

    def test_o_superusuario_apaga_o_que_a_regra_protege_e_fica_registrado(self):
        """Quem responde pela empresa precisa poder limpar um erro.

        Sem isso, cadastro errado ficava para sempre ou alguém ia mexer no
        banco por fora -- que é o caminho onde as coisas somem sem ninguém
        saber. O registro é a outra metade: histórico apagado em silêncio
        é pior do que histórico errado.
        """
        from .models import ExclusaoRegistrada

        protegidos = self._propostas_de_historico()
        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        for orcamento in protegidos:
            with self.subTest(status=orcamento.status):
                # O botão aparece, e avisa que ali se passa por cima.
                self.assertContains(pagina, f'data-excluir="{orcamento.id}"')

                resposta = self.post({
                    "action": "delete",
                    "id": orcamento.id,
                    "confirmacao_exclusao": "CONFIRMAR",
                    "motivo_exclusao": "duplicado no cadastro",
                })

                self.assertEqual(resposta.status_code, 200)
                self.assertFalse(
                    Orcamento.objects.filter(pk=orcamento.pk).exists()
                )

                rastro = ExclusaoRegistrada.objects.get(
                    identificacao__startswith=f"#{orcamento.pk} —"
                )
                self.assertTrue(rastro.forcada)
                self.assertEqual(rastro.autor, self.gestor)
                self.assertEqual(rastro.motivo, "duplicado no cadastro")
                self.assertIn("Situação:", rastro.resumo)

    def test_o_rascunho_apagado_pela_regra_normal_nao_conta_como_forcado(self):
        """`forcada` separa "apagou rascunho" de "apagou histórico".

        Se marcasse tudo, o registro perderia a utilidade: ninguém
        procuraria a exclusão que importa no meio de centenas de rotina.
        """
        from .models import ExclusaoRegistrada

        rascunho = Orcamento.objects.create(
            nome_cliente="Rascunho comum", responsavel=self.gestor,
        )

        self.post({
            "action": "delete",
            "id": rascunho.pk,
            "confirmacao_exclusao": "CONFIRMAR",
        })

        rastro = ExclusaoRegistrada.objects.get(
            identificacao__startswith=f"#{rascunho.pk} —"
        )
        self.assertFalse(rastro.forcada)

    def test_a_proposta_com_aceite_eletronico_tambem_cede_ao_superusuario(self):
        """`on_delete=PROTECT` fazia a exclusão levantar em vez de acontecer.

        O aceite eletrônico protege o orçamento. Para o superusuário a
        corrente é desmontada -- e o registro diz o que foi junto, porque
        é justamente o que ninguém lembraria depois.
        """
        from .models import AceiteOrcamento, ExclusaoRegistrada

        orcamento = self._orcamento_com_item()
        orcamento.marcar_enviado()
        AceiteOrcamento.objects.create(
            orcamento=orcamento,
            assinante_nome="Ana Cliente",
            assinante_documento="52998224725",
            proposta_hash="x" * 64,
            ip_hash="y" * 64,
            navegador_hash="z" * 64,
        )

        resposta = self.post({
            "action": "delete",
            "id": orcamento.pk,
            "confirmacao_exclusao": "CONFIRMAR",
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Orcamento.objects.filter(pk=orcamento.pk).exists())
        self.assertFalse(AceiteOrcamento.objects.exists())

        rastro = ExclusaoRegistrada.objects.get(
            identificacao__startswith=f"#{orcamento.pk} —"
        )
        self.assertIn("Removidos junto por dependência", rastro.resumo)
        self.assertIn("AceiteOrcamento", rastro.resumo)

    def test_enviar_devolve_o_link_do_site_publico(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({"action": "enviar", "id": orcamento.id})
        dados = resposta.json()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(orcamento.token, dados["link"])
        # o link é do site do cliente, nunca do subdomínio interno
        self.assertNotIn("interno.", dados["link"])

        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertIsNotNone(orcamento.enviado_em)

        # O endereço devolvido não é apenas uma string bonita: a própria
        # aplicação precisa reconhecer o token e entregar o documento.
        pagina = self.client.get(urlsplit(dados["link"]).path)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Aprovar proposta")

    def test_gerar_link_devolve_contatos_do_cadastro_vinculado(self):
        cliente = Cliente.objects.create(
            nome_cliente="Leandro Almeida",
            telefone="(11) 95388-7201",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
            email="leandro@example.com",
        )
        orcamento = self._orcamento_com_item()
        orcamento.nome_cliente = ""
        orcamento.cliente = cliente
        orcamento.save(update_fields=["nome_cliente", "cliente"])

        resposta = self.post({"action": "enviar", "id": orcamento.id})
        dados = resposta.json()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(dados["destinatario"], "Leandro Almeida")
        self.assertEqual(dados["whatsapp"], "(11) 95388-7201")
        self.assertEqual(dados["email"], "leandro@example.com")
        self.assertIn(orcamento.token, dados["link"])

    def test_botao_enviar_ja_carrega_id_e_contatos_do_cliente(self):
        cliente = Cliente.objects.create(
            nome_cliente="Leandro Almeida",
            telefone="(11) 95388-7201",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
            email="leandro@example.com",
        )
        orcamento = self._orcamento_com_item()
        orcamento.nome_cliente = ""
        orcamento.cliente = cliente
        orcamento.save(update_fields=["nome_cliente", "cliente"])

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertContains(
            resposta,
            f'data-orcamento-id="{orcamento.id}"',
        )
        self.assertContains(resposta, 'data-whatsapp="(11) 95388-7201"')
        self.assertContains(resposta, 'data-email="leandro@example.com"')

    def test_whatsapp_explica_confirmacao_e_tem_fallback_para_popup_bloqueado(self):
        """A conversa sai do WhatsApp de quem está logado no aparelho.

        Ela abre no próprio toque, com o endereço já montado na página --
        único momento em que o navegador autoriza abrir uma janela. Quando
        ainda assim ela é bloqueada, a saída é um botão que a pessoa toca,
        e NÃO trocar a guia do painel pela do WhatsApp: no computador isso
        levava o operador para o WhatsApp Web e ele perdia a proposta de
        vista no meio do envio.
        """
        self._orcamento_com_item()

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        # A saída existe e está escrita na tela.
        self.assertContains(resposta, "Abrir conversa no WhatsApp")
        self.assertContains(resposta, "Confirme o envio dentro do WhatsApp")

        # O endereço da conversa é montado no próprio navegador, sem
        # esperar resposta nenhuma -- era a espera que fazia o botão ficar
        # "calculando" e a janela ser bloqueada.
        self.assertContains(resposta, "function montarConversa(")
        self.assertContains(resposta, "Painel.whatsapp.abrir(telefone, mensagem)")
        self.assertContains(resposta, "Painel.whatsapp.alvo()")

        # O botão verde é DE PROPÓSITO a versão web: é a saída de quem não
        # tem o aplicativo instalado. Mandá-lo de volta ao aplicativo faria
        # dele um botão que não faz nada.
        self.assertContains(resposta, "data-whatsapp-web")

    def test_trocar_de_cliente_nao_recarrega_o_whatsapp(self):
        """Navegar a aba derruba o WhatsApp Web e o obriga a subir de novo.

        Ele é um aplicativo de página única: `window.open` com
        `/send?phone=` é NAVEGAÇÃO DE DOCUMENTO, e cada envio recomeçava
        reconexão, decifragem e redesenho de todas as conversas -- o
        "carregando as mensagens" que aparecia a cada cliente.

        Não dá para trocar a conversa por dentro: a página é de outro
        domínio. Então o caminho confiável no PC é uma única aba Web;
        copiar a mensagem permite trocar o cliente por dentro dela.
        """
        from pathlib import Path

        painel = Path(
            "sistema_interno/static/interno/painel.js"
        ).read_text(encoding="utf-8")

        # 1. Mesmo cliente: só traz a aba para a frente.
        self.assertIn("motivo: \"mesma-conversa\"", painel)
        self.assertIn("function focarAba()", painel)

        # 2. O atalho sem recarregar: copiar a mensagem e trocar a
        #    conversa dentro do WhatsApp, que não sai da página.
        self.assertIn("copiar: function (mensagem, telefone)", painel)
        self.assertIn('"https://web.whatsapp.com/"', painel)

        # Nunca se cria uma aba vazia para tentar encontrar a anterior.
        # Se ela não existe, o destino precisa ser uma URL real.
        self.assertNotIn('global.open("", NOME_ABA_WHATSAPP)', painel)
        self.assertNotIn("whatsapp://send?phone=", painel)

        # A aba continua sendo uma só, com nome estável.
        self.assertIn('var NOME_ABA_WHATSAPP = "ls-whatsapp-web"', painel)
        self.assertIn("https://web.whatsapp.com/send?phone=", painel)
        # No celular, wa.me continua levando ao aplicativo.
        self.assertIn('"https://wa.me/" + digitos', painel)

    def test_a_conversa_aberta_e_lembrada_sem_guardar_caminho_nativo(self):
        """O cliente é lembrado, mas o PC sempre usa WhatsApp Web."""
        from pathlib import Path

        painel = Path(
            "sistema_interno/static/interno/painel.js"
        ).read_text(encoding="utf-8")

        self.assertIn('var CHAVE_CONVERSA = "ls:whatsapp:conversa"', painel)
        self.assertNotIn("CHAVE_CAMINHO", painel)
        # `localStorage` lança em janela anônima; nada disso pode derrubar
        # um envio.
        for funcao in ("function guardado(chave)", "function guardar(chave, valor)"):
            with self.subTest(funcao=funcao):
                trecho = painel[painel.index(funcao):]
                self.assertIn("catch (e)", trecho[:260])

    def test_gravacao_acorda_o_servidor_sem_repetir_post(self):
        from pathlib import Path

        painel = Path(
            "sistema_interno/static/interno/painel.js"
        ).read_text(encoding="utf-8")

        # `/pronto/`, e não `/healthz/`.
        #
        # O `healthz` responde sem tocar o banco -- e precisa ser assim,
        # porque é ele que a hospedagem usa para decidir se a instância
        # está viva. Mas acordar só o processo resolve metade: o primeiro
        # clique de quem volta vai consultar o banco, e abrir conexão
        # nova com o Supabase custa segundos. `/pronto/` faz um
        # `SELECT 1` e deixa a conexão quente. Ver `core.views.pronto`.
        self.assertIn('fetch("/pronto/?painel=1"', painel)
        self.assertIn("Painel.rede.post(destino", painel)
        self.assertIn("POST único", painel)

    def test_link_e_mensagem_ja_vem_prontos_no_botao_enviar(self):
        """A tela não depende de rede para mostrar o que compartilhar.

        Era isto que faltava: o modal pedia o link por POST ao abrir e,
        quando esse pedido tropeçava -- bastou uma tabela de histórico
        ainda não migrada no servidor --, aparecia "Link indisponível"
        num orçamento que estava perfeito.

        Vale para proposta JÁ ENVIADA, que é quando existe o que
        compartilhar. Rascunho é o teste seguinte.
        """
        orcamento = self._orcamento_com_item()
        orcamento.marcar_enviado()

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        html = resposta.content.decode()

        self.assertIn(f'data-link="', html)
        self.assertIn(orcamento.token, html)
        self.assertIn("data-mensagem=", html)
        # A mensagem levada ao WhatsApp traz o essencial da proposta.
        self.assertIn("Aqui é da Lazer &amp; Sport", html)

    def test_rascunho_nao_entrega_o_link_do_cliente(self):
        """A página do cliente recusa rascunho; o painel não pode oferecê-la.

        O endereço vinha pronto no botão desde sempre, e a janela de envio
        abria já com "Abrir página pública" apontando para ele. Quem
        conferia a proposta ANTES de mandar levava um 404 no rosto -- e a
        leitura óbvia era que o sistema tinha quebrado.

        Para conferir antes de enviar existe a prévia interna, que é do
        painel e abre rascunho. Ela continua no botão.
        """
        rascunho = self._orcamento_com_item()
        self.assertFalse(rascunho.publicado)

        html = self.client.get(
            self.URL, HTTP_HOST="interno.testserver",
        ).content.decode()

        self.assertNotIn(rascunho.token, html)
        self.assertIn(
            f"/orcamentos/{rascunho.pk}/previa/", html,
            "A prévia interna tem de continuar à mão: é ela que abre rascunho.",
        )

    def test_abrir_envio_publica_e_devolve_link_copiavel(self):
        """O botão Enviar precisa abrir a janela com um link que funcione."""
        rascunho = self._orcamento_com_item()

        resposta = self.post({
            "action": "enviar", "id": rascunho.pk, "canal": "preparar",
        })

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertIn(rascunho.token, dados["link"])
        self.assertIn(f"/orcamentos/{rascunho.pk}/previa/", dados["preview_url"])
        rascunho.refresh_from_db()
        self.assertEqual(rascunho.status, Orcamento.Status.AGUARDANDO_RESPOSTA)
        self.assertTrue(rascunho.enviado_em)
        # Preparar cria o endereço, mas não finge que WhatsApp, e-mail ou
        # cópia foram usados antes da escolha do operador.
        self.assertFalse(rascunho.envios.exists())

    def test_depois_de_enviada_o_link_aparece(self):
        enviada = self._orcamento_com_item()
        enviada.marcar_enviado()

        dados = self.post({
            "action": "enviar", "id": enviada.pk, "canal": "preparar",
        }).json()

        self.assertIn(enviada.token, dados["link"])

    def test_mensagem_da_proposta_tem_itens_total_e_link(self):
        from sistema_interno.views_gestao import OrcamentosInnerView

        orcamento = self._orcamento_com_item()
        texto = OrcamentosInnerView.mensagem_da_proposta(
            orcamento, "https://exemplo.com/orcamento/abc/"
        )

        self.assertIn(orcamento.destinatario, texto)
        self.assertIn(f"nº {orcamento.pk}", texto)
        self.assertIn("Total: R$", texto)
        self.assertIn("https://exemplo.com/orcamento/abc/", texto)

    def test_conversa_whatsapp_monta_o_endereco_com_ddi(self):
        from sistema_interno.views_gestao import OrcamentosInnerView

        url = OrcamentosInnerView.conversa_whatsapp("(11) 99999-8888", "oi")

        self.assertTrue(url.startswith("https://wa.me/5511999998888?text="))
        # Número curto demais não vira conversa: melhor botão sem link do
        # que abrir uma conversa com o número errado.
        self.assertEqual(OrcamentosInnerView.conversa_whatsapp("123", "oi"), "")

    def test_enviar_sem_id_devolve_erro_claro(self):
        resposta = self.post({"action": "enviar", "id": ""})

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("orçamento", resposta.json()["msg"].lower())
        self.assertNotIn("expected a number", resposta.json()["msg"].lower())

    @override_settings(DEBUG=False, SITE_URL="interno.lazersport.com.br/")
    def test_link_corrige_dominio_sem_protocolo_e_remove_interno(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({"action": "enviar", "id": orcamento.id})

        self.assertTrue(
            resposta.json()["link"].startswith(
                "https://lazersport.com.br/orcamento/"
            )
        )

    def test_previa_interna_abre_rascunho_sem_permitir_resposta(self):
        orcamento = self._orcamento_com_item()

        resposta = self.client.get(
            f"/orcamentos/{orcamento.pk}/previa/",
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Prévia interna")
        self.assertContains(resposta, "Cama elástica")
        self.assertNotContains(resposta, 'id="formDecisao"')

    def test_enviar_orcamento_vazio_e_recusado(self):
        """Link para uma proposta sem itens é constrangimento na frente do cliente."""
        vazio = Orcamento.objects.create(nome_cliente="Fulano")

        resposta = self.post({"action": "enviar", "id": vazio.id})

        self.assertEqual(resposta.status_code, 400)
        vazio.refresh_from_db()
        self.assertEqual(vazio.status, Orcamento.Status.RASCUNHO)

    def test_reenviar_nao_reescreve_a_data_de_envio(self):
        orcamento = self._orcamento_com_item()

        self.post({"action": "enviar", "id": orcamento.id})
        orcamento.refresh_from_db()
        primeira = orcamento.enviado_em

        self.post({"action": "enviar", "id": orcamento.id})
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.enviado_em, primeira)

    def test_enviar_por_whatsapp_devolve_conversa_pronta(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({
            "action": "enviar",
            "canal": "whatsapp",
            "whatsapp": "(11) 99999-8888",
            "id": orcamento.id,
        })

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["whatsapp_url"].startswith("https://wa.me/5511999998888"))
        self.assertIn(orcamento.token, dados["whatsapp_url"])
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.whatsapp_cliente, "(11) 99999-8888")

    def test_enviar_por_email_entrega_template_da_marca(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({
            "action": "enviar",
            "canal": "email",
            "email": "cliente@example.com",
            "id": orcamento.id,
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["cliente@example.com"])
        self.assertIn("Lazer & Sport", mail.outbox[0].subject)
        self.assertIn(orcamento.token, mail.outbox[0].alternatives[0].content)

    @override_settings(
        DEFAULT_FROM_EMAIL="Lazer & Sport <contato@lazersport.com.br>",
        EMAIL_RESPOSTA="vendas@lazersport.com.br",
    )
    def test_email_sai_com_a_marca_e_volta_para_quem_enviou(self):
        orcamento = self._orcamento_com_item()

        self.post({
            "action": "enviar",
            "canal": "email",
            "email": "cliente@example.com",
            "id": orcamento.id,
        })

        enviado = mail.outbox[0]
        self.assertEqual(
            enviado.from_email,
            "Lazer & Sport <contato@lazersport.com.br>",
        )
        # O atendente logado é o primeiro a receber a resposta.
        self.assertIn("vendas@lazersport.com.br", enviado.reply_to)

    def test_email_invalido_nao_marca_como_enviado(self):
        orcamento = self._orcamento_com_item()

        resposta = self.post({
            "action": "enviar",
            "canal": "email",
            "email": "email quebrado",
            "id": orcamento.id,
        })

        self.assertEqual(resposta.status_code, 400)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)

    # ------------------------------------------------------- a vencer
    def test_tela_separa_os_que_vencem_em_ate_tres_dias(self):
        perto = Orcamento.objects.create(
            nome_cliente="Vence logo",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() + timedelta(days=2),
        )
        longe = Orcamento.objects.create(
            nome_cliente="Tem tempo",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() + timedelta(days=20),
        )
        aprovado = Orcamento.objects.create(
            nome_cliente="Já fechou",
            status=Orcamento.Status.APROVADO,
            validade=timezone.localdate() + timedelta(days=1),
        )

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        vencendo = resposta.context["vencendo"]

        self.assertIn(perto, vencendo)
        self.assertNotIn(longe, vencendo)
        # proposta já aprovada não é cobrança pendente
        self.assertNotIn(aprovado, vencendo)

    # -------------------------------------------------------- acesso
    def test_colaborador_sem_gerencia_nao_entra(self):
        operador = User.objects.create_user(
            username="operador",
            password="senha-segura",
            is_staff=True,
        )
        atribuir_funcoes(operador, ["producao"])
        self.client.force_login(operador)

        resposta = self.client.get(self.URL, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("producao", resposta["Location"])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class RegistroDeEnvioTests(TestCase):
    """"O cliente disse que não recebeu" precisa ter onde ser conferido.

    Sem registro, ninguém responde se a proposta saiu, para qual endereço
    e o que o servidor de e-mail respondeu. Cada tentativa vira uma linha
    -- inclusive, e principalmente, as que falharam.
    """

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica",
            descricao="Cama elástica 3m",
            valor_brinquedo=Decimal("280.00"),
            avaliacao=Decimal("5.00"),
            voltz="110",
        )
        self.orcamento = Orcamento.objects.create(
            nome_cliente="Festa da Ana",
            whatsapp_cliente="(11) 99999-8888",
            email_cliente="ana@example.com",
        )
        ItemOrcamento.objects.create(
            orcamento=self.orcamento,
            descricao="Cama elástica",
            brinquedo=self.brinquedo,
            quantidade=1,
            valor_unitario=Decimal("280.00"),
        )
        aprovar_blocos(self.orcamento, self.gestor)

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_envio_por_whatsapp_fica_registrado(self):
        self.post({
            "action": "enviar",
            "canal": "whatsapp",
            "whatsapp": "(11) 99999-8888",
            "id": self.orcamento.pk,
        })

        envio = self.orcamento.envios.get()
        self.assertEqual(envio.canal, "whatsapp")
        self.assertEqual(envio.destino, "(11) 99999-8888")
        self.assertTrue(envio.sucesso)
        self.assertEqual(envio.responsavel, self.gestor)

    def test_envio_por_email_fica_registrado(self):
        self.post({
            "action": "enviar",
            "canal": "email",
            "email": "ana@example.com",
            "id": self.orcamento.pk,
        })

        envio = self.orcamento.envios.get()
        self.assertEqual(envio.canal, "email")
        self.assertEqual(envio.destino, "ana@example.com")
        self.assertTrue(envio.sucesso)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="",
        EMAIL_HOST_PASSWORD="",
    )
    def test_smtp_desligado_vira_registro_de_falha(self):
        """A falha é justamente a que precisa aparecer no histórico."""
        resposta = self.post({
            "action": "enviar",
            "canal": "email",
            "email": "ana@example.com",
            "id": self.orcamento.pk,
        })

        self.assertEqual(resposta.status_code, 400)
        envio = self.orcamento.envios.get()
        self.assertFalse(envio.sucesso)
        self.assertIn("SMTP", envio.detalhe)

    def test_resposta_traz_o_historico_para_a_tela(self):
        self.post({
            "action": "enviar",
            "canal": "whatsapp",
            "whatsapp": "(11) 99999-8888",
            "id": self.orcamento.pk,
        })

        dados = self.post({
            "action": "enviar",
            "id": self.orcamento.pk,
        }).json()

        self.assertGreaterEqual(len(dados["envios"]), 1)
        self.assertIn("canal", dados["envios"][0])
        self.assertIn("email_configurado", dados)

    def test_conversa_do_whatsapp_vem_pronta_com_o_link(self):
        """A proposta sai do WhatsApp de quem está logado no aparelho."""
        dados = self.post({
            "action": "enviar",
            "canal": "whatsapp",
            "whatsapp": "(11) 99999-8888",
            "id": self.orcamento.pk,
        }).json()

        self.orcamento.refresh_from_db()
        self.assertTrue(dados["whatsapp_url"].startswith("https://wa.me/5511999998888"))
        self.assertIn(self.orcamento.token, dados["whatsapp_url"])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DescontoInteligenteTests(TestCase):
    """Desconto em reais ou em porcentagem, sem calculadora à parte.

    No telefone o cliente pede "dá dez por cento?". Antes, quem montava a
    proposta abria a calculadora, fazia a conta do subtotal e digitava o
    resultado -- e errava quando um item mudava depois.

    O QUE NÃO PODE MUDAR: o campo que chega ao servidor continua sendo
    reais. A porcentagem é jeito de digitar, não jeito de guardar; a
    proposta que o cliente lê mostra um valor, não uma conta.
    """

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor", password="senha-segura", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def tela(self):
        return self.client.get(self.URL, HTTP_HOST="interno.testserver").content.decode()

    def test_o_campo_enviado_ao_servidor_continua_em_reais(self):
        html = self.tela()

        # O campo visível perdeu o `name`: quem viaja é o escondido, já
        # convertido para reais pelo navegador.
        self.assertIn('id="orcamentoDescontoValor"', html)
        self.assertIn('type="hidden" id="orcamentoDescontoValor" name="desconto"', html)

    def test_a_tela_oferece_troca_de_unidade_e_atalhos(self):
        html = self.tela()

        self.assertIn('id="descontoUnidade"', html)
        self.assertIn('data-desconto-pct="10"', html)
        self.assertIn('id="descontoRedondo"', html)
        self.assertIn('id="descontoZerar"', html)

    def test_o_servidor_aceita_o_desconto_convertido(self):
        """Dez por cento de 1.287,40 chega como 128,74 e é assim que fica
        guardado -- é o número que o cliente vê na proposta."""
        resposta = self.client.post(
            self.URL,
            {
                "action": "save",
                "id": "",
                "nome_cliente": "Buffet Estrela Azul",
                "status": Orcamento.Status.RASCUNHO,
                "frete": "150,00",
                "desconto": "128,74",
                "itens": json.dumps([{
                    "descricao": "Tobogã inflável",
                    "quantidade": 1,
                    "valor_unitario": "1287.40",
                }]),
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.json()["status"], "sucesso", resposta.json())
        orcamento = Orcamento.objects.get(nome_cliente="Buffet Estrela Azul")
        self.assertEqual(orcamento.desconto, Decimal("128.74"))
        self.assertEqual(orcamento.total, Decimal("1308.66"))
