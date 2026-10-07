# Processo operacional e SAP

O Sistema Prosegur prepara informações para etapas posteriores de compras, faturamento e contabilização. O modelo Excel usado pela operação é específico de cada empresa e deve ser fornecido pela implantação.

## Sequência funcional

1. Consolidar os documentos válidos da competência.
2. Identificar empresa, loja, fornecedor e tipo de serviço.
3. Associar nota, boleto, demonstrativo e conhecimento quando houver correspondência.
4. Resolver centros de custo, rateios e valores por serviço.
5. Alimentar as abas master e dinâmica do template.
6. Recalcular fórmulas e pivôs.
7. Validar totais contra as bases de referência.
8. Gerar o arquivo SAP de cada empresa.
9. Registrar divergências e pendências para tratamento.

## Contratos que precisam ser definidos

Cada nova empresa deve documentar:

- tipos de requisição e pedido;
- moedas e condições de pagamento;
- centros de custo por loja e serviço;
- regras de rateio;
- nomes das abas e colunas do template;
- campos obrigatórios para criação do arquivo SAP;
- critérios para estorno e reaproveitamento de histórico;
- responsável pela conferência antes da carga.

## Controle antes da carga

O relatório SAP só deve ser encaminhado quando a auditoria confirmar que:

- todos os documentos esperados foram processados ou justificados;
- os valores do relatório batem com a base master;
- as linhas sem fornecedor, loja ou centro de custo foram tratadas;
- o período e a empresa do nome do arquivo estão corretos;
- a aprovação operacional foi registrada.

Os códigos, IDs, templates e parâmetros da operação original foram retirados da versão pública. Eles devem ser configurados pela organização que reutilizar o projeto.
