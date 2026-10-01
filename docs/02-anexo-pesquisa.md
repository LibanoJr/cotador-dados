# Anexo: pesquisa, método e fontes

Este anexo sustenta a proposta (`01-proposta.md`). Ele mostra como a pesquisa foi feita, o que foi
encontrado, com que grau de confiança, o que a pesquisa corrigiu no caminho e o que ainda precisa ser
confirmado com dados reais. As referências numeradas seguem a mesma numeração da proposta, com
acréscimos a partir do número 25.

---

## 1. Método

### 1.1 Perguntas que guiaram a pesquisa

1. Existe alguma fonte oficial que permita conferir o dado da operadora sem depender dela?
2. Quais regras sobre preço são objetivas o bastante para virar validação automática?
3. Quais obrigações de publicação as operadoras têm, e portanto que dados estão acessíveis sem parceria?
4. Qual o tamanho real do problema para o Cotador?
5. Quão confiável é a extração de tabelas por LLM hoje, com números e não com promessa?
6. O que os concorrentes oferecem, e onde há espaço para diferenciação?
7. Quais os limites legais da coleta automatizada?

### 1.2 Hierarquia de fontes

| Nível | Tipo | Exemplos | Uso |
|---|---|---|---|
| A | Fonte primária oficial | Portal de dados abertos, site da ANS, texto de norma, decisão do STJ | Base para regras implementadas |
| B | Fonte secundária especializada | Legislação compilada (Legisweb, Legismap), Idec, escritórios de advocacia | Aceita quando reproduz a norma; marcada para troca por fonte A |
| C | Imprensa e blogs | Portais de notícia, blogs do setor | Só para números de mercado e contexto |
| D | Pesquisa acadêmica e benchmarks | arXiv, relatórios de ferramentas | Ordem de grandeza, nunca como garantia |

Regra adotada: nenhuma regra de validação do protótipo se apoia apenas em fonte de nível C.

### 1.3 Como a IA entrou no trabalho

| Etapa | Papel da IA (Claude) | Papel humano |
|---|---|---|
| Pesquisa | Buscas na web, leitura das fontes, resumo e classificação de cada afirmação por confiabilidade | Definir o foco e decidir o que entra na proposta |
| Proposta | Redação de seções e tabelas | Escolher o recorte e aprovar as decisões |
| Código | Escrita da maior parte dos modelos, serviços, telas e testes | Definir o que construir, rodar os testes, usar o sistema no navegador e em produção, apontar o que não funcionava |
| Publicação | Guia passo a passo do deploy | Configurar GitHub, Vercel e banco, e conferir o resultado no ar |
| Revisão | Segunda leitura da proposta contra o código | Decidir o que corrigir |

**O que a revisão encontrou** (erros reais, corrigidos antes da entrega):

- **Nome de modelo inválido na configuração do extrator por LLM.** Passaria despercebido, porque o
  extrator só roda com chave de API.
- **Norma desatualizada.** A obrigação de divulgar a rede no portal era citada pela RN 285/2011, hoje
  consolidada na RN 486/2022 [11].
- **Periodicidade desatualizada.** O conjunto de valor comercial era tratado como mensal; a ANS passou
  a atualizá-lo semanalmente [16].
- **Promessa sem implementação.** A proposta prometia uma restrição de banco contra vigências
  sobrepostas que o código não tinha. Foi implementada e testada em PostgreSQL.
- **Fonte errada por padrão na tela.** A ordem alfabética colocava a ANS como primeira opção de envio,
  e os PDFs de uma operadora eram atribuídos à fonte errada. O erro só apareceu no teste visual no
  navegador; os testes automáticos não pegavam. Virou duas defesas: o frontend não oferece a ANS como
  fonte de envio, e o backend alerta quando a operadora do documento difere da operadora da fonte.
- **CORS entre frontend e backend.** Apareceu ao rodar os dois em origens diferentes, como será na
  Vercel. Virou configuração documentada e um aviso na tela quando a API não responde.
