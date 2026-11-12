"""Dados de EXEMPLO para os gráficos do painel -- e o botão de desfazer.

    python manage.py semear_analises            # cria (um ano de movimento)
    python manage.py semear_analises --apagar   # apaga só o que este comando criou

PARA O COMPUTADOR E PARA DEMONSTRAÇÃO, NUNCA PARA O BANCO DE VERDADE. O
comando se recusa a rodar com DEBUG desligado (a não ser com --mesmo-assim).

NADA DO QUE JÁ EXISTE É ALTERADO. Tudo o que nasce aqui leva uma marca que o
--apagar procura, e é só isso que ele apaga:
  * visitas e idas ao carrinho: `InteracaoPorHora.origem = "exemplo"`;
  * curtidas: dispositivo começando com "exemplo-analises-";
  * contas: usuário começando com "exemplo_analises_" (leva junto perfil,
    presença, acessos, pedidos e pontos delas);
  * pedidos e orçamentos: observação começando com "[exemplo analises]";
  * clientes, eventos e projetos: nome começando com "[Exemplo]";
  * cupons: código começando com "EXAN".
Os brinquedos, combos, promoções e peças que já estão no banco recebem
visitas e pedidos de exemplo, mas o cadastro deles não é tocado.
"""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

MARCA = "[exemplo analises]"
PREFIXO_CONTA = "exemplo_analises_"
PREFIXO_APARELHO = "exemplo-analises-"
PREFIXO_NOME = "[Exemplo]"
PREFIXO_CUPOM = "EXAN"
DIAS = 365


