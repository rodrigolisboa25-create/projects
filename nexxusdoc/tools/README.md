# 🛠️ Gerador do catálogo de manuais

`build_manuais.py` lê um manifesto privado de documentos vigentes e prepara a base para consulta pelo agente. A relação real de arquivos, seus caminhos e IDs do Drive foi removida da publicação.

1. Copie `manuais_manifest.example.json` para `manuais_manifest.json` fora do controle de versão e preencha a lista autorizada.
2. Configure `NEXXUS_MANUALS_ROOT` para a raiz local dos arquivos sincronizados e `NEXXUS_MANUALS_MANIFEST` para o manifesto.
3. Opcionalmente configure `NEXXUS_MANUALS_AREA`; execute `python tools/build_manuais.py`.

O arquivo resultante `base_manuais.json` é dado operacional e não deve ser publicado. O filtro do script ajuda a remover linhas de credenciais, mas não substitui uma revisão antes de distribuir a base internamente.
