"""Transportadoras recomendadas (LEIA-ME-V10, seção 89).

O frete saiu do site e a equipe passou a indicar quem leva a máquina. O
que estes testes seguram:

  * o telefone gravado em dígitos e mostrado do jeito que se lê, e o
    link do WhatsApp com a cotação já escrita;
  * a lista inicial: todo estado com pelo menos duas transportadoras
    ativas, e nenhum contato sem a página de onde ele veio -- é o que
    separa uma recomendação de um número inventado;
  * quem vê (Vendas, Gestão, Produção) e quem mexe (só Gestão);
  * a tela de um estado: só quem entrega lá, as nacionais primeiro, e
    cada botão de contato só quando o campo existe.
"""

import csv
import importlib
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from django.apps import apps as apps_do_django
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from . import transportadoras as regras
from .models import Transportadora
from .permissoes import atribuir_funcoes, capacidades

SEMENTE = importlib.import_module("sistema_interno.migrations.0064_transportadoras_iniciais")
CSV = Path(__file__).resolve().parent.parent / "ferramentas" / "transportadoras" / "transportadoras.csv"
ROTA = "/logistica/transportadoras/"
HOST = "interno.testserver"


# ======================================================================
# REGRAS PURAS
# ======================================================================
class TelefoneTests(SimpleTestCase):
    def test_formata_cada_tipo_de_numero(self):
        self.assertEqual(regras.formatar_telefone("1121889000"), "(11) 2188-9000")
        self.assertEqual(regras.formatar_telefone("11991004606"), "(11) 99100-4606")
        self.assertEqual(regras.formatar_telefone("08007753333"), "0800 775 3333")
        self.assertEqual(regras.formatar_telefone("03001159999"), "0300 115 9999")
        self.assertEqual(regras.formatar_telefone("40033277"), "4003-3277")
        self.assertEqual(regras.formatar_telefone(""), "")

    def test_aceita_o_que_a_pessoa_cola(self):
        self.assertEqual(regras.normalizar_telefone("+55 (11) 2188-9000"), "1121889000")
        self.assertEqual(regras.normalizar_telefone("0800-775-3333"), "08007753333")
        self.assertEqual(regras.formatar_telefone("+55 11 99100-4606"), "(11) 99100-4606")

    def test_ligar_com_ddd_vai_com_o_pais_e_0800_vai_como_esta(self):
        self.assertEqual(regras.link_telefone("1121889000"), "tel:+551121889000")
        self.assertEqual(regras.link_telefone("08007033339"), "tel:08007033339")
        self.assertEqual(regras.link_telefone("40033277"), "tel:40033277")
        self.assertEqual(regras.link_telefone(""), "")

    def test_validacao_so_aceita_numero_que_existe(self):
        for bom in ("1121889000", "11991004606", "08007753333", "40033277", ""):
            regras.validar_telefone(bom)
        for ruim in ("(11) 2188-9000", "123", "112188900", "011218890001"):
            with self.assertRaises(ValidationError, msg=ruim):
                regras.validar_telefone(ruim)

    def test_whatsapp_precisa_de_ddd(self):
        regras.validar_whatsapp("11913662652")
        regras.validar_whatsapp("1140033277")
        for ruim in ("08007753333", "40033277", "11-91366-2652"):
            with self.assertRaises(ValidationError, msg=ruim):
                regras.validar_whatsapp(ruim)


