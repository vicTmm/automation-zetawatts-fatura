# Regras de faturamento

Fonte: SPEC fornecida pelo usuário. Versão do cálculo: `spec-1`.

## Entradas mensais

Consumo, TE_for, TUSD_for, TE_inj, TUSD_inj, bandeira, créditos de saldo utilizados,
créditos do mês corrente utilizados, valor da fatura Enel e desconto percentual.
O operador informa `10` para 10%. Todas as tarifas, inclusive bandeira, são em R$/kWh.
Os campos de créditos representam parcelas efetivamente utilizadas naquele mês;
a aplicação não calcula saldo remanescente nem importa dados do portal da Enel.

## Fórmulas preservadas

| Resultado | Fórmula |
| --- | --- |
| Tarifa de fornecimento | TE_for + TUSD_for + bandeira |
| Tarifa de injeção | TE_inj + TUSD_inj |
| Créditos utilizados | Créditos saldo + créditos mês corrente |
| Total | Consumo × tarifa de fornecimento |
| Fatura Zeta | (1 − desconto / 100) × créditos utilizados × tarifa de injeção |
| Desconto percentual (chamado “Desconto 10%” na SPEC) | desconto / 100 × tarifa de injeção × créditos mês corrente |
| Desconto bandeira | créditos utilizados × bandeira |
| Desconto total | desconto percentual + desconto bandeira |
| Valor da eletricidade | Fatura Zeta antes de arredondar / créditos utilizados |

Fatura Enel é um valor informado, preservado separadamente; não é deduzido do Total
para inventar um resultado de economia. A bandeira não compõe a tarifa de injeção.

## Precisão e validação

- Decimal com 50 dígitos de precisão; não há arredondamento intermediário.
- Moeda: duas casas, arredondamento comercial (`ROUND_HALF_UP`). Tarifas e kWh: até oito casas.
- Desconto total é arredondado depois da soma das parcelas não arredondadas;
  em casos de fração de centavo, a soma das parcelas exibidas pode diferir em R$ 0,01.
- Aceita `1234.56` ou `1.234,56`. Um ponto sozinho é separador decimal: `1.234` vale 1,234.
- Campos vazios não são convertidos em zero. Valores negativos e não finitos são rejeitados.
- Desconto permitido: 0 a 100. Entradas limitadas a 1 bilhão e oito casas decimais.
- Créditos zerados: Fatura Zeta = 0 e valor da eletricidade = não aplicável.
- Créditos acima do consumo geram aviso para conferência, sem alterar a fórmula.

## Decisões confirmadas pelo usuário

- Tela web em Python.
- Na SPEC, manter a diferença de base de desconto: Fatura Zeta usa todos os créditos;
  “Desconto 10%” usa somente créditos do mês corrente.
- Preservar também as regras específicas das demais abas para os novos meses.

Quando existem créditos de saldo na SPEC, o PDF discrimina também o desconto sobre
eles, para explicar o valor a pagar. A linha “Desconto total” continua seguindo a
fórmula confirmada: desconto sobre créditos do mês + desconto bandeira.

## Demais perfis

Nas expressões abaixo, `d` é o desconto informado dividido por 100.

| Perfil | Regra |
| --- | --- |
| Itaipu / Laura Jardim | Tarifa = TE + TUSD + bandeira. Total = consumo × tarifa. Desconto percentual = d × total. Desconto bandeira = créditos utilizados × bandeira. Fatura Zeta = total − Enel − descontos. |
| Essencial | Igual ao perfil anterior, com desconto total = mínimo(desconto percentual + bandeira, total − Enel), e Fatura Zeta = máximo(total − Enel − desconto total, 0). |
| 235 | Consumo = eletricidade Enel + painel. Tarifa = TE + TUSD + bandeira. Total = máximo((tarifa + bandeira) × consumo, 0). Desconto percentual = d × total. Desconto bandeira = (crédito utilizado da Enel + painel) × bandeira. Fatura Zeta = máximo(total − Enel − descontos, 0). Valor eletricidade = Zeta / consumo. |
| 281 | Consumo = eletricidade Enel + painel. Tarifa = TE + TUSD + bandeira. Total = tarifa × consumo. Desconto percentual = d × total. Desconto bandeira = (painel + crédito utilizado da Enel) × bandeira. Fatura Zeta = máximo(total − Enel − descontos, 0). Valor eletricidade = Zeta / (painel + crédito utilizado da Enel). |
| Pio Borges / ZeroHum | Tarifa GD1 = TE_for + TUSD_GD1; tarifa GD2 = TE_for + TUSD_GD2. Energia injetada = créditos GD1 × tarifa GD1 + créditos GD2 × tarifa GD2. Zeta = (1 − d) × energia injetada. Desconto total = descontos GD1 + GD2 + bandeira. |
| Geraldo Martins | Mesma Fatura Zeta do perfil GD1/GD2. Desconto total = total de fornecimento + iluminação/multas − Zeta − Enel. |

