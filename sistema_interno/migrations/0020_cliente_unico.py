"""Um cadastro de cliente só, para o painel e para o mapa do site.

Eram dois. Este, do painel, com contato, documento e histórico de
proposta; e `core.Clientes`, do site, que existia só para pôr um alfinete
no mapa da vitrine. O mesmo buffet era digitado nos dois lugares, e nada
obrigava os dois a concordarem -- o mapa mostrava o endereço antigo
enquanto a proposta saía com o novo.

Esta migração:

1. dá ao cliente do painel o que faltava para ele sozinho alimentar o
   mapa (logo, link, "aparece no mapa", país e precisão da coordenada);
2. renomeia `pessoa` e `empresa` para `residencial` e `comercial` -- o
   nome que interessa a quem carrega o caminhão;
3. TRAZ PARA CÁ cada linha do cadastro do site. O que já estava ligado a
   um cliente interno (pelo antigo `cliente_mapa`) apenas completa o
   cadastro; o que não estava vira cliente novo, com o endereço e a
   coordenada que o mapa já usava. Nada é descartado.

O passo 3 é o que torna a migração irreversível na prática: depois dela,
o cadastro do site deixa de existir (ver a migração de `core`).
"""

from django.db import migrations, models
import django.db.models.deletion


def trazer_clientes_do_site(apps, schema_editor):
    Cliente = apps.get_model("sistema_interno", "Cliente")
    EnderecoCliente = apps.get_model("sistema_interno", "EnderecoCliente")
    ClienteDoSite = apps.get_model("core", "Clientes")

    # 1) Os nomes velhos do tipo.
    Cliente.objects.filter(tipo="pessoa").update(tipo="residencial")
    Cliente.objects.filter(tipo="empresa").update(tipo="comercial")

    for antigo in ClienteDoSite.objects.all():
        interno = Cliente.objects.filter(cliente_mapa_id=antigo.pk).first()

        if interno is None:
            # Cliente que só existia no mapa. Nome repetido significa a
            # mesma empresa cadastrada dos dois lados: junta, não duplica.
            nome = (antigo.descricao_cliente or "").strip() or f"Cliente {antigo.pk}"
            interno = Cliente.objects.filter(nome_cliente__iexact=nome).first()

        if interno is None:
            interno = Cliente(
                nome_cliente=nome[:90],
                # Quem estava no mapa é ponto de venda, não residência.
                tipo="comercial",
                telefone="",
                telefone_digitos="",
            )

        # O cadastro do painel manda no que os dois tinham (contato, nome).
        # O do site manda no que só ele tinha.
        if antigo.logo_cliente and not interno.logo:
            interno.logo = antigo.logo_cliente
        if antigo.site_cliente and not interno.site_cliente:
            interno.site_cliente = antigo.site_cliente

        # Buffet não vira alfinete de cliente: ele já tem o card dele em
        # "Nossos Parceiros", e os dois juntos o mostrariam duas vezes no
        # site. A regra vive no `save()` do modelo, que a migração não
        # executa -- por isso é repetida aqui.
        if antigo.exibir_no_mapa and antigo.ativo and interno.tipo != "buffet":
            interno.publicar_no_mapa = True
        interno.save()

        endereco = interno.enderecos.first()
        tinha_endereco = endereco is not None
        if endereco is None:
            endereco = EnderecoCliente(cliente=interno)

        # Endereço do painel, quando existe, é o mais recente: o do site só
        # preenche o que estiver vazio.
        mesma_rua = (
            (endereco.cep or "").strip() == (antigo.cep or "").strip()
            and (endereco.endereco or "").strip().lower()
            == (antigo.rua or "").strip().lower()
            and (endereco.numero or "").strip() == (antigo.numero or "").strip()
        )

        endereco.cep = endereco.cep or (antigo.cep or "")
        endereco.endereco = endereco.endereco or (antigo.rua or "")
        endereco.numero = endereco.numero or (antigo.numero or "")
        endereco.bairro = endereco.bairro or (antigo.bairro or "")
        endereco.cidade = endereco.cidade or (antigo.cidade or "")
        endereco.estado = endereco.estado or (antigo.estado or "")
        endereco.pais = antigo.pais or "Brasil"

        # A COORDENADA SÓ VEM JUNTO COM O ENDEREÇO DELA.
        #
        # A do mapa já foi conferida por alguém e vale a pena aproveitar --
        # mas só enquanto apontar para a rua que ficou gravada. Se o painel
        # já tinha um endereço diferente (mudança de sede, correção), o
        # ponto do mapa é do endereço ANTIGO: herdá-lo escreveria a rua nova
        # com o alfinete velho, que é exatamente a divergência que esta
        # migração existe para acabar. Sem coordenada, o cadastro fica
        # pendente e é localizado depois -- pelo botão "recalcular" da tela
        # ou pelo comando `conferir_mapa`.
        herda_ponto = not tinha_endereco or mesma_rua
        if endereco.latitude is None and antigo.latitude is not None and herda_ponto:
            endereco.latitude = antigo.latitude
            endereco.longitude = antigo.longitude
            endereco.precisao = antigo.precisao_local or ""
        elif not endereco.precisao and endereco.latitude is not None:
            endereco.precisao = "manual"

        # Não grava um endereço vazio só porque a linha do site existia.
        if endereco.endereco or endereco.cidade or tinha_endereco:
            endereco.save()