- **Números em formato americano** nas mensagens de validação.
- **Correção de valor que falhava em silêncio.** Encontrado usando a demonstração publicada: quando a API
  recusava o valor digitado, a tela fechava o campo como se tivesse salvo, e o erro aparecia só no fim da
  página. Agora a tela aceita os formatos comuns de número e mostra o erro ao lado do campo.
- **Comparação que sumia depois de publicar.** Também encontrado em produção: a tabela publicada aparecia
  como "primeira versão", embora fosse a versão 2. Agora ela se compara com a versão que substituiu, e um
  teste automático cobre o caso.

A lição registrada: teste automatizado não substitui usar o sistema como o usuário usa. Cinco dos nove
problemas só apareceram usando o sistema, dois deles já em produção.

---

## 2. Achados

Cada achado traz o nível da fonte (seção 1.2) e como foi usado.

### 2.1 Regras de preço por faixa etária

| Achado | Nível | Fonte | Uso |
|---|---|---|---|
| A RN 563/2022 revogou a RN 63/2003 mantendo o texto, em vigor desde 01/02/2023 | B | [7] | Citação correta nas regras e no código |
| Dez faixas para contratos a partir de 2004: 0-18, 19-23, 24-28, 29-33, 34-38, 39-43, 44-48, 49-53, 54-58, 59+ | B | [6][7] | `servicos/faixas.py` |
| Última faixa no máximo 6 vezes a primeira (art. 3º, I) | B | [6][7] | Regra `RN563_LIMITE_6X`, erro |
| Variação acumulada da 7ª à 10ª não maior que a da 1ª à 7ª (art. 3º, II) | B | [6][7] | Regra `RN563_VARIACAO_7_10`, erro |
| "Variação acumulada" tem sentido matemático (razão entre valores), não soma de percentuais | A | STJ, Tema 1.016 [8] | Forma de cálculo da regra acima |
| Nenhuma variação negativa entre faixas (art. 3º, III, incluído pela RN 254/2011) | B | [6] | Regra `VALOR_DECRESCENTE`, erro |

### 2.2 Referência oficial de preço (o achado principal)

| Achado | Nível | Fonte | Uso |
|---|---|---|---|
| A ANS publica o valor comercial da mensalidade por faixa etária de cada plano, vindo da Nota Técnica de Registro de Produto (NTRP) | A | [4][25] | Tabela `ValorComercialANS` |
| Limites de comercialização: até 30% acima; no mínimo o maior entre a despesa assistencial estimada e 30% abaixo | A | [4][25] | Regras `ANS_ACIMA_DA_BANDA` e `ANS_ABAIXO_DA_BANDA`, liberáveis com justificativa |
| A variação entre faixas da tabela de venda deve manter relação com a da NTRP | A | [25] | Regra `ANS_PADRAO_FAIXAS_DIFERENTE`, alerta |
| O valor comercial é referência e pode diferir da tabela de venda, dentro dos limites | A | [25] | Motivo para a banda ser liberável, e não bloqueio absoluto |
| O conjunto de valor comercial passou de mensal para semanal | A | [16] | Frequência da sincronização |
| A NTRP só existe para planos médico-hospitalares com preço preestabelecido | A | [4] | Limitação declarada na proposta |
| O dicionário de dados usa `VL_COMERCIAL_MENSALIDADE` e um identificador interno `ID_PLANO` | A | [25] | Nome de coluna no importador; ver pendência 4.1 |

**Por que a banda bloqueia, mas é liberável.** Um preço fora da banda tem três explicações: erro de
extração ou de ligação ao registro (a mais provável), nota técnica desatualizada na base da ANS, ou
descumprimento regulatório. Bloquear sem saída travaria a operação no segundo caso. Só alertar deixaria
passar o primeiro. A liberação com justificativa resolve os dois e ainda gera dado: se uma fonte
acumula liberações, algo nela merece atenção.

### 2.3 Outros dados abertos úteis