class Command(BaseCommand):
    help = "Cria (ou apaga, com --apagar) dados de exemplo marcados para os gráficos do painel."

    def add_arguments(self, parser):
        parser.add_argument("--apagar", action="store_true", help="Apaga só os dados de exemplo.")
        parser.add_argument("--mesmo-assim", action="store_true", help="Roda mesmo com DEBUG desligado.")
        parser.add_argument("--semente", type=int, default=76)

    def handle(self, *args, **opcoes):
        if not settings.DEBUG and not opcoes["mesmo_assim"]:
            raise CommandError("Dados de exemplo só no computador (DEBUG ligado). Use --mesmo-assim para insistir.")
        if opcoes["apagar"]:
            self.apagar()
        else:
            self.apagar(silencioso=True)
            self.semear(random.Random(opcoes["semente"]))
        cache.clear()

    # ------------------------------------------------------------------
    @transaction.atomic
    def apagar(self, silencioso=False):
        from sistema_interno.models import Cliente, Orcamento

        from core.models import (
            BrinquedosProjeto,
            Cupom,
            Eventos,
            Favorito,
            InteracaoPorHora,
            MontagemTresD,
            Pedido,
            PedidoProjeto3D,
            Projetos,
            RegistroCadastro,
        )

        apagados = {
            "interações": InteracaoPorHora.objects.filter(origem="exemplo").delete()[0],
            "curtidas": Favorito.objects.filter(dispositivo__startswith=PREFIXO_APARELHO).delete()[0],
            "pedidos": Pedido.objects.filter(observacoes__startswith=MARCA).delete()[0],
            "orçamentos": Orcamento.objects.filter(observacoes__startswith=MARCA).delete()[0],
            "clientes": Cliente.objects.filter(nome_cliente__startswith=PREFIXO_NOME).delete()[0],
            "cupons": Cupom.objects.filter(codigo__startswith=PREFIXO_CUPOM).delete()[0],
            "eventos": Eventos.objects.filter(titulo__startswith=PREFIXO_NOME).delete()[0],
            "projetos": Projetos.objects.filter(titulo__startswith=PREFIXO_NOME).delete()[0],
            "montagens": MontagemTresD.objects.filter(nome__startswith=PREFIXO_NOME).delete()[0],
            "brinquedos projetados": BrinquedosProjeto.objects.filter(nome_brinquedo_projeto__startswith=PREFIXO_NOME).delete()[0],
            "pedidos 3D": PedidoProjeto3D.objects.filter(nome__startswith=PREFIXO_NOME).delete()[0],
            "registros de cadastro": RegistroCadastro.objects.filter(username__startswith=PREFIXO_CONTA).delete()[0],
            "contas": User.objects.filter(username__startswith=PREFIXO_CONTA).delete()[0],
        }
        if not silencioso:
            for nome, quantos in apagados.items():
                self.stdout.write(f"  {nome}: {quantos} linha(s) apagada(s)")
            self.stdout.write(self.style.SUCCESS("Dados de exemplo apagados."))

    # ------------------------------------------------------------------
    @transaction.atomic
    def semear(self, sorte):
        from sistema_interno.models import Cliente, ItemOrcamento, Orcamento

        from core.models import (
            AcessoDiario,
            Brinquedos,
            BrinquedosProjeto,
            CategoriasBrinquedos,
            ClientePerfil,
            Combos,
            Cupom,
            Eventos,
            Favorito,
            InteracaoPorHora,
            ItemPedido,
            MontagemTresD,
            PecasReposicao,
            Pedido,
            PedidoProjeto3D,
            PresencaUsuario,
            Projetos,
            Promocoes,
            RegistroCadastro,
        )

        fuso = timezone.get_current_timezone()
        agora = timezone.localtime(timezone.now(), fuso)
        hoje = agora.date()

        def momento(dias_atras, hora=None):
            dia = hoje - dt.timedelta(days=dias_atras)
            hora = sorte.choice(HORAS) if hora is None else hora
            quando = timezone.make_aware(dt.datetime.combine(dia, dt.time(hora, sorte.randint(0, 59))), fuso)
            return min(quando, agora - dt.timedelta(minutes=sorte.randint(1, 30)))

        # Mais gente à tarde e à noite, mais no fim de semana, e o ano crescendo.
        HORAS = [9, 10, 11, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 20, 21, 21, 22]

        def peso_do_dia(dias_atras):
            dia = hoje - dt.timedelta(days=dias_atras)
            fim_de_semana = 1.55 if dia.weekday() >= 5 else (1.15 if dia.weekday() == 4 else 1.0)
            crescimento = 0.55 + 0.45 * (1 - dias_atras / DIAS)
            black_friday = 1.8 if dias_atras < 14 else 1.0
            return fim_de_semana * crescimento * black_friday

        brinquedos = list(Brinquedos.objects.order_by("id"))
        combos = list(Combos.objects.order_by("id"))
        promocoes = list(Promocoes.objects.order_by("id"))
        pecas = list(PecasReposicao.objects.order_by("id"))
        categorias = list(CategoriasBrinquedos.objects.order_by("id"))
        if not brinquedos:
            raise CommandError("O banco não tem brinquedos: cadastre o catálogo antes de semear.")

        # ---- visitas e idas ao carrinho, hora a hora ----
        interacoes = {}

        def somar(evento, alvo, objeto_id, quantidade, quando):
            hora = quando.replace(minute=0, second=0, microsecond=0)
            chave = (evento, alvo, objeto_id, hora)
            interacoes[chave] = interacoes.get(chave, 0) + quantidade

        alvos = (
            [("brinquedo", b.pk, sorte.uniform(0.4, 3.2)) for b in brinquedos]
            + [("combo", c.pk, sorte.uniform(0.6, 2.0)) for c in combos]
            + [("promocao", p.pk, sorte.uniform(0.8, 3.5)) for p in promocoes]
            + [("peca", p.pk, sorte.uniform(0.3, 1.2)) for p in pecas]
            + [("categoria", c.pk, sorte.uniform(1.0, 4.0)) for c in categorias]
        )
        for dias_atras in range(DIAS):
            peso = peso_do_dia(dias_atras)
            for alvo, objeto_id, popularidade in alvos:
                if alvo == "promocao" and dias_atras > 40 and sorte.random() < 0.7:
                    continue  # promoção é coisa recente
                visitas = int(sorte.gauss(2.2, 1.4) * popularidade * peso)
                if visitas <= 0:
                    continue
                for _ in range(sorte.randint(1, 3)):
                    parte = max(1, visitas // 2)
                    quando = momento(dias_atras)
                    somar("visita", alvo, objeto_id, parte, quando)
                    if alvo != "categoria" and sorte.random() < 0.16:
                        somar("carrinho", alvo, objeto_id, sorte.randint(1, 2), quando)
        InteracaoPorHora.objects.bulk_create(
            [
                InteracaoPorHora(evento=e, alvo=a, objeto_id=o, hora=h, origem="exemplo", quantidade=q)
                for (e, a, o, h), q in interacoes.items()
            ],
            batch_size=2000,
        )

        # ---- contas de exemplo, com perfil, origem, presença e acessos ----
        origens = ["site"] * 5 + ["app"] * 3 + ["google"] * 2 + ["apple"]
        contas = []
        for n in range(48):
            criada = momento(int(DIAS * (sorte.random() ** 1.6)))
            contas.append(User(
                username=f"{PREFIXO_CONTA}{n:02d}", email=f"{PREFIXO_CONTA}{n:02d}@exemplo.invalid",
                first_name=sorte.choice(NOMES), date_joined=criada, is_active=True,
            ))
        User.objects.bulk_create(contas)
        contas = list(User.objects.filter(username__startswith=PREFIXO_CONTA).order_by("username"))
        ClientePerfil.objects.bulk_create([
            ClientePerfil(user=c, nome_completo=f"{c.first_name} {sorte.choice(SOBRENOMES)}", telefone="(11)9" + f"{sorte.randint(1000, 9999)}-{sorte.randint(1000, 9999)}")
            for c in contas
        ])
        perfis = {p.user_id: p for p in ClientePerfil.objects.filter(user__in=contas)}
        RegistroCadastro.objects.bulk_create([
            RegistroCadastro(usuario=c, username=c.username, email=c.email, origem=sorte.choice(origens),
                             cidade=sorte.choice(["São Paulo", "Campinas", "Guarulhos", "Santos", "Sorocaba"]), estado="SP", pais="Brasil")
            for c in contas
        ])
        RegistroCadastro.objects.filter(username__startswith=PREFIXO_CONTA).update(criacao=agora)
        for registro in RegistroCadastro.objects.filter(usuario__in=contas).select_related("usuario"):
            RegistroCadastro.objects.filter(pk=registro.pk).update(criacao=registro.usuario.date_joined)

        presencas, acessos = [], []
        for i, conta in enumerate(contas):
            if i % 7 == 6:
                continue  # nunca entrou depois de criar a conta
            idade = (hoje - timezone.localtime(conta.date_joined).date()).days
            if i < 4:
                ultimo = agora - dt.timedelta(minutes=sorte.randint(0, 3))       # online agora
            elif i < 9:
                ultimo = agora - dt.timedelta(minutes=sorte.randint(20, 300))    # hoje
            else:
                ultimo = agora - dt.timedelta(days=sorte.randint(1, max(1, min(idade, 80))), hours=sorte.randint(0, 9))
            ultimo = max(ultimo, conta.date_joined)
            presencas.append(PresencaUsuario(usuario=conta, visto_em=ultimo, onde=sorte.choice(["site", "site", "app", "painel"])))
            dias_vistos = {timezone.localtime(ultimo).date()}
            frequencia = sorte.uniform(0.05, 0.4)
            for d in range(min(idade, DIAS)):
                if sorte.random() < frequencia * peso_do_dia(d) / 1.4:
                    dias_vistos.add(hoje - dt.timedelta(days=d))
            for dia in dias_vistos:
                if dia > timezone.localtime(ultimo).date():
                    continue
                inicio = timezone.make_aware(dt.datetime.combine(dia, dt.time(sorte.choice(HORAS), sorte.randint(0, 59))), fuso)
                fim = min(inicio + dt.timedelta(minutes=sorte.randint(2, 180)), agora)
                if dia == timezone.localtime(ultimo).date():
                    fim = max(fim, ultimo)
                    inicio = min(inicio, fim)
                acessos.append(AcessoDiario(usuario=conta, dia=dia, primeiro=inicio, ultimo=fim))
            if i % 3 == 0:
                User.objects.filter(pk=conta.pk).update(last_login=ultimo - dt.timedelta(days=sorte.randint(0, 20)))
        PresencaUsuario.objects.bulk_create(presencas)
        AcessoDiario.objects.bulk_create(acessos, batch_size=2000)

        # ---- curtidas e lista de desejos ----
        favoritos = []
        ja_da_conta = set()
        for n in range(420):
            dias_atras = int(DIAS * (sorte.random() ** 1.4))
            usa_peca = bool(pecas) and sorte.random() >= 0.85
            produto = sorte.choice(pecas) if usa_peca else sorte.choice(brinquedos)
            tipo = "curtida" if sorte.random() < 0.72 else "desejo"
            quando = momento(dias_atras)
            conta = sorte.choice(contas) if sorte.random() < 0.35 else None
            if conta is not None and conta.date_joined > quando:
                conta = None  # ninguém curte com a conta antes de criá-la
            # uma curtida por conta e produto (a regra do banco): repetida, vira de visitante
            if conta is not None and (tipo, usa_peca, produto.pk, conta.pk) in ja_da_conta:
                conta = None
            if conta is not None:
                ja_da_conta.add((tipo, usa_peca, produto.pk, conta.pk))
            favoritos.append((
                Favorito(
                    tipo=tipo,
                    brinquedo=None if usa_peca else produto,
                    peca=produto if usa_peca else None,
                    usuario=conta,
                    dispositivo=f"{PREFIXO_APARELHO}{n:04d}",
                    origem=sorte.choice(["site", "app"]),
                ),
                quando,
            ))
        Favorito.objects.bulk_create([f for f, _ in favoritos])
        criados = list(Favorito.objects.filter(dispositivo__startswith=PREFIXO_APARELHO).order_by("dispositivo"))
        for fav, (_, quando) in zip(criados, favoritos):
            Favorito.objects.filter(pk=fav.pk).update(criacao=quando)

        # ---- cupons de exemplo ----
        cupons = [
            Cupom(codigo=f"{PREFIXO_CUPOM}-BF10", desconto_percentual=Decimal("10"), todos_usuarios=True, quantidade_uso=500),
            Cupom(codigo=f"{PREFIXO_CUPOM}-VIP15", desconto_percentual=Decimal("15"), todos_usuarios=True, quantidade_uso=100, reutilizavel=True),
            Cupom(codigo=f"{PREFIXO_CUPOM}-PRIMEIRA", desconto_percentual=Decimal("5"), todos_usuarios=True, quantidade_uso=1000),
        ]
        Cupom.objects.bulk_create(cupons)
        codigos = [c.codigo for c in cupons]

        # ---- pedidos da loja ----
        vendaveis = (
            [("brinquedo", b.pk, b.nome_brinquedo, b.valor_brinquedo or Decimal("4990")) for b in brinquedos]
            + [("combo", c.pk, c.descricao, c.valor_combo) for c in combos]
            + [("promocao", p.pk, p.descricao, p.preco_promocao) for p in promocoes if p.preco_promocao]
            + [("pecas", p.pk, p.nome, p.preco_venda or Decimal("49")) for p in pecas]
        )
        pesos = [3 if t == "brinquedo" else 2 if t == "promocao" else 1 for t, *_ in vendaveis]
        pedidos, itens_por_pedido = [], []
        for n in range(170):
            dias_atras = int(DIAS * (sorte.random() ** 1.25))
            quando = momento(dias_atras)
            escolhidos = sorte.choices(vendaveis, weights=pesos, k=sorte.choice([1, 1, 1, 2, 2, 3]))
            itens = []
            bruto = Decimal("0")
            for tipo, pk, nome, preco in escolhidos:
                quantidade = 1 if tipo != "pecas" else sorte.randint(1, 4)
                subtotal = (Decimal(preco) * quantidade).quantize(Decimal("0.01"))
                bruto += subtotal
                itens.append((tipo, pk, nome, Decimal(preco), quantidade, subtotal))
            cupom = sorte.choice(codigos) if sorte.random() < 0.22 else None
            percentual = {codigos[0]: Decimal("10"), codigos[1]: Decimal("15"), codigos[2]: Decimal("5")}.get(cupom, Decimal("0"))
            desconto = (bruto * percentual / 100).quantize(Decimal("0.01"))
            frete = Decimal(sorte.choice(["0", "0", "89.90", "149.90", "220.00"]))
            liquido = bruto - desconto
            status = sorte.choices(
                ["finalizado", "pago", "em_preparacao", "saiu_entrega", "cancelado", "aguardando_pagamento"],
                weights=[60, 8, 5, 4, 12, 6] if dias_atras > 10 else [20, 20, 15, 10, 8, 20],
            )[0]
            ja_existiam = [c for c in contas if c.date_joined <= quando]
            conta = sorte.choice(ja_existiam) if (ja_existiam and sorte.random() < 0.8) else None
            pedidos.append((Pedido(
                cliente=perfis.get(conta.pk) if conta else None,
                status=status, tipo_envio="frete" if frete else "retirada",
                total_bruto=bruto, valor_desconto=desconto, total_liquido=liquido, valor_frete=frete,
                total_final=liquido + frete, forma_pagamento=sorte.choice(["pix", "pix", "credito", "debito"]),
                cupom_codigo=cupom, cupom_percentual=percentual if cupom else None,
                cidade=sorte.choice(["São Paulo", "Campinas", "Guarulhos"]), estado="SP",
                observacoes=f"{MARCA} pedido de demonstração",
            ), quando))
            itens_por_pedido.append(itens)
        Pedido.objects.bulk_create([p for p, _ in pedidos])
        criados = list(Pedido.objects.filter(observacoes__startswith=MARCA).order_by("id"))
        linhas = []
        for pedido, (_, quando), itens in zip(criados, pedidos, itens_por_pedido):
            Pedido.objects.filter(pk=pedido.pk).update(criacao=quando, atualizado=quando + dt.timedelta(hours=sorte.randint(1, 50)))
            for tipo, pk, nome, preco, quantidade, subtotal in itens:
                linhas.append(ItemPedido(
                    pedido=pedido, object_id=pk, nome_item=nome, tipo_item=tipo,
                    preco_unitario=preco, quantidade=quantidade, subtotal=subtotal,
                ))
        ItemPedido.objects.bulk_create(linhas)
        ItemPedido.objects.filter(pedido__observacoes__startswith=MARCA).update(criacao=agora)

        # ---- clientes da carteira e orçamentos ----
        clientes = [
            Cliente(nome_cliente=f"{PREFIXO_NOME} {nome}", telefone=f"(11) 9{sorte.randint(1000, 9999)}-{sorte.randint(1000, 9999)}",
                    email=f"contato{i}@exemplo.invalid")
            for i, nome in enumerate([
                "Buffet Pula-Pula", "Espaço Kids Alegria", "Shopping Norte Diversão", "Escola Pequeno Príncipe",
                "Hotel Fazenda Sol", "Condomínio Jardins", "Clube Atlético Vila", "Arena Games Centro",
                "Festa & Cia Eventos", "Parque das Crianças",
            ])
        ]
        Cliente.objects.bulk_create(clientes)
        clientes = list(Cliente.objects.filter(nome_cliente__startswith=PREFIXO_NOME).order_by("id"))
        for i, cliente in enumerate(clientes):
            Cliente.objects.filter(pk=cliente.pk).update(criacao=momento(int(DIAS * sorte.random() ** 0.8)))
        clientes = list(Cliente.objects.filter(nome_cliente__startswith=PREFIXO_NOME).order_by("id"))
        orcaveis = [("brinquedo", b) for b in brinquedos] + [("peca", p) for p in pecas]
        orcamentos = []
        for n in range(90):
            cliente = sorte.choice(clientes)
            inicio = max(timezone.localtime(cliente.criacao).date(), hoje - dt.timedelta(days=DIAS - 1))
            dias_atras = sorte.randint(0, max(0, (hoje - inicio).days))
            quando = momento(dias_atras)
            status = sorte.choices(["aprovado", "recusado", "aguardando_resposta", "em_negociacao", "expirado"], weights=[38, 18, 22, 10, 12])[0]
            respondido = None
            if status in ("aprovado", "recusado"):
                respondido = min(quando + dt.timedelta(days=sorte.randint(0, 9), hours=sorte.randint(1, 8)), agora - dt.timedelta(minutes=5))
            escolhidos = sorte.sample(orcaveis, k=min(len(orcaveis), sorte.choice([1, 2, 2, 3, 4])))
            fechado = sorte.random() < 0.3
            orcamentos.append((Orcamento(
                cliente=cliente, nome_cliente=cliente.nome_cliente, status=status, respondido_em=respondido,
                frete=Decimal(sorte.choice(["0", "250", "480"])), desconto=Decimal(sorte.choice(["0", "0", "300", "800"])),
                observacoes=f"{MARCA} proposta de demonstração",
            ), quando, escolhidos, fechado))
        Orcamento.objects.bulk_create([o for o, *_ in orcamentos])
        criados = list(Orcamento.objects.filter(observacoes__startswith=MARCA).order_by("id"))
        linhas = []
        for orcamento, (_, quando, escolhidos, fechado) in zip(criados, orcamentos):
            soma = Decimal("0")
            for tipo, objeto in escolhidos:
                preco = (objeto.valor_brinquedo if tipo == "brinquedo" else objeto.preco_venda) or Decimal("3500")
                quantidade = 1 if tipo == "brinquedo" else sorte.randint(2, 10)
                soma += preco * quantidade
                linhas.append(ItemOrcamento(
                    orcamento=orcamento, descricao=str(objeto), quantidade=quantidade, valor_unitario=preco,
                    brinquedo=objeto if tipo == "brinquedo" else None, peca=objeto if tipo == "peca" else None,
                ))
            mudancas = {"criacao": quando}
            if fechado:
                mudancas["valor_final"] = (soma * Decimal("0.92")).quantize(Decimal("1"))
            Orcamento.objects.filter(pk=orcamento.pk).update(**mudancas)
        ItemOrcamento.objects.bulk_create(linhas)

        # ---- eventos e projetos (o dev costuma não ter nenhum) ----
        for titulo in ("Festa Junina do Clube", "Colônia de Férias Kids", "Black Friday na Loja"):
            evento = Eventos.objects.create(titulo=f"{PREFIXO_NOME} {titulo}", descricao="Evento de demonstração para os gráficos do painel.")
            evento.brinquedos.add(*sorte.sample(brinquedos, k=min(len(brinquedos), sorte.randint(2, 5))))
        for titulo in ("Playground do Condomínio", "Espaço Kids do Shopping"):
            projetado = BrinquedosProjeto.objects.create(nome_brinquedo_projeto=f"{PREFIXO_NOME} {titulo}", descricao="Projeto de demonstração.")
            BrinquedosProjeto.objects.filter(pk=projetado.pk).update(criacao=momento(sorte.randint(30, 300)))
            Projetos.objects.create(titulo=f"{PREFIXO_NOME} {titulo}", descricao="Projeto de demonstração.", brinquedo_projetado=projetado)
            for k in range(sorte.randint(3, 7)):
                montagem = MontagemTresD.objects.create(nome=f"{PREFIXO_NOME} montagem {k + 1}", projeto=projetado, feito_por="equipe")
                MontagemTresD.objects.filter(pk=montagem.pk).update(criacao=momento(sorte.randint(0, 200)))
        for n in range(26):
            pedido3d = PedidoProjeto3D.objects.create(
                nome=f"{PREFIXO_NOME} cliente {n + 1}", whatsapp="11999990000", largura=Decimal("8"), comprimento=Decimal("12"),
                status=sorte.choice(["novo", "conversa", "orcado", "fechado", "fechado", "arquivado"]),
            )
            PedidoProjeto3D.objects.filter(pk=pedido3d.pk).update(criacao=momento(int(DIAS * sorte.random() ** 1.3)))

        self.stdout.write(self.style.SUCCESS(
            f"Semeado: {len(interacoes)} horas de interação, {len(contas)} contas, {len(acessos)} acessos, "
            f"{len(favoritos)} curtidas, {len(pedidos)} pedidos, {len(orcamentos)} orçamentos, "
            f"{len(clientes)} clientes, 3 cupons, 3 eventos, 2 projetos. Apague com --apagar."
        ))


NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elisa", "Fábio", "Gabi", "Heitor", "Iara", "João", "Karen", "Lucas",
         "Marina", "Nicolas", "Olívia", "Pedro", "Quésia", "Rafael", "Sofia", "Tiago", "Úrsula", "Vitor", "Yasmin"]
SOBRENOMES = ["Silva", "Souza", "Oliveira", "Santos", "Pereira", "Lima", "Costa", "Almeida", "Ribeiro", "Martins"]