def desfazer(apps, schema_editor):
    """Só devolve os nomes de tipo. As linhas trazidas ficam.

    Recriar o cadastro paralelo seria refazer o problema, e não há como
    saber quais dos clientes de hoje nasceram lá.
    """
    Cliente = apps.get_model("sistema_interno", "Cliente")
    Cliente.objects.filter(tipo="residencial").update(tipo="pessoa")
    Cliente.objects.filter(tipo="comercial").update(tipo="empresa")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_vitrine_cupons"),
        ("sistema_interno", "0019_colaborador_operacional"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="ativo",
            field=models.BooleanField(
                default=True,
                help_text="Desmarque para arquivar sem apagar o histórico de propostas.",
                verbose_name="Cadastro ativo",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="publicar_no_mapa",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Põe o alfinete deste cliente no mapa da página inicial. "
                    "Precisa do endereço do estabelecimento com localização."
                ),
                verbose_name="Aparece no mapa do site",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Aparece no mapa e na faixa de clientes do rodapé do site.",
                null=True,
                upload_to="logo_clientes/",
                verbose_name="Logo do cliente",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="site_cliente",
            field=models.URLField(
                blank=True,
                help_text='Vira o link "Visitar Instagram" no balão do mapa.',
                null=True,
                verbose_name="Instagram ou site",
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="pais",
            field=models.CharField(
                default="Brasil",
                help_text=(
                    "Cliente fora do Brasil não tem CEP: preencha cidade, estado e país."
                ),
                max_length=60,
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="precisao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("exato", "Endereço exato"),
                    ("rua", "Meio da rua"),
                    ("bairro", "Centro do bairro"),
                    ("cidade", "Centro da cidade"),
                    ("manual", "Informada à mão"),
                ],
                default="",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="complemento",
            field=models.CharField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
        # O número do imóvel cabia em 5 caracteres. "1250-A" não cabe.
        migrations.AlterField(
            model_name="enderecocliente",
            name="numero",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="cep",
            field=models.CharField(blank=True, max_length=18),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="bairro",
            field=models.CharField(blank=True, max_length=50),
        ),
        # 25 caracteres não cabem "Embu das Artes" com o estado junto, e
        # cortavam nomes reais de município.
        migrations.AlterField(
            model_name="enderecocliente",
            name="cidade",
            field=models.CharField(max_length=60),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="estado",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("residencial", "Residencial"),
                    ("comercial", "Comercial"),
                    ("buffet", "Buffet parceiro"),
                    ("condominio", "Condomínio"),
                    ("escola", "Escola"),
                    ("orgao", "Órgão público"),
                ],
                db_index=True,
                default="residencial",
                max_length=12,
                verbose_name="Tipo de cadastro",
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="parceiro",
            field=models.ForeignKey(
                blank=True,
                help_text="Buffet que atende este cliente, quando a festa vem por ele.",
                limit_choices_to={"tipo": "buffet"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clientes_atendidos",
                to="sistema_interno.cliente",
                verbose_name="Buffet responsável",
            ),
        ),
        migrations.RunPython(trazer_clientes_do_site, desfazer),
        migrations.RemoveField(model_name="cliente", name="cliente_mapa"),
    ]
