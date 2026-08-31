# Diretriz do aplicativo interno

Este documento vale para tudo que roda em **interno.lazersport.com.br**
(`sistema_interno/`) — **e também para as telas de gestão do site**
(`core/templates/gestao/`), que hoje moram dentro deste aplicativo.

Já foram dois painéis. O `/adm/` era um lugar à parte, azul, com menu
escrito sempre aberto, e este documento dizia que não valia para lá.
Aquele painel deixou de existir: menu, topo, sessão, identidade e regras
de cadastro passaram a ser os daqui, e as telas herdadas foram traduzidas
para esta paleta. Onde este documento fala em "tela nova", vale igual para
uma tela herdada que for mexida.

Quem lê isto antes de criar uma tela nova entrega algo que parece parte do
mesmo aplicativo. Quem não lê entrega mais uma tela com desenho próprio —
e o preço disso já foi pago uma vez.

---

## 1. O que este lugar é

O interno é a **bancada de trabalho da empresa**: orçamento, produção,
estoque, clientes, financeiro e manutenção. É onde o dia acontece.

Três fatos moldam todas as decisões de interface:

1. **É usado em tablet, em pé, na fábrica.** Com uma mão só, às vezes com
   luva, com o aparelho apoiado na bancada. Não é um sistema de escritório.
2. **Quem usa não trabalha com computador.** Monta brinquedo, atende
   cliente, controla material. A tela precisa ser óbvia sem treinamento.
3. **A mesma pessoa cuida do chão de fábrica e da vitrine no mesmo dia.**
   Trocar de assunto não pode parecer trocar de sistema.

Por isso o interno é **grafite quente com âmbar**, tem **trilho de ícones**
no lugar de menu escrito, e tem **abas na base da tela** no celular e no
tablet em pé — e por isso as telas do site seguem a mesma cor e a mesma
forma. Enquanto elas eram azuis, a identidade mudava a cada clique do
menu, e a pessoa parava para se localizar antes de cada tarefa.

---

## 2. Princípios

### 2.1. Decisão antes de dado
A tela abre mostrando **o que precisa de você**, não um relatório. A home é
uma fila de decisões; o gráfico vem depois, se vier. Número sem ação ao
lado é enfeite.

### 2.2. O caminho mais curto até terminar a tarefa
Se a pessoa precisa sair da tela para concluir o que começou, o fluxo está
errado. Foi por isso que nasceram o "cadastrar brinquedo na hora", o
"cadastrar cliente na hora" e o "criar produto de dentro do manual": em
todos os três, sair e voltar significava perder o trabalho pela metade.

### 2.3. Cadastro que falta é cadastro que se cria na hora
Todo campo de busca tem, no rodapé, a linha **"Cadastrar ..."** já com o
que a pessoa digitou. O que falta no cadastro aparece justamente quando o
cliente está esperando do outro lado do telefone.

### 2.4. Rascunho bom vence tela em branco
Formulário longo em branco trava. Roteiro padrão de produção, valor
sugerido vindo do catálogo, quantidade começando em 1: tudo que dá para
preencher com um palpite razoável já vem preenchido — e **nunca**
sobrescreve o que a pessoa ajustou à mão.

### 2.5. A palavra do galpão, não a do sistema
"Cadastro", não "registro". "Buffet parceiro", não "entidade vinculada".
"O que precisa de você", não "pendências do usuário". Se a frase não sai
na conversa da bancada, ela não entra na tela.

### 2.6. Erro explica o que fazer
`"Informe ao menos um contato: telefone/WhatsApp ou e-mail."` — e não
`"Campo obrigatório"`. A mensagem aparece dentro do próprio modal, com o
que foi digitado ainda na tela.

### 2.7. Nada de tela morta
Tela sem conteúdo mostra **o próximo passo**, com botão. Lista vazia de
manual não diz "nenhum registro": diz que sem etapa a ordem sai sem
acompanhamento e oferece gerar o roteiro padrão.