class WhatsAppTests(SimpleTestCase):
    def test_link_com_o_55_e_a_mensagem_codificada(self):
        link = regras.link_whatsapp("11913662652", regras.mensagem_cotacao("PE"))
        partes = urlsplit(link)
        self.assertEqual(f"{partes.scheme}://{partes.netloc}{partes.path}", "https://wa.me/5511913662652")
        texto = unquote(partes.query.removeprefix("text="))
        self.assertEqual(
            texto,
            "Olá! Somos da Lazer & Sport (fábrica de brinquedos em SP). Gostaria de "
            "uma cotação de frete de São Paulo/SP para ___/PE de uma máquina de "
            "aproximadamente ___ kg / ___ m³.",
        )
        # O "&" do nome da empresa não pode virar outro parâmetro da URL.
        self.assertNotIn("&", partes.query)

    def test_sem_estado_o_destino_fica_em_branco(self):
        self.assertIn("para ___ de uma máquina", regras.mensagem_cotacao(""))
        self.assertIn("para ___ de uma máquina", regras.mensagem_cotacao("XX"))

    def test_0800_e_numero_unico_nao_viram_whatsapp(self):
        self.assertEqual(regras.link_whatsapp("08007753333", "oi"), "")
        self.assertEqual(regras.link_whatsapp("40033277", "oi"), "")
        self.assertEqual(regras.link_whatsapp("1140033277"), "https://wa.me/551140033277")
        self.assertEqual(regras.link_whatsapp("+55 11 91366-2652"), "https://wa.me/5511913662652")

    def test_email_leva_assunto_e_mensagem(self):
        link = regras.link_email("sac@braspress.com", "AM")
        self.assertTrue(link.startswith("mailto:sac@braspress.com?"))
        consulta = parse_qs(urlsplit(link).query)
        self.assertEqual(
            consulta["subject"], ["Cotação de frete: São Paulo/SP para Amazonas (AM) - Lazer & Sport"],
        )
        self.assertIn("para ___/AM", consulta["body"][0])


class EstadosEInstagramTests(SimpleTestCase):
    def test_sao_os_27_estados(self):
        self.assertEqual(len(regras.SIGLAS), 27)
        self.assertEqual(len(set(regras.SIGLAS)), 27)
        self.assertEqual(set(regras.REGIAO_DA_UF.values()), set(regras.REGIOES))

    def test_lista_de_ufs_vai_para_a_ordem_do_mapa_sem_repetir(self):
        self.assertEqual(regras.gravar_ufs("sp, pe;BA pe"), "BA,PE,SP")
        self.assertEqual(regras.gravar_ufs(["RS", "AC"]), "AC,RS")
        self.assertEqual(regras.gravar_ufs(""), "")

    def test_sigla_desconhecida_e_recusada(self):
        with self.assertRaises(ValidationError):
            regras.ler_ufs("SP,XX")
        with self.assertRaises(ValidationError):
            regras.validar_lista_de_ufs("PE,BA")  # fora da ordem gravada

    def test_instagram_guarda_so_o_perfil(self):
        for escrito in ("@patrustransportes", "https://www.instagram.com/patrustransportes/",
                        "instagram.com/patrustransportes?hl=pt", " patrustransportes "):
            self.assertEqual(regras.normalizar_instagram(escrito), "patrustransportes")
        self.assertEqual(regras.link_instagram("@jadlog.oficial"), "https://instagram.com/jadlog.oficial")
        with self.assertRaises(ValidationError):
            regras.validar_instagram("perfil com espaço")

    def test_busca_aceita_genero_plural_e_acento(self):
        texto = regras.sem_acento("Carga aérea expressa; peça frágil")
        for procurado in ("aéreo", "AEREA", "peças", "expresso", "carga aerea", "FRAGIL"):
            self.assertTrue(all(t in texto for t in regras.termos_de_busca(procurado)), procurado)
        self.assertFalse(all(t in texto for t in regras.termos_de_busca("fluvial")))

    def test_iniciais_do_selo(self):
        self.assertEqual(regras.iniciais("Expresso São Miguel"), "ES")
        self.assertEqual(regras.iniciais("Braspress"), "BR")
        self.assertEqual(regras.iniciais("TBL Bertolini"), "TB")