Referências: últimas linhas preenchidas da planilha, extraídas com os valores
armazenados pelo Excel. Os percentuais originais são 10% nos perfis legados, 12,5%
em Icaraí (agosto/2026) e 20% nos perfis GD1/GD2; o cadastro permite informar o desconto
contratual. Nas abas GD1/GD2, as fórmulas de tarifa inspecionadas usam TE_for, mesmo
onde existem colunas separadas de TE_GD1 e TE_GD2. Não trocamos essa referência.

### Particularidades preservadas

- `Faturamento 235!O45`: a bandeira já está em F45 e aparece novamente em `(F45+D45)*J45`.
- `Faturamento 281!H45`: eletricidade painel = −70 kWh, resultando em consumo de 30 kWh.
  Os perfis com painel aceitam esse ajuste negativo e mostram aviso.
- `Faturamento ZeroHum Maricá!Q5`: iluminação/multas contém um abatimento. Esse campo
  admite sinal negativo, inclusive em Geraldo Martins.
- Essencial pode produzir desconto negativo quando Enel supera o total. Essa regra é
  preservada e sinalizada; o total a pagar permanece limitado a zero.
- A aplicação não bloqueia um valor só porque diverge do padrão comercial esperado.
  Dados inválidos, perfil incorreto e divisão por zero são tratados explicitamente.

## Revisão dos três arquivos fornecidos

### Planilha e reconciliação

| Aba | Mês de referência | Fatura Zeta | Desconto total |
| --- | --- | ---: | ---: |
| Faturamento 235 | agosto/2026 | R$ 964,56 | R$ 155,98 |
| Faturamento 281 | agosto/2026 | R$ 0,00 | R$ 2,43 |
| Faturamento Itaipu | setembro/2025 | R$ 2.016,95 | R$ 570,36 |
| Faturamento Icaraí | agosto/2026 | R$ 2.474,13 | R$ 413,62 |
| Faturamento Laura Jardim | agosto/2026 | R$ 982,93 | R$ 190,81 |
| Faturamento Essencial | julho/2026 | R$ 11,92 | R$ 1.707,07 |
| Faturamento Geraldo Martins | julho/2026 | R$ 874,54 | R$ 247,20 |
| Faturamento Pio Borges | julho/2026 | R$ 518,76 | R$ 146,62 |
| Faturamento ZeroHum Maricá | agosto/2026 | R$ 2.818,58 | R$ 796,73 |

As nove comparações, incluindo Total, estão nos testes automáticos. Não foram
alterados o XLSX, o PPTX nem o PDF originais.

Importação: 42 registros em 235, 31 em 281, 31 em Itaipu, 42 em Icaraí,
31 em Laura Jardim, 26 em Essencial, 13 em Geraldo Martins, 12 em Pio Borges
e 6 em ZeroHum Maricá. Total: **234 registros e 9 clientes**.

Treze linhas iniciais/incompletas da aba 281 não têm consumo ou fatura disponíveis.
Na aba Pio Borges, outubro/2025 (linha 5) não tem consumo. Essas 14 linhas não foram
importadas. Erros históricos `#DIV/0!` em Y/Z de Pio Borges são preservados como campos
sem valor, sem substituir os resultados financeiros válidos por zeros.

Históricos com entradas incompletas ou fórmulas diferentes ficam para consulta.
Um registro só se torna editável quando a comparação entre o perfil e os resultados
originais confere a menos de um centavo em Zeta, desconto total e Total.

### Modelo a partir de AG em Icaraí

- `AH2:AH4`: dados cadastrais do WW Studio.
- `AI8`, `AJ8`: créditos utilizados e tarifa de injeção do mês de agosto/2026.
- `AK8 = SUM(P43,Q43)` inclui o desconto bandeira, produzindo R$ 2.887,75.
  No PPTX/PDF, a linha Energia injetada usa R$ 2.827,57 e a bandeira fica separada.
  O gerador segue a separação do documento: créditos × tarifa de injeção.
- `AK12 = P43`: total a pagar, R$ 2.474,13.
- `AK13 = -Q43`: desconto total, −R$ 413,62.
- `AK16 = SUM(Q32:Q43)`: acumulado de setembro/2025 a agosto/2026, R$ 7.846,65.
- `AK1 = TODAY()+10` é uma data móvel. A aplicação usa vencimento explícito e
  salvo por mês; para o exemplo de agosto, mantém 20/09/2026, conforme o PDF.

### PPTX e PDF

O PPTX tem uma página de 540 × 780 pontos e o PDF fornecido confirma o conteúdo
do mês de agosto/2026. A aplicação reutiliza a logo original e recria identificação,
tabela de itens, gráficos, total acumulado e espaço inferior para boleto.

Há pequenas adaptações: fonte Helvetica, cabeçalho mais largo sem QR Pix automático,
valores de quantidade com duas casas e gráfico de consumo com exatamente 12 meses.
O gráfico de consumo do exemplo contém 13 pontos apesar do título “12 meses”.
O gráfico de desconto e o acumulado já usam 12 meses no original.

Os arquivos não determinam uma política de arredondamento para todos os casos.
A aplicação usa a política descrita acima e reproduz os valores de referência dos
nove clientes. Há casos de um centavo de diferença entre soma de parcelas já
arredondadas e arredondamento da soma; não alteramos uma parcela para esconder isso.