---

## 3. Cor e tipografia

Os tokens estão no topo de `sistema_interno/static/interno/interno_modern.css`.

| Uso | Token | Cor |
|---|---|---|
| Fundo da aplicação | `--bg-0` … `--bg-2` | grafite quente |
| Superfície de painel | `--panel`, `--panel-2`, `--panel-3` | grafite claro |
| Ação principal | `--acento` | âmbar `#F2A93B` |
| Confirmação / destaque frio | `--apoio` | teal `#3DD9C0` |
| Positivo | `--green` | `#5FD68A` |
| Atenção | `--yellow` | `#FFC94D` |
| Erro / urgente | `--red` | `#FF7A6B` |
| Texto | `--text`, `--text-2`, `--muted` | creme → areia |

Regras:

* **Âmbar é ação, não decoração.** Se tudo é âmbar, nada é.
* **Vermelho só para o que é urgente de verdade** — prazo estourado,
  estoque zerado, falha. Vermelho gasto vira ruído e a pessoa para de ver.
* Nunca escreva cor solta em hexadecimal numa tela nova: use os tokens.
  Os nomes históricos `--blue` e `--cyan` são apelidos do âmbar e do teal;
  código novo pede por `--acento`, `--acento-2` e `--apoio`.

Hierarquia de texto: título da tela grande e apertado (`letter-spacing`
negativo), rótulo de seção em maiúsculas pequenas (`.app-eyebrow`,
`.ls-page-kicker`), apoio em `--muted`. Nunca mais de três pesos por bloco.

---

## 4. Estrutura da tela

```
ls-shell
├── ls-sidebar        trilho de ícones; expande e a escolha fica no aparelho
├── ls-abas           abas de baixo (só em tela estreita)
└── ls-main
    ├── ls-topbar     nome da tela + sino de avisos + conta
    └── ls-content    o trabalho
```

Dentro do conteúdo, a ordem é sempre a mesma:

1. `ls-page-hero` — o que é esta tela, em uma frase, e a ação principal à
   direita. (O parágrafo some no tablet: ajuda quem abre pela primeira vez
   e atrapalha quem abre quarenta vezes por dia.)
2. `ls-metrics` — poucos números, todos ligados a uma decisão. A faixa se
   ajusta à quantidade de cartões; passar de cinco é sinal de que a tela
   virou relatório.
3. `ls-filter-panel` — busca e filtros, em `<form method="get">`.
4. `ls-data-panel` — a lista ou tabela, com `ls-empty` desenhado.
5. Modais no fim do arquivo, dados via `{{ ...|json_script:"..." }}`.

---

## 5. Componentes

### Busca (`ls-busca.js`)
O campo de escolher qualquer coisa: item de orçamento, cliente, buffet,
produto, colaborador. **Nunca use `<select>` com mais de ~10 opções** —
no tablet ele abre uma roleta que não aceita digitar.

```js
var campo = LSBusca.criar({
  nome: "cliente",                 // name do input escondido
  opcoes: [{valor, rotulo, detalhe, grupo, valorDireita}],
  placeholder: "Buscar cliente...",
  criar: {rotulo: "Cadastrar cliente", aoClicar: function (digitado) {}},
  aoEscolher: function (opcao) {}
});
lugar.appendChild(campo.elemento);
```

Dá filtro sem acento, grupo, preço à direita, teclado (setas/Enter/Esc) e
linha de 48px. `definirValor(valor, false)` repõe sem disparar
`aoEscolher` — use ao reabrir um cadastro salvo, senão o formulário
reescreve o que já estava lá.

### Formulário em modal
Todo cadastro segue o mesmo contrato: `POST` com um campo `action`,
resposta JSON `{status, msg}`, erro voltando para o próprio modal.

```js
Painel.ligar({form: "formCliente", erro: "clienteErro"});
```