| Conjunto | Nível | Fonte | Uso previsto |
|---|---|---|---|
| Operadoras ativas e canceladas, em CSV e API JSON | A/B | [2] | Cadastro-mestre de operadoras |
| Características dos produtos (segmentação, abrangência, contratação, situação) | A | [3] | Cadastro-mestre de planos por registro |
| Área de comercialização dos planos | A | [16] | Validar a região da tabela (etapa seguinte) |
| Rede hospitalar e de urgência por plano | A | [5] | Etapa 3 do plano |
| Solicitações de alteração de rede hospitalar (mensal) | B | [17] | Gatilho de reconferência de rede |
| Planos com comercialização suspensa (trimestral) | C | [14] | Retirar da cotação; implementado com referência fictícia |

### 2.4 Obrigações de publicação das operadoras

| Achado | Nível | Fonte | Uso |
|---|---|---|---|
| Rede assistencial divulgada no portal, por plano, com nome comercial, número de registro, tipo de contratação e situação (ativo, suspenso, cancelado); hoje na RN 486/2022 | B | [11] | Fonte pública de rede, sem login |
| Percentual único de reajuste do agrupamento de contratos com menos de 30 vidas publicado no site (RN 565/2022) | B | [15] | Sinal de contexto na conferência de tabelas PME |
| Tabelas de venda reais trazem o registro ANS de cada produto | C | [1] | Ligação automática ao registro; implementada |

### 2.5 Tamanho do mercado

| Achado | Nível | Fonte |
|---|---|---|
| 668 operadoras ativas com beneficiários; as dez maiores concentram 42% | C | [9] |
| Cerca de 340 cooperativas no sistema Unimed | C | [9] |
| Mais de 53 milhões de beneficiários em planos médico-hospitalares | A | [10] |
| Individuais são 14,5%; reajuste máximo de 5,11% para 2026-2027 | C | [12] |
| Coletivo empresarial responde por cerca de 73% dos vínculos | C | [13] |
| O DF cresceu 5,95% em beneficiários em 12 meses até março de 2026 | A | [10] |

Leitura: o grosso do mercado do corretor é coletivo (PME e adesão), onde o preço não é tabelado pela
ANS. É exatamente onde uma referência independente mais ajuda.

### 2.6 Extração com LLM

| Achado | Nível | Fonte | Consequência no desenho |
|---|---|---|---|
| Modelos de ponta acertam de 89% a 98% dos campos, mas só 42% a 77% dos documentos saem inteiramente corretos | D | [21] | Numa tabela com dezenas de valores, ao menos um erro é provável; conferência obrigatória |
| Em tabelas complexas, ferramentas variam de 64,6 a 90,2 pontos | D | [22] | Testar com os próprios documentos (gabarito da Fase 0) |
| Verificação simbólica reduz alucinação em tabelas geradas por LLM | D | [23] | Ancoragem de cada valor no texto do PDF, independentemente do extrator |

### 2.7 Concorrência

| Concorrente | Oferta | Fonte |
|---|---|---|
| Agger (Painel do Corretor) | Mais de 3.000 corretoras; IA para sugerir planos | [18] |
| Simulador Online | Tabelas, rede e carências | [18] |
| Baeta | Assessoria com multicálculo e equipe que mantém tabelas | [18] |

Nenhum destaca a procedência ou a vigência do dado; todos se apoiam em "tabelas atualizadas" mantidas
por equipe. As assessorias recebem tabelas das operadoras e podem ser parceiras de dados (inferência).

### 2.8 Aspectos legais

| Achado | Nível | Fonte | Consequência |
|---|---|---|---|
| Não há regulação específica de raspagem no Brasil; os riscos são dados pessoais, conteúdo com login e termos de uso | B | [19][20] | RPA só com credencial legítima e ritmo baixo; e-mail e parcerias primeiro |
| Rede credenciada inclui nomes de profissionais, que são dados pessoais sob a LGPD | B | [20] | Minimização e finalidade documentada |
| Carências máximas: 300 dias para parto a termo, 180 para demais casos, 24 horas para urgência e emergência (Lei 9.656/98, art. 12, V) | B | [24] | Validação futura de carências |

