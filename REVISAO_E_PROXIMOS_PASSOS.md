# Zetawatts — revisão da entrega e próximos passos

**Preparado em:** 15/09/2026 · **Revisão prevista:** 16/09/2026  
**Projeto:** automação de Operação > Fatura  
**Situação:** aplicação implementada e validada localmente; publicação e validação em Supabase/Vercel pendentes.

Este documento reúne o que foi desenvolvido, as decisões adotadas, os resultados de validação e o plano de continuidade. As tarefas futuras são propostas para a revisão; não foram executadas como parte da preparação deste arquivo.

## 1. Resumo da entrega

A aplicação permite selecionar um cliente e um mês, digitar os dados obtidos na Enel, calcular os valores conforme a regra daquele cliente, conferir a prévia e salvar uma fatura para download em PDF. Novos clientes reutilizam perfis de cálculo, sem exigir uma macro ou aba própria.

| Área | Situação atual |
| --- | --- |
| Operação mensal | Tela única em Python, com cadastro, formulário, cálculo, histórico e PDF. |
| Regras de cálculo | Sete perfis implementados para as nove abas existentes. |
| Migração inicial | Nove clientes e 234 registros mensais importados; 14 linhas incompletas excluídas. |
| Modelo de fatura | PDF gerado diretamente em Python, baseado no PPTX/PDF fornecidos e com a logo original. |
| Validação local | 22 testes automatizados aprovados, teste de navegador e inspeção visual de PDFs realizados. |
| Banco local | SQLite em `data/zeta.db`. |
| Preparação para nuvem | Suporte a PostgreSQL/Supabase e configuração Vercel presentes; ainda sem validação nesses serviços. |
| Uso operacional | Precisa de revisão dos cadastros, homologação pela operação e piloto antes da adoção regular. |

### Decisões já confirmadas

- **Tela web em Python** como solução para a operação.
- **Manter as fórmulas da SPEC:** o desconto da Fatura Zeta considera todos os créditos utilizados; o campo “Desconto 10%” considera somente os créditos do mês corrente.
- **Preservar as regras específicas de cada aba**, inclusive as diferenças entre GD1/GD2 e as fórmulas antigas dos demais clientes.
- Continuar obtendo os dados da Enel manualmente nesta versão.
- Manter manual o recorte do boleto. Automação da Enel e geração de cobrança/Pix ficam para uma etapa futura.

## 2. O que foi desenvolvido

### Tela e rotina mensal

- [x] Listagem e busca de clientes; cadastro e edição em uma única aplicação.
- [x] Cadastro com nome, razão social, CPF/CNPJ, número do cliente Enel, endereço, desconto padrão e perfil de cálculo.
- [x] Seleção de cliente e mês de referência.
- [x] Campos que se adaptam ao perfil do cliente, inclusive GD1/GD2 e painel.
- [x] Vencimento informado explicitamente e salvo na fatura.
- [x] Cálculo dos valores e apresentação da regra utilizada.
- [x] Prévia automática da página completa da fatura.
- [x] Salvamento e download do PDF; alterações pendentes precisam ser salvas antes do download.
- [x] Histórico mensal e gráficos dos 12 meses encerrados na referência selecionada.
- [x] Observações internas que não aparecem no documento do cliente.
- [x] Anexo opcional de recorte do boleto em PNG/JPG, até 1,4 MB e 8 megapixels.
- [x] Interface adaptada a computador e celular, verificada em larguras de 1.440 e 390 pixels.

**Comportamento dos novos meses:** consumo, tarifas e demais entradas começam em branco. Somente o desconto padrão vem do cadastro. Isso evita reaproveitar valores antigos sem conferência.

**Rascunhos:** a tela mantém alterações ao alternar cliente ou mês enquanto a página permanece aberta. Os rascunhos ficam na memória do navegador; fechar ou recarregar a página pode descartá-los, com aviso.

### Cálculos e integridade dos registros

