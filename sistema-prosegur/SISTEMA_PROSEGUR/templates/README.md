# Templates da operação

O sistema original utiliza modelos Excel para gerar as planilhas SAP de cada empresa. Os arquivos preenchidos e os modelos reais não foram publicados porque podem conter cadastros, fórmulas, fornecedores, centros de custo e dados operacionais.

A nova implantação deve fornecer, no mínimo:

- `Planilha_SAP_SBF.xlsx`;
- `Planilha_SAP_FISIA.xlsx`;
- base de fornecedores e referências;
- estrutura de abas e colunas esperada por `main.py`.

Os caminhos são configurados em `main.py` pela pasta `SISTEMA_PROSEGUR/templates`. Ajuste os nomes das abas, colunas, fórmulas e centros de custo à organização que receberá o projeto.
