# Manual do Estoque Contábil (Programa Contábil | Visão de Estoque de Materiais)

Fonte oficial para o Optimus responder dúvidas sobre o próprio sistema: páginas, botões,
parâmetros, bases, regras de cálculo, permissões e rotinas. Cada seção começa com "## " e
tem uma linha de palavras-chave usada para escolher as seções enviadas ao Optimus.
Ao alterar o sistema, atualize a seção correspondente (este arquivo vai junto no instalador).

## Visão geral do sistema
<!-- chaves: o que é o sistema, o que o sistema faz, sobre o sistema, para que serve o sistema, programa contábil, objetivo, visão geral, arquitetura, fisia, navegador, menu, páginas, navegação, seletor de competência, tela de carregamento, página inicial, abre em qual página, recarregar, f5, grupos do menu, recolher grupo, submenu, seta, logo, símbolo, ícone do sistema -->
O Estoque Contábil é um aplicativo local (roda no computador do usuário e abre no navegador em http://127.0.0.1:8765) que substitui as planilhas pesadas da posição contábil de estoque da Fisia (empresa 7170) por processamento Python auditável.

Fluxo principal: extrai do SAP a ZMM119 (posição) e a MB59 (Base GR), enriquece com o cadastro All Brazil do Drive e com as regras do Mapping, grava tudo num banco local (DuckDB) e apresenta indicadores, gráficos, base detalhada, controles e o agente Optimus.

Menu lateral (ordem): Visão e relatórios · Base de estoque · Extrações SAP · Bases All Brazil · Mapping · Controles e auditoria · Health Center · Optimus · Documentação · Configurações. O menu pode ser recolhido; recolhido, mostra só os ícones.
Grupos do menu (ANÁLISE CONTÁBIL, OPERAÇÃO, INTELIGÊNCIA, ADMINISTRAÇÃO): com o menu expandido, clicar no nome do grupo (seta ao lado) recolhe ou mostra as páginas dele; a escolha fica guardada no navegador. Ao ir para uma página de um grupo recolhido (por um botão ou notificação), o grupo se abre sozinho. Com o menu geral recolhido, todos os ícones aparecem, sem grupos. Grupos sem nenhuma página liberada para o usuário não aparecem.
Página inicial: ao abrir ou recarregar o sistema (F5, nova aba, atalho, novo login), ele sempre começa na Visão e relatórios, nunca na última página aberta. Exceção: quando o sistema é aberto pelo clique numa notificação do Windows e não havia aba aberta, ele abre direto na página da notificação.
Textos fixos: no topo do menu, abaixo de "Estoque Contábil", aparece "Inventory Mgmt" (abreviação de Inventory Management, para caber sem rolagem; na tela de login aparece por extenso); no topo da página, ao lado do botão que recolhe o menu, o caminho é "Inventory Management / <página atual>".
Símbolo do sistema: ícone próprio com três placas empilhadas em tons de azul-marinho (as bases consolidadas) e um gráfico de barras crescente saindo do topo. Aparece no atalho da área de trabalho, no topo do menu, na tela de login, na tela de carregamento, nas notificações do Windows, na aba do navegador e na capa da documentação técnica. Só a aba do navegador mostra o ícone com fundo quadrado; nos demais lugares ele aparece sem fundo. O atalho recebe o ícone ao instalar ou atualizar o sistema.
Cores: a tela de carregamento (faixa "Programa Contábil | Visão de Estoque de Materiais" e o círculo de progresso) usa azul-marinho em dois tons. As páginas do grupo OPERAÇÃO (Extrações SAP, Bases All Brazil, Mapping, Controles e auditoria) seguem o mesmo tema azul-marinho de Configurações: cards com faixa de título azul-marinho, botões, selos, avisos e cabeçalhos de tabela em azul; o painel "Execuções atuais" é azul-marinho escuro. Selos de atenção continuam amarelos.

Seletor de competência: no topo da tela, escolhe a competência (mês AAAA-MM) usada por todas as páginas. Só aparecem competências com Base de Estoque carregada nesta máquina.

Tela de carregamento: ao abrir, aparece a faixa "Programa Contábil | Visão de Estoque de Materiais" enquanto o sistema prepara os dados.

Cada máquina tem o próprio banco local; as máquinas trocam competências atualizadas pelo Drive compartilhado Estoque_Cont (ver "Ponte de dados").

## Perfis de acesso e permissões
<!-- chaves: perfil, permissão, permissões, acesso, administrador, admin, usuário, liberar, bloqueado, não aparece, sem acesso, login, entrar, sessão, e-mail corporativo, páginas liberadas, 403, desativar, desativado, excluir usuário, revogar, lista central de acessos, outra máquina, novo usuário, cadastrar usuário, 7 dias -->
Login: pelo e-mail corporativo vinculado ao Windows (@gruposbf.com.br). Só entra quem foi liberado em Configurações > Acesso corporativo.

Perfis:
- Administrador: acessa todas as páginas e todas as ações operacionais (executar SAP, upload de planilhas, editar Mapping, excluir competência, Share Link, instalador, ponte de dados, backup e restauração, Configurações).
- Usuário: vê as páginas liberadas pelo administrador. Visão e relatórios e Documentação são obrigatórias para todo usuário; Optimus precisa ser marcado para liberar o chat. Todo usuário também acessa Configurações, mas só as seções Interface e experiência e Notificações (preferências do próprio computador); o restante de Configurações é exclusivo de administradores. O usuário não executa extrações SAP, uploads de planilha, alterações de Mapping, Share Link nem ações administrativas.

Se uma página não aparece no menu, o perfil não tem acesso: um administrador deve marcá-la em Configurações > Acesso corporativo.

Lista central de acessos: cadastros, alterações de perfil/páginas, desativações e exclusões feitos por qualquer administrador valem em TODAS as máquinas, sem reinstalar. A lista fica no Drive compartilhado, em Estoque_Cont\acesso; cada máquina a consulta no login e a cada ~2 minutos. Um usuário desativado ou excluído perde a sessão em até ~2 minutos; um usuário recém-cadastrado já consegue entrar na própria máquina (o administrador também precisa dar a ele acesso de Leitor ao drive Estoque_Cont no Google Drive, para receber os dados). Quando dois administradores alteram o mesmo usuário, vale a alteração mais recente. Os administradores iniciais nunca são desativados nem excluídos.
Segurança: só administradores devem ter permissão de edição (Gerenciador de conteúdo) no Estoque_Cont; usuários ficam como Leitor. Se a máquina passar 7 dias sem conseguir consultar a lista (sem Drive ou VPN), usuários comuns ficam bloqueados nela até reconectar; administradores continuam entrando. Bloquear o login não apaga os dados já existentes na máquina do usuário; para cortar o recebimento de dados novos, remova o usuário do drive Estoque_Cont no Google Drive.

## Página Visão e relatórios
<!-- chaves: visão e relatórios, overview, dashboard, painel, relatório, relatórios, kpi, cards, card, indicadores, gráficos, gráfico, valor fiscal, utilização livre, média pmm, cobertura all brazil, share link, html, pdf, relatório pdf, relatório html, mesmos gráficos, paisagem, animação, aging for season, lifecycle × aging, lifecycle x aging, seta, setas, seta vermelha, seta azul, variação, division description, risco de obsolescência, obsolescência, provisão, mais de 12 meses, futures, interrogação, ajuda do gráfico, o que mostra o gráfico, local de estoque, valor por centro, origem do material, evolução, variação por categoria, pmm analítico, composição do custo fiscal, pizza, dispersão, abreviado, bi, mi -->
Título: "Posição contábil do estoque - Fisia". Indicadores calculados diretamente da Base de Estoque da competência selecionada.

Cards (KPIs):
- Valor fiscal: soma de Vlr Tot Fisc.
- Utilização livre: soma das unidades disponíveis (Utilização livre).
- Materiais: quantidade de SKUs (Materiais) distintos.
- Média PMM: Vlr Tot Fisc ÷ quantidade livre (preço médio ponderado da competência).
- Cobertura All Brazil: % dos registros com o atributo Division preenchido pelo All Brazil.
Valores muito grandes são abreviados (ex.: R$ 1,38 bi); o valor completo aparece ao passar o mouse. A abreviação é calculada pelo espaço do card e mantida ao trocar de página, sem mostrar o valor completo por um instante ao voltar.

Gráficos:
- Lifecycle × Aging: valor fiscal por faixa de aging, separado por Lifecycle (Active/Inactive).
- Aging for Season: matriz ano × season com valor fiscal; anos anteriores a 2022 agrupados em "<2022". Tem coluna Total (por ano), linha Total (por season) e total geral igual ao card Valor fiscal. A variação em relação ao ano anterior aparece no balão ao passar o mouse sobre um valor; "<2022" não é comparado.
- Division Description: valor fiscal (colunas em degradê laranja) e quantidade livre por divisão (Calçados, Vestuário etc.), com uma linha azul acima das colunas mostrando a variação % de cada divisão em relação à competência anterior (passar o mouse no ponto mostra a variação em R$). Sem competência anterior, a linha não aparece.
- Local de estoque: valor fiscal e quantidade livre por Local (definido no Mapping Planta e local). "Não informado" é o estoque de centros que não têm linha na aba "Planta e local" do Mapping; quando existe, uma nota abaixo do gráfico lista os centros, a quantidade de linhas e o valor (ex.: em 09/2026, centro 2115 com R$ 5,96 mi). Para resolver, cadastre o centro no Mapping: todas as competências são recalculadas e a nota some.
- Valor por centro: concentração do valor fiscal por Centro.
- Origem do material: valor fiscal por Material Origin (nacional, importação direta etc.), com barras mais grossas e espaçadas para ocupar o card.
Os gráficos de barras horizontais (Local de estoque, Origem do material e Risco de obsolescência) distribuem as barras pela altura do card, sem deixar espaço vazio embaixo.
- Evolução da posição de estoque: valor fiscal (barras em degradê laranja) e quantidade livre (linha azul) de todas as competências compiladas.
- Risco de obsolescência: uma barra empilhada 100% por divisão mostrando como o estoque já recebido se divide por faixa de Aging (tons claros = recente, tons escuros = antigo). À direita, o % do estoque recebido com mais de 12 meses (faixas 12-18 meses, 18-24 meses, 2-5 anos e >5 anos) — quanto maior, maior o risco de perda de valor e de provisão. Futures (pedidos ainda não recebidos, sem idade) fica fora da barra e aparece abaixo do nome da divisão ("Futures: X% do valor"); o rodapé traz o total em R$ com mais de 12 meses. Substituiu o antigo "Variação por categoria", cuja informação agora está na linha do Division Description.
Ajuda dos gráficos: cada gráfico da Visão e relatórios tem um ícone "?" ao lado do título; ao clicar, abre um balão com uma explicação simples do que o gráfico mostra (fecha ao clicar fora ou com Esc). O ícone não aparece no HTML do Share Link nem no PDF.
Cores da página: os cards dos gráficos têm fundo azul-marinho bem claro; no Aging for Season as células vão do laranja claro ao laranja forte conforme o valor; os relatórios HTML (Share Link) e PDF (Optimus) saem com as mesmas cores.
Aging for Season: matriz de valor fiscal (Vlr Tot Fisc, o mesmo do card Valor fiscal) por ano da coleção (linhas: "Tudo que for antes de 2022": <2022, 2022 a 2027) e season (colunas FA, HO, SP, SU). A coluna Total soma cada ano (ex.: 2026 = só os produtos da coleção 2026), a linha Total soma cada season e o total geral (canto azul-marinho) é igual ao card Valor fiscal da competência. A comparação com o ano anterior não ocupa mais linhas na tabela: passe o mouse sobre um valor e o balão mostra a variação em % e o valor do ano anterior. No HTML e no PDF a tabela sai só com os valores e os totais.
- PMM analítico: PMM visualizado por Período, Division Description, Centro, Local de estoque ou Season (seletor "Visualizar por").
- Composição do custo fiscal: pizza 3D com FOB, Imposto de Importação (II) e Outros Custos.
- Dispersão do estoque livre: valor fiscal × quantidade livre; o tamanho do ponto representa o volume de registros; há seletor de dimensão. Não tem legenda: cada ponto traz o nome do grupo ao lado e as cores só ajudam a diferenciar os pontos (não representam categorias).

Animações: gráficos e cards animam só na primeira vez que aparecem depois que o sistema é carregado (abrir, F5, novo login). Ao ir para outra página e voltar, eles aparecem prontos, sem repetir a animação. Podem ser desligadas em Configurações > Interface e experiência.

Share Link (administradores): gera um relatório HTML autônomo da competência (Relatorio_Estoque_Contabil_AAAA-MM.html) para compartilhar com quem não usa o sistema.

Mapa mental (todos os perfis): o botão "Mapa mental", à esquerda de Filtros, abre um pop-up escuro, em tela cheia, com os insights da competência em forma de mapa mental (como no NotebookLM). No centro fica a esfera "Estoque Fisia" com o valor fiscal; dela saem 7 temas: Valor e giro, Aging e obsolescência, Divisões, Onde está o estoque, Coleções e seasons, Evolução e Composição do custo. Clicar numa esfera faz o ramo crescer para o próximo nível; clicar de novo recolhe. Detalhamentos: Onde está o estoque › cada local › os centros (lojas) daquele local, com valor, % do local, unidades e linhas (os 12 maiores e "Outros N centros", que também abre); Aging › Até 12 meses › faixas 1) a 4), Mais de 12 meses › faixas 5) a 8) e Por divisão; Divisões › cada divisão › variação vs mês anterior, estoque livre, PMM, mais de 12 meses e Aging da divisão (por faixa); Coleções e seasons › cada season › todos os anos; Evolução › Competências › valor, unidades e PMM de cada competência. Cores por tema: ciano (Valor e giro), laranja (Aging), azul (Divisões), verde (Onde está o estoque), amarelo (Coleções), branco (Evolução) e vermelho (Composição do custo). O painel à direita mostra o caminho, o número e o insight da esfera clicada. Botões: Expandir tudo, Recolher e Centralizar; arraste para mover, role o mouse para aproximar e Esc fecha. Todos os números vêm dos dados desta página (mesma competência e mesmos filtros) — nada é inventado. O botão e o pop-up não aparecem no HTML do Share Link nem no PDF.