---

## 3. Formato de trabalho da referência ANS no protótipo

O protótipo lê dois CSVs com separador `;` e decimal com vírgula, como nos dados abertos da ANS:

```
produtos:        REGISTRO_PLANO;NM_PLANO;RAZAO_SOCIAL;CONTRATACAO;SITUACAO;DT_SITUACAO
valor comercial: REGISTRO_PLANO;FAIXA_ETARIA;VL_COMERCIAL_MENSALIDADE
```

`VL_COMERCIAL_MENSALIDADE` é o nome do dicionário oficial. Os demais nomes são de trabalho. O mapeamento
fica isolado num único dicionário (`servicos/sincronizacao_ans.py`, `COLUNAS`), então adaptar ao
layout real é mudar só esse ponto. Os registros fictícios começam com 900, faixa que não corresponde a
produtos reais.

---

## 4. Pendências a confirmar na fase de descoberta

1. **Chave de junção entre os conjuntos reais.** O valor comercial usa um identificador interno do
   plano (`ID_PLANO`); a tabela de venda traz o número de registro. É preciso confirmar no dicionário
   de dados como ligar os dois. É a primeira tarefa da prova de conceito.
2. **Piso da banda.** O piso real é o maior entre -30% e a despesa assistencial estimada. O protótipo usa
   só os -30%; falta localizar a despesa assistencial nos conjuntos.
3. **Taxa de ligação automática.** Medir, nas tabelas atuais do Cotador, quantas trazem o registro ANS.
4. **Unimed.** Mapear como as singulares distribuem tabelas e se o registro aparece em todas.
5. **Norma de referência do Anexo II-B da NTRP.** O dicionário cita tanto a IN DIPRO 8/2002 quanto a
   RN 564/2022; confirmar a vigente.
6. **Extensão `btree_gist` no Postgres gerenciado** escolhido para produção.

## 5. Fontes secundárias a trocar por primárias

A pesquisa priorizou velocidade. Antes de uso em produção, estas referências devem ser substituídas
pelo texto oficial no site da ANS ou do Planalto: [6] e [7] (RN 563/2022 e RN 254/2011), [11] (RN
486/2022), [15] (RN 565/2022) e [24] (Lei 9.656/98). Os números de mercado [9], [12] e [13] devem ser
conferidos no painel de beneficiários da ANS.

---

## 6. Referências

