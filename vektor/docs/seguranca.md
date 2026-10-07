# Segurança da versão pública

Esta pasta é uma cópia sanitizada do projeto Vektor para documentação, preservação e adaptação a outros ambientes.

## Conteúdo removido ou substituído

- IDs de planilhas, pastas, arquivos, projetos Google Cloud e bibliotecas, exceto os dois links de planilhas cuja referência foi autorizada na documentação.
- E-mails pessoais e corporativos.
- URLs internas, links de painéis, agentes, documentos e treinamentos.
- Endpoints específicos da implantação original.
- Conteúdo integral da política corporativa usada pelo assistente.
- Chaves, tokens e credenciais que eventualmente aparecessem como literais.
- Bases JSON, planilhas, PDFs, anexos de e-mail, históricos e demais dados operacionais.

## Conteúdo preservado

- Os 19 arquivos e seus nomes originais.
- Estrutura dos módulos, funções, telas e fluxos.
- Regras de processamento e mecanismos de auditoria.
- Declaração dos serviços avançados e nomes das bibliotecas vinculadas.
- Pontos de integração necessários para reconstruir a solução em outro ambiente.

## Referências externas autorizadas

A documentação identifica as planilhas `Vektor_Info_calibrate` e `Capta_Clara` por link para explicar o contrato de integração. Os dados das planilhas não foram copiados para o GitHub, e o acesso ao conteúdo continua protegido pelas permissões do Google Drive. A exposição controlada desses links não autoriza a publicação de linhas, usuários, destinatários, valores ou históricos operacionais.

## Cuidados antes de implantar

- Use propriedades do script ou um cofre de segredos para valores de ambiente.
- Aplique privilégio mínimo às contas e aos escopos OAuth.
- Restrinja o Web App ao público autorizado.
- Separe dados de teste e produção.
- Revise remetentes, destinatários e acionadores antes de habilitar envios.
- Não armazene dados financeiros, documentos ou auditorias no repositório.
- Valide as políticas de retenção e privacidade da nova organização.

## Controles existentes no desenho

### Identidade e autorização

- identificação pela conta Google autenticada;
- lista de usuários autorizados;
- perfil e empresa vinculados ao usuário;
- permissão por módulo;
- lista de funções permitidas por papel;
- validação no backend antes de operações protegidas;
- sessão com tempo de expiração.

### Integridade operacional

- chaves de deduplicação para comunicações;
- hash, nome e tamanho para documentos Prosegur;
- atualização da auditoria antes de finalizar mensagens;
- validação de campos obrigatórios antes de envios;
- estado persistente de jobs e heartbeat;
- snapshots e hashes dos backups do Numerário;
- histórico de alertas, envios e métricas.

### Segredos e configuração

IDs, endpoints e credenciais devem ficar em propriedades do script ou em um mecanismo de segredo equivalente. O navegador recebe somente os dados necessários para a função exibida.

## Riscos a revisar em cada implantação

| Risco | Controle recomendado |
| --- | --- |
| Web App acessível ao público incorreto | Restringir o acesso e testar com conta não autorizada |
| Escopos OAuth maiores que o necessário | Remover módulos e escopos não utilizados |
| Envio para destinatários reais durante teste | Usar contas de homologação e destinatário de teste |
| Reprocessamento de e-mails ou documentos | Validar deduplicação e histórico antes de ativar gatilhos |
| Exposição de IDs ou tokens no frontend | Manter valores no backend e nas propriedades do script |
| Dados sensíveis em logs | Registrar somente contexto operacional necessário |
| Concorrência em Sheets ou JSON | Usar locks, chaves e escrita validada |
| Job interrompido | Persistir progresso, heartbeat e permitir retomada controlada |
| Resposta de IA sem base | Limitar contexto, registrar fonte e manter decisão humana |

## Checklist antes da produção

- [ ] Os IDs e segredos foram cadastrados fora do código.
- [ ] Os marcadores de exemplo foram substituídos.
- [ ] As bibliotecas usam IDs e versões autorizados.
- [ ] Os serviços avançados e APIs foram revisados.
- [ ] Os escopos OAuth correspondem aos módulos implantados.
- [ ] Usuários sem permissão foram testados.
- [ ] Envios usam destinatários de homologação.
- [ ] Gatilhos foram instalados pela conta correta.
- [ ] Logs e históricos não armazenam conteúdo excessivo.
- [ ] Backup, restauração e retomada de jobs foram validados.