Filtros da página (todos os perfis): o botão "Filtros", à esquerda do Share Link, abre um pop-up com os mesmos agrupadores do PMM analítico e da Dispersão: Division Description, Centro, Local de estoque e Season. Escolha a dimensão à esquerda, marque um ou mais valores (há busca e os botões Marcar visíveis/Desmarcar; cada valor mostra o valor fiscal e o número de linhas) e clique em "Aplicar filtros". Todos os cards e gráficos passam a mostrar só o que foi filtrado, inclusive a Evolução (o mesmo filtro em cada competência) e as comparações com a competência anterior. Valores marcados na mesma dimensão somam (ex.: Centro 2115 ou 2116); dimensões diferentes se combinam (ex.: Centro 2115 e Season SU). "Não informado" é o campo vazio. Os filtros ativos aparecem como etiquetas abaixo do título: o × remove aquele filtro e "Limpar filtros" remove todos. A Cobertura All Brazil continua sendo a da competência inteira. O Share Link e o PDF continuam saindo com a competência inteira. Não há filtro por data (a posição ZMM119 é uma foto do mês, sem data por linha).

Relatórios com os mesmos gráficos da tela: o HTML do Share Link e o PDF gerado pelo Optimus são uma cópia fiel desta página (cards de indicadores, Lifecycle × Aging em barras horizontais, matriz Aging for Season com setas, colunas por Division, barras de Local/Centro/Origem, Evolução com barras e linha, Variação por categoria, PMM analítico com Pareto, pizza 3D da Composição do custo fiscal e Dispersão do estoque livre), com os mesmos tipos de gráfico, cores e valores. O sistema abre a própria Visão e relatórios em segundo plano (Microsoft Edge invisível, na sessão de quem pediu), espera os gráficos ficarem prontos e salva o resultado. O HTML abre em qualquer navegador sem o sistema. O PDF sai em A4 paisagem, cerca de 4 páginas, sem cortar gráfico no meio. A geração leva de 30 a 40 segundos; o PDF fica guardado e só é refeito quando os dados ou o layout da página mudam. Se o Edge não estiver disponível, o sistema entrega a versão simplificada (barras e tabelas) para não deixar o pedido sem resposta. Não exige nenhuma alteração no fluxo do n8n.

