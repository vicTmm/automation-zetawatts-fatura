# Zetawatts · Faturamento

Aplicação web em Python para cadastrar clientes, registrar os dados mensais da Enel,
calcular a fatura conforme a regra de cada cliente e gerar o PDF. O cadastro de um
novo cliente reutiliza um perfil de cálculo, sem criar outra aba ou macro.

Para revisar a entrega, consulte [Revisão completa, implementation plan e tasks](REVISAO_E_PROXIMOS_PASSOS.md).

## Executar localmente

Requer Python 3.12 ou superior. No PowerShell, na pasta do projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/import_workbook.py "Controle de créditos ZetaGD.xlsx"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Abra **http://127.0.0.1:8000**. Os dados locais ficam em `data/zeta.db`.
A importação também está disponível na tela. Reimportar não sobrescreve registros.
Para um banco vazio, pule o comando de importação e use **Novo cliente**.

## Rotina mensal

1. Selecione o cliente e o mês de referência.
2. Informe o vencimento e os dados obtidos manualmente no portal da Enel.
3. Confira os totais e a prévia. A seção “Como este valor é calculado” mostra a regra.
4. Se desejar, anexe o recorte do boleto já preparado em PNG/JPG.
5. Clique em **Salvar fatura** e depois **Baixar PDF**.

A prévia se atualiza automaticamente. O download usa a última versão salva;
alterações pendentes precisam ser salvas antes de baixar. Os rascunhos sobrevivem
à troca de cliente/mês enquanto a página está aberta. Recarregar ou fechar a página
descarta rascunhos não salvos, com aviso do navegador.

Complete razão social, CPF/CNPJ, endereço e número do cliente Enel no cadastro
antes de emitir. A planilha contém esse cadastro completo apenas para Icaraí.
Observações internas não aparecem no PDF. Nenhuma mensagem é enviada ao cliente.

## Regras e importação

- Sete perfis atendem às nove abas: SPEC/Icaraí, Itaipu/Laura Jardim, Essencial,
  235, 281, GD1/GD2 Pio Borges/ZeroHum e GD1/GD2 Geraldo Martins.
- As fórmulas específicas e particularidades da planilha foram preservadas,
  conforme confirmação do usuário. Consulte [regras e revisão dos arquivos](docs/regras.md).
- A primeira importação trouxe **9 clientes e 234 registros mensais**.
  Quatorze linhas sem consumo ou valor da fatura ficaram fora.
- Histórico importado preserva os resultados originais. Só permite edição quando
  as entradas estão completas e os totais conferem com o perfil atual.
- Novos meses começam com os dados de consumo e tarifas em branco. Somente o desconto
  padrão vem do cadastro; não há cópia automática de consumo ou tarifas antigas.
- Cada salvamento mantém uma revisão no banco. Conflitos de edição são detectados.
  Alterar o cadastro não modifica documentos já salvos. O perfil de um mês existente
  permanece o registrado naquele mês; mudar o perfil no cadastro vale para novos meses.
- Os gráficos usam exatamente os 12 meses encerrados no mês selecionado. Meses sem
  registro aparecem sem valor. O acumulado usa a precisão original antes de arredondar.

## PDF

O gerador reproduz o conteúdo e a identidade visual do modelo fornecido, com a logo
original, identificação, itens, total, desconto, gráficos e espaço para boleto.
O cabeçalho inclui o QR Code Pix original (`assets/pix.png`), a chave
42.808.090/0001-91 e o nome ZETAWATTS GD. Esse QR é estático, sem valor fixo,
e aparece também quando o recorte do boleto não foi anexado.
Gera o PDF diretamente em Python, sem precisar abrir PowerPoint ou Google Slides.
A prévia é uma imagem renderizada do próprio PDF.

O recorte do boleto é opcional e manual, limitado a 1,4 MB e 8 megapixels.
O código não reutiliza o boleto nem o QR Pix do exemplo. Acesso automático à Enel,
emissão de cobrança/Pix e envio ao cliente ficam fora desta versão.

## Vercel + Supabase

A aplicação tem configuração para deploy em Vercel e persistência PostgreSQL no
Supabase. A execução e os testes desta entrega foram locais; nenhum serviço externo
foi criado ou publicado.

1. Crie um projeto no Supabase e obtenha a URL de conexão PostgreSQL do pooler.
2. Copie `.env.example` para `.env` e configure `DATABASE_URL` com `sslmode=require`.
   Use o usuário do banco com permissão para criar as tabelas, conforme a conexão
   fornecida pelo Supabase. Codifique caracteres especiais da senha na URL.
3. Execute `scripts/init_db.py` com o Python do ambiente virtual. O script cria as
   tabelas, habilita RLS e retira o acesso dos papéis `anon` e `authenticated`.
   O backend usa a conexão privada do banco, nunca uma chave no navegador.
4. Importe a planilha pelo script, agora com `DATABASE_URL` configurada, ou pela tela
   depois do deploy. Não é necessário enviar a planilha junto com o código.
5. Importe o repositório na Vercel, selecione FastAPI e configure as variáveis:
   `DATABASE_URL`, `APP_PASSWORD` e `APP_ENV=production`.
6. Após o deploy, entre com usuário **operador** e a senha definida em `APP_PASSWORD`.

`app.py` é o ponto de entrada. O servidor recusa produção sem senha e PostgreSQL.
Localmente, sem senha, o acesso é limitado ao loopback. A autenticação desta versão
usa uma senha compartilhada para a operação; não há contas individuais ou recuperação
de senha. As tabelas guardam o conteúdo das faturas e as revisões; mantenha o backup
do banco conforme a operação da equipe.

Referências de deploy: [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi),
[runtime Python](https://vercel.com/docs/functions/runtimes/python) e
[conexões PostgreSQL do Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

## Validação

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -v
py -3 scripts/check_ui.py
```

O teste de interface usa Edge instalado, um banco temporário e a planilha original.
Os testes de cálculo incluem valores de referência das nove abas em
`tests/reference_cases.json`. Sem o XLSX original, apenas o teste de importação real
é ignorado; os testes das nove regras continuam disponíveis.

Backend: FastAPI, Decimal, SQLite/PostgreSQL, openpyxl para leitura, ReportLab e
PDFium. Interface: HTML, CSS e JavaScript, sem etapa de build ou serviços de fontes.