- [x] Cálculo com `Decimal`, precisão de 50 dígitos e sem arredondamento intermediário.
- [x] Valores monetários exibidos com duas casas e arredondamento comercial; entradas de tarifas e kWh com até oito casas decimais.
- [x] Aceitação de valores como `1.234,56` e `1234.56`.
- [x] Validação de campos obrigatórios, percentuais, datas, números inválidos e divisão por zero.
- [x] Avisos para situações previstas pelas regras, como ajustes negativos de painel e créditos superiores ao consumo.
- [x] Resultados recalculados no servidor, sem confiar em totais enviados pelo navegador.
- [x] Separação dos registros por cliente e mês.
- [x] Revisões gravadas no banco a cada salvamento e detecção de conflito entre edições simultâneas.
- [x] Preservação dos dados cadastrais e da regra registrados em uma fatura salva.
- [x] Proteção da tela contra respostas de cálculo/prévia atrasadas após uma troca rápida de cliente ou mês.

Alterar o cadastro não modifica automaticamente as faturas anteriores. Salvar novamente uma fatura atualiza os dados cadastrais daquele documento, mas mantém o perfil de cálculo do mês. Mudar o perfil no cadastro vale para novos meses.

### Importação e documentos

- [x] Importador da planilha original com mapeamento das nove abas conhecidas.
- [x] Preservação dos resultados históricos armazenados no XLSX.
- [x] Reimportação sem sobrescrever registros existentes.
- [x] Bloqueio de edição de históricos cujas entradas estejam incompletas ou não correspondam à regra atual.
- [x] PDF com identificação, itens, total a pagar, descontos, gráficos e espaço para boleto.
- [x] Prévia renderizada a partir do próprio PDF.
- [x] Uso da logo original extraída do PPTX.

Os três arquivos originais foram preservados. O processo gera PDF diretamente; não edita o PowerPoint nem produz um novo PPTX. Também não atualiza a planilha ou sincroniza com Google Sheets.

### Infraestrutura e acesso

- [x] Backend FastAPI e interface HTML/CSS/JavaScript, sem etapa de build de frontend.
- [x] Persistência SQLite local e implementação de acesso a PostgreSQL.
- [x] Configuração de deploy, variáveis de ambiente e instruções de execução.
- [x] Autenticação com usuário `operador` e senha compartilhada configurável.
- [x] Bloqueio de execução em produção sem senha e conexão PostgreSQL.
- [x] Acesso local sem senha restrito ao próprio computador.
- [x] Proteções de origem das requisições e de cache dos dados da API.
- [x] Inicialização das tabelas PostgreSQL com RLS e retirada de acesso dos papéis públicos do Supabase.
- [x] Workflow de testes definido para GitHub Actions; execução no GitHub ainda pendente.

## 3. Planilha revisada: dados e regras preservadas

### Cobertura da importação e valores de referência

Os valores abaixo correspondem ao último mês disponível de cada aba, e não a um mês comum a todos os clientes. São referências incluídas nos testes de cálculo; não representam faturas emitidas pela nova aplicação.

| Cliente | Registros importados | Referência de comparação | Fatura Zeta | Desconto total |
| --- | ---: | --- | ---: | ---: |
| 235 | 42 | agosto/2026 | R$ 964,56 | R$ 155,98 |
| 281 | 31 | agosto/2026 | R$ 0,00 | R$ 2,43 |
| Itaipu | 31 | setembro/2025 | R$ 2.016,95 | R$ 570,36 |
| Icaraí | 42 | agosto/2026 | R$ 2.474,13 | R$ 413,62 |
| Laura Jardim | 31 | agosto/2026 | R$ 982,93 | R$ 190,81 |
| Essencial | 26 | julho/2026 | R$ 11,92 | R$ 1.707,07 |
| Geraldo Martins | 13 | julho/2026 | R$ 874,54 | R$ 247,20 |
| Pio Borges | 12 | julho/2026 | R$ 518,76 | R$ 146,62 |
| ZeroHum Maricá | 6 | agosto/2026 | R$ 2.818,58 | R$ 796,73 |
| **Total** | **234** | | | |

### Perfis implementados

| Perfil | Clientes atuais | Particularidade principal |
| --- | --- | --- |
| SPEC | Icaraí | Fatura Zeta calculada pelos créditos utilizados e tarifa de injeção; bases distintas de desconto conforme a SPEC. |
| Legado sobre total | Itaipu e Laura Jardim | Fatura Zeta resulta do total menos Enel e descontos. |
| Essencial | Essencial | Limita o desconto ao total menos Enel; Fatura Zeta tem piso zero. |
| Painel 235 | 235 | Soma consumo Enel e painel; preserva a segunda incidência da bandeira no cálculo do total. |
| Painel 281 | 281 | Soma consumo Enel e painel; aceita o ajuste negativo de painel existente na origem. |
| GD1/GD2 | Pio Borges e ZeroHum Maricá | Calcula créditos e tarifas separadamente por modalidade GD. |
| GD1/GD2 Geraldo | Geraldo Martins | Usa GD1/GD2 para a fatura; desconto total considera também fornecimento, iluminação/multas e Enel. |