# ======================================================================
# O MODELO
# ======================================================================
class ModeloTests(TestCase):
    def nova(self, **campos):
        dados = {
            "nome": "Transportadora Teste", "tipo": "regional", "estados_atendidos": "SP",
            "fonte_url": "https://exemplo.com.br/contato",
        }
        dados.update(campos)
        return Transportadora.objects.create(**dados)

    def test_salvar_grava_so_digitos_e_a_tela_formata(self):
        t = self.nova(telefone="(11) 2188-9000", whatsapp="+55 11 91366-2652",
                      instagram="@perfil.teste", estados_atendidos="sp,ba")
        t.refresh_from_db()
        self.assertEqual(t.telefone, "1121889000")
        self.assertEqual(t.whatsapp, "11913662652")
        self.assertEqual(t.instagram, "perfil.teste")
        self.assertEqual(t.estados_atendidos, "BA,SP")
        self.assertEqual(t.telefone_formatado, "(11) 2188-9000")
        self.assertEqual(t.whatsapp_formatado, "(11) 91366-2652")
        self.assertTrue(t.link_whatsapp("BA").startswith("https://wa.me/5511913662652?text="))
        self.assertIn("___%2FBA", t.link_whatsapp("BA"))

    def test_o_banco_recusa_telefone_com_mascara(self):
        t = self.nova(telefone="1121889000")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transportadora.objects.filter(pk=t.pk).update(telefone="(11) 2188-9000")

    def test_nome_unico_sem_diferenca_de_maiusculas(self):
        self.nova(nome="Nome Repetido")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.nova(nome="NOME REPETIDO")

    def test_nacional_atende_os_27_e_a_busca_no_banco_acha_so_a_sigla_inteira(self):
        brasil = self.nova(nome="Brasil Todo", tipo="nacional", atende_todo_brasil=True, estados_atendidos="")
        norte = self.nova(nome="Só AM e AP", estados_atendidos="AM,AP")
        self.assertEqual(len(brasil.ufs), 27)
        self.assertTrue(brasil.atende("rr"))
        self.assertTrue(norte.atende("AP"))
        self.assertFalse(norte.atende("PA"))

        no_para = set(Transportadora.objects.atendem("PA").values_list("pk", flat=True))
        self.assertIn(brasil.pk, no_para)
        self.assertNotIn(norte.pk, no_para)  # "AM,AP" não contém a sigla PA
        self.assertFalse(Transportadora.objects.atendem("XX").exists())

    def test_texto_para_copiar_tem_o_contato_inteiro(self):
        t = self.nova(nome="Empresa de Cargas Ltda", nome_fantasia="Cargas", telefone="08007753333",
                      whatsapp="11913662652", email="sac@cargas.com.br", site="https://cargas.com.br",
                      instagram="cargas")
        self.assertEqual(
            t.texto_para_copiar(),
            "Cargas (Empresa de Cargas Ltda)\nTelefone: 0800 775 3333\nWhatsApp: (11) 91366-2652\n"
            "E-mail: sac@cargas.com.br\nSite: https://cargas.com.br\nInstagram: @cargas",
        )


