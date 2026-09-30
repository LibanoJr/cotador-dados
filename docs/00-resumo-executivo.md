# Resumo executivo: dados confiáveis e sempre atualizados no Cotador

## O problema, visto pelo corretor

O corretor usa o Cotador na frente do cliente. Quando o preço está errado ou vencido, quem perde a
credibilidade primeiro é ele, e depois o Cotador. Hoje a equipe lê e digita cada tabela, por plano e por
operadora, e o erro só aparece quando alguém reclama. Isso não escala: o mercado tem 668 operadoras
ativas, e só o sistema Unimed reúne cerca de 340 cooperativas com tabelas próprias.

**A causa raiz não é a digitação. É não existir verificação independente do dado.** Quem lê o material é
quem garante que ele está certo. Automatizar só a digitação produziria erros mais rápido.

## O que a pesquisa mostrou

- **Todo plano tem um número de registro na ANS**, que aparece nas tabelas de venda, na divulgação da
  rede e nas listas de suspensão. Ele liga o material da operadora aos dados oficiais.
- **A ANS publica, como dado aberto e com atualização semanal, o valor comercial de cada plano por faixa
  etária.** O preço de venda precisa ficar a até 30% dele. É uma forma de conferir o preço com uma fonte
  que não é a operadora.
- **As regras de faixa etária da RN 563/2022 são verificáveis por máquina**, e o STJ definiu como
  calculá-las.

## A solução

Uma esteira que recebe o material (e-mail, upload, portais), extrai os valores, liga cada plano ao
registro ANS, valida em quatro níveis e manda para conferência humana **só o que tem risco**. Cada
tabela é publicada como uma nova versão com vigência; nada é sobrescrito.

Os quatro níveis de validação são:

1. estrutura;
2. regras da ANS;
3. cruzamento com os dados oficiais;
4. coerência com o histórico.

Para o corretor, cada preço passa a mostrar de onde veio, desde quando vale, quando foi conferido e se
a fonte está atrasada. Nenhum concorrente pesquisado mostra isso.

## Primeira entrega e como medir

| | |
|---|---|
| **Escopo** | Tabelas PME e adesão das 3 operadoras mais cotadas, já cruzadas com a ANS (semanas 3 a 8, após 2 semanas de descoberta) |
| **Métrica principal** | Percentual de valores publicados que precisaram de correção depois |
| **Métricas de apoio** | Tempo do recebimento à publicação; idade do dado por fonte; divergências reportadas por corretores |
| **Acompanhamento** | Revisão quinzenal nos 3 primeiros meses e conversa mensal com 5 corretores ativos |

## O que o protótipo já demonstra

Com dados fictícios, de ponta a ponta:

- um erro de digitação pego por quatro regras independentes;
- um preço fora da referência da ANS publicado só com justificativa auditada;
- um plano suspenso saindo da cotação na data certa;
- cotações de datas passadas reproduzindo o preço que valia no dia.

São 57 testes automatizados, rodados em PostgreSQL. A stack é a mesma da empresa: Django, DRF, React,
PostgreSQL e Vercel.

## Riscos principais

- **Layouts de PDF mudam sem aviso.** Mitigação: extrator por IA como reserva, com verificação de que
  cada valor aparece no documento.
- **Acesso a portais depende de credenciais pessoais.** Mitigação: contas de serviço e parcerias de dados.
- **A referência da ANS valida a plausibilidade do preço, não o valor exato.** Por isso a conferência
  humana continua onde há risco.
