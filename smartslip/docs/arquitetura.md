# Arquitetura e fluxo do SmartSlip

## Componentes

O SmartSlip é uma aplicação web hospedada no Google Apps Script. O backend concentra autenticação, regras de negócio, integração com Google Sheets e Drive, chamadas de inteligência artificial, tarefas agendadas e endpoints para a interface. O frontend é um único documento HTML responsivo, com estilos e JavaScript executados no navegador.

## Camadas

| Camada | Responsabilidade |
| --- | --- |
| Interface | Formulários, upload, dashboards, histórico, administração e experiência móvel |
| Aplicação | Validações, permissões, fila, reenvio, exclusão e composição das respostas |
| Inteligência artificial | Extração documental, pré-validação de totais e análise de evidências |
| Persistência | Abas do Google Sheets para base, fila, usuários, pesquisas, custos e auditoria |
| Arquivos | Google Drive organizado por competência e loja |
| Automação | Acionadores para fila, cotação, alertas e rotinas periódicas |

## Fluxo do comprovante

1. A interface carrega o usuário autenticado, perfil e lojas permitidas.
2. O usuário seleciona arquivos e informa o período do movimento.
3. O backend valida extensão, tamanho, datas, total e regras de acesso.
4. Os arquivos são persistidos no Drive e os itens entram na fila.
5. O processador chama a IA, normaliza a resposta e aplica regras complementares.
6. O resultado é gravado na base com protocolo, hash, status e evidências.
7. A interface apresenta o resultado no histórico e nos indicadores.

## Filas e idempotência

Cada envio recebe protocolo e identificadores derivados do conteúdo e do contexto. O backend verifica registros anteriores antes da gravação, controla lotes com vários anexos e impede que uma repetição confiável seja processada como um novo documento. Falhas permanecem rastreáveis e podem ser tratadas pelo fluxo de reenvio.

## Observabilidade

O projeto registra duração, origem, modelo, consumo e custo estimado das chamadas de IA. A área de desempenho reúne volume, tempo de resposta, taxa de erro, chamadas lentas e disponibilidade dos componentes usados pela aplicação.

## Portabilidade

Para aplicar o sistema em outra organização, substitua as bases de lojas, defina os domínios permitidos, configure propriedades, revise destinatários de alerta e adapte as regras de classificação. O código publicado não depende dos identificadores da implantação original.
