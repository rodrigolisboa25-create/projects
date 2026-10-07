# Publicação do agente Gemini

O arquivo `workflows/ops_contabil_agent_gemini.json` é importável no n8n. Ele usa o Google Gemini somente como modelo; a interface incorporada é a URL pública do Chat Trigger do n8n.

1. Importe o JSON na instância n8n corporativa.
2. No node **Google Gemini Chat Model**, selecione a credencial Google Gemini aprovada pela empresa e um modelo disponível para essa credencial.
3. Configure no ambiente do n8n:
   - `OPS_API_BASE_URL`: URL pela qual o n8n alcança o Ops Contábil.
   - `OPS_API_TOKEN`: o mesmo token configurado na API local.
4. No Chat Trigger, mantenha a origem permitida restrita à URL do sistema e publique o workflow.
5. Copie a URL de produção do Chat Trigger e configure `N8N_CHAT_URL` antes de iniciar o Ops Contábil.

Enquanto o Ops Contábil estiver restrito a `127.0.0.1`, um n8n hospedado na nuvem não consegue chamar sua API. Para produção, disponibilize a API em uma rede corporativa protegida, com HTTPS e autenticação; não exponha a porta local diretamente à internet.

O fluxo é somente leitura: ele recebe agregados e evidências limitadas da rota `/api/agent/context`, sem acesso a credenciais SAP e sem ferramenta de gravação.