No servidor, `RespostaJSONMixin` despacha para `acao_<nome>` e
`ErroDeFormulario` vira mensagem — nunca 500.

### A janela (modal) — o contrato de estrutura
Toda janela tem **cabeçalho fixo, corpo que rola, rodapé fixo**. O
`painel.js` marca `modal-dialog-scrollable modal-dialog-centered` em toda
janela do painel, na carga e no `show.bs.modal` — então **não é preciso
lembrar disso no template**, e janela nova nasce certa.

A altura vem de `--ls-vh`, escrita pelo `painel.js` a partir do
`visualViewport`. **Nunca use `100dvh` para medir janela**: `dvh` não
enxerga o teclado do tablet, e era exatamente isso que deixava "Salvar" e
"Cancelar" escondidos atrás dele, sem rolagem que os alcançasse. Um teste
(`JanelasDoPainelTests`) reprova o `100dvh` que voltar.

Campo que ganha foco e está fora de vista é trazido para o meio do corpo
da janela — rolar a página não resolveria, porque no modal quem rola é o
corpo.

**Nada fixo pode ficar acima da janela.** O modal do Bootstrap é
z-index 1055. As abas de baixo são 1100 e cobriam o rodapé: num aparelho
estreito o toque em "Salvar" caía na aba. Elas somem com
`body.modal-open`. Elemento fixo novo que passe de 1055 precisa sumir do
mesmo jeito — há teste que reprova o que aparecer.

### Campos que se digitam da direita para a esquerda
Dinheiro, metragem e porcentagem funcionam como maquininha: só dígitos,
duas casas sempre. `1` → `0,01`, `10` → `0,10`, `100` → `1,00`,
`123456` → `1.234,56`.

```html
<input data-mascara="moeda"      inputmode="decimal">  <!-- R$        -->
<input data-mascara="medida"     inputmode="decimal">  <!-- metros    -->
<input data-mascara="percentual" inputmode="decimal">  <!-- 0 a 100 % -->
```

Valor que **já existe** (vindo do servidor ou posto por `Painel.valor`) é
número, não digitação: entra por `moedaFinal`, senão "80" viraria "0,80".
Linha criada por JavaScript precisa de `Painel.aplicarMascaras(tr)`.

Nunca use `type="number"` para dinheiro: vários navegadores recusam a
vírgula e apagam o valor no envio.

### Campo de texto
`<textarea>` cresce com o que se escreve, até 320px, e só então rola.
Automático — `Painel.acomodarTextos` roda na carga e ao abrir a janela.
Medir um campo escondido devolve zero, por isso o ajuste acontece no
`shown.bs.modal`, não antes.

### Tabela
`.ls-table` com `data-rotulo` em cada `<td>`: em tela estreita a linha
vira cartão e o rótulo aparece sozinho. Sem `data-rotulo`, a tabela fica
ilegível no celular.

### Estado
`.ls-status` com `success` / `warning` / `danger` / `info` / `neutral`.
Um selo por linha. Dois selos disputando atenção não informam nada.

### Campo de foto (`.ls-foto`)
Uma peça só para o painel inteiro: retângulo tracejado que aceita clique e
arraste, miniatura dentro dele quando já há imagem, e um "Remover" que
manda `remover_logo=1` para o servidor. Antes cada tela tinha o seu — numa
o `input type=file` aparecia cru, com o botão cinza do sistema; noutra uma
área branca tracejada; noutra um botão azul dentro de um cartão.

```html
<div class="ls-foto" id="clienteLogoCampo">
  <span class="ls-foto-miniatura"><i class="bi bi-image"></i><img src="" alt=""></span>
  <span class="ls-foto-copy">
    <strong>Escolha uma imagem</strong>
    <span>PNG, JPG ou WEBP.</span>
    <span class="ls-foto-acoes">
      <label class="ls-foto-escolher">Selecionar
        <input type="file" name="logo" accept="image/png,image/jpeg,image/webp">
      </label>
      <button type="button" class="ls-foto-limpar" hidden>Remover</button>
    </span>
  </span>
</div>
```

