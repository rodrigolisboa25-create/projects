Mapeamento das bases piloto

Escopo confirmado

Posição de Estoque - FISIA.xlsb: aba fonte Base Orig., cabeçalho na linha 5.

MB59_BASE GR - SEASON.XLSX: aba fonte BASE, cabeçalho na linha 2.

All Brazil Materials: enriquece atributos de material; o arquivo de estoque registra a pasta 1DUWWyh9Q1i-pkPWcT0jlk7gdj3HNZl38.

MB59 / BASE

Foram identificados 82.535 registros efetivos (linhas 3 a 82.537). O UsedRange chega à linha 122.299 por formatação residual. A soma exibida de Montante em MI é R$ 248.688.604,33.

Campos SAP: Material, Texto breve material, Centro, Depósito, Tipo de movimento, Doc.material, Data de lançamento, Qtd. UM registro, Nome do usuário, Cód.débito/crédito, Data de entrada, Referência, Pedido, Item, Data do documento, Fornecedor e Montante em MI.

Regras legadas mapeadas:

Saída

Fórmula atual

Regra Python/SQL

SKU

LEFT(Material,10)

primeiros 10 caracteres, com teste de padrão

PO

LEFT(Pedido,2)

prefixo do pedido

SEASON&YEAR

Season & Year

concatenação validada

Material Origin Des.

prefixo 48 = IMPORTADO; demais = NACIONAL

dimensão versionada de prefixos

Modelo-cor&quantidade

SKU & Quantidade

manter campos separados e gerar chave com delimitador

As cinco fórmulas são repetidas em 82.535 linhas (412.675 fórmulas), além do subtotal. Elas serão substituídas por cálculo vetorizado.

ZMM119 automática / contrato posicional homologado

A exportação XLSX gerada diretamente pela ZMM119 possui cabeçalho na linha 1 e 18 colunas fixas de A. O importador automático usa a posição física como fonte de verdade; nomes não são usados para localizar ou reordenar campos. O cabeçalho é validado apenas como assinatura de segurança para detectar mudança de layout.

Coluna

Campo interno

Cabeçalho SAP

A

company

Empresa

B

plant

Centro

C

material

Material

D

material_description

Texto breve material

E

base_unit

UM básica

F

ncm

NCM

G

unrestricted_quantity

Utilização livre

H

blocked_quantity

Bloqueado

I

average_company_cost

Custo Médio Empresa

J

fiscal_cost

Custo Fiscal

K

total

Total

L

icms_st_amount

Vlr ICMS ST

M

ipi_amount

Vlr IPI

N

inventory_type

Tipo

O

company_total_amount

Vlr Tot Emp

P

fiscal_total_amount

Vlr Tot Fisc

Q

average_commercial_cost

Custo Médio Comercial

R

commercial_total_amount

Vlr Total CC

O arquivo homologado ZMM119_2026-08.xlsx apresentou dimensão A1:R491610, isto é, 1 linha de cabeçalho e 491.609 registros de dados.

Posição de Estoque / Base Orig.

A amostra contém 995 registros (linhas 6 a 1.000) e 39 colunas de B a AN. Totais legados: Utilização livre = 3.013 e Vlr Tot Fisc = R$ 445.035,28. A data-base em AB2 é 31/07/2026.

Origem ZMM119: Empresa até Vlr Total CC (D). Origem All Brazil: Division Description, Material Origin Des., Lifecycle e Lifecycle Descrip. (Z e AE).

PASSO A PASSO homologado para Product Offer End, Season e Year, sempre por campo: (1) Base GR/MB59 da competência por CE & MAT; (2) posição de estoque do mês anterior por CE & MAT; (3) último All Brazil válido do mês, sem Centro. No All Brazil, o sistema procura primeiro o Material completo e, somente se ele não existir, usa o Estilo-Cor de 10 caracteres contra Material Nbr. A medição de agosto encontrou 125.489/125.489 chaves, sem conflitos: 1.662 por Material exato e 123.827 pelo fallback de Estilo-Cor.

A exportação bruta MB59 de agosto contém 115.649 movimentos e foi consolidada em 17.929 chaves CE & MAT. O layout bruto não trouxe Product Offer End, Season ou Year; portanto, nessa competência a cascata continuou para a posição anterior e o All Brazil. O importador aceita essas colunas opcionais quando vierem em uma futura exportação enriquecida.

Regras legadas:

Saída

Regra

CE & MAT

Centro + Material; no sistema serão duas chaves ou concatenação com delimitador

STATUS OPERAÇÃO

centro para status pela dimensão de plantas

CE UNIT

Vlr Tot Emp / Utilização livre

Estilo-Cor

10 primeiros caracteres do Material

Estilo

6 primeiros caracteres de Estilo-Cor

Custo Fiscal UNIT.

Vlr Tot Fisc / Utilização livre

Days

data-base menos Product Offer End Dt

AGING

negativo = Futures; demais por faixas versionadas

Local

centro para local atual pela dimensão de plantas

FOB / II / Outros Custos

50% / 35% / 15% do Vlr Tot Fisc

Season/Coleção

Season + Year

histórico

Year anterior a 2022 deve virar <2022

Faixas observadas: 0–104, 105–194, 195–284, 285–374, 375–554, 555–734, 735–1.814 e 1.815–19.995 dias. Valores negativos são 0) Futures.

Riscos corrigidos no novo desenho

leitura posicional sem contrato/trava de layout; a ZMM119 automática usa A homologado e bloqueia qualquer drift estrutural;

concatenação sem separador e possíveis colisões;

divisão por zero escondida;

VLOOKUP com #N/A para centro/material desconhecido;

regra de origem reduzida a “48 ou outros”;

SUBTOTAL dependente de filtro como controle oficial;

data-base fixa em célula;

fórmula preenchida somente em parte do UsedRange;

taxa 50/35/15 sem versão ou vigência.

O contrato executável está em config/schemas.yaml. Mudança de ordem é aceita; ausência, duplicidade ou ambiguidade de campo obrigatório coloca a fonte em quarentena.
