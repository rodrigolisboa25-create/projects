# Segurança e sanitização

## Conteúdo publicado

Esta versão mantém o código necessário para entender e adaptar o sistema, mas separa o software dos dados da operação.

Foram removidos ou substituídos:

- credenciais do `.env`;
- e-mails pessoais e corporativos;
- IDs de pastas, arquivos e recursos Google;
- caminhos internos de máquinas e drives;
- bancos SQLite e documentos processados;
- PDFs de notas, boletos, demonstrativos e conhecimentos;
- planilhas preenchidas, cadastros e centros de custo;
- logs, relatórios de auditoria e métricas de produção;
- URLs e endpoints internos.

## Controles do fluxo

- o Apps Script só deve finalizar uma mensagem depois que o anexo e a auditoria forem persistidos;
- a etapa local mantém uma chave documental para reduzir reprocessamento;
- a auditoria compara quantidade, conteúdo esperado e totais;
- contas técnicas devem usar o menor escopo Gmail/Drive possível;
- segredos ficam em variáveis de ambiente, propriedades do script ou cofre autorizado;
- arquivos de produção permanecem fora do GitHub;
- relatórios devem ser compartilhados apenas com os perfis necessários.

## Riscos de implantação

| Risco | Mitigação |
| --- | --- |
| Exposição de credencial IMAP | Usar `.env` local e nunca versionar o arquivo |
| Leitura de caixa de e-mail indevida | Conta técnica dedicada e filtro/marcador controlado |
| Documento duplicado | Conferir banco e chave documental antes do reprocessamento |
| Saída com dado incorreto | Exigir auditoria e conferência de totais antes da promoção |
| Template com fórmula ou cadastro errado | Homologar cada empresa e competência separadamente |
| Exposição de PDFs | Usar pastas Drive restritas e retenção definida |
| Limpeza irreversível | Fazer backup antes de `Limpar_Banco.bat` |

## Antes de publicar uma nova adaptação

- [ ] Não há `.env`, banco, PDF, planilha preenchida ou log no commit.
- [ ] Não há e-mail, token, ID ou caminho interno no código.
- [ ] Os escopos Google foram revisados.
- [ ] A conta executora está documentada.
- [ ] A pasta de entrada não é pública.
- [ ] A auditoria e o procedimento de recuperação foram testados.