A classe `tem-imagem` no `.ls-foto` troca o ícone pela miniatura. Onde a
tela pede VÁRIAS imagens de uma vez não há miniatura única para mostrar:
ali basta o `input type=file`, que já nasce com o mesmo retângulo
tracejado.

### Os três papéis de botão
Só existem três, e a cor é a mesma no painel inteiro:

| Papel | Como | Exemplo |
|---|---|---|
| Conclui | verde (`.btn-success`) | Salvar, Criar, Novo cliente |
| Mexe na tela | âmbar (`.btn-primary`) | Filtrar, Buscar, Recalcular |
| Destrói | vermelho (`.btn-danger`) | Excluir |

Nas telas herdadas, quem separa "concluir" de "filtrar" é o **método do
formulário**, e não o nome da classe: metade dos botões de filtrar é um
`<button type="submit">` sem classe nenhuma. `GET` reorganiza a tela;
`POST` grava.

---

## 6. Toque

Regras que valem para qualquer aparelho de toque (bloco
`@media (pointer:coarse)` no fim do CSS):

* alvo mínimo **48px**; botão dentro de tabela, **46×46**;
* campo de formulário com **16px** de fonte — abaixo disso o Safari do
  iPad dá zoom sozinho ao focar e a pessoa perde o formulário de vista;
* rodapé de modal **grudado na base**, senão o "Salvar" desaparece abaixo
  da dobra em formulário longo — e a altura da janela sai de `--ls-vh`,
  não de `dvh`, para o teclado não cobrir esse rodapé;
* em tela estreita o modal vira **folha**, encostada na base, com o topo
  arredondado;
* o que é destrutivo pede confirmação em texto (o nome digitado), nunca um
  toque só.

---

## 7. É um aplicativo, não um site

O painel declara manifesto (`/manifest.webmanifest`) e service worker
(`/sw.js`), os dois servidos da **raiz do subdomínio** por `views_app.py`
— de `/static/` o aplicativo abriria dentro da pasta de estáticos e o
service worker não controlaria nada.

Instalado, ele abre em tela cheia, com ícone próprio e sem barra de
endereço; some também o toque acidental na barra, que tirava a pessoa do
meio de um cadastro.

O service worker **repassa tudo para a rede, de propósito**. Painel de
operação com resposta em cache mostra número velho sem avisar, e ninguém
confere um dado que a tela apresenta como atual. Se um dia for preciso
guardar algo, que seja uma fila de envio — nunca a resposta de uma tela.

---

## 8. Cadastro de cliente — um só

Não existe "cliente do painel" e "cliente do site". Existe
`sistema_interno.Cliente`, e a vitrine **lê** dele:

* `tipo` diz onde o brinquedo vai parar — residencial, comercial, buffet,
  condomínio, escola, órgão público. Não é burocracia: residência quer
  entrega na porta; comércio quer nota, horário de carga e alguém para
  receber; escola e condomínio pedem portaria.
* `publicar_no_mapa` diz se o alfinete aparece na página inicial; o
  **endereço do estabelecimento** diz onde. É um endereço só, e serve para
  entrega, montagem e mapa.
* `logo` e `site_cliente` são a parte do cadastro que fica visível para
  quem não é da casa.
* Buffet nunca vira alfinete: ele já tem o card dele em "Nossos
  Parceiros", e os dois juntos o mostrariam duas vezes. A regra mora no
  `save()` do modelo.

Marcado para o mapa **não é** o mesmo que desenhado no mapa: sem
coordenada não há alfinete, e a tela diz isso (`Cliente.no_mapa`) em vez
de deixar a pessoa achar que publicou.