A página se atualiza sozinha quando uma extração SAP, upload ou recebimento pelo Drive termina.

## Página Base de estoque
<!-- chaves: base de estoque, planilha online, base orig, grade, tabela, linhas, colunas, pesquisar, buscar, filtro, filtros, pendências de joins, baixar xlsx, exportar, excel, download, reprocessar joins, recarregar base, paginação, identificação, cálculos e enriquecimento -->
Título: "Base de Estoque — Planilha online". É a posição linha a linha da competência: a ZMM119 carregada por contrato posicional A:R mais os campos calculados e enriquecidos (MB59, último All Brazil válido do mês e Mapping). Mostra também o status da MB59 da competência.

Recursos:
- Busca geral: material, descrição, centro, NCM, aging e outros textos; botão Pesquisar.
- Linhas por página: 25, 50, 100 ou 200; botões Anterior/Próxima.
- Atalhos de grupos de colunas: Identificação, SAP ZMM119, Cálculos e enriquecimento.
- Filtros por coluna (linha de filtros no cabeçalho) e Limpar filtros.
- Somente pendências de joins: mostra só as linhas em que algum enriquecimento não foi encontrado (ex.: sem Division ou sem Product Offer End Date).
- Baixar XLSX: exporta a base da competência respeitando busca e filtros aplicados.
- Soma acima das colunas: a linha "Σ" entre os grupos e os nomes das colunas mostra a soma de Utilização livre, Bloqueado, Total, Vlr ICMS ST, Vlr IPI, Vlr Tot Emp, Vlr Tot Fisc, Vlr Total CC, FOB, II e Outros Custos. A soma é de TODAS as linhas que atendem à busca e aos filtros (não só da página exibida): sem filtro aparece "Σ TOTAL"; com filtro, "Σ FILTRO" em amarelo. Custos unitários, Days e Year não são somados.
- Reprocessar joins: reaplica All Brazil, PASSO A PASSO e Mapping sem reler a ZMM119 e sem executar o SAP.
- Recarregar base: relê o arquivo ZMM119 já salvo da competência e recompõe todos os cálculos e enriquecimentos.
Esses dois botões ficam disponíveis a quem tem acesso à página Base de estoque.

As colunas e fórmulas estão nas seções "Colunas da Base de Estoque" e "Regras de cálculo".

## Colunas da Base de Estoque
<!-- chaves: coluna, colunas, campo, campos, ce & mat, status operação, empresa, centro, material, texto breve, um básica, ncm, bloqueado, custo médio empresa, custo fiscal, total, icms st, ipi, tipo, vlr tot emp, vlr tot fisc, custo médio comercial, vlr total cc, ce unit, estilo-cor, estilo, custo fiscal unit, division description, material origin, product offer end dt, days, aging, lifecycle, local, fob, ii, outros custos, season, year, season/coleção -->
Vindas da ZMM119 (colunas A:R): Empresa, Centro, Material, Texto breve material, UM básica, NCM, Utilização livre, Bloqueado, Custo Médio Empresa, Custo Fiscal, Total, Vlr ICMS ST, Vlr IPI, Tipo, Vlr Tot Emp, Vlr Tot Fisc, Custo Médio Comercial, Vlr Total CC.