# ======================================================================
# A LISTA INICIAL (migração 0064)
# ======================================================================
class SementeTests(TestCase):
    CONTATOS = ("telefone", "whatsapp", "email", "instagram")

    def test_todo_estado_tem_pelo_menos_duas_ativas(self):
        for sigla in regras.SIGLAS:
            with self.subTest(uf=sigla):
                self.assertGreaterEqual(Transportadora.objects.ativas().atendem(sigla).count(), 2)

    def test_todo_estado_tem_uma_nacional_e_as_regioes_tem_regionais(self):
        for sigla in regras.SIGLAS:
            self.assertTrue(
                Transportadora.objects.ativas().atendem(sigla).filter(tipo="nacional").exists(), sigla,
            )
        regionais = Transportadora.objects.ativas().filter(tipo="regional")
        for regiao in regras.REGIOES:
            ufs = [s for s in regras.SIGLAS if regras.REGIAO_DA_UF[s] == regiao]
            self.assertTrue(any(t.atende(uf) for t in regionais for uf in ufs), regiao)

    def test_todo_contato_preenchido_tem_fonte_e_data(self):
        self.assertGreaterEqual(Transportadora.objects.count(), len(SEMENTE.TRANSPORTADORAS))
        for t in Transportadora.objects.all():
            with self.subTest(transportadora=t.nome):
                if any(getattr(t, campo) for campo in self.CONTATOS):
                    self.assertTrue(t.fonte_url.startswith("https://"), t.nome)
                    self.assertIsNotNone(t.verificado_em)
                if t.telefone:
                    self.assertTrue(t.fonte_url)

    def test_cada_linha_passa_na_validacao_do_modelo(self):
        for t in Transportadora.objects.all():
            with self.subTest(transportadora=t.nome):
                t.full_clean()
                self.assertTrue(t.telefone or t.whatsapp, "sem nenhum número para chamar")

    def test_as_grandes_nacionais_estao_la(self):
        nomes = " ".join(Transportadora.objects.values_list("nome", flat=True))
        for marca in ("Braspress", "Jadlog", "Patrus", "Rodonaves", "FedEx", "Total Express",
                      "Azul Cargo", "LATAM Cargo", "Correios"):
            self.assertIn(marca, nomes)

    def test_o_csv_da_revisao_diz_o_mesmo_que_a_migracao(self):
        with CSV.open(encoding="utf-8", newline="") as arquivo:
            linhas = {linha["nome"]: linha for linha in csv.DictReader(arquivo)}
        self.assertEqual(set(linhas), {dados["nome"] for dados in SEMENTE.TRANSPORTADORAS})
        for dados in SEMENTE.TRANSPORTADORAS:
            linha = linhas[dados["nome"]]
            with self.subTest(transportadora=dados["nome"]):
                for campo in ("tipo", "estados_atendidos", "telefone", "whatsapp", "email",
                              "instagram", "site", "fonte_url", "observacoes"):
                    self.assertEqual(linha[campo], dados[campo], campo)
                self.assertEqual(linha["telefone_formatado"], regras.formatar_telefone(dados["telefone"]))
                self.assertEqual(linha["verificado_em"], SEMENTE.CONFERIDO_EM.isoformat())

    def test_rodar_de_novo_nao_duplica_e_desfazer_apaga_so_a_lista(self):
        propria = Transportadora.objects.create(nome="Cadastrada pela equipe", estados_atendidos="SP")
        Transportadora.objects.filter(nome="Braspress Transportes Urgentes").update(observacoes="editada")

        SEMENTE.criar(apps_do_django, None)
        self.assertEqual(Transportadora.objects.filter(nome__iexact="braspress transportes urgentes").count(), 1)
        self.assertEqual(Transportadora.objects.get(nome__startswith="Braspress").observacoes, "editada")

        SEMENTE.apagar(apps_do_django, None)
        self.assertEqual(list(Transportadora.objects.values_list("pk", flat=True)), [propria.pk])