As fórmulas completas, unidades e referências de células estão em [Regras de faturamento](docs/regras.md).

### Pontos importantes encontrados na origem

1. **Quatorze linhas ficaram fora da importação:** 13 linhas de 281 sem consumo ou valor da fatura e outubro/2025 de Pio Borges, sem consumo. É preciso decidir se serão completadas na origem ou mantidas fora do histórico.
2. **Oito cadastros precisam ser completados:** somente Icaraí tinha os dados completos de identificação nos arquivos fornecidos. O download exige razão social, CPF/CNPJ, endereço e número do cliente Enel.
3. **Históricos não são todos editáveis:** a edição só é habilitada com entradas completas e diferença inferior a um centavo entre a regra atual e os resultados originais de Total, Fatura Zeta e Desconto total. Os demais ficam para consulta.
4. **Erros históricos de divisão por zero em Pio Borges:** campos indisponíveis permanecem sem valor; não foram inventados resultados zero para preencher essas lacunas.
5. **235 inclui bandeira duas vezes no total:** preservado conforme a fórmula da aba e a decisão de manter regras específicas.
6. **281 tem painel de −70 kWh em agosto/2026:** o ajuste foi preservado; o consumo resultante é 30 kWh.
7. **Nas abas GD, as tarifas usam TE_for:** essa referência foi mantida mesmo onde existem colunas separadas de TE_GD1 e TE_GD2.
8. **Essencial pode apresentar desconto negativo; iluminação/multas pode ter abatimento:** os casos previstos pela origem são aceitos, com os avisos aplicáveis.

Essas particularidades já fazem parte da implementação. A revisão serve para conferir a reprodução e registrar o entendimento operacional; qualquer mudança futura de fórmula deverá ser tratada como uma alteração de regra.

## 4. Conferência do modelo da fatura

### Caso de referência: Icaraí, agosto/2026

| Dado ou resultado | Valor esperado |
| --- | ---: |
| Consumo | 4.186 kWh |
| Créditos de saldo utilizados | 0 kWh |
| Créditos do mês corrente utilizados | 2.347 kWh |
| TE_for / TUSD_for | 0,44818 / 0,99550 R$/kWh |
| TE_inj / TUSD_inj | 0,44818 / 0,75658 R$/kWh |
| Bandeira | 0,02564 R$/kWh |
| Desconto contratual | 12,5% |
| Fatura Enel | R$ 3.343,48 |
| Energia injetada antes do desconto | R$ 2.827,57 |
| Desconto percentual | R$ 353,45 |
| Desconto bandeira | R$ 60,18 |
| **Fatura Zeta** | **R$ 2.474,13** |
| **Desconto total** | **R$ 413,62** |
| Desconto acumulado, setembro/2025 a agosto/2026 | R$ 7.846,65 |
| Vencimento do exemplo fornecido | 20/09/2026 |

Abra o [PDF gerado para conferência](output/pdf/Icarai-fatura-ZetaGD-2026-08.pdf) e compare com o [PDF original fornecido](WW%20Studio_fatura_ZetaGD_agosto-2026.pdf). O PDF gerado é um artefato local de validação, sem recorte de boleto.

### Adaptações do modelo

- A célula `AK8` do modelo na planilha soma valores que incluem a bandeira. O PDF fornecido separa energia injetada e bandeira; o gerador segue essa separação.
- O vencimento deixa de depender de `TODAY()+10` e passa a ser um dado explícito salvo por mês.
- O gráfico de consumo usa exatamente 12 meses; o exemplo original apresenta 13 pontos apesar do título “12 meses”.
- Foram mantidos o tamanho de página de 540 × 780 pontos e a identidade visual, com adaptações de fonte, cabeçalho e apresentação de quantidades.
- O cabeçalho reutiliza o QR Pix estático do modelo, com a chave 42.808.090/0001-91 e o nome ZETAWATTS GD, sem valor fixo. A imagem do boleto precisa ser anexada manualmente, quando aplicável. A geração de cobranças Pix individuais permanece para uma etapa futura.
- Na SPEC, quando houver créditos de saldo, o PDF também discrimina o desconto correspondente para explicar o total a pagar. O campo Desconto total continua seguindo a fórmula confirmada.
- Pode haver diferença de R$ 0,01 entre somar parcelas já arredondadas e arredondar a soma original. O sistema preserva a precisão do cálculo e não altera uma parcela para forçar a soma visual.

