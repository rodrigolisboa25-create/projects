# Artefatos executivos do Optimus

O backend local está preparado para duas ações do agente:

- `report_pdf`: devolve um link autenticado para gerar e baixar o PDF da página Visão e relatórios na competência solicitada.
- `executive_presentation`: devolve KPIs, comparação com a competência compilada anterior, histórico mensal, divisões, locais, origens, lifecycle/aging e o roteiro dos slides.

O agente solicita as ações pelo protocolo:

```text
[[OPS_ACTION]]{"type":"report_pdf","period":"2026-08"}[[/OPS_ACTION]]
[[OPS_ACTION]]{"type":"executive_presentation","period":"2026-08"}[[/OPS_ACTION]]
```

Para materializar a apresentação no n8n, conecte a saída estruturada de `executive_presentation` a:

1. Google Slides para criar a apresentação e preencher título, resumo e seções.
2. Google Drive para salvar o arquivo e retornar o link corporativo.
3. PDF, se desejado, para exportar uma cópia final.

Regra de segurança: os nós devem usar somente o payload devolvido pelo Ops Contábil. Indicadores ausentes não podem ser estimados. A criação de Slides fica no n8n; a leitura, os cálculos e a competência permanecem controlados pelo Python.