Toda gravação passa por `sistema_interno/clientes.py`, venha da aba
Clientes, da tela do mapa ou do cadastro rápido de dentro do orçamento —
é o que mantém nome repetido, contato obrigatório e endereço com a mesma
regra em todo lugar.

> **Cuidado com caixa de marcar.** Caixa desmarcada não é enviada pelo
> navegador, e "não veio" é indistinguível de "esta tela não pergunta
> isso" — o cadastro rápido do orçamento não pergunta sobre o mapa e não
> pode despublicar ninguém. Por isso todo formulário que pergunta manda um
> `<input type="hidden">` de mesmo nome, antes da caixa.

---

## 9. Permissão

| Papel | Vê |
|---|---|
| Colaborador (`is_staff`) | Minha produção, estoque, movimentações |
| Gestor (`Gerente.ativo` ou superusuário) | Tudo, inclusive comercial e financeiro |

Use `InternoRequiredMixin` e `GestorInternoRequiredMixin`. **Item de menu
que leva a um desvio é pior que item de menu ausente**: se a view exige
gestor, envolva o link em `{% if eh_gestor_interno %}`.

---

## 9.1. A tela troca sem recarregar a página — o que isso cobra de você

Clicar no menu **não recarrega a página**. `ls-soft-navigation.js` busca a
tela nova, garante o CSS dela e troca só a área de conteúdo; o menu, a
barra de cima e as folhas do painel continuam sendo os mesmos nós, com os
mesmos ouvintes.

Isso é o que acabou com a tela sem estilo por um instante — a que fazia o
logotipo aparecer do tamanho do arquivo e o ícone do botão de enviar virar
um símbolo qualquer do aparelho. Antes a troca era `document.write`, que
jogava o documento fora e remontava tudo, o `<head>` junto.

Em troca, três combinados. Todos têm teste em `tests_navegacao.py`, e
quebrar qualquer um só aparece no navegador **depois do segundo clique** —
que é onde ninguém testa à mão.

**1. Script de tela usa `LSTela.pronto()`, nunca `DOMContentLoaded`.**

```html
{% block scripts %}
<script>
LSTela.pronto(function () {
  "use strict";
  ...
});
</script>
{% endblock %}
```

`DOMContentLoaded` acontece uma vez por *página*, e a página não recarrega:
da segunda tela em diante o evento não vem mais, e o script nunca roda. Os
botões aparecem e nenhum deles faz nada.

**2. Folha de estilo em `extra_css` leva `data-ls-tela="1"`.**

```html
{% block extra_css %}
<link rel="stylesheet" data-ls-tela="1" href="{% static 'interno/minha_tela.css' %}?v=1">
{% endblock %}
```

É a marca que diz "esta folha é desta tela". Sem ela, a folha entra no
`<head>` na primeira vez que a tela abrir e continua valendo em todas as
seguintes — a tela certa, com as regras de outra. `<style>` escrito dentro
de `extra_css` não precisa de marca; dentro de `{% block content %}`,
menos ainda, porque sai junto com o conteúdo.

**3. O que a tela pendura no `<body>` ela tem de saber desfazer.**

Menu flutuante de ações, painel de busca e afins vivem fora da área
trocada, por causa do `position:fixed`. `Painel.limparPendurados()` apaga
os do painel antes de cada troca; se a sua tela pendurar algo próprio no
`<body>`, ele precisa entrar nessa limpeza — senão sobra órfão na tela
seguinte, e o primeiro da fila passa a ser um botão de uma tela que já não
existe.

E uma consequência boa de graça: como a área de conteúdo é recriada,
`Painel.montarTela()` roda de novo a cada tela. Máscara de campo, textarea
que cresce e agrupamento de ações de tabela já vêm prontos — você não
chama nada.

---

## 9.2. Regras que valem em qualquer tela

