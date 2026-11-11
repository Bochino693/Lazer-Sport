"""Importação de orçamento do Word: o documento vira uma proposta conferida.

O PEDIDO. O comercial recebe e escreve orçamento em Word, e depois digita
tudo de novo no painel -- cliente, item por item, preço por preço. É o
retrabalho que mais erra: um zero a menos no unitário, a cama elástica de
3 m no lugar da de 4 m, o frete esquecido. A importação lê o .docx e monta
o orçamento para a pessoa só CONFERIR.

POR QUE EM CAMADAS, E NÃO "A IA LÊ E PRONTO". Uma IA lendo um documento
acerta quase sempre -- e "quase sempre" não serve para dinheiro. Então
cada camada faz o que sabe fazer bem, e a seguinte desconfia da anterior:

  1. `leitor`        abre o .docx com zipfile + xml.etree e numera cada
                     parágrafo e cada célula ("P12", "T1L3C4"). Esse id é
                     o que permite dizer DE ONDE veio cada valor.
  2. `deterministica` lê o que dá para ler com regra: dinheiro em reais
                     (com Decimal, nunca float), quantidade, CPF/CNPJ
                     validado, telefone, e-mail, datas, e as tabelas de
                     itens pelo cabeçalho. Funciona sem IA nenhuma.
  3. `ia`            pede ao Claude que entenda o documento e devolva o
                     orçamento num esquema fixo, CITANDO o id e o trecho
                     exato de cada valor.
  4. `conferencia`   não acredita em ninguém: todo valor da IA tem de
                     estar escrito na linha que ela citou; quantidade vezes
                     unitário tem de dar o total da linha; a soma tem de
                     bater com o total do documento; e quando as tabelas
                     e a IA leem números diferentes, o alerta é vermelho e
                     a pessoa decide. O que não tem fonte fica vazio.
  5. `catalogo`      casa cada item com o catálogo (nome exato, depois
                     semelhança com os números conferidos) e o cliente
                     com o cadastro (documento, e-mail, telefone, nome).
  6. `formulario`    lista o que falta preencher, valida o envio no
                     servidor e cria o rascunho -- nunca envia nada ao
                     cliente.

O ARQUIVO NÃO FICA GUARDADO. Ele é lido da memória do pedido e descartado;
o que a tela de conferência precisa (as linhas numeradas e a leitura) mora
na sessão de quem importou até o orçamento ser criado ou descartado, e da
importação sobra só o nome do arquivo, na atividade do orçamento.
"""