Calculadas pelo sistema: CE & MAT, CE UNIT, Estilo-Cor, Estilo, Custo Fiscal UNIT., Days, AGING, FOB, II, Outros Custos, Season/Coleção.

Pelo Mapping: STATUS OPERAÇÃO (por Centro), Local (por Centro), Lifecycle (pela Lifecycle Descrip.), AGING (faixa pelos Days).

Pelo All Brazil: Division Description, Material Origin Des., Lifecycle Descrip.

Pelo PASSO A PASSO (MB59 → posição anterior → All Brazil): Product Offer End Dt, Season, Year.

## Regras de cálculo
<!-- chaves: regra, regras, cálculo, cálculos, fórmula, fórmulas, como é calculado, pmm, ce unit, custo fiscal unit, aging, days, futures, faixa, fob, ii, imposto de importação, outros custos, 50%, 35%, 15%, estilo-cor, estilo, ce & mat, season/coleção, <2022, divisão por zero, cobertura -->
- CE & MAT = Centro + Material (chave oficial da MB59 e da posição anterior).
- CE UNIT = Vlr Tot Emp ÷ Utilização livre (vazio quando a utilização livre é zero).
- Custo Fiscal UNIT. = Vlr Tot Fisc ÷ Utilização livre (vazio quando zero).
- Estilo-Cor = 10 primeiros caracteres do Material. Estilo = 6 primeiros caracteres do Material.
- Days (aging) = data-base contábil − Product Offer End Dt. Sem Product Offer End Dt, Days e AGING ficam vazios.
- AGING: Days negativo = "0) Futures". Para os demais, a faixa do Mapping "Faixas de aging" cujo "Dias iniciais" é o maior valor menor ou igual a Days. Faixas padrão: 1) 0-3 meses (0), 2) 3-6 meses (105), 3) 6-9 meses (195), 4) 9-12 meses (285), 5) 12-18 meses (375), 6) 18-24 meses (555), 7) 2-5 anos (735), 8) >5 anos (1815). As faixas vigentes podem ser editadas no Mapping.
- FOB = 50%, II (imposto de importação) = 35% e Outros Custos = 15% do Vlr Tot Fisc.
- Season/Coleção = Season + Year (ex.: SU2025). Nas visões históricas, anos anteriores a 2022 viram "<2022".
- PMM = soma do Vlr Tot Fisc ÷ soma da Utilização livre, sempre por agregado (nunca média de preços unitários).
- Cobertura All Brazil = % das linhas com Division Description preenchida.
- A data-base contábil padrão é o último dia da competência.

## Fontes de dados
<!-- chaves: fonte, fontes, bases, bases utilizadas, quais bases, zmm119, mb59, base gr, all brazil, origem dos dados, de onde vem, empresa 7170, 8000, drive @all brazil materials, landing, onde ficam os arquivos, banco de dados -->
- ZMM119 (SAP): posição de estoque. Somente a Empresa 7170 é considerada; linhas de outras empresas (ex.: 8000) são descartadas na importação. Layout posicional fixo A:R: se o SAP mudar a ordem das colunas, a carga é bloqueada.
- MB59 / BASE GR (SAP): movimentos de material da competência (variante BASE GR). Fornece Product Offer End Date, Season e Year por CE & MAT. Colunas reconhecidas por nome e sinônimos.
- All Brazil: cadastro mestre de materiais no drive compartilhado "@All Brazil Materials", organizado em pastas de ano e mês ("AAAA\MM. Mês"), arquivos ALL_BRAZIL_DD_MM.xlsx, aba Data. Fornece Division Description, Material Origin, Lifecycle Descrip. e, como última opção, Product Offer End Date/Season/Year.
- Mapping: regras auxiliares editáveis (faixas de aging, planta e local, lifecycle, status da operação).
Arquivos SAP ficam em %LOCALAPPDATA%\OpsContabil\landing\zmm119\AAAA-MM e ...\landing\mb59\AAAA-MM. O banco fica em %LOCALAPPDATA%\OpsContabil\processed\ops_contabil.duckdb.

## Relacionamento com o All Brazil
<!-- chaves: all brazil, join, relacionamento, cruzamento, material nbr, estilo-cor, fallback, snapshot, data-base, último arquivo, cobertura, chaves repetidas, conflitos, division, material origin, lifecycle -->
- Arquivo usado: somente o snapshot mais recente da pasta do mês da competência cuja data seja menor ou igual à data-base. Arquivos anteriores do mesmo mês não são usados como alternativa, e a data do snapshot não pode ser de outro mês.
- Chave: somente Material, nunca Centro. Primeiro o Material completo = Material Nbr; se o SKU completo não existir no cadastro, usa o Estilo-Cor (10 primeiros caracteres) = Material Nbr.
- Controles: cobertura (% casado), chaves repetidas no cadastro e conflitos (chaves repetidas com valores diferentes nos campos usados). Repetições sem divergência não afetam o resultado.
- Onde ver: Controles e auditoria > Fonte All Brazil selecionada; Bases All Brazil para a biblioteca de arquivos.

## PASSO A PASSO (Product Offer End Date, Season e Year)
<!-- chaves: passo a passo, product offer end date, product offer end dt, season, year, prioridade, mb59, posição anterior, mês anterior, não localizado, pendência, enriquecimento -->
Para cada linha, cada campo (Product Offer End Date, Season, Year) é buscado nesta ordem, parando na primeira fonte que tiver valor:
1. MB59 (Base GR) da própria competência, por CE & MAT.
2. Posição de Estoque do mês anterior, por CE & MAT.
3. All Brazil, por Material (sem Centro).
Se nenhuma fonte tiver o valor, o campo fica vazio e a linha aparece em "Somente pendências de joins". O sistema nunca inventa o valor. Por isso a MB59 deve ser carregada antes (ou junto) da ZMM119.

## Página Extrações SAP
<!-- chaves: extrações sap, extração, extrair, sap, sap gui, robô, executar, rodar, zmm119, mb59, competência, data-base contábil, conexão sap, sso, prd, p_fisia, fisia, variante, base gr, data inicial, data final, execuções atuais, cancelar, status, pasta, landing, ordem -->
Título: "Central de extrações SAP" (somente administradores executam). O sistema localiza o SAP GUI, abre a conexão produtiva/SSO desta máquina e conduz a exportação sozinho.

ZMM119 — posição de estoque. Parâmetros: Competência; Data-base contábil (padrão: último dia da competência); Conexão SAP (opcional; vazio = escolha automática de PRD/SSO); "Marcar parâmetro P_FISIA" (marcado por padrão). Botão Executar ZMM119. Saída em %LOCALAPPDATA%\OpsContabil\landing\zmm119\AAAA-MM.