**Link público só existe depois de o documento sair do rascunho.** A
página do cliente recusa rascunho com 404, de propósito. Pergunte a
`Orcamento.publicado` / `OrdemServico.publicado` antes de mostrar
endereço — foi entregar o link cedo demais que fazia o gestor levar um
404 ao conferir a proposta antes de mandar. Para conferir antes de
enviar existe a prévia interna, que é do painel e abre rascunho.

**A bolinha do menu e a tela têm de contar a mesma coisa.** A tela de
Pedidos listava uma tabela e o selo contava outra: o menu dizia "6
pedidos" sobre uma tela vazia. Nada dava erro, e nenhum teste percebia
porque as duas fontes nunca se cruzavam. Quando criar um contador, cruze
os dois num teste.

**Excluir: a regra da tela decide, o superusuário tem a última palavra.**
Use `exclusoes.pode_excluir()` e `exclusoes.remover()`. A exclusão que
passa por cima de uma proteção fica registrada em `ExclusaoRegistrada`,
e o botão avisa antes com `data-protegido="1"` — apagar histórico não
pode ter a mesma cara de apagar um rascunho.

**Aviso para a equipe e aviso para o cliente são arquivos diferentes.**
`notificacoes.py` diz "isto precisa da sua ação" e vai por push;
`notificacoes_cliente.py` diz "a decisão é sua" e vai por e-mail. Um
texto para os dois vira ou cobrança ao cliente ou recado ameno à equipe.

**Nada de consulta por linha.** Duas armadilhas já custaram 26 idas ao
banco numa página de 25:

- `.first()` numa propriedade que o template toca (vira ORDER BY +
  LIMIT 1 e ignora o prefetch — use `all()[0]`);
- `.select_related()` sobre relação que a view já traz por prefetch
  (monta consulta nova e joga o cache fora).

`tests_desempenho.py` abre cada lista com 3 e com 25 registros e reprova
se a conta crescer.

**Urgência com caminho óbvio traz o botão junto.** Item de fila que só
aponta é item que se lê, se adia e vence. Se o atalho não tem como
funcionar naquele caso (falta e-mail, prazo já passou), não mostre o
botão: botão que falha ao ser tocado ensina a não tocar em botão nenhum.

**Cor: grafite e âmbar, teal para execução.** O /adm do site é azul, e é
dele que este aplicativo se distingue. `tests_navegacao.py` lista os
tons do painel antigo e reprova qualquer um de volta.

**A ação só aparece quando cabe naquela situação.** A lista trazia os
mesmos botões em toda linha, e cada um falhava de um jeito diferente
quando não cabia: "Enviar" numa proposta vencida gerava o link de uma
página que anuncia "proposta expirada"; "Registrar pagamento" numa
proposta quitada abria uma janela pedindo um valor que já estava lá.
Botão que não cabe não é neutro — ele ensina a duvidar dos outros.
Pergunte ao modelo (`pode_enviar`, `pode_receber_pagamento`, `quitado`,
`pode_refazer`) e **repita a regra no servidor**: a tela é sugestão, a
regra é onde os dados entram.