1. Tabela de preços Notredame Intermédica com registro ANS por produto (exemplo de mercado): https://da-arquivos.webhostusp.sti.usp.br/arquivos/auxilio-saude/Notredame/Demonstrativo_Reajuste_Notredame_-_Set25_-_Mai26.pdf
2. ANS disponibiliza API para os conjuntos de operadoras ativas e canceladas: https://legismap.com.br/conteudos/artigos-e-noticias/noticias-ans-em-15-09-2021
3. ANS, relatório do Plano de Dados Abertos (lista de conjuntos): https://www.gov.br/ans/pt-br/arquivos/acesso-a-informacao/perfil-do-setor/dados-abertos/pda-edicao-2017-2019/relatorio_final_pda_2017-2019.pdf
4. Portal de Dados Abertos, Painel de Precificação e Valor Comercial por Município (NTRP): https://dados.gov.br/dataset/painel-de-precificacao e https://dados.gov.br/dataset/valor-comercial-medio-por-municipio-ntrp
5. Portal de Dados Abertos, Produtos e Prestadores Hospitalares: https://dados.gov.br/dataset/produtos-e-prestadores-hospitalares
6. Texto da RN 63/2003, com o inciso III incluído pela RN 254/2011: https://www.legisweb.com.br/legislacao/?id=99845
7. RN 563/2022 sucede a RN 63/2003: https://calculacentro.com/blog/plano-saude-faixas-etarias-ans-reajuste e https://www.migalhas.com.br/depeso/457714/reajuste-por-idade-em-plano-de-saude-validades-e-cream-skimming
8. STJ, Tema 1.016 (REsp 1.716.113/DF): https://informativos.trilhante.com.br/julgados/stj-resp-1716113-df
9. Conjur, "Brasil tem 668 operadoras de plano de saúde e 53 milhões de beneficiários" (jun/2026): https://www.conjur.com.br/2026-jun-12/brasil-tem-668-operadoras-de-plano-de-saude-e-53-milhoes-de-beneficiarios/
10. ANS, números de beneficiários de março de 2026: https://www.gov.br/ans/pt-br/assuntos/noticias/numeros-do-setor/ans-divulga-numeros-de-beneficiarios-em-marco
11. Divulgação da rede assistencial no portal: RN 285/2011 (https://idec.org.br/consultas/dicas-e-direitos/planos-de-saude-devero-mostrar-mapa-com-rede-credenciada-em-seus-sites-saiba-como-vai-funcionar), consolidada na RN 486/2022; portal corporativo na RN 497/2022 (https://legismap.com.br/conteudos/artigos-e-noticias/alerta-regulatorio-orizon-31-03-2022)
12. Reajuste dos individuais 2026-2027 e participação dos individuais: https://mercadoeconsumo.com.br/03/06/2026/servicos/numero-de-beneficiarios-de-planos-de-saude-sobe-em-abril-para-52958-milhoes-diz-ans/
13. Participação do coletivo empresarial: https://www.em.com.br/mundo-corporativo/2026/07/7469968-planos-de-saude-superam-53-milhoes-de-beneficiarios.html
14. Monitoramento da Garantia de Atendimento e suspensões por registro: https://portal.afya.com.br/saude/ans-suspende-comercializacao-de-70-planos-de-saude-outros-40-foram-reativados
15. RN 565/2022, agrupamento de contratos: https://www.unimed.coop.br/site/web/dourados/agrupamento-de-contratos-coletivos e https://www.unimed.coop.br/site/web/litoralsul/rn-565
16. ANS atualiza os conjuntos de área de comercialização e valor comercial (mensal para semanal): https://www.gov.br/ans/pt-br/assuntos/noticias/sobre-ans/ans-atualiza-dois-conjuntos-de-dados-abertos
17. Conjunto mensal de solicitações de alteração de rede hospitalar: https://legismap.com.br/conteudos/artigos-e-noticias/noticias-ans-em-26-04-2021
18. Concorrentes: https://agger.com.br/produtos/painel-do-corretor/ , https://www.simuladoronline.com/ , https://www.baeta.com.br/solucoes/saude
19. Demarest, "Web scraping: legal ou ilegal": https://www.demarest.com.br/wp-content/uploads/2022/01/Web-scraping-legal-ou-ilegal-1.pdf
20. Web scraping e LGPD: https://jus.com.br/artigos/87950/web-sscraping-na-lei-geral-protecao-de-dados-pessoais
21. Real-Time Trustworthiness Scoring for LLM Structured Outputs and Data Extraction (arXiv 2603.18014): https://arxiv.org/pdf/2603.18014
22. Resultados do RD-TableBench: https://llms.reducto.ai/table-extraction-accuracy-scanned-pdfs
23. Verificação simbólica para reduzir alucinação em tabelas geradas por LLM (arXiv 2508.09324): https://arxiv.org/pdf/2508.09324v1.pdf
24. Lei 9.656/1998, art. 12, V: https://www.legjur.com/legislacao/art/lei_00096561998-12
25. Portal de Dados Abertos, Valor Comercial da Mensalidade por Faixa Etária (dicionário e critérios de comercialização): https://dados.gov.br/dados/conjuntos-dados/valor-comercial-da-mensalidade-por-faixa-etaria
26. Vercel, Django sem configuração e runtime Python: https://vercel.com/changelog/zero-configuration-django-support.md e https://vercel.com/docs/frameworks/full-stack/django
