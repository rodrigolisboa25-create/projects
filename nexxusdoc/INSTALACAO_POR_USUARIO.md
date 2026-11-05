# Instalação do NexxusDoc (por usuário)

O NexxusDoc roda no Windows de cada pessoa. Documentos, entrevistas, bases de conhecimento e acessos ficam na pasta compartilhada do Google Drive.

## Antes de instalar

1. O Google Drive para computador precisa estar instalado e sincronizando esta pasta do projeto.
2. A pessoa precisa estar cadastrada em **Configurações → Acessos por área** (pelo master ou pelo owner da área).
3. Para usar o chat, a **VPN corporativa (GlobalProtect)** precisa estar conectada.

## Instalar ou atualizar

1. Abra esta pasta pelo Google Drive e dê dois cliques em **`INSTALAR_NEXXUSDOC.bat`**.
2. O instalador usa o Python 3.11–3.13 existente ou baixa o Python 3.13 oficial (com verificação SHA-256), cria o ambiente local em `%LOCALAPPDATA%\GrupoSBF\NormasProcedimentos`, instala as dependências, ajusta o `.env` (porta 8790, URL do n8n, pasta compartilhada) e cria o atalho **NexxusDoc** na Área de Trabalho.
3. Rodar o instalador de novo atualiza a instalação: ele encerra o NexxusDoc aberto, copia a versão nova, preserva o `.env` e remove atalhos com nomes antigos.

## Usar

- Abra o atalho **NexxusDoc**. Não abre janela de console; o navegador abre quando o sistema estiver pronto (alguns segundos).
- Clicar no atalho de novo apenas reabre a página. O servidor local encerra sozinho 30 minutos depois que o navegador for fechado.
- O NexxusDoc usa a porta 8790 e não interfere no **Estoque Contábil** (porta 8765); os dois podem ficar abertos ao mesmo tempo.
- Se algo falhar ao abrir, o aviso indica o log em `%LOCALAPPDATA%\GrupoSBF\NormasProcedimentos\logs\nexus.log`.

## Login

O sistema pede o e-mail e compara com o UPN da conta Windows. Se o Windows não informar o UPN, a TI precisa ajustar a conta. Cada pessoa deve usar a própria sessão do Windows.