## 5. Validação realizada e limites atuais

### Resultados registrados durante o desenvolvimento

| Verificação | Resultado e cobertura |
| --- | --- |
| Testes automatizados Python | **22 aprovados.** Fórmulas, casos de referência das nove abas, validações, importação, API, histórico, PDF e acesso. |
| Casos de cálculo especiais | Créditos zerados, percentuais extremos, GD1/GD2 mistos, limites de Essencial/235, ajustes negativos previstos e arredondamento. |
| Persistência e edição | Salvar e reabrir; isolamento por cliente/mês; conflito entre versões; preservação cadastral e de regra. |
| Importação real | Nove clientes e 234 registros; reimportação sem duplicar; conferência do acumulado de Icaraí. |
| Fluxo no navegador | Playwright com Edge, usando banco temporário: cadastro, seleção, entrada, prévia, salvamento, download, histórico e rascunhos. |
| Interface | Verificação em computador e celular, sem rolagem horizontal indevida ou erros JavaScript no fluxo testado. |
| PDF | Inspeção visual de Icaraí, Pio Borges e 281; verificação da prévia PNG e dos valores do exemplo. |
| Verificações técnicas | Dependências sem incompatibilidades reportadas por `pip check`; sintaxe JavaScript e compilação Python verificadas. |

Os resultados acima são os registrados na etapa de desenvolvimento. A preparação deste documento não constitui uma nova rodada de testes da aplicação.

### O que ainda precisa de validação ou desenvolvimento

- **Nuvem:** a conexão real ao Supabase, as permissões do banco, o runtime da Vercel e os tempos de geração do PDF ainda não foram exercitados nesses serviços.
- **Homologação operacional:** ainda falta executar um ciclo de faturamento com conferência da operação, inclusive dos dados obtidos na Enel e do recorte real de boleto.
- **Autenticação:** existe uma senha compartilhada. Não há contas individuais, recuperação de senha, perfis de acesso ou identificação do operador em cada alteração.
- **Revisões:** ficam registradas no banco, mas não há tela para consultar diferenças ou restaurar uma versão anterior.
- **Documento emitido:** o PDF é gerado sob demanda. Os gráficos e o acumulado usam o histórico disponível no momento do download; alterar meses anteriores pode mudar essa parte de um PDF baixado novamente. Não existe arquivo imutável da versão enviada.
- **Situação da cobrança:** não há fluxo de emitida, enviada, paga ou cancelada, nem conciliação de pagamentos.
- **Rascunhos:** não sobrevivem ao fechamento da página e não são compartilhados entre dispositivos.
- **Anexos:** a imagem do boleto fica dentro dos dados da fatura e das revisões; armazenamento separado pode ser necessário conforme o volume crescer.
- **Importação:** cobre os formatos das nove abas conhecidas. Uma nova estrutura de planilha requer mapeamento adicional; clientes novos podem ser cadastrados pela tela com um perfil existente.
- **Versionamento:** no momento desta revisão, o código da aplicação ainda está sem commit, e os arquivos originais também aparecem como não rastreados. É preciso separar código e documentos de clientes antes de publicar o repositório.
- **Reprodutibilidade:** as dependências têm faixas de versão; ainda não há um arquivo que fixe todas as versões utilizadas na entrega.

## 6. Roteiro para revisar amanhã

### Abrir a aplicação

Se ela já estiver aberta, acesse **http://127.0.0.1:8000**. Se o servidor estiver desligado, execute no PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Projetos\automation-zetawatts-fatura'
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Mantenha esse terminal aberto durante o uso. O comando utiliza o ambiente virtual já preparado. Para instalar em outro computador, siga o [README](README.md). A execução local usa `data/zeta.db` quando não há `DATABASE_URL` configurada.

### Checklist de revisão sugerido