MB59 — movimentos de material. Parâmetros: Variante SAP (padrão BASE GR); Data inicial e Data final (padrão: primeiro e último dia da competência). Botão Executar MB59. Saída em ...\landing\mb59\AAAA-MM.

Ordem recomendada: MB59 primeiro, depois ZMM119 (a MB59 alimenta o PASSO A PASSO).

Ao terminar, o sistema importa o arquivo, aplica All Brazil, PASSO A PASSO e Mapping, atualiza as páginas e envia a competência ao Drive compartilhado. Exportações grandes podem demorar: enquanto o SAP mostra progresso de download, o robô continua aguardando.

Execuções atuais: mostra o andamento e o resultado de cada execução; botões "Cancelar ativas" e "Atualizar status".

O Optimus também pode iniciar a extração pelo chat, sempre com resumo e confirmação explícita do usuário.

## Upload manual de planilha SAP (contingência)
<!-- chaves: upload, carregar planilha, contingência, xlsx, arquivo, manual, exportei, falhou, extração falhou, planilha errada, validação, guardrail, substituir base -->
Se a extração automática falhar, o administrador exporta a transação manualmente no SAP em XLSX e envia em Extrações SAP > "Contingência: carregar planilha exportada do SAP" (há um para ZMM119 e outro para MB59): Selecionar arquivo .xlsx > Carregar planilha.
- ZMM119: usa a competência e a data-base preenchidas acima; valida o layout A:R e exige pelo menos uma linha da empresa 7170.
- MB59: usa a competência preenchida; valida o cabeçalho da Base GR e exige lançamentos dentro da competência.
- Se a planilha for de outra transação (ex.: MB59 enviada no campo da ZMM119) ou não for do SAP, o sistema recusa e explica o motivo; a base atual não é alterada. O arquivo anterior é preservado até a nova carga ser validada.
Depois do upload o processamento é o mesmo da extração automática.

## Página Bases All Brazil
<!-- chaves: bases all brazil, all brazil, biblioteca, biblioteca mensal, pastas, snapshot, drive, atualizar pastas, arquivos, cadastro mestre -->
Mostra, organizada por ano e mês, a biblioteca de arquivos do cadastro mestre All Brazil encontrada no drive "@All Brazil Materials" desta máquina. A lista é dinâmica: anos e meses vêm das pastas reais do Drive ("AAAA" e "MM. Mês"), então um mês novo criado no Drive (ex.: 10. Outubro) aparece sozinho, sem cadastro. O botão "Abrir no Drive" abre a pasta do mês quando o link dela já é conhecido; num mês novo, abre a pasta principal @All Brazil Materials. Botão "Atualizar pastas" relê o Drive. Observação: a competência só aparece em Visão e relatórios depois da extração ZMM119/MB59 daquele mês (fechamento); a All Brazil do mês é usada no enriquecimento. Serve para conferir quais snapshots existem e qual será usado em cada competência (o mais recente do mês até a data-base). Se o Drive não estiver sincronizado, a página e o Health Center avisam.

## Página Mapping
<!-- chaves: mapping, regras auxiliares, mapeamento, faixas de aging, planta e local, local, lifecycle, status da operação, status operação, baixados, ativo, editar, incluir, excluir, recalcular -->
Título: "Mapping — regras auxiliares" (edição por administradores). Grupos:
- Faixas de aging (Dias iniciais, Faixa AGING, Meses de referência).
- Planta e local (Planta, Local anterior, Local atual): define o Local de cada Centro.
- Lifecycle (Lifecycle Descrip. → Lifecycle; padrão Active = F1, Inactive = F4).
- Status da operação (Planta → STATUS OPERAÇÃO, ex.: ATIVO ou BAIXADOS).
Cada inclusão, alteração ou exclusão recalcula todas as competências compiladas; as colunas vindas do SAP, MB59 e All Brazil não são alteradas. As competências recalculadas são enviadas ao Drive para as outras máquinas.
Mapping compartilhado: as regras valem para todos os usuários do sistema. Uma loja ou centro cadastrado (ou alterado/excluído) numa máquina aparece na página Mapping das outras em até 2 minutos (ou no próximo login), pela pasta Estoque_Cont\mapping do Drive, e as competências locais são recalculadas com a regra nova. Para a mesma regra vale a alteração mais recente; regra excluída ou renomeada não volta. O selo no topo da página mostra "N regras ativas · compartilhado · data/hora" (amarelo se houver erro ou envio pendente). Cada máquina precisa ter a versão do sistema com esse recurso instalada para enviar e receber as regras.

## Página Controles e auditoria
<!-- chaves: controles e auditoria, governança, auditoria, controle, controles automáticos, contrato de colunas, campos obrigatórios, consistência all brazil, competência e data-base, estrutura reconhecida, estado operacional, rastreabilidade -->
Contrato de dados e rastreabilidade da competência:
- Controles automáticos: Ordem e contrato de colunas (ZMM119 posicional A:R; MB59 e All Brazil por nomes e sinônimos), Campos obrigatórios (ausência bloqueia a importação antes de alterar a competência), Consistência All Brazil (chaves repetidas e conflitos), Competência e data-base (snapshot do mês e não posterior à data-base).
- Fonte All Brazil selecionada: data do snapshot, arquivo, cobertura, chaves repetidas e conflitos.
- Estrutura reconhecida: Posição de Estoque, MB59_BASE GR e All Brazil com a quantidade de campos reconhecidos.
- Estado operacional: extração SAP (exclusiva de administradores), regras de dados ativas e configuração do Optimus.

## Página Health Center
<!-- chaves: health center, saúde, diagnóstico, semáforo, status, erro, problema, não funciona, vpn, rede, n8n, google drive, google slides, duckdb, fontes, permissões, drive compartilhado, sincronização, backup programado, suporte, pontuação -->
Diagnóstico real e independente de cada componente, com semáforo (saudável, atenção, crítico), pontuação geral, detalhe e "como resolver". Indicadores:
- SAP GUI: instalação local e última execução.
- VPN / rede: túnel VPN e acesso à rede corporativa.
- n8n / Optimus: webhook do agente.
- Google Drive: pasta @All Brazil Materials sincronizada.
- Google Slides: template e rota das apresentações do Optimus.
- DuckDB: banco local acessível e linhas da competência.
- Fontes: ZMM119, MB59 e All Brazil presentes na competência.
- Permissões: sessão, perfil e páginas liberadas.
- Drive compartilhado: pasta Estoque_Cont da ponte (conectado, somente leitura ou inacessível).
- Sincronização de competências: envios/recebimentos pelo Drive (em dia, envio pendente, erro, suspensa sem Drive).
- Backup programado (administradores): desativado, em dia, atrasado ou com falha.
- Controle de acessos: consulta à lista central de acessos (Estoque_Cont\acesso): em dia, ainda não verificada, sem verificação recente, envio pendente, erro na sincronização, prazo próximo ou bloqueado (7 dias sem verificação).
Suporte: transformacao_digital@gruposbf.com.br.