# ======================================================================
# QUEM VÊ E QUEM MEXE
# ======================================================================
class AcessoTests(TestCase):
    def usuario(self, nome, *funcoes):
        user = User.objects.create_user(username=nome, password="senha-segura")
        atribuir_funcoes(user, funcoes)
        return user

    def abrir(self, user, rota=ROTA):
        self.client.force_login(user)
        return self.client.get(rota, HTTP_HOST=HOST)

    def postar(self, user, **dados):
        self.client.force_login(user)
        return self.client.post(ROTA, dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_vendas_gestao_e_producao_abrem(self):
        for funcao in ("vendas", "gestao", "producao"):
            with self.subTest(funcao=funcao):
                resposta = self.abrir(self.usuario(f"pessoa-{funcao}", funcao))
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'href="/logistica/transportadoras/"')

    def test_outras_funcoes_nao_entram_nem_veem_o_menu(self):
        for funcao in ("criacao", "financeiro", "ambulante"):
            with self.subTest(funcao=funcao):
                user = self.usuario(f"pessoa-{funcao}", funcao)
                self.assertFalse(capacidades(user)["transportadoras"])
                self.assertEqual(self.abrir(user).status_code, 302)

    def test_fora_do_subdominio_interno_nao_abre(self):
        self.client.force_login(self.usuario("gestor", "gestao"))
        resposta = self.client.get(ROTA, HTTP_HOST="testserver")
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("/logistica/", resposta["Location"])

    def test_so_gestao_ve_os_botoes_de_cadastro(self):
        vendedor = self.abrir(self.usuario("vendedor", "vendas"))
        self.assertNotContains(vendedor, "data-tp-novo")
        self.assertNotContains(vendedor, "data-tp-editar")
        self.assertNotContains(vendedor, 'id="modalTransportadora"')
        gestor = self.abrir(self.usuario("gestor", "gestao"))
        self.assertContains(gestor, "data-tp-novo")
        self.assertContains(gestor, "data-tp-desativar")
        self.assertContains(gestor, 'id="modalTransportadora"')

    def test_vendas_e_producao_nao_gravam(self):
        alvo = Transportadora.objects.get(nome="Patrus Transportes")
        for funcao in ("vendas", "producao"):
            with self.subTest(funcao=funcao):
                resposta = self.postar(self.usuario(f"p-{funcao}", funcao), action="desativar", id=alvo.pk)
                self.assertEqual(resposta.status_code, 403)
                self.assertEqual(resposta.json()["status"], "erro")
        alvo.refresh_from_db()
        self.assertTrue(alvo.ativo)

    def test_gestao_cadastra_corrige_desativa_e_reativa(self):
        gestor = self.usuario("gestor", "gestao")
        resposta = self.postar(
            gestor, action="salvar", nome="Expresso Teste", nome_fantasia="Teste", tipo="regional",
            estados=["SP", "AM"], cidade_sede="Manaus", uf_sede="AM", telefone="(92) 3333-4444",
            whatsapp="(92) 99999-8888", instagram="@expresso.teste", site="expressoteste.com.br",
            fonte_url="https://expressoteste.com.br/contato", ordem="5",
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        t = Transportadora.objects.get(nome="Expresso Teste")
        self.assertEqual((t.telefone, t.whatsapp, t.instagram), ("9233334444", "92999998888", "expresso.teste"))
        self.assertEqual(t.estados_atendidos, "AM,SP")
        self.assertEqual(t.site, "https://expressoteste.com.br")
        self.assertIsNotNone(t.verificado_em)  # contato com fonte ganha a data de hoje

        self.postar(gestor, action="salvar", id=t.pk, nome="Expresso Teste", tipo="nacional",
                    atende_todo_brasil="1", fonte_url=t.fonte_url, telefone=t.telefone)
        t.refresh_from_db()
        self.assertTrue(t.atende_todo_brasil)
        self.assertEqual(t.estados_atendidos, "")

        self.postar(gestor, action="desativar", id=t.pk)
        t.refresh_from_db()
        self.assertFalse(t.ativo)
        self.assertNotContains(self.abrir(self.usuario("vend", "vendas"), ROTA + "?uf=AM"), "Expresso Teste")
        desativadas = self.abrir(gestor)
        self.assertContains(desativadas, "Desativadas")
        self.assertContains(desativadas, "data-tp-reativar")

        self.postar(gestor, action="reativar", id=t.pk)
        t.refresh_from_db()
        self.assertTrue(t.ativo)

    def test_contato_sem_fonte_nao_entra(self):
        resposta = self.postar(self.usuario("gestor", "gestao"), action="salvar", nome="Sem Fonte",
                               tipo="regional", estados=["SP"], telefone="11 2222-3333")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("fonte", resposta.json()["msg"])
        self.assertFalse(Transportadora.objects.filter(nome="Sem Fonte").exists())

    def test_sem_estado_e_sem_brasil_inteiro_e_recusado(self):
        resposta = self.postar(self.usuario("gestor", "gestao"), action="salvar", nome="Sem Estado",
                               tipo="regional")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("estados", resposta.json()["msg"])

    def test_numero_que_nao_existe_e_recusado(self):
        resposta = self.postar(self.usuario("gestor", "gestao"), action="salvar", nome="Número Curto",
                               tipo="regional", estados=["SP"], whatsapp="0800 775 3333",
                               fonte_url="https://exemplo.com.br")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("WhatsApp", resposta.json()["msg"])


# ======================================================================
# A TELA DE UM ESTADO
# ======================================================================
class TelaDoEstadoTests(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username="vendedor", password="senha-segura")
        atribuir_funcoes(self.vendedor, ["vendas"])
        self.client.force_login(self.vendedor)

    def abrir(self, consulta=""):
        resposta = self.client.get(ROTA + consulta, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    @staticmethod
    def cartao(html, transportadora):
        achado = re.search(
            rf'<article[^>]*id="tp-{transportadora.pk}"[^>]*>(.*?)</article>', html, re.S,
        )
        return achado.group(1) if achado else None

    def test_o_estado_mostra_so_quem_entrega_la(self):
        html = self.abrir("?uf=PE")
        pacifico = Transportadora.objects.get(nome="Pacífico Log")
        patrus = Transportadora.objects.get(nome="Patrus Transportes")
        braspress = Transportadora.objects.get(nome="Braspress Transportes Urgentes")
        self.assertIsNotNone(self.cartao(html, pacifico))
        self.assertIsNotNone(self.cartao(html, braspress))
        self.assertIsNone(self.cartao(html, patrus))  # Patrus não entrega em PE
        self.assertIn("Para Pernambuco (PE)", html)
        self.assertIn('class="tp-uf is-ativa"', html)

    def test_nacionais_primeiro_depois_regionais_depois_mudancas(self):
        html = self.abrir("?uf=AM")
        posicoes = [html.index(f'data-tp-secao="{tipo}"') for tipo in ("nacional", "regional", "mudancas")]
        self.assertEqual(posicoes, sorted(posicoes))

    def test_os_botoes_do_cartao_saem_dos_campos(self):
        html = self.abrir("?uf=SP")
        patrus = Transportadora.objects.get(nome="Patrus Transportes")
        cartao = self.cartao(html, patrus)
        self.assertIn('href="https://wa.me/551140033277?text=Ol%C3%A1%21%20Somos%20da%20Lazer%20%26%20Sport', cartao)
        self.assertIn("%20para%20___%2FSP%20de%20uma%20m%C3%A1quina", cartao)
        self.assertIn("Chamar no WhatsApp", cartao)
        self.assertIn('href="tel:40033277"', cartao)
        self.assertIn('href="https://instagram.com/patrustransportes"', cartao)
        self.assertIn('href="https://patrus.com.br"', cartao)
        self.assertIn("Copiar contato", cartao)
        self.assertIn("4003-3277", cartao)
        self.assertNotIn("mailto:", cartao)  # Patrus sem e-mail conferido: sem botão

    def test_sem_whatsapp_nem_instagram_nao_ha_botao(self):
        html = self.abrir("?uf=RR")
        latam = Transportadora.objects.get(nome="LATAM Cargo Brasil")
        cartao = self.cartao(html, latam)
        self.assertIn('href="tel:03001159999"', cartao)
        self.assertNotIn("wa.me", cartao)
        self.assertNotIn("instagram.com", cartao)
        self.assertNotIn('data-tp-acao="email"', cartao)

    def test_email_com_assunto_do_estado(self):
        html = self.abrir("?uf=BA")
        braspress = Transportadora.objects.get(nome="Braspress Transportes Urgentes")
        cartao = self.cartao(html, braspress)
        self.assertIn('href="mailto:sac@braspress.com?subject=Cota%C3%A7%C3%A3o%20de%20frete', cartao)
        self.assertIn("Bahia%20%28BA%29", cartao)
        self.assertIn('href="tel:+551121889000"', cartao)
        self.assertIn("(11) 2188-9000", cartao)

    def test_a_fonte_e_a_data_aparecem_no_cartao(self):
        html = self.abrir("?uf=MT")
        carvalima = Transportadora.objects.get(nome="Carvalima Transportes")
        cartao = self.cartao(html, carvalima)
        self.assertIn(f'href="{carvalima.fonte_url}"', cartao)
        self.assertIn("Conferido em 13/11/2026", cartao)

    def test_os_27_estados_tem_botao_e_contagem(self):
        html = self.abrir()
        for sigla in regras.SIGLAS:
            self.assertIn(f'href="?uf={sigla}"', html)
        self.assertIn("Todas as transportadoras", html)

    def test_busca_do_servidor_filtra_sem_javascript(self):
        html = self.abrir("?uf=SP&q=commerce")
        tbl = Transportadora.objects.get(nome="Transportes Bertolini (TBL)")
        total = Transportadora.objects.get(nome="Total Express")
        self.assertIsNone(self.cartao(html, tbl))  # TBL não entrega em SP
        self.assertIsNotNone(self.cartao(html, total))  # "e-commerce" nas observações
        self.assertIsNone(self.cartao(html, Transportadora.objects.get(nome="Correios")))

    def test_busca_por_aereo_acha_as_aereas(self):
        html = self.abrir("?q=a%C3%A9reo")
        self.assertIsNotNone(self.cartao(html, Transportadora.objects.get(nome="Azul Cargo Express")))
        self.assertIsNone(self.cartao(html, Transportadora.objects.get(nome="Correios")))

    def test_estado_desconhecido_vira_todos(self):
        html = self.abrir("?uf=ZZ")
        self.assertIn("Todas as transportadoras", html)