**Filtro de lista não vai ao servidor.** O servidor manda, junto da
página, um índice enxuto (`busca_local.montar_indice`) e
`ls-filtro-local.js` procura nele — sem rede, sem recarregar e sem mexer
na URL. Duas coisas são obrigatórias: **o índice cobre o filtro inteiro,
não a página desenhada** (senão a tela responde "nada encontrado" sobre
um registro da página 2), e **os campos do índice são os mesmos que a
busca do servidor percorre** (se divergirem, digitar e apertar "Trazer
todos" dão respostas diferentes, e ninguém confia em nenhuma das duas).
As linhas apenas somem e voltam: nada reescreve a tabela, então os
ouvintes já pendurados nos botões continuam valendo.

**Janela que mostra parte do cadastro precisa de regra própria.**
`salvar_cliente` lê o formulário inteiro, e está certo para a edição:
campo ausente ali significa "o usuário apagou". Numa janela de três
campos, essa mesma leitura apaga o telefone de quem só veio informar o
CPF. Para isso existe `completar_cadastro`, onde cada campo é opcional e
só grava quando veio preenchido — com as mesmas validações da edição.
E lembre: **caixa desmarcada não viaja no POST**, então "não" e "nem
perguntamos" chegam iguais; mande um marcador escondido junto quando a
diferença importar.

**Nenhuma tela pede arquivo que não existe.** Indicadores pedia um
`Chart.min.js` que nunca esteve no repositório, e o site pedia oito
imagens de reserva que também não. Nada disso dava erro: a página abria,
respondia 200, e simplesmente não mostrava o que devia — a falha mais
difícil de achar olhando, porque quem usa supõe que não há dado.
`tests_estaticos.py` percorre todo `{% static %}` do projeto, e
`tests_urls.py` abre cada rota saindo da própria lista de URLs, de modo
que rota nova entra na varredura sozinha.

**Nada de CDN.** O painel roda na estrada, instalado como aplicativo:
Bootstrap, os ícones e a fonte já são servidos daqui. Um gráfico de uma
série cabe em SVG escrito à mão; não vale trazer biblioteca para isso.

**Impresso: altura mínima, nunca fixa.** Com `height`, um endereço de
quatro linhas empurra o rodapé para fora da moldura e o papel sai
cortado justamente na parte que explica o documento. E impressora
descarta fundo por padrão — se a cor carrega significado (a faixa do
aviso de frágil), marque `print-color-adjust:exact`.

---

## 10. Checklist da tela nova

- [ ] Estende `base_inner.html` e preenche `top_title`.
- [ ] Hero com uma frase e a ação principal.
- [ ] No máximo quatro métricas, todas ligadas a uma decisão.
- [ ] Busca com `LSBusca` em vez de `<select>` longo.
- [ ] Cadastro que falta pode ser criado sem sair da tela.
- [ ] Estado vazio com o próximo passo e botão.
- [ ] `data-rotulo` em toda `<td>`.
- [ ] Mensagem de erro que diz o que fazer.
- [ ] Testado com `HTTP_HOST="interno.testserver"` — inclusive o caso de
      quem não é gestor.
- [ ] Nenhuma cor solta: só tokens.
- [ ] Imagem entra por `.ls-foto` (ou por `input type=file`, se forem
      várias) — nunca pelo botão cru do navegador.
- [ ] Botão de concluir verde, de filtrar âmbar, de excluir vermelho.
- [ ] Caixa de marcar acompanhada do campo escondido de mesmo nome.
- [ ] Script da tela dentro de `LSTela.pronto()` (ver 9.1).
- [ ] Folha em `extra_css` marcada com `data-ls-tela="1"` (ver 9.1).
- [ ] Data que olha para a frente com `data-nao-passado` no campo — e a
      conferência repetida na view, que é por onde os dados entram.
- [ ] Link público só depois de `publicado` (ver 9.2).
- [ ] Contador novo cruzado com a tela num teste (ver 9.2).
- [ ] Exclusão por `exclusoes.remover()` (ver 9.2).
- [ ] Lista aberta com 3 e com 25 registros: a conta de consultas não
      pode crescer (ver 9.2).
- [ ] Cada ação de linha perguntou ao modelo se cabe naquela situação — e
      o servidor repete a regra (ver 9.2).
- [ ] Busca da lista com índice local: `data-filtro-alvo` na caixa,
      `data-registro` na linha, e o índice cobrindo o filtro inteiro
      (ver 9.2).
- [ ] Nenhum `{% static %}` apontando para arquivo que não existe, e
      nenhuma biblioteca de fora (ver 9.2).
- [ ] Se imprime: altura mínima em vez de fixa, e
      `print-color-adjust:exact` onde a cor significa algo (ver 9.2).