- [ ] **Visão geral:** localizar os nove clientes e conferir os meses do histórico.
- [ ] **Icaraí:** abrir agosto/2026 e comparar os totais com a tabela da seção 4.
- [ ] **Documento:** abrir o PDF gerado e conferir identificação, vencimento, itens, gráficos e espaço do boleto.
- [ ] **GD1/GD2:** selecionar Pio Borges ou Geraldo Martins e conferir os campos específicos.
- [ ] **Regras especiais:** conferir 235, 281 e Essencial usando a seção 3 e o documento de regras.
- [ ] **Novo mês:** observar os campos em branco e o desconto padrão, sem salvar dados fictícios no histórico operacional.
- [ ] **Cadastros:** listar os dados faltantes dos oito clientes além de Icaraí.
- [ ] **Lacunas históricas:** registrar o encaminhamento das 14 linhas excluídas.
- [ ] **Uso mensal:** avaliar se a sequência preencher → conferir → salvar → baixar é clara para quem vai operar.
- [ ] **Prioridades:** escolher as tarefas iniciais da seção 8 e registrar as decisões na seção 10.

Conferir documentos existentes pode ser feito sem salvar alterações. Para repetir automaticamente os exercícios de criação e salvamento em banco temporário, há o script `scripts/check_ui.py`, descrito no README.

## 7. Implementation plan

### Fase 1 — Homologar dados, regras e apresentação

**Objetivo:** confirmar que a aplicação atende à rotina com dados reais e cadastros completos.

**Trabalho:** executar o roteiro de revisão, completar os cadastros, dar destino às lacunas da planilha e conferir PDFs representativos de SPEC, GD e regras especiais. Ajustes de apresentação devem preservar as fórmulas já confirmadas.

**Entregável:** registro de revisão preenchido, lista de correções e cadastros prontos para os clientes do piloto.

**Critério de conclusão:** valores conciliados com as referências; nenhuma divergência financeira sem explicação; identificação e boleto legíveis nos documentos escolhidos.

### Fase 2 — Preparar a operação e a persistência em nuvem

**Objetivo:** tornar a versão reproduzível e comprovar armazenamento, recuperação e controle de acesso.

**Trabalho:** organizar o versionamento, fixar dependências, validar PostgreSQL/Supabase com dados de teste e testar backup/restauração. Definir quem terá acesso e como será preservada a versão enviada de cada fatura. Se for necessário manter o documento exato, implementar o armazenamento da versão emitida e de seu histórico antes de iniciar emissões regulares.

**Entregável:** versão identificada do código, banco de homologação validado, procedimento de recuperação e decisões de acesso/documento registradas.

**Critério de conclusão:** salvar, reabrir, importar e detectar conflitos no PostgreSQL real; dados inacessíveis pelos papéis públicos; recuperação testada; estratégia de acesso e emissão adequada à operação.

### Fase 3 — Validar a aplicação hospedada

**Objetivo:** comprovar o fluxo completo em um ambiente de homologação na Vercel.

**Trabalho:** configurar variáveis, testar autenticação e banco, gerar prévias/PDFs, anexar um boleto de teste e verificar o comportamento após reinício da aplicação. Medir tempo de resposta e limites de tamanho com o volume atual. Executar o workflow de testes no repositório.

**Entregável:** endereço de homologação, resultados dos testes externos e instruções de operação atualizadas.

**Critério de conclusão:** fluxo mensal completo funcionando no endereço hospedado, persistência comprovada e nenhuma falha impeditiva de emissão ou acesso.

### Fase 4 — Fazer piloto e ampliar o uso

**Objetivo:** comprovar a rotina em um ciclo real antes de atender toda a carteira.

**Trabalho:** começar por Icaraí, um cliente GD1/GD2 e um cliente com regra especial; conferir entradas da Enel e resultados com o processo atual. Depois de resolver as divergências, ampliar para os nove clientes.

**Entregável:** faturas do piloto conferidas, manual mensal curto e registro das ocorrências encontradas.

**Critério de conclusão:** operação consegue executar o ciclo, localizar os documentos e recuperar os dados; os valores e documentos são aprovados na conferência.

**Sequência:** homologação funcional → preparação do banco e da operação → homologação hospedada → piloto → ampliação. Organização do código e levantamento dos cadastros podem avançar em paralelo. Automações da Enel e do Pix permanecem fora dessas fases.