## Página Optimus
<!-- chaves: optimus, agente, chat, assistente, ia, perguntar, conversa, pdf, apresentação, slides, google slides, saudação, n8n, o que o optimus faz, importar planilha, planilha baixada, contingência, extração falhou, proativo, aviso automático, avisos do optimus, reprocessar joins, regra de mapping, cadastrar acesso, desativar acesso, backup agora, sincronizar ponte -->
"Optimus - Agente contábil": chat que consulta agregados e evidências das competências, sem permissão de contabilizar ou alterar dados. Precisa da página Optimus liberada no perfil.
O que faz: responde sobre dados, regras, fontes e uso do sistema; pesquisa linhas reais da base; consulta Mapping, MB59, All Brazil, execuções e status SAP; compara competências; gera o PDF da Visão e relatórios (com os mesmos gráficos da tela; leva de 30 a 40 segundos); prepara apresentação executiva no Google Slides; inicia extrações ZMM119/MB59 somente após resumo e confirmação explícita; e importa, pelo modo de contingência, planilhas ZMM119/MB59 já baixadas do SAP.
Importar planilha já baixada (administradores): peça, por exemplo, "importe a ZMM119 que baixei". O Optimus procura as planilhas .xlsx salvas nos últimos 45 dias em Downloads, Área de Trabalho, Documentos e pastas TEMP (as mesmas que o robô do SAP usa), reconhece pelo cabeçalho se cada uma é ZMM119 ou MB59, mostra a lista e prepara um resumo (arquivo, tamanho, data, competência e data-base). Nada é importado antes do seu "sim"; a carga usa exatamente o mesmo processo do upload contingencial da página Extrações SAP (validação completa, substituição da base da competência) e aparece em Execuções atuais. O arquivo original não é movido nem apagado. Se a planilha mudar depois do resumo, a importação é recusada.
Optimus proativo na falha de extração: se uma extração ZMM119/MB59 falhar, o sistema procura sozinho a planilha que o SAP chegou a salvar depois do início da extração (inclusive no destino oficial) e o Optimus escreve no chat oferecendo importá-la; a notificação do Windows da falha passa a abrir o Optimus. Basta responder "sim" para importar ou "não" para deixar como está. Se nenhuma planilha foi salva, ele orienta a exportar manualmente e pedir a importação.
Optimus proativo (avisos automáticos): enquanto um administrador está com o sistema aberto, o Optimus verifica a situação na hora depois de cada carga, extração, upload ou alteração de Mapping e, além disso, a cada 5 minutos (VPN e conexão do agente a cada 2 minutos), e avisa no chat (com notificação do Windows se você estiver em outra página ou janela). O sistema só detecta os fatos (consultas exatas ao banco, ao Drive e ao Health Center); quem escreve a mensagem, explica o impacto e orienta a correção é o próprio agente Optimus, consultando o manual e a Documentação técnica. Avisos atuais:
- All Brazil mais nova no Drive do que a usada na Base de Estoque da competência mais recente (oferece reprocessar os joins);
- centros sem regra no Mapping (Planta e local ou Status da operação), como o 2115 que aparece como "Não informado" (pede o local e o status e prepara a regra);
- linhas da Base de Estoque sem preenchimento (Division, Origem, Lifecycle, Season, Year, Product Offer End Dt, AGING), com a causa provável;
- indicadores do Health Center em atenção ou crítico, com o "como corrigir" e onde saber mais na Documentação;
- fechamento: o mês virou e a competência do mês anterior ainda não foi compilada;
- qualidade da All Brazil (cobertura abaixo de 100% ou chaves em conflito);
- variações relevantes contra a competência anterior (valor fiscal total ±10%, por divisão ±15%, ou aumento de 2 pontos no estoque com mais de 12 meses);
- extração SAP rodando há mais de 40 minutos;
- nova competência disponível e nova versão da Documentação (estes dois só avisam quando mudam).
Cada aviso é enviado uma vez e só volta se a situação mudar (ou se o problema for resolvido e reaparecer). Para não poluir o chat, chega no máximo um aviso do Optimus por minuto (a oferta de importar a planilha depois de uma extração com falha não espera). Usuários comuns não recebem avisos proativos, e quem não está com o sistema aberto também não.
VPN desligada ou Optimus sem conexão: sem a VPN o n8n recusa o acesso (HTTP 403) e o agente não consegue escrever. Por isso, nesse caso, quem avisa é o próprio sistema, em até 2 minutos: notificação do Windows "Optimus sem conexão · VPN / rede: Não detectada" (abre o Health Center; categoria "VPN e conexão do Optimus" em Configurações > Notificações) e um quadro laranja "Aviso do sistema · Health Center" no chat com o diagnóstico e o "como resolver" do próprio Health Center. O status do chat mostra "Sem conexão (VPN / n8n)". O aviso não se repete enquanto a conexão continuar fora; os avisos do Optimus que surgirem nesse tempo ficam guardados. Quando a conexão volta, o Optimus escreve primeiro que ela voltou, quanto tempo ficou fora e a causa, e em seguida entrega os avisos guardados. Se a VPN cair mas o n8n continuar acessível, o próprio Optimus escreve o aviso (extrações SAP dependem da VPN).
Responder a um aviso específico: cada aviso proativo tem o botão "↩ Responder a este aviso". Ao clicar, aparece acima da caixa de texto "Respondendo a: <título do aviso>" (o × cancela); a sua mensagem fica vinculada àquele aviso e, se ele tiver uma ação, ela volta a ser a decisão pendente — mesmo que outros avisos tenham chegado depois. Aviso já confirmado ou recusado não volta a ficar pendente. Sem o botão, basta dizer a qual aviso você se refere (ex.: "sobre o All Brazil: sim").
Mensagens não lidas: quando chega mensagem do Optimus e você não está olhando o chat, o ícone do Optimus no menu lateral mostra um contador vermelho (com o menu expandido ou recolhido). Ao abrir o Optimus, o contador zera e as notificações do Optimus no sino ficam como lidas.
Ações que o Optimus pode fazer (sempre com resumo e só depois do seu "sim"; administradores): reprocessar os joins de uma competência, incluir ou alterar regra de Mapping (com recálculo de todas as competências), sincronizar a ponte do Drive, fazer backup agora, ativar ou desativar o backup programado e escolher a frequência (sem trocar a pasta), cadastrar ou alterar acesso (perfil e páginas) e desativar acesso. Qualquer perfil pode pedir para ajustar as próprias preferências de notificação e de Interface e experiência deste computador. Ficam fora do Optimus, de propósito: excluir competência, excluir usuário, restaurar backup, trocar a pasta do Drive e o instalador — o Optimus orienta o caminho em Configurações.
Consultas que o Optimus faz para orientar: Health Center completo, lacunas da Base de Estoque, centros sem regra no Mapping, visão de Configurações (acessos, competências, ponte, backup, notificações) e busca na Documentação técnica (seção e página).
Ao abrir, cumprimenta o usuário pelo primeiro nome com uma frase digitada em ritmo humano. A conversa das últimas 8 horas fica guardada no navegador: ao voltar ao chat ou abrir o sistema em outra aba, a mesma conversa aparece (sem nova saudação). Sempre que a página Optimus é aberta, o chat já aparece rolado até a última mensagem.
Enquanto o Optimus analisa uma pergunta, o item Optimus do menu lateral mostra três pontinhos animados (só com o menu expandido), mesmo que o usuário esteja em outra página.
Se o Optimus não conseguir responder (limite de interações com ferramentas locais, n8n indisponível, tempo esgotado etc.), além da mensagem no chat é enviada uma notificação do Windows "Optimus não conseguiu responder", mesmo com a janela do chat fechada.

