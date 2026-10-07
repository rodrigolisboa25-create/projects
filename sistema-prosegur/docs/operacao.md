# Operação passo a passo

## Preparar uma competência

1. Confirme o período que será processado.
2. Separe os PDFs autorizados na pasta `Idocs_Prosegur`.
3. Confira se os templates SAP e bases de referência estão disponíveis.
4. Verifique se o banco e a pasta de saída pertencem à mesma instalação.
5. Confirme que não há outro processamento escrevendo no mesmo diretório.

## Executar

Na raiz do projeto:

```powershell
python SISTEMA_PROSEGUR/main.py
```

Ou use `RODAR_ROBO_PROSEGUR.bat` no Windows. O processo registra o avanço em `SISTEMA_PROSEGUR/processamento.log` e atualiza o banco local.

## Conferir o resultado

Após a execução, valide:

- quantidade de PDFs identificados por tipo;
- documentos com tipo `UNKNOWN`;
- quantidade de notas, boletos e demonstrativos;
- total financeiro por empresa e período;
- arquivos criados em `PROSEGUR_PROCESS`;
- divergências apontadas pelo agente de auditoria;
- métricas gravadas para o Vektor.

Para abrir a análise comparativa, execute `ANALISE_BASE_PROSEGUR.bat` depois que os relatórios master e oficial estiverem disponíveis.

## Como interpretar falhas

| Sintoma | Verificação |
| --- | --- |
| PDF não reconhecido | Conferir layout, nome e texto extraído; revisar `detect_document_type()` e o parser correspondente |
| Total diferente | Comparar valor no PDF, linha master, relatório oficial e auditoria |
| Nota sem boleto ou DEM | Conferir número normalizado, lote e competência |
| Saída em pasta errada | Revisar período informado e o mapeamento de empresa |
| Falha ao abrir Excel | Validar template, abas esperadas e dependências `openpyxl` |
| Job de e-mail sem anexos | Conferir marcador, permissões Gmail/Drive e auditoria do Apps Script |
| Reprocessamento duplicado | Verificar `documentos.db` e a chave documental antes de limpar o banco |

## Limpeza controlada

`Limpar_Banco.bat` apaga banco, log e relatório de auditoria após confirmação explícita. Essa ação deve ser feita somente quando a competência anterior foi exportada e preservada em local autorizado.

Não apague PDFs de entrada ou saídas de produção para corrigir uma falha sem antes guardar uma cópia e registrar o motivo.

## Retomada

O fluxo deve ser retomado a partir do último estado confirmado:

1. preserve o log e o relatório de auditoria;
2. identifique o documento ou etapa que falhou;
3. corrija a base de referência ou o parser;
4. reexecute apenas com uma cópia controlada do lote;
5. compare a quantidade de documentos e totais antes de substituir as saídas.

## Atualização do Apps Script

O Apps Script é uma etapa separada. Antes de ativar o acionador:

- confirme o projeto e a conta executora;
- revise IDs das pastas e marcadores;
- valide a auditoria no Drive;
- teste com uma mensagem e um PDF de homologação;
- verifique se a mensagem só é finalizada depois da persistência do anexo.