## 8. Tasks dos próximos passos

**Prioridades:** P0 = preparar a homologação/piloto; P1 = concluir antes da operação regular em nuvem; P2 = evolução posterior. Todas as tarefas abaixo estão pendentes. A distribuição entre operação e desenvolvimento é uma sugestão, ainda sem responsáveis individuais ou prazos atribuídos.

| ID | Prioridade | Tarefa | Quem conduz | Conclusão verificável | Depende de |
| --- | --- | --- | --- | --- | --- |
| T01 | P0 | Executar a revisão funcional e registrar divergências. | Operação + desenvolvimento | Checklist da seção 6 preenchido e cada divergência documentada com cliente/mês. | — |
| T02 | P0 | Completar os oito cadastros pendentes. | Operação | Dados de identificação conferidos para cada cliente que entrará em uso. | — |
| T03 | P0 | Revisar as 14 linhas excluídas da importação. | Operação + desenvolvimento | Cada lacuna classificada como corrigir/importar ou manter ausente, com motivo; reimportação verificada se houver correções. | T01 |
| T04 | P0 | Homologar PDF e anexo de boleto. | Operação + desenvolvimento | PDFs de SPEC, GD e perfil especial conferidos, incluindo legibilidade do recorte manual. | T01, T02 para os clientes escolhidos |
| T05 | P0 | Resolver os ajustes encontrados na revisão. | Desenvolvimento | Divergências encerradas e testes relevantes aprovados; corrigida também a mensagem antiga que menciona SPEC ao bloquear históricos de outros perfis. | T01, T04 |
| T06 | P0 | Organizar o versionamento e registrar a versão local. | Desenvolvimento | Código e documentação em commit revisável; originais de clientes, banco, anexos e segredos fora da publicação do código. | — |
| T07 | P1 | Fixar dependências e comprovar instalação limpa. | Desenvolvimento | Instalação reproduzida com versões registradas e suíte aprovada. | T06 |
| T08 | P1 | Definir acesso dos operadores e adequar autenticação, se necessário. | Operação + desenvolvimento | Número de operadores e modelo de acesso registrados; implementação e testes cobrem a decisão. | T01 |
| T09 | P1 | Definir e implementar a preservação da fatura enviada. | Operação + desenvolvimento | Se exigido documento imutável, alterar mês anterior ou cadastro não muda a versão já emitida; se adotado arquivo manual no piloto, procedimento e local definidos. | T04 |
| T10 | P1 | Validar Supabase/PostgreSQL em homologação. | Desenvolvimento | Importação, reimportação, gravação, leitura, conflito e permissões testados em banco real; resultados registrados. | T06, T07 |
| T11 | P1 | Definir backup e testar restauração. | Desenvolvimento + operação | Cópia restaurada em ambiente separado e conferência de registros/documentos aprovada; frequência e responsável definidos. | T09, T10 |
| T12 | P1 | Publicar e testar ambiente de homologação Vercel. | Desenvolvimento | Login, persistência, prévia, PDF e anexo funcionando; tempos de resposta e limites registrados. | T08, T10 |
| T13 | P1 | Executar CI e ampliar verificações para o ambiente hospedado. | Desenvolvimento | Workflow aprovado no repositório e teste do fluxo hospedado documentado, sem dados pessoais nos logs. | T06, T07, T12 para a parte hospedada |
| T14 | P1 | Preparar manual mensal e tratamento de falhas. | Desenvolvimento + operação | Passos para faturar, corrigir entrada, lidar com conflito, guardar documento e recuperar dados descritos. | T05, T09, T11, T12 |
| T15 | P1 | Executar o piloto com três perfis representativos. | Operação + desenvolvimento | Icaraí, um GD e um perfil especial conciliados com a origem, sem pendência impeditiva. | T02–T05, T08–T14 |
| T16 | P1 | Ampliar a operação para os nove clientes. | Operação | Cadastros completos, ciclo realizado e ocorrências acompanhadas. | T15 |
| T17 | P2 | Persistir rascunhos além da sessão do navegador. | Desenvolvimento | Rascunho recuperado após fechar/reabrir; tratamento de conflito definido. | Priorização após piloto |
| T18 | P2 | Criar consulta de revisões e fluxo de correção. | Desenvolvimento + operação | Operador identifica alterações e corrige documentos sem perder a versão anterior. | T08, T09 |
| T19 | P2 | Adicionar situação da fatura e filtros operacionais. | Desenvolvimento + operação | Estados e transições definidos; listagem permite localizar pendentes, emitidas e demais situações acordadas. | T15 |
| T20 | P2 | Avaliar armazenamento separado de anexos e PDFs. | Desenvolvimento | Volume e custo medidos; se necessário, arquivos migrados com acesso restrito e recuperação testada. | T09, T11, T15 |