## Página Documentação
<!-- chaves: documentação, documento, especificação, especificação técnico-documental, técnico-documental, pdf da documentação, manual técnico, localizar no documento, buscar no documento, palavra-chave, sumário, baixar pdf -->
Fica no menu em ADMINISTRAÇÃO. Mostra a Especificação Técnico-Documental do Estoque Contábil em PDF (arquitetura, páginas, parâmetros, dados, integrações, segurança, instalação e operação).
- Localizar no documento: digite palavras-chave e clique em Localizar. A busca ignora acentos e maiúsculas, exige que todas as palavras estejam na mesma página e aceita frase exata entre aspas (ex.: "ponte de dados"). Os resultados mostram a página, a seção, a quantidade de ocorrências e trechos com os termos destacados; clicar abre o PDF na página.
- Sumário: lista os capítulos com a página; clicar leva direto ao trecho.
- Botões: Abrir em nova aba e Baixar PDF.
- Atualização: o documento é mantido pela equipe do sistema; cada nova versão chega às máquinas pela ponte do Drive (sem reinstalar) e também pelo instalador. O topo mostra a versão documental e a data da última atualização.
- Acesso: obrigatória para todos os perfis (administradores e usuários).

## Página Configurações
<!-- chaves: configurações, configuração, preferências, interface e experiência, densidade, linhas por página, animações, animação dos gráficos, animação dos cards, salvar configurações, competências compiladas, excluir competência, apagar competência, acesso corporativo -->
Todos os perfis acessam Configurações, mas o perfil Usuário vê apenas Interface e experiência e Notificações (preferências do próprio computador, salvas com "Salvar configurações" e, nas notificações, na hora). As demais seções são exclusivas de administradores. Seções:
- Interface e experiência: Densidade (Compacta/Confortável), Linhas por página (25/50/100/200), Ativar animações da interface, Ativar animação dos gráficos, Ativar animação dos cards. Botão "Salvar configurações".
- Notificações: notificações do Windows por categoria (Extrações SAP, Uploads e cargas, Respostas do Optimus, Atualizações pelo Drive, Backup e restauração, VPN e conexão do Optimus) e som; salvas na hora (ver "Notificações do Windows").
- Instalador do Estoque Contábil (ver "Instalador").
- Competências compiladas: lista as competências (linhas, quantidade, valor fiscal) e permite excluir uma competência carregada incorretamente, digitando a competência para confirmar. Antes de excluir é criado um backup recuperável. A exclusão vale só para esta máquina; a ponte não traz de volta a mesma versão excluída.
- Ponte de dados — Drive compartilhado; Backup programado; Restaurar a partir de um backup (seções próprias).
- Acesso corporativo: e-mail, perfil (Usuário/Administrador) e páginas liberadas; Salvar acesso; desativar ou excluir acessos. A lista mostra todos os logins do sistema, inclusive os cadastrados por outros administradores, com quem fez a última alteração e quando. Quando a pessoa já entrou neste computador, aparece "Último acesso neste computador: data e hora" (cada um entra pelo próprio computador e os acessos não são compartilhados entre máquinas; se nunca entrou aqui, nada é mostrado); acima dela aparece a situação da lista central de acessos (última sincronização, máquinas de administrador publicando, envios pendentes e erros).

## Notificações do Windows
<!-- chaves: notificação, notificações, notificar, aviso, avisos, alerta, sino, toast, central de notificações, som, desativar notificações, ativar notificações, notificação de teste, não recebo notificação -->
O sistema envia somente notificações nativas do Windows (as mesmas do Teams e do Outlook), com o nome e o ícone "Estoque Contábil". Elas saem do próprio sistema instalado no computador, então chegam mesmo com o navegador fechado ou minimizado, e ficam na Central de Notificações do Windows.
Ao clicar: se o sistema já estiver aberto no navegador (Chrome ou Edge), a MESMA aba vem para frente e vai direto para a página da notificação (por exemplo, o chat do Optimus com a conversa em andamento); só abre o sistema quando ele não estiver aberto (e, se o servidor estiver parado, aciona o mesmo inicializador do atalho da área de trabalho). A notificação clicada fica marcada como lida.
Quando avisa:
- Extrações SAP: início (silencioso), conclusão com a base carregada, falha, ação necessária ou cancelamento da ZMM119/MB59.
- Uploads e cargas da base: planilha carregada por upload (concluída ou com falha), recarga da Base de Estoque e reprocessamento de joins. Uma planilha da transação errada é recusada na hora, na tela, sem notificação.
- Respostas do Optimus: quando o Optimus responde e o usuário está em outra janela, com a aba minimizada ou em outra página do sistema (olhando o chat, não notifica); e sempre que o Optimus não conseguir responder (erro).
- Atualizações recebidas pelo Drive: competências novas ou atualizadas por outra máquina.
- Backup e restauração: backup programado concluído ou com falha e restauração concluída.
- VPN e conexão do Optimus: a VPN ou o n8n caiu e o Optimus ficou sem conexão (só administradores com o sistema aberto; o clique abre o Health Center).
Sino no topo da tela (qualquer perfil): caixa com as notificações já enviadas (até 200), com o número das não lidas em vermelho; clicar num aviso abre a página da tarefa e o marca como lido; há "Marcar todas como lidas", "Limpar histórico" e o link "Preferências". O contador atualiza na hora.
Preferências: em Configurações > Notificações (ou pelo link Preferências do sino): interruptor geral, um por categoria e o som; salvas na hora e válidas para aquele computador. "Enviar notificação de teste" confirma que o Windows está exibindo os avisos.
Se não aparecer nada: confira o modo Não incomodar/Assistente de foco e Configurações do Windows > Sistema > Notificações > Estoque Contábil.

