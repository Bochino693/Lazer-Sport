# Diretriz do aplicativo interno

Este documento vale para tudo que roda em **interno.lazersport.com.br**
(`sistema_interno/`). Não vale para o `/adm/` do site (`core/templates/gestao/`),
que é outro lugar, com outra cara e outro público.

Quem lê isto antes de criar uma tela nova entrega algo que parece parte do
mesmo aplicativo. Quem não lê entrega mais uma tela parecida com o painel
do site — e o objetivo aqui é justamente o contrário.

---

## 1. O que este lugar é

O interno é a **bancada de trabalho da empresa**: orçamento, produção,
estoque, clientes, financeiro e manutenção. É onde o dia acontece.

Três fatos moldam todas as decisões de interface:

1. **É usado em tablet, em pé, na fábrica.** Com uma mão só, às vezes com
   luva, com o aparelho apoiado na bancada. Não é um sistema de escritório.
2. **Quem usa não trabalha com computador.** Monta brinquedo, atende
   cliente, controla material. A tela precisa ser óbvia sem treinamento.
3. **A mesma pessoa também abre o `/adm/` do site no mesmo dia.** Se os
   dois forem parecidos, ela mexe no lugar errado.

Por isso o interno é **grafite quente com âmbar**, tem **trilho de ícones**
no lugar de menu escrito, e tem **abas na base da tela** no celular e no
tablet em pé. O `/adm/` é azul, com menu escrito sempre aberto. A diferença
é proposital: cor e forma são o jeito mais rápido de o olho saber onde
está, antes de ler qualquer título.

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
2. `ls-metrics` — no máximo quatro números que mudam a decisão.
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

## 8. Permissão

| Papel | Vê |
|---|---|
| Colaborador (`is_staff`) | Minha produção, estoque, movimentações |
| Gestor (`Gerente.ativo` ou superusuário) | Tudo, inclusive comercial e financeiro |

Use `InternoRequiredMixin` e `GestorInternoRequiredMixin`. **Item de menu
que leva a um desvio é pior que item de menu ausente**: se a view exige
gestor, envolva o link em `{% if eh_gestor_interno %}`.

---

## 9. Checklist da tela nova

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
