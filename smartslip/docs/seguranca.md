# Segurança da versão pública

## Conteúdo removido

A preparação para publicação removeu ou substituiu:

- IDs das planilhas persistente e auxiliar;
- IDs de arquivos usados em testes;
- URL da implantação ativa;
- endpoint interno do gateway de inteligência artificial;
- e-mails pessoais e operacionais;
- domínios e nomes específicos da organização;
- links de arquivos reais no Google Drive.

Nenhum conteúdo da planilha persistente foi copiado para o repositório.

## Configuração segura

As chaves e identificadores devem ser cadastrados em **Propriedades do script**. Não grave tokens, chaves de API, IDs privados ou destinatários reais diretamente em `Code.gs` ou `Index.html`.

Use uma conta de implantação com os menores privilégios necessários. Restrinja o aplicativo da web à organização quando o processo usar informações internas e revise os escopos solicitados pelo Apps Script antes da publicação.

## Dados de demonstração

As telas da documentação usam somente dados fictícios. Antes de adicionar novas imagens ao repositório, verifique nomes, e-mails, lojas, valores, protocolos, endereços e links visíveis.
