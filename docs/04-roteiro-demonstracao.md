# Roteiro de demonstração

Serve para testar o protótipo por conta própria (cerca de 5 minutos) e como roteiro do vídeo.
Todos os dados são fictícios.

## Situação inicial

- Estão publicadas as tabelas de janeiro de 2026 da Alfa Saúde (3 planos) e de março da Beta Vida
  (2 planos), todas no DF, contratação PME.
- A referência ANS fictícia está sincronizada. Nela, o plano Vida Mais Enfermaria está com a
  comercialização suspensa desde 15/08/2026.
- Chega o reajuste de junho da Alfa: 12,5% em todas as faixas. O PDF tem dois problemas plantados,
  como os que aparecem no dia a dia.

## Passo a passo

**1. Receber o material.** Preencha o campo **Revisor** no topo. Em **Conferência**, com a fonte
"Alfa Saúde: e-mail do comercial", clique em **Enviar amostra** (`alfa_pme_df_2026-06.pdf`). Três
tabelas entram na fila, já extraídas, ligadas ao registro ANS e validadas.

**2. Essencial Enfermaria: o caso comum.** Marcada como "sem pendências". Reajuste uniforme de 12,5%,
dentro da banda da ANS. Um clique em **Publicar no cotador**. É isso que a proposta quer tornar
automático depois que a fonte tiver histórico medido.

**3. Premium Apartamento: erro de digitação.** A faixa 59+ veio com um dígito a mais (R$ 24.669,60).
Quatro verificações independentes apontam o mesmo valor: o limite de 6 vezes da RN 563/2022, a
variação acumulada entre faixas (mesma norma), a variação atípica em relação à versão vigente e a banda
de preço da ANS. O botão de publicar fica bloqueado. Clique em **Corrigir** na linha 59+, digite
`2.466,96` e salve. O bloqueio some, o valor fica marcado como "corrigido" e a correção vai para o
histórico. Publique.

**4. Essencial Apartamento: preço fora da referência oficial.** Nada errado nas regras de faixa etária,
mas o preço ficou 35% acima do valor comercial registrado na nota técnica, e o limite é 30%. Pode ser
erro de extração, nota técnica desatualizada na ANS ou descumprimento da operadora. O sistema bloqueia,
mas permite publicar com justificativa. Escreva, por exemplo, "confirmado com o comercial em 30/09" e
clique em **Publicar com justificativa**.

**5. Cotação.** Em **Cotação**, cote DF, PME, idades `30, 45, 62`, com a data em branco (hoje):
- o Vida Mais Enfermaria não aparece, e um aviso explica que a ANS suspendeu a comercialização;
- cada resultado mostra vigência, versão, fonte, link para o documento original, data da conferência
  e registro ANS;
- o Essencial Apartamento aparece marcado como "acima da referência ANS, confirmado pela equipe".

**6. Cotação no passado.** Troque a data para 10/03/2026 e cote de novo. Aparecem os preços de
janeiro, que valiam naquele dia, e o Vida Mais Enfermaria volta, porque em março ainda não estava
suspenso. É assim que uma proposta enviada ao cliente pode ser defendida depois.

**7. Fontes e saúde dos dados.** Indicadores de qualidade (98,8% dos valores aceitos sem correção, uma
liberação justificada), o catálogo de fontes com SLA de frescor (a fonte que depende de uma pessoa
aparece atrasada) e a referência ANS com a situação de cada produto.

**8. Duplicata.** Volte à Conferência e envie a mesma amostra de novo: o sistema recusa, porque o hash
do arquivo já foi processado.

**9. Recomeçar.** No fim da tela de Fontes, **Reiniciar demonstração** recria o cenário inicial.

## Roteiro do vídeo (4 a 6 minutos)

| Tempo | O que mostrar | O que falar |
|---|---|---|
| 0:00 a 0:40 | Slide ou README | O problema não é digitar menos; é o corretor não poder confiar no preço que mostra ao cliente. Hoje não existe verificação independente do dado. |
| 0:40 a 1:10 | Diagrama da proposta | A esteira: receber, extrair, ligar ao registro ANS, validar em quatro níveis, conferir só o que o sistema marcou e publicar com vigência. |
| 1:10 a 1:40 | Passos 1 e 2 | Três tabelas extraídas e já validadas; o caso comum é um clique. |
| 1:40 a 2:40 | Passo 3 | O erro de digitação pego por quatro regras independentes; correção registrada. |
| 2:40 a 3:30 | Passo 4 | A banda da ANS é a verificação que não depende da operadora; bloqueio com saída justificada e auditada. |
| 3:30 a 4:30 | Passos 5 e 6 | O que o corretor vê: procedência, suspensão, cotação reproduzível no passado. |
| 4:30 a 5:00 | Passo 7 | Métricas para acompanhar depois da entrega; o que é real e o que é simulado; próximos passos. |

Dicas: grave em 1280×800 ou maior, com o campo Revisor já preenchido e o cenário recém-reiniciado.
Fale do problema do corretor antes de falar de tecnologia.
