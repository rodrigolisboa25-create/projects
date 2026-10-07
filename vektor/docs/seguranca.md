# Segurança da versão pública

Esta pasta é uma cópia sanitizada do projeto Vektor para documentação, preservação e adaptação a outros ambientes.

## Conteúdo removido ou substituído

- IDs de planilhas, pastas, arquivos, projetos Google Cloud e bibliotecas.
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

## Cuidados antes de implantar

- Use propriedades do script ou um cofre de segredos para valores de ambiente.
- Aplique privilégio mínimo às contas e aos escopos OAuth.
- Restrinja o Web App ao público autorizado.
- Separe dados de teste e produção.
- Revise remetentes, destinatários e acionadores antes de habilitar envios.
- Não armazene dados financeiros, documentos ou auditorias no repositório.
- Valide as políticas de retenção e privacidade da nova organização.
