# 🔐 Escopo da versão pública

Esta pasta foi produzida a partir de uma cópia separada. A origem no Drive corporativo não foi modificada.

## Incluído

Código Python, HTML, CSS e JavaScript da aplicação e do instalador; questionário; modelos iniciais de referências; recursos visuais próprios; workflow n8n sem vínculos de credenciais; prompt e gerador de catálogo de manuais com manifesto parametrizado.

## Excluído

Cadastros e assinaturas de acesso, chaves de publicação, configurações de conexão, identificadores de recursos internos, entrevistas, procedimentos reais, bases de conhecimento, manuais corporativos, planilhas, relatórios, logs, backups, arquivos temporários e documentos gerados. A lista original de manuais e IDs do Drive foi retirada do utilitário e substituída por um manifesto externo de exemplo.

## Substituições na cópia

- E-mails corporativos viraram endereços `example.com`.
- Webhooks, ponte de sincronização, ID de pasta e projeto de dados viraram valores de exemplo.
- Vínculos de credenciais, metadados de instância e dados fixados foram removidos do export n8n.
- Caminhos e nomes internos de pasta foram generalizados.

Isso preserva a estrutura do código, mas algumas integrações exigem ajuste antes de funcionar em outra implantação. Não use esta publicação como backup operacional. Revise `.env.example`, o instalador, os nós do n8n e as permissões antes de executar o sistema com dados reais.