### Backlog fora desta primeira versão

- Obter dados automaticamente do portal da Enel.
- Gerar cobrança/Pix e substituir o recorte manual do boleto.
- Enviar faturas automaticamente aos clientes.
- Sincronizar Google Sheets ou criar importação genérica para outros formatos de planilha.

Esses itens precisam de especificação própria quando forem priorizados.

## 9. Mapa técnico e arquivos para consulta

Fluxo implementado: **dados manuais da Enel → tela web → cálculo no backend → salvamento no banco → geração do PDF → download pelo operador**. O importador XLSX alimenta os cadastros e o histórico. O envio ao cliente continua manual.

| Arquivo ou pasta | Responsabilidade |
| --- | --- |
| [README.md](README.md) | Instalação, execução, rotina mensal, preparação de deploy e comandos de validação. |
| [docs/regras.md](docs/regras.md) | Fórmulas, particularidades e análise dos três arquivos originais. |
| [app.py](app.py) | API, validação das requisições, autenticação, importação, salvamento e documentos. |
| [backend/calculations.py](backend/calculations.py) e [backend/rules.py](backend/rules.py) | Precisão numérica, perfis de cálculo, entradas e itens da fatura. |
| [backend/importer.py](backend/importer.py) | Mapeamento e importação da planilha existente. |
| [backend/storage.py](backend/storage.py) | SQLite/PostgreSQL, registros, revisões e conflitos de edição. |
| [backend/history.py](backend/history.py) | Janela de 12 meses e acumulados. |
| [backend/pdf.py](backend/pdf.py) | Layout do PDF e renderização da prévia. |
| [frontend/index.html](frontend/index.html), [app.js](frontend/app.js) e [styles.css](frontend/styles.css) | Estrutura, comportamento e aparência da tela. |
| [assets/logo.png](assets/logo.png) | Logo original usada nos documentos. |
| [scripts/start.ps1](scripts/start.ps1), [import_workbook.py](scripts/import_workbook.py) e [init_db.py](scripts/init_db.py) | Inicialização local, importação e preparação do banco. |
| [tests/test_calculations.py](tests/test_calculations.py), [test_workflow.py](tests/test_workflow.py) e [reference_cases.json](tests/reference_cases.json) | Testes de cálculo e fluxo; valores de referência das nove abas. |
| [scripts/check_ui.py](scripts/check_ui.py) | Verificação automatizada da interface em banco temporário. |
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | Workflow de testes para o repositório. |
| [requirements.txt](requirements.txt), [requirements-dev.txt](requirements-dev.txt) e [pyproject.toml](pyproject.toml) | Dependências e configuração Python. |
| [.env.example](.env.example), [vercel.json](vercel.json) e [.vercelignore](.vercelignore) | Configuração de ambiente e preparação da hospedagem. |

O banco guarda documentos e revisões em `zeta_documents` e `zeta_revisions`. A conexão privada fica no servidor. Os arquivos de validação em `output/` e `tmp/`, o banco local e o ambiente virtual não fazem parte do código a publicar.

## 10. Registro da revisão de 16/09/2026

Preencher durante a revisão:

| Tema | Decisão ou observação | Responsável | Prazo |
| --- | --- | --- | --- |
| Conferência de valores e regras | | | |
| Ajustes no PDF e recorte de boleto | | | |
| Dados cadastrais pendentes | | | |
| Destino das 14 linhas excluídas | | | |
| Quantidade de operadores e acesso | | | |
| Preservação da versão enviada da fatura | | | |
| Ambiente Supabase/Vercel e responsável | | | |
| Backup e recuperação | | | |
| Clientes e período do piloto | | | |
| Primeiras tarefas escolhidas | | | |

**Próxima ação sugerida:** revisar Icaraí/agosto de 2026 com o PDF de referência, registrar os ajustes e iniciar T01, T02 e T06.