## Ponte de dados (Drive compartilhado Estoque_Cont)
<!-- chaves: ponte, ponte de dados, drive compartilhado, estoque_cont, sincronizar, sincronização, enviar competências, receber, recebe, recebem, base atualizada, dados atualizados, atualização entre máquinas, outro usuário, outros usuários, outra máquina, mesmos dados, reinstalar, contingência, alterar pasta, selecionar pasta, pasta compartilhada -->
Serve só como meio de transporte entre máquinas; não controla os dados e nunca apaga nada de uma máquina.
- Envio: toda atualização local concluída (extração SAP, upload, recarga, reprocessamento, Mapping) publica a competência em Estoque_Cont\periodos\AAAA-MM.
- Recebimento: as outras máquinas verificam o Drive a cada ~2 minutos e aplicam somente versões mais novas e completas; a tela se atualiza sozinha. Não é preciso reinstalar.
- Se duas máquinas atualizarem a mesma competência, prevalece a atualização mais recente.
- Tabela em Configurações: Competência, Nesta máquina, No Drive, Situação (Sincronizada, Aguardando envio ao Drive, Disponível no Drive (será recebida), Mais recente no Drive, Mais recente nesta máquina, Somente nesta máquina).
- Botões: "Sincronizar agora" e "Enviar competências desta máquina".
- Contingência: "Selecionar pasta…" (janela do Windows) > "Validar e usar esta pasta"; opção de deixar aviso na pasta anterior para as outras máquinas seguirem a nova; "Voltar à detecção automática".
- Recomenda-se que só administradores tenham permissão de edição na pasta Estoque_Cont.
- A subpasta acesso guarda a lista central de acessos (um arquivo por máquina de administrador em acesso\alteracoes); ver "Perfis de acesso e permissões".

## Backup programado
<!-- chaves: backup, cópia de segurança, backup programado, frequência, diária, semanal, mensal, retenção, substitui, sobrescreve, espaço em disco, cópia anterior, pasta de backup, fazer backup agora, usar automática, perda de dados -->
Cópia completa do banco desta máquina em .zip (ops_contabil_backup_AAAAMMDD_HHMMSS_<COMPUTADOR>.zip).
- Ativar backup programado; Frequência (Diária, Semanal, Mensal).
- Cada novo backup SUBSTITUI o anterior: o novo é gravado e conferido (zip íntegro e banco completo) e só então os backups anteriores deste computador naquela pasta são apagados. Se a gravação ou a conferência falhar, o backup anterior continua intacto. Assim a pasta guarda sempre um único backup por computador e não enche o disco. Backups de outros computadores na mesma pasta nunca são apagados.
- Pasta de backup: "Selecionar pasta…" abre a janela do Windows; "Usar automática" = Estoque_Cont\backups\<nome do computador> (ou %LOCALAPPDATA%\OpsContabil\backup sem Drive). Clique em "Salvar configurações" para aplicar.
- Além do destino, uma cópia do backup mais recente fica também em %LOCALAPPDATA%\OpsContabil\backup (também substituída a cada backup), para não se perder junto com o Drive.
- "Fazer backup agora" gera um backup imediato. As configurações valem por computador.

## Restaurar a partir de um backup
<!-- chaves: restaurar, restauração, recuperar, recuperação, backup, perdi os dados, banco danificado, banco corrompido, voltar backup, desastre, drive perdido, zip -->
Configurações > Restaurar a partir de um backup (administradores):
1. "Procurar backups" lista os backups da pasta configurada, deste computador e da pasta backups do Drive; ou "Escolher arquivo .zip…" pela janela do Windows.
2. "Conferir": o sistema abre o backup sem alterar nada e mostra, por competência, o que há no backup e nesta máquina, com o resultado (Volta ao estado do backup, Será incluída, Não está no backup: sai desta máquina).
3. Digitar RESTAURAR e clicar em "Restaurar este backup". Os dados voltam do backup; acessos e configurações da máquina são mantidos; o banco anterior fica guardado como cópia (ops_contabil.antes-da-restauracao-...).
4. Depois, a máquina recebe do Drive o que houver de mais recente e reenvia ao Drive o que ele não tiver; um backup antigo nunca sobrescreve dado mais novo no Drive.
Se só a pasta do Drive se perder, não é preciso restaurar: escolha uma nova pasta na contingência e use "Enviar competências desta máquina".

## Instalador e novos usuários
<!-- chaves: instalador, instalar, instalação, novo usuário, primeiro acesso, baixar pacote, zip, atualizar máquina, versão, reinstalar, atalho -->
Configurações > Instalador do Estoque Contábil (administradores): "Baixar pacote ZIP" (INSTALAR_ESTOQUE_CONTABIL.zip, com INSTALAR_ESTOQUE_CONTABIL.bat) e a versão publicada. Envie ao novo usuário: ele extrai e executa o .bat; o sistema é instalado em %LOCALAPPDATA%\OpsContabil com atalho na área de trabalho e já vem com as competências da versão. Reinstalar numa máquina já preparada atualiza o programa e só substitui competências novas ou mais recentes, sem apagar dados locais. O acesso do usuário precisa ser liberado em Acesso corporativo. Atualizações de dados posteriores chegam pela ponte do Drive, sem reinstalar.

## Perguntas frequentes e solução de problemas
<!-- chaves: dúvida, problema, erro, não carrega, não atualiza, competência não aparece, dados diferentes, outra máquina, extração demorada, sap travou, página em branco, optimus não responde, como faço, onde fica -->
- Competência não aparece no seletor: ainda não foi carregada nesta máquina; se foi carregada em outra, aguarde a ponte (ou Configurações > Sincronizar agora) e veja o Health Center > Sincronização.
- Dados diferentes entre máquinas: verifique a tabela da Ponte de dados; a mais recente prevalece.
- Extração SAP falhou ou demorou demais: veja Extrações SAP > Execuções atuais e o Health Center (SAP GUI, VPN); use o upload manual como contingência.
- Linhas sem Division/Season/Product Offer End Date: filtre "Somente pendências de joins"; confira MB59 da competência, o snapshot All Brazil e use "Reprocessar joins".
- Optimus não responde: Health Center > n8n / Optimus e VPN / rede.
- Página não aparece no menu: permissão do perfil (Configurações > Acesso corporativo).
- Suporte: transformacao_digital@gruposbf.com.br.
