/****************************************************
 * SMARTSLIP - API para Google AI Studio / Gemini
 * 
 * Funções:
 * - consultar_info_loja
 * - salvar_dados_comprovante_planilha
 *
 ****************************************************/

const SMARTSLIP_TOKEN_PROPERTY = "SMARTSLIP_TOKEN";

// Planilha antiga onde está a aba Info_limites.
// ATENÇÃO: coloque aqui o ID exato da planilha Base_Legada/Info_limites.
const SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID = PropertiesService.getScriptProperties().getProperty("SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID") || "";

// Nova planilha SmartSlip, onde ficam BASE_SMARTSLIP e SMARTSLIP_FILA.
const SMARTSLIP_DB_SPREADSHEET_ID = PropertiesService.getScriptProperties().getProperty("SMARTSLIP_DB_SPREADSHEET_ID") || "";
const SMARTSLIP_BASE_LOJAS_SPREADSHEET_ID = SMARTSLIP_DB_SPREADSHEET_ID;
const SMARTSLIP_ABA_BASE_LOJAS = "BASE_LOJAS";

const SMARTSLIP_ABA_INFO_LIMITES = "Info_limites";
const SMARTSLIP_ABA_DESTINO = "BASE_SMARTSLIP";
const SMARTSLIP_ABA_FILA = "SMARTSLIP_FILA";
const SMARTSLIP_ABA_VEKTOR_EMAILS = "VEKTOR_EMAILS";
const SMARTSLIP_VEKTOR_EMAILS_SPREADSHEET_ID = SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID;
const SMARTSLIP_ABA_USUARIOS = "SMARTSLIP_USUARIOS";
const SMARTSLIP_ABA_PESQUISA_SATISFACAO = "SMARTSLIP_PESQUISA_SATISFACAO";
const SMARTSLIP_ABA_PESQUISA_CICLOS = "SMARTSLIP_PESQUISA_CICLOS";
const SMARTSLIP_PESQUISA_PRIMEIRO_CICLO = "2026-09-21";
const SMARTSLIP_PESQUISA_INTERVALO_MESES = 3;
const SMARTSLIP_PESQUISA_MIN_RESPOSTA_EXECUTIVO_PCT = 80;
const SMARTSLIP_PESQUISA_TIMEZONE = "America/Sao_Paulo";

const SMARTSLIP_PESQUISA_TESTE_ADM_ATIVO = false;
const SMARTSLIP_PESQUISA_TESTE_ADM_EMAIL = "admin@empresa.com.br";

const SMARTSLIP_COOLDOWN_ENVIO_SEGUNDOS = 10;
const SMARTSLIP_TOLERANCIA_TOTAL_IA = 5.00;
const SMARTSLIP_DOMINIOS_CORPORATIVOS = [
  "empresa.com.br", 
  "empresa-a.com.br", 
  "empresa-b.com.br"
];
const SMARTSLIP_ABA_CUSTOS_IA = "SMARTSLIP_CUSTOS_IA";
const SMARTSLIP_ABA_LOG_EXCLUSOES = "SMARTSLIP_LOG_EXCLUSOES";
const SMARTSLIP_STATUS_EXCLUIDO = "EXCLUIDO";
const SMARTSLIP_EMAIL_VEKTOR = "operacao@empresa.com.br";
const SMARTSLIP_EMAIL_ALERTA_INATIVIDADE_CC = "alertas@empresa.com.br";
const SMARTSLIP_ALERTA_INATIVIDADE_HANDLER = "smartSlipExecutarAlertasInatividadeDiarios";
const SMARTSLIP_ALERTA_INATIVIDADE_PREFIXO_PROP = "SMARTSLIP_ALERTA_INATIVIDADE_ENVIADO_";
const SMARTSLIP_INATIVIDADE_PROP_BOLETO = "SMARTSLIP_INATIVIDADE_DIAS_BOLETO";
const SMARTSLIP_INATIVIDADE_PROP_DEP_BANCARIO = "SMARTSLIP_INATIVIDADE_DIAS_DEP_BANCARIO";
const SMARTSLIP_INATIVIDADE_PROP_CARRO_FORTE = "SMARTSLIP_INATIVIDADE_DIAS_CARRO_FORTE";
const SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_POR = "SMARTSLIP_INATIVIDADE_ATUALIZADO_POR";
const SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_EM = "SMARTSLIP_INATIVIDADE_ATUALIZADO_EM";
const SMARTSLIP_INATIVIDADE_PADRAO_BOLETO = 4;
const SMARTSLIP_INATIVIDADE_PADRAO_DEP_BANCARIO = 4;
const SMARTSLIP_INATIVIDADE_PADRAO_CARRO_FORTE = 8;
var SMARTSLIP_MEMO_CONFIG_INATIVIDADE_ = null;
const SMARTSLIP_URL_ACESSO = ScriptApp.getService().getUrl() || "";

function smartSlipGetUsuarioAtual() {
  const email = String(Session.getActiveUser().getEmail() || "").trim().toLowerCase();

  const primeiroNome = smartSlipExtrairPrimeiroNome(email);

  let lojaPadrao = "";
  let empresaPadrao = "";
  let tipoDeposito = "";
  let tipoDepositoOrigem = "";
  let time = "";
  let gerenteRegional = "";
  let emailRegional = "";

  let acessoUsuario = {
    role: "Usuário",
    is_admin: false,
    is_analista_pro: false,
    is_regional: false,
    can_comp_hub: false
  };

  try {
    acessoUsuario = smartSlipGetAcessoUsuario(email);
  } catch (errAcesso) {
    Logger.log("Erro ao verificar acesso do usuário: " + String(errAcesso && errAcesso.message ? errAcesso.message : errAcesso));
  }

  try {
    const prefs = smartSlipObterPreferenciasUsuario(email);

    lojaPadrao = prefs.loja_padrao || "";
    empresaPadrao = prefs.empresa_padrao || "";
    tipoDeposito = prefs.tipo_deposito || "";
    tipoDepositoOrigem = prefs.tipo_deposito_origem || "";
    time = prefs.time || "";
    gerenteRegional = prefs.gerente_regional || "";
    emailRegional = prefs.email_regional || "";

    /*
      Regra:
      A loja padrão só pode vir da SMARTSLIP_USUARIOS,
      gravada após o usuário selecionar e salvar em Configurações.

      Não buscar loja automaticamente por histórico/fila.
      Isso evita que, no primeiro acesso, uma loja seja carregada sem confirmação do usuário.
    */

if (lojaPadrao) {

  const dadosBase =
    smartSlipConsultarDadosOperacionaisLoja_(
      lojaPadrao
    );

  if (dadosBase.ok) {

    /*
     * TIPO DE DEPÓSITO
     *
     * Se o usuário já possui um tipo salvo,
     * preserva o valor.
     *
     * Isso é importante porque o usuário
     * pode ter corrigido manualmente o tipo
     * nas Configurações.
     */
    if (!tipoDeposito) {
      tipoDeposito =
        dadosBase.tipo_deposito ||
        "";

      tipoDepositoOrigem =
        "BASE_LOJAS";
    }


    /*
     * DADOS REGIONAIS
     *
     * Sempre são atualizados pela
     * BASE_LOJAS.
     *
     * Assim, uma troca de Regional ou Time
     * passa a refletir imediatamente no
     * SmartSlip.
     */
    time =
      dadosBase.time ||
      "";

    gerenteRegional =
      dadosBase.gerente_regional ||
      "";

    emailRegional =
      dadosBase.email_regional ||
      "";
  }
}

  } catch (errLoja) {
    Logger.log("Erro ao obter loja padrão do usuário: " + String(errLoja && errLoja.message ? errLoja.message : errLoja));

    lojaPadrao = "";
    empresaPadrao = "";
    tipoDeposito = "";
    tipoDepositoOrigem = "";
    time = "";
    gerenteRegional = "";
    emailRegional = "";
  }

  return {
    email: email,
    primeiro_nome: primeiroNome,
    perfil: acessoUsuario.role || "Usuário",
    is_admin: acessoUsuario.is_admin === true,
    is_analista_pro: acessoUsuario.is_analista_pro === true,
    is_regional: acessoUsuario.is_regional === true,
    can_comp_hub: acessoUsuario.can_comp_hub === true,
    loja_padrao: lojaPadrao,
    empresa_padrao: empresaPadrao,
    tipo_deposito: tipoDeposito,
    tipo_deposito_origem: tipoDepositoOrigem,
    time: time,
    gerente_regional: gerenteRegional,
    email_regional: emailRegional
  };
}

function smartSlipExtrairPrimeiroNome(email) {
  if (!email) return "Usuário";

  const parte = String(email).split("@")[0] || "";
  const primeiro = parte.split(/[._-]/)[0] || "Usuário";

  return primeiro.charAt(0).toUpperCase() + primeiro.slice(1).toLowerCase();
}

function smartSlipNormalizarPerfilSmartSlip(valor) {
  return String(valor || "")
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function smartSlipGetAcessoUsuario(email) {
  try {
    email = String(email || "").trim().toLowerCase();

    const acessoPadrao = {
      role: "Usuário",
      role_norm: "USUARIO",
      is_admin: false,
      is_analista_pro: false,
      is_regional: false,
      can_comp_hub: false
    };

    if (!email) {
      return acessoPadrao;
    }

    const ss = SpreadsheetApp.openById(SMARTSLIP_VEKTOR_EMAILS_SPREADSHEET_ID);
    const sh = ss.getSheetByName(SMARTSLIP_ABA_VEKTOR_EMAILS);

    if (!sh) {
      Logger.log("SmartSlip Acesso: aba VEKTOR_EMAILS não encontrada.");
      return acessoPadrao;
    }

    const values = sh.getDataRange().getValues();

    if (values.length < 2) {
      return acessoPadrao;
    }

    const headers = values[0].map(function(h) {
      return String(h || "").trim();
    });

    const idxEmail = smartSlipEncontrarIndiceHeader_(headers, [
      "Email",
      "EMAIL",
      "E-mail",
      "E_MAIL"
    ]);

    const idxRole = smartSlipEncontrarIndiceHeader_(headers, [
      "ROLE",
      "Role",
      "Perfil",
      "PERFIL"
    ]);

    const idxAtivo = smartSlipEncontrarIndiceHeader_(headers, [
      "ATIVO",
      "Ativo",
      "Status",
      "STATUS"
    ]);

    if (idxEmail < 0 || idxRole < 0) {
      Logger.log("SmartSlip Acesso: colunas Email/ROLE não encontradas na VEKTOR_EMAILS.");
      Logger.log(JSON.stringify(headers));
      return acessoPadrao;
    }

    for (let i = 1; i < values.length; i++) {
      const row = values[i];

      const emailRow = String(row[idxEmail] || "").trim().toLowerCase();
      const roleRaw = String(row[idxRole] || "").trim();
      const roleNorm = smartSlipNormalizarPerfilSmartSlip(roleRaw);

      const ativoRaw = idxAtivo >= 0
        ? smartSlipNormalizarPerfilSmartSlip(row[idxAtivo])
        : "SIM";

      const estaAtivo = ![
        "NAO",
        "FALSE",
        "0",
        "INATIVO",
        "N"
      ].includes(ativoRaw);

      if (emailRow !== email || !estaAtivo) {
        continue;
      }

      const isAdmin =
        roleNorm.includes("ADMINISTRADOR") ||
        roleNorm.includes("ADMIN");

      const isAnalistaPro =
        roleNorm.includes("ANALISTA PRO") ||
        roleNorm.includes("ANALISTA_PRO") ||
        roleNorm.includes("ANALISTA-PRO") ||
        (roleNorm.includes("ANALISTA") && roleNorm.includes("PRO"));

      const isContasReceber =
        roleNorm.includes("CONTAS_RECEBER") ||
        roleNorm.includes("CONTAS RECEBER") ||
        roleNorm.includes("CONTAS-RECEBER");

      const isRegional =
        roleNorm.includes("GERENTES_REG") ||
        roleNorm.includes("GERENTES REG") ||
        roleNorm.includes("GERENTE_REG") ||
        roleNorm.includes("GERENTE REG") ||
        roleNorm.includes("REGIONAL");

      return {
        role: roleRaw || "Usuário",
        role_norm: roleNorm || "USUARIO",
        is_admin: isAdmin,
        is_analista_pro: isAnalistaPro,
        is_regional: isRegional,
        can_comp_hub: isAdmin || isAnalistaPro || isContasReceber
      };
    }

    return acessoPadrao;

  } catch (err) {
    Logger.log("Erro smartSlipGetAcessoUsuario: " + String(err && err.message ? err.message : err));

    return {
      role: "Usuário",
      role_norm: "USUARIO",
      is_admin: false,
      is_analista_pro: false,
      is_regional: false,
      can_comp_hub: false
    };
  }
}

function smartSlipUsuarioEhAdmin(email) {
  return smartSlipGetAcessoUsuario(email).is_admin === true;
}


function smartSlipGetToken() {
  const token = PropertiesService
    .getScriptProperties()
    .getProperty(SMARTSLIP_TOKEN_PROPERTY);

  if (!token) {
    throw new Error("SMARTSLIP_TOKEN não configurado nas propriedades do script.");
  }

  return token;
}

/**
 * Web App usado pelo Gemini / AI Studio.
 *
 * Recebe:
 * {
 *   token: "...",
 *   acao: "consultar_info_loja" ou "salvar_dados_comprovante_planilha",
 *   args: {...}
 * }
 */
function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents || "{}");

    const tokenEsperado = smartSlipGetToken();

    if (body.token !== tokenEsperado) {
      return smartSlipJson_({
        ok: false,
        erro: "Token inválido."
      });
    }

    const acao = String(body.acao || "").trim();
    const args = body.args || {};

    if (acao === "consultar_info_loja") {
      return smartSlipJson_(smartSlipConsultarInfoLoja_(args.loja_informada));
    }

    if (acao === "salvar_dados_comprovante_planilha") {
      return smartSlipJson_(smartSlipSalvarDadosComprovantePlanilha_(args));
    }

    return smartSlipJson_({
      ok: false,
      erro: "Ação não reconhecida: " + acao
    });

  } catch (err) {
    return smartSlipJson_({
      ok: false,
      erro: smartSlipSafeErr_(err)
    });
  }
}

/**
 * Consulta a aba Info_limites para localizar a loja e empresa.
 */
function smartSlipConsultarInfoLoja_(lojaInformada) {
  if (!lojaInformada) {
    return {
      ok: false,
      erro: "loja_informada não recebida."
    };
  }

  const lojaDigits = String(lojaInformada).replace(/\D/g, "");

  if (!lojaDigits) {
    return {
      ok: false,
      erro: "Número da loja inválido."
    };
  }

  const lojaSemZeros = String(Number(lojaDigits));
  const loja4 = lojaDigits.padStart(4, "0").slice(-4);

  const ss = SpreadsheetApp.openById(SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_INFO_LIMITES);

  if (!sh) {
    throw new Error("Aba '" + SMARTSLIP_ABA_INFO_LIMITES + "' não encontrada.");
  }

  const values = sh.getDataRange().getValues();

  if (values.length < 2) {
    throw new Error("Aba '" + SMARTSLIP_ABA_INFO_LIMITES + "' está vazia.");
  }

  const headers = values[0].map(function(h) {
    return String(h || "").trim();
  });

  const idxNormLoja = smartSlipEncontrarIndiceHeader_(headers, [
    "Norm_Loja",
    "NORM_LOJA",
    "Norm Loja",
    "Loja",
    "LOJA"
  ]);

  let idxEmpresa = smartSlipEncontrarIndiceHeader_(headers, [
    "EMPRESA0",
    "EMPRESA",
    "Empresa"
  ]);

  // Fallback: você comentou que EMPRESA0 está na coluna G.
  // Coluna G = índice 6.
  if (idxEmpresa < 0) {
    idxEmpresa = 6;
  }

  if (idxNormLoja < 0) {
    throw new Error("Coluna Norm_Loja não encontrada na aba Info_limites.");
  }

  for (let i = 1; i < values.length; i++) {
    const row = values[i];

    const normLojaRaw = row[idxNormLoja];
    const normLojaDigits = String(normLojaRaw || "").replace(/\D/g, "");

    if (!normLojaDigits) {
      continue;
    }

    const normLojaSemZeros = String(Number(normLojaDigits));
    const normLoja4 = normLojaDigits.padStart(4, "0").slice(-4);

    const bateu =
      normLojaSemZeros === lojaSemZeros ||
      normLoja4 === loja4;

    if (bateu) {
      const empresaRaw = String(row[idxEmpresa] || "").trim();
      const empresaNorm = smartSlipNormalizarEmpresa_(empresaRaw);

      return {
        ok: true,
        loja_informada: String(lojaInformada),
        loja_normalizada: normLoja4,
        empresa: empresaNorm,
        empresa_original: empresaRaw,
        linha_info_limites: i + 1
      };
    }
  }

  return {
    ok: false,
    erro: "Loja não encontrada na Info_limites.",
    loja_informada: String(lojaInformada),
    loja_normalizada_tentativa: loja4
  };
}

/**
 * Salva o comprovante validado na aba BASE_SMARTSLIP.
 */
function smartSlipSalvarDadosComprovantePlanilha_(dados) {
  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  let sh = ss.getSheetByName(SMARTSLIP_ABA_DESTINO);

  if (!sh) {
    sh = ss.insertSheet(SMARTSLIP_ABA_DESTINO);
    smartSlipCriarCabecalho_(sh);
  }

  smartSlipGarantirCabecalho_(sh);
  smartSlipValidarDadosComprovante_(dados);

  sh.appendRow([
    new Date(),
    dados.id_comprovante || "",
    dados.hash_comprovante || "",
    dados.protocolo || "",
    dados.indice_comprovante || "",
    dados.loja || "",
    dados.empresa || "",
    dados.tipo_documento || "",
    dados.data_deposito || "",
    dados.valor_deposito || 0,
    dados.banco || "",
    dados.data_movimento || "",
    dados.houve_retirada === true ? "Sim" : "Não",
    dados.valor_retirada || 0,
    dados.motivo_retirada || "",
    dados.data_geracao_documento || "",
    dados.codigo_autenticacao || "",
    dados.link_comprovante || "",
    dados.status_processamento || "",
    (dados.pendencias || []).join(" | "),
    (dados.divergencias || []).join(" | "),
    dados.confianca_geral || "",
    JSON.stringify(dados),

    dados.cupom_retirada_marketing_file_id || "",
    dados.cupom_retirada_marketing_link || "",
    dados.cupom_retirada_marketing_nome || ""
  ]);

  return {
    ok: true,
    mensagem: "Dados salvos com sucesso na planilha.",
    aba_destino: SMARTSLIP_ABA_DESTINO
  };
}

function smartSlipGetCabecalhoBase_() {
  return [
    "Data Registro",
    "ID Comprovante",
    "Hash Comprovante",
    "Protocolo",
    "Índice Comprovante",
    "Loja",
    "Empresa",
    "Tipo Documento",
    "Data Depósito",
    "Valor Depósito",
    "Banco",
    "Data Movimento",
    "Houve Retirada",
    "Valor Retirada",
    "Motivo Retirada",
    "Data Geração Documento",
    "Código Autenticação",
    "Link Comprovante",
    "Status Processamento",
    "Pendências",
    "Divergências",
    "Confiança Geral",
    "JSON Original",
    "Anexos Retirada ID",
    "Link Anexos Retirada",
    "Resumo Anexos Retirada"
  ];
}

/**
 * Cria cabeçalho da aba BASE_SMARTSLIP.
 */
function smartSlipCriarCabecalho_(sh) {
  const headers = smartSlipGetCabecalhoBase_();

  if (sh.getMaxColumns() < headers.length) {
    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length - sh.getMaxColumns()
    );
  }

  sh.getRange(
    1,
    1,
    1,
    headers.length
  ).setValues([headers]);

  sh.setFrozenRows(1);
}

/**
 * Garante que a aba tem cabeçalho.
 */
function smartSlipGarantirCabecalho_(sh) {
  const headers = smartSlipGetCabecalhoBase_();

  if (sh.getMaxColumns() < headers.length) {
    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length - sh.getMaxColumns()
    );
  }

  if (sh.getLastRow() === 0) {
    sh.getRange(
      1,
      1,
      1,
      headers.length
    ).setValues([headers]);

    sh.setFrozenRows(1);
    return;
  }

  const primeiraCelula = String(
    sh.getRange(1, 1).getValue() || ""
  ).trim();

  if (primeiraCelula !== "Data Registro") {
    sh.insertRowBefore(1);
  }

  sh.getRange(
    1,
    1,
    1,
    headers.length
  ).setValues([headers]);

  sh.setFrozenRows(1);
}

/**
 * Valida campos obrigatórios antes de salvar.
 */
function smartSlipValidarDadosComprovante_(dados) {
  const obrigatorios = [
    "loja",
    "empresa",
    "tipo_documento",
    "data_deposito",
    "valor_deposito",
    "data_movimento",
    "houve_retirada",
    "valor_retirada",
    "motivo_retirada",
    "data_geracao_documento",
    "status_processamento",
    "pendencias",
    "divergencias",
    "confianca_geral"
  ];

  const faltantes = [];

  obrigatorios.forEach(function(campo) {
    const valor = dados[campo];

    const vazio =
      valor === undefined ||
      valor === null ||
      valor === "";

    if (vazio) {
      faltantes.push(campo);
    }
  });

  if (!Array.isArray(dados.pendencias)) {
    faltantes.push("pendencias deve ser array");
  }

  if (!Array.isArray(dados.divergencias)) {
    faltantes.push("divergencias deve ser array");
  }

  if (
  dados.houve_retirada === true &&
  smartSlipMotivoRetiradaEhMarketing_(
    dados.motivo_retirada
  ) &&
  !String(
    dados.cupom_retirada_marketing_link || ""
  ).trim()
) {
  faltantes.push(
    "anexos de evidência da retirada por Marketing"
  );
}

  if (faltantes.length) {
    throw new Error("Campos obrigatórios ausentes/inválidos: " + faltantes.join(", "));
  }
}

/**
 * Localiza índice de cabeçalho por nomes possíveis.
 */
function smartSlipEncontrarIndiceHeader_(headers, nomesPossiveis) {
  for (let i = 0; i < headers.length; i++) {
    const h = String(headers[i] || "").trim().toLowerCase();

    for (let j = 0; j < nomesPossiveis.length; j++) {
      const alvo = String(nomesPossiveis[j] || "").trim().toLowerCase();

      if (h === alvo) {
        return i;
      }
    }
  }

  return -1;
}

/**
 * Normaliza nome da empresa.
 */
function smartSlipNormalizarEmpresa_(empresaRaw) {
  const txt = String(empresaRaw || "")
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  if (txt.includes("EMPRESA B") || txt.includes("NIKE")) {
    return "Empresa B";
  }

  if (txt.includes("EMPRESA A")) {
    return "Empresa A";
  }

  return "Nao identificado";
}

/**
 * Resposta JSON padrão.
 */
function smartSlipJson_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Erro seguro.
 */
function smartSlipSafeErr_(err) {
  try {
    if (!err) return "erro desconhecido";
    if (err.message) return err.message;
    return String(err);
  } catch (e) {
    return "erro ao serializar erro";
  }
}

/**
 * Teste manual da consulta de loja.
 * Rode pelo Apps Script antes de conectar no AI Studio.
 */
function smartSlipTesteConsultarLoja() {
  const r = smartSlipConsultarInfoLoja_("241");
  Logger.log(JSON.stringify(r, null, 2));
}

/**
 * Teste manual de salvamento.
 * Rode pelo Apps Script antes de conectar no AI Studio.
 */
function smartSlipTesteSalvar() {
  const r = smartSlipSalvarDadosComprovantePlanilha_({
    loja: "0241",
    empresa: "Empresa A",
    tipo_documento: "deposito_caixa_eletronico",
    data_deposito: "2026-05-08",
    valor_deposito: 37200.46,
    banco: "Itaú",
    data_movimento: "2026-05-07",
    houve_retirada: false,
    valor_retirada: 0,
    motivo_retirada: "Não houve retirada",
    data_geracao_documento: "2026-05-08",
    codigo_autenticacao: "TESTE123",
    link_comprovante: "",
    status_processamento: "PRONTO_PARA_SALVAR",
    pendencias: ["sem_pendencias"],
    divergencias: ["sem_divergencias"],
    confianca_geral: 0.95
  });

  Logger.log(JSON.stringify(r, null, 2));
}

function smartSlipTesteDoPostFake() {
  const fakeEvent = {
    postData: {
      contents: JSON.stringify({
        token: smartSlipGetToken(),
        acao: "consultar_info_loja",
        args: {
          loja_informada: "241"
        }
      })
    }
  };

  const r = doPost(fakeEvent);
  Logger.log(r.getContent());
}

function smartSlipGetConfigIaGateway_() {
  const properties =
    PropertiesService.getScriptProperties();

  const baseUrl = String(
    properties.getProperty(
      "SMARTSLIP_IA_BASE_URL"
    ) || ""
  )
    .trim()
    .replace(/\/+$/g, "");

  const apiKey = String(
    properties.getProperty(
      "SMARTSLIP_IA_API_KEY"
    ) || ""
  ).trim();

  const model = String(
    properties.getProperty(
      "SMARTSLIP_IA_MODEL"
    ) || ""
  ).trim();

  if (!baseUrl) {
    throw new Error(
      "SMARTSLIP_IA_BASE_URL não configurada nas propriedades do script."
    );
  }

  if (!apiKey) {
    throw new Error(
      "SMARTSLIP_IA_API_KEY não configurada nas propriedades do script."
    );
  }

  if (!model) {
    throw new Error(
      "SMARTSLIP_IA_MODEL não configurada nas propriedades do script."
    );
  }

  return {
    base_url: baseUrl,
    api_key: apiKey,
    model: model
  };
}


function smartSlipMontarConteudoIaGateway_(
  prompt,
  base64Arquivo,
  mimeType
) {
  const conteudo = [
    {
      type: "text",
      text: String(prompt || "")
    }
  ];

  if (!base64Arquivo) {
    return conteudo;
  }

  const mime = String(
    mimeType ||
    "application/pdf"
  ).trim();

  const base64Limpo = String(
    base64Arquivo || ""
  )
    .split(",")
    .pop();

  const dataUrl =
    "data:" +
    mime +
    ";base64," +
    base64Limpo;

  /*
    PDFs são enviados como arquivo.

    Imagens são enviadas como image_url
    contendo Data URL Base64.
  */
  if (mime === "application/pdf") {
    conteudo.push({
      type: "file",

      file: {
        file_data: dataUrl
      }
    });

  } else {
    conteudo.push({
      type: "image_url",

      image_url: {
        url: dataUrl
      }
    });
  }

  return conteudo;
}


function smartSlipExtrairTextoRespostaIaGateway_(
  json
) {
  const content =
    json &&
    json.choices &&
    json.choices[0] &&
    json.choices[0].message
      ? json.choices[0].message.content
      : null;

  if (typeof content === "string") {
    return content.trim();
  }

  /*
    Alguns gateways podem devolver content
    em formato de array.
  */
  if (Array.isArray(content)) {
    return content
      .map(function(item) {
        if (!item) {
          return "";
        }

        if (typeof item === "string") {
          return item;
        }

        return String(
          item.text || ""
        );
      })
      .join("")
      .trim();
  }

  return "";
}


function smartSlipChamarIaGateway_(
  prompt,
  base64Arquivo,
  mimeType
) {
  const config =
    smartSlipGetConfigIaGateway_();

  const url =
    config.base_url +
    "/v1/chat/completions";

  const payload = {
    model:
      config.model,

    messages: [
      {
        role: "user",

        content:
          smartSlipMontarConteudoIaGateway_(
            prompt,
            base64Arquivo,
            mimeType
          )
      }
    ],

    /*
      Mantém o requisito atual do SmartSlip:
      retorno obrigatoriamente em JSON.
    */
    response_format: {
      type: "json_object"
    }
  };

  const response =
    UrlFetchApp.fetch(
      url,
      {
        method: "post",

        contentType:
          "application/json",

        headers: {
          Authorization:
            "Bearer " +
            config.api_key,

          Accept:
            "application/json"
        },

        payload:
          JSON.stringify(
            payload
          ),

        muteHttpExceptions:
          true
      }
    );

  const statusCode =
    response.getResponseCode();

  const textoResposta =
    response.getContentText();

  Logger.log(
    "HTTP IA GATEWAY: " +
    statusCode
  );

  /*
    Não logar chave nem Authorization.
  */
  if (
    statusCode < 200 ||
    statusCode >= 300
  ) {
    throw new Error(
      "Erro IA Gateway HTTP " +
      statusCode +
      ": " +
      textoResposta
    );
  }

  let json;

  try {
    json =
      JSON.parse(
        textoResposta
      );

  } catch (err) {
    throw new Error(
      "O IA Gateway retornou uma resposta inválida: " +
      textoResposta
    );
  }

  const respostaTexto =
    smartSlipExtrairTextoRespostaIaGateway_(
      json
    );

  if (!respostaTexto) {
    throw new Error(
      "O IA Gateway não retornou conteúdo válido: " +
      textoResposta
    );
  }

  return {
    http_status:
      statusCode,

    model:
      config.model,

    usage:
      json.usage || {},

    texto:
      respostaTexto,

    raw:
      json
  };
}

function smartSlipTesteLiteLlmModelos() {
  const config =
    smartSlipGetConfigIaGateway_();

  const url =
    config.base_url +
    "/v1/models";

  const response =
    UrlFetchApp.fetch(
      url,
      {
        method: "get",

        headers: {
          Authorization:
            "Bearer " +
            config.api_key,

          Accept:
            "application/json"
        },

        muteHttpExceptions:
          true
      }
    );

  const statusCode =
    response.getResponseCode();

  const texto =
    response.getContentText();

  Logger.log(
    "HTTP LITELLM MODELS: " +
    statusCode
  );

  Logger.log(texto);

  if (
    statusCode < 200 ||
    statusCode >= 300
  ) {
    throw new Error(
      "Não foi possível consultar os modelos do gateway. HTTP " +
      statusCode +
      ": " +
      texto
    );
  }

  return texto;
}

function smartSlipTesteGeminiPing() {
  const apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");

  if (!apiKey) {
    throw new Error("GEMINI_API_KEY não configurada nas propriedades do script.");
  }

  const model = "gemini-3-flash-preview";

  const url =
    "https://generativelanguage.googleapis.com/v1beta/models/" +
    model +
    ":generateContent?key=" +
    encodeURIComponent(apiKey);

  const payload = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: "Responda somente este JSON: {\"ok\":true,\"mensagem\":\"Gemini funcionando no Apps Script\"}"
          }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.1,
      response_mime_type: "application/json"
    }
  };

  const resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const statusCode = resp.getResponseCode();
  const txt = resp.getContentText();

  Logger.log("HTTP STATUS: " + statusCode);
  Logger.log(txt);

  if (statusCode < 200 || statusCode >= 300) {
    throw new Error("Erro Gemini API HTTP " + statusCode + ": " + txt);
  }

  const json = JSON.parse(txt);
  const respostaTexto = json.candidates[0].content.parts[0].text;

  Logger.log("RESPOSTA GEMINI:");
  Logger.log(respostaTexto);

  return respostaTexto;
}

function smartSlipTesteGeminiComArquivoDrive() {
  const fileId = smartSlipGetScriptProperty("SMARTSLIP_TEST_FILE_ID");

  const file = DriveApp.getFileById(fileId);
  const linkComprovante = file.getUrl();
  const blob = file.getBlob();

  const base64 = Utilities.base64Encode(blob.getBytes());
  const mimeType = blob.getContentType();

const respostasUsuario = {
  loja: "0255",
  data_movimento_inicio: "01/05/2026",
  data_movimento_fim: "04/05/2026",
  houve_retirada: false,
  valor_retirada: 0,
  motivo_retirada: "Não houve retirada",
  mais_comprovantes: false
};

  const resultado = smartSlipChamarGemini(base64, mimeType, respostasUsuario);

  Logger.log(JSON.stringify(resultado, null, 2));

  if (resultado.dados_comprovante && resultado.dados_comprovante.loja) {
    const infoLoja = smartSlipConsultarInfoLoja_(resultado.dados_comprovante.loja);

    Logger.log("INFO LOJA:");
    Logger.log(JSON.stringify(infoLoja, null, 2));

    if (infoLoja.ok) {
      resultado.dados_comprovante.loja = infoLoja.loja_normalizada;
      resultado.dados_comprovante.empresa = infoLoja.empresa;
    }
  }

  Logger.log("RESULTADO FINAL:");
  Logger.log(JSON.stringify(resultado, null, 2));
}

function smartSlipChamarGemini(base64Arquivo, mimeType, respostasUsuario) {
  const apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");

  if (!apiKey) {
    throw new Error("GEMINI_API_KEY não configurada nas propriedades do script.");
  }

  const model = "gemini-3.6-flash";

  const url =
    "https://generativelanguage.googleapis.com/v1beta/models/" +
    model +
    ":generateContent?key=" +
    encodeURIComponent(apiKey);

  const prompt = `
Você é o Agente SmartSlip, especialista em leitura, extração, validação e interpretação semântica de comprovantes de depósito numerário para lojas Empresa A e Empresa B/Nike.

Objetivo:
Ler o comprovante anexado, extrair dados essenciais e retornar SOMENTE JSON válido.

Regras obrigatórias:
- Nunca invente número de loja.
- Nunca use CNPJ, código de barras, número de documento, autenticação, agência, conta ou identificador bancário como número de loja.
- Se a loja não estiver clara no comprovante e também não estiver em respostasUsuario.loja, retorne loja como null.
- Se respostasUsuario.loja estiver preenchido, use esse valor como loja informada pelo usuário.
- A empresa só pode ser "Empresa A", "Empresa B" ou "Nao identificado".
- Nunca use razão social como empresa. Exemplo proibido: "SBF COMERCIO DE PRODUTOS ESPORTIVOS S/A".
- Se a empresa não foi consultada na base Info_limites, retorne empresa como "Nao identificado".
- Se o comprovante estiver ilegível, retorne status = "INELEGIVEL".
- Se faltar dado obrigatório, retorne status = "PRECISA_COMPLEMENTO".
- Banco/origem deve ser lido exclusivamente do comprovante.
- Se banco/origem não for identificado, retorne banco como "Nao identificado".
- Banco/origem não é campo obrigatório e não deve gerar pergunta complementar.
- Nunca pergunte banco/origem para a loja.
- A data de movimento vem das respostas do usuário, não do comprovante.
- A data de movimento pode ser uma data única ou um período com data inicial e data final.
- Se houver data_movimento_inicio e data_movimento_fim, use ambas.
- Se houver apenas data_movimento, trate como data única.
- A data final do movimento nunca pode ser maior que a data do depósito/documento.
- Se a data do movimento for maior que a data do depósito/documento, retorne status = "DIVERGENCIA".
- Se todos os dados estiverem completos, retorne status = "PRONTO_PARA_SALVAR".
- Datas devem estar no formato dd/mm/aaaa.
- Se o comprovante trouxer data em outro formato, converta para dd/mm/aaaa.
- Tenha atenção máxima ao ano das datas. Não troque 2026 por 2025.
- Se a data do comprovante estiver próxima ao período de movimento informado pelo usuário, mantenha coerência de ano.
- Se houver dúvida visual apenas no ano, use o ano do período de movimento como referência e registre a dúvida em observacoes.
- Nunca retorne uma data de depósito/documento em ano anterior ao movimento informado quando o dia e mês indicarem que o depósito ocorreu logo após o movimento.
- Valor deve ser número decimal. Exemplo: 37200.46.
- Não envie nada para Slack.
- Não escreva explicações fora do JSON.
- Para cada item em pendencias, crie uma pergunta correspondente em perguntas_complementares.
- Se loja estiver ausente, perguntas_complementares deve conter: "Qual o número da loja?"
- Se data_movimento estiver ausente, perguntas_complementares deve conter: "Qual a data do movimento desse depósito?"
- Se houve_retirada estiver null, perguntas_complementares deve conter: "Houve alguma retirada desse movimento para estorno, reembolso no ato ou algo do tipo?"
- Se houver múltiplos comprovantes na mesma imagem/PDF, tente identificar e processar todos os comprovantes fisicamente visíveis e legíveis.
- Retorne um array chamado "comprovantes", com um item para cada comprovante físico claramente separado na imagem/PDF.
- qtd_comprovantes_detectados deve representar somente a quantidade de comprovantes físicos visíveis, não a quantidade de códigos, valores, linhas ou blocos de texto.
- Não crie comprovantes adicionais por inferência.
- Não continue sequência de código de autenticação, controle, terminal, envelope ou qualquer outro identificador.
- Não replique comprovantes parecidos como se fossem novos.
- Não deduza valores ausentes com base em padrão visual, repetição ou sequência.
- Não use valores de conta, terminal, envelope, autenticação, telefone, controle ou identificadores como valor de depósito.
- O campo valor_deposito só pode ser preenchido quando houver evidência textual clara no próprio comprovante.
- O valor_deposito deve ser extraído preferencialmente de linhas como "VALOR TOTAL EM DINHEIRO", "VALOR DO DEPÓSITO", "TOTAL", "VALOR RECEBIDO" ou expressão equivalente.
- Cada item do array deve conter: status, indice_comprovante, tipo_documento, data_deposito, valor_deposito, banco, data_geracao_documento, codigo_autenticacao, observacoes, confianca_item, posicao_visual_aproximada e evidencias.
- Para cada comprovante, retorne evidencias com os trechos textuais que sustentam os campos extraídos.
- O objeto evidencias deve conter: valor_deposito_texto, data_deposito_texto, codigo_autenticacao_texto, controle_texto e bloco_textual_comprovante.
- valor_deposito_texto deve conter o trecho exato onde o valor foi lido. Se o valor não estiver claro, retorne valor_deposito como null.
- data_deposito_texto deve conter o trecho exato onde a data foi lida. Se a data não estiver clara, retorne data_deposito como null.
- Para comprovantes de pagamento de boleto, recibos de Lotéricas CAIXA e documentos equivalentes, considere DATA DE PAGAMENTO como a data operacional principal do comprovante.
- Quando existir uma DATA DE PAGAMENTO claramente legível e não existir no documento uma data distinta de geração, emissão ou impressão, preencha data_geracao_documento com a mesma data identificada em data_deposito.
- Nesses casos, não deixe data_geracao_documento como null apenas porque o comprovante não utiliza literalmente os termos "data de geração" ou "data de emissão".
- Só aplique essa regra quando a data de pagamento estiver claramente legível e sustentada por evidência textual no próprio comprovante.
- Nunca invente ou estime data_geracao_documento quando nenhuma data confiável estiver visível.
- codigo_autenticacao_texto deve conter o trecho exato onde o código foi lido. Se não estiver claro, retorne codigo_autenticacao como string vazia.
- bloco_textual_comprovante deve conter um resumo textual do próprio comprovante físico usado para aquele item, sem misturar dados de outro comprovante.
- posicao_visual_aproximada deve indicar onde o comprovante aparece na imagem/PDF, por exemplo: "linha 1 coluna 1", "linha 2 coluna 3", "parte superior direita".
- Se algum comprovante estiver cortado, ilegível ou parcialmente visível, inclua esse item com status = "INELEGIVEL", não preencha valor_deposito sem evidência e explique em observacoes.
- Se houver dúvida sobre valor, data ou código, marque o item como "PENDENCIA" ou "INELEGIVEL"; nunca complete por suposição.
- Não misture valores de comprovantes diferentes.
- Não some os valores dos comprovantes.
- Não invente valores, datas, banco, controle ou código de autenticação.
- Quando houver boleto bancário de fundo e recibo/comprovante de Lotéricas CAIXA por cima, trate o conjunto visual como um único comprovante de pagamento, usando o recibo da Lotéricas CAIXA como fonte principal do valor pago.
- Não conte o boleto bancário de fundo como um segundo comprovante separado se ele estiver parcialmente coberto pelo recibo de pagamento.
- Não replique o valor de um comprovante para outro.
- Se dois comprovantes tiverem o mesmo valor, mesma data e mesmo banco, só retorne ambos se houver evidência documental distinta para cada um, com bloco_textual_comprovante e posicao_visual_aproximada claramente diferentes.
- Se houver dúvida se dois itens são comprovantes distintos ou duplicação da mesma leitura, marque o item como PENDENCIA e explique em observacoes.
- Valores iguais podem existir em comprovantes diferentes. Não trate valor repetido como duplicidade por si só.
- Se dois comprovantes tiverem o mesmo valor, retorne ambos somente se houver evidência documental distinta para cada um.
- Quando houver comprovantes com o mesmo valor, cada item deve trazer codigo_autenticacao_texto, controle_texto ou bloco_textual_comprovante claramente distinto.
- Não use a mesma posicao_visual_aproximada genérica para vários comprovantes. Diferencie por ordem e localização, por exemplo: "comprovante 1 de cima para baixo", "comprovante 2 de cima para baixo", "comprovante 3 de cima  para baixo".
- Se três comprovantes tiverem o mesmo valor, mas forem documentos fisicamente distintos, retorne os três, desde que cada item tenha evidência própria no bloco_textual_comprovante.
- O bloco_textual_comprovante de cada item deve conter trechos específicos daquele comprovante, incluindo valor, data e código/controle quando visível. 
- Para valores repetidos, a posicao_visual_aproximada e o bloco_textual_comprovante precisam indicar claramente comprovantes físicos diferentes.
- Se não for possível distinguir se o valor repetido pertence a dois comprovantes diferentes ou se é duplicação da mesma leitura, marque o item como PENDENCIA e explique em observacoes.
- A loja, empresa, data_movimento, houve_retirada, valor_retirada e motivo_retirada vêm das respostas do usuário e se aplicam ao arquivo inteiro.
- codigo_autenticacao não é campo bloqueante. Se não for identificado, retorne como string vazia e registre em observacoes apenas como observação.
- Se codigo_autenticacao for lido claramente em codigo_autenticacao_texto, não escreva que ele foi inferido.
- Observações sobre codigo_autenticacao não devem transformar o comprovante em PENDENCIA quando valor_deposito, data_deposito e bloco_textual_comprovante estiverem claros.
- Use observacoes de inferência apenas para campos críticos como valor_deposito, data_deposito, tipo_documento ou identificação física do comprovante.

Respostas complementares já informadas pelo usuário:
${JSON.stringify(respostasUsuario || {}, null, 2)}

Retorne exatamente neste formato JSON:

{
  "status": "PRONTO_PARA_SALVAR | PRECISA_COMPLEMENTO | DIVERGENCIA | PENDENCIA | INELEGIVEL",
  "qtd_comprovantes_detectados": 0,
  "alerta_qualidade_imagem": "",
  "criterio_contagem": "",
  "dados_arquivo": {
    "loja": null,
    "empresa": "Nao identificado",
    "data_movimento": null,
    "data_movimento_inicio": null,
    "data_movimento_fim": null,
    "houve_retirada": null,
    "valor_retirada": null,
    "motivo_retirada": null,
    "link_comprovante": ""
  },
  "comprovantes": [
  {
    "status": "PRONTO_PARA_SALVAR | INELEGIVEL | PENDENCIA",
    "indice_comprovante": 1,
    "tipo_documento": "boleto_bancario | deposito_caixa_eletronico | comprovante_carro_forte | outro_comprovante_deposito | nao_identificado",
    "data_deposito": null,
    "valor_deposito": null,
    "banco": "Nao identificado",
    "data_geracao_documento": null,
    "codigo_autenticacao": "",
    "confianca_item": 0,
    "posicao_visual_aproximada": "",
    "evidencias": {
      "valor_deposito_texto": "",
      "data_deposito_texto": "",
      "codigo_autenticacao_texto": "",
      "controle_texto": "",
      "bloco_textual_comprovante": ""
    },
    "observacoes": []
  }
  ],
  "pendencias": [],
  "divergencias": [],
  "perguntas_complementares": [],
  "confianca_geral": 0
}
`;

  const payload = {
    contents: [
      {
        role: "user",
        parts: [
          {
            inline_data: {
              mime_type: mimeType || "application/pdf",
              data: base64Arquivo
            }
          },
          {
            text: prompt
          }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.2,
      response_mime_type: "application/json"
    }
  };

  const resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const statusCode = resp.getResponseCode();
  const txt = resp.getContentText();

  Logger.log("HTTP GEMINI: " + statusCode);
  Logger.log(txt);

  if (statusCode < 200 || statusCode >= 300) {
    throw new Error("Erro Gemini API HTTP " + statusCode + ": " + txt);
  }

  const json = JSON.parse(txt);

  smartSlipRegistrarCustoIa_({
  origem: "LEITURA_COMPLETA_COMPROVANTE",
  modelo: model,
  usage: json.usageMetadata || {},
  respostasUsuario: respostasUsuario || {},
  httpStatus: statusCode
});

  const respostaTexto =
    json &&
    json.candidates &&
    json.candidates[0] &&
    json.candidates[0].content &&
    json.candidates[0].content.parts &&
    json.candidates[0].content.parts[0] &&
    json.candidates[0].content.parts[0].text;

  if (!respostaTexto) {
    throw new Error("Gemini não retornou texto válido: " + txt);
  }

  const resultado = JSON.parse(respostaTexto);
  return smartSlipAplicarRegrasComplementares_(resultado, respostasUsuario);
}

function smartSlipPreValidarTotalComprovanteApp(payload) {
  try {
    payload = payload || {};

    smartSlipAssertUsuarioAutorizado_();

    if (!payload.arquivoBase64) {
      throw new Error("Arquivo não recebido para pré-validação.");
    }

    const valorTotalUsuario = Number(payload.valor_total_usuario || 0);

    if (!valorTotalUsuario || valorTotalUsuario <= 0) {
      throw new Error("Valor total informado pelo usuário inválido.");
    }

    const base64Arquivo = String(payload.arquivoBase64 || "").split(",").pop();
    const mimeType = payload.mimeType || "application/pdf";

    const leitura = smartSlipChamarGeminiTotalDocumental_(
      base64Arquivo,
      mimeType,
      {
        loja: payload.loja || "",
        origem: "PRE_VALIDACAO_TOTAL_DOCUMENTAL"
      }
    );

    const valorTotalIa = smartSlipNumeroPreValidacaoIa_(leitura.valor_total_documental);
    const confianca = Number(leitura.confianca || 0);
    const evidencia = String(leitura.evidencia_textual_total || "").trim();

    const okParaComparar =
      String(leitura.status || "").toUpperCase() === "OK" &&
      valorTotalIa > 0 &&
      confianca >= 0.95 &&
      evidencia.length >= 8;

    const diferenca = Math.abs(valorTotalIa - valorTotalUsuario);
    const qtdValoresConsiderados = Number(leitura.qtd_valores_considerados || 0);

    if (!okParaComparar) {
      return {
        ok: true,
        status_validacao: "IA_NAO_CONFIAVEL",
        bloquear_envio: false,
        valor_total_usuario: valorTotalUsuario,
        valor_total_ia: valorTotalIa || null,
        diferenca: diferenca || null,
        confianca: confianca,
        mensagem:
          "A IA não conseguiu validar o total do comprovante com segurança. Revise os valores digitados antes de enviar.",
        leitura_ia: leitura
      };
    }
    
// Múltiplos comprovantes no mesmo arquivo:
// se a IA leu todos os valores com alta confiança, a divergência deve bloquear.
if (
  diferenca > SMARTSLIP_TOLERANCIA_TOTAL_IA &&
  qtdValoresConsiderados > 1 &&
  confianca >= 0.98
) {
  return {
    ok: true,
    status_validacao: "DIVERGENTE_MULTIPLO_BLOQUEANTE",
    bloquear_envio: true,
    valor_total_usuario: valorTotalUsuario,
    valor_total_ia: valorTotalIa,
    diferenca: diferenca,
    confianca: confianca,
    mensagem:
      "A IA identificou múltiplos comprovantes no arquivo e leu os valores com alta confiança, mas a soma informada está diferente do total lido.",
    leitura_ia: leitura
  };
}

// Múltiplos comprovantes com leitura não plenamente confiável:
// não bloqueia automaticamente, mas orienta revisão.
if (diferenca > SMARTSLIP_TOLERANCIA_TOTAL_IA && qtdValoresConsiderados > 1) {
  return {
    ok: true,
    status_validacao: "DIVERGENTE_MULTIPLO_NAO_BLOQUEANTE",
    bloquear_envio: false,
    valor_total_usuario: valorTotalUsuario,
    valor_total_ia: valorTotalIa,
    diferenca: diferenca,
    confianca: confianca,
    mensagem:
      "A IA encontrou diferença no total e há múltiplos comprovantes no arquivo, mas a leitura não atingiu confiança suficiente para bloquear automaticamente. Revise os valores antes de enviar.",
    leitura_ia: leitura
  };
}

if (diferenca > SMARTSLIP_TOLERANCIA_TOTAL_IA) {
  return {
    ok: true,
    status_validacao: "DIVERGENTE_ALTA_CONFIANCA",
    bloquear_envio: true,
    valor_total_usuario: valorTotalUsuario,
    valor_total_ia: valorTotalIa,
    diferenca: diferenca,
    confianca: confianca,
    mensagem:
      "A soma dos valores diários informados não confere com o total lido pela IA no comprovante.",
    leitura_ia: leitura
  };
}

    return {
      ok: true,
      status_validacao: "OK",
      bloquear_envio: false,
      valor_total_usuario: valorTotalUsuario,
      valor_total_ia: valorTotalIa,
      diferenca: diferenca,
      confianca: confianca,
      mensagem: "Total validado pela IA. Soma informada confere com o comprovante.",
      leitura_ia: leitura
    };

  } catch (err) {
    return {
      ok: false,
      status_validacao: "ERRO_PRE_VALIDACAO",
      bloquear_envio: false,
      erro: String(err && err.message ? err.message : err)
    };
  }
}

function smartSlipChamarGeminiTotalDocumental_(base64Arquivo, mimeType, contextoCusto) {
  const apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");

  if (!apiKey) {
    throw new Error("GEMINI_API_KEY não configurada nas propriedades do script.");
  }

  const model = "gemini-3.6-flash";

  const url =
    "https://generativelanguage.googleapis.com/v1beta/models/" +
    model +
    ":generateContent?key=" +
    encodeURIComponent(apiKey);

  const prompt = `
Você é o validador de total documental do SmartSlip.

Objetivo:
Ler SOMENTE os valores de depósito/pagamento fisicamente visíveis no comprovante anexado e retornar JSON válido.

Regras críticas:
- Não extraia loja, banco, data de movimento ou qualquer outro campo.
- Leia somente valores monetários de comprovantes de depósito/pagamento.
- Se houver vários comprovantes físicos no mesmo arquivo, some apenas os valores dos comprovantes claramente visíveis.
- Se houver boleto bancário de fundo e recibo de Lotéricas/CAIXA sobreposto, considere o conjunto como um único comprovante, usando o recibo como fonte principal.
- Não conte boleto de fundo como outro comprovante se ele estiver coberto por recibo.
- Não invente valores.
- Não use código de barras, autenticação, controle, telefone, terminal, agência, conta ou identificador como valor.
- Não complete valor por suposição.

Regra de confiança:
- Só retorne status = "OK" quando todos os valores considerados estiverem visualmente claros, legíveis e sustentados por evidência textual própria.
- Se houver múltiplos comprovantes no mesmo arquivo e todos os valores estiverem claramente legíveis, retorne status = "OK", qtd_valores_considerados maior que 1, valor_total_documental com a soma dos valores e confianca >= 0.98.
- Se houver múltiplos comprovantes, mas algum valor estiver cortado, parcialmente visível, borrado, sobreposto, distante, duplicado de forma duvidosa ou sem evidência textual própria, retorne status = "IA_NAO_CONFIAVEL".
- Se houver dúvida se dois valores pertencem a comprovantes distintos ou se a leitura duplicou o mesmo comprovante, retorne status = "IA_NAO_CONFIAVEL".
- Se o valor estiver ilegível ou houver dúvida, retorne status = "IA_NAO_CONFIAVEL".
- Só use confianca >= 0.98 quando a leitura dos valores for praticamente certa.
- Use confianca entre 0.95 e 0.97 quando praticamente certa.
- Use confianca entre 0.95 e 0.97 quando os valores parecem corretos, mas existe pequena incerteza visual.
- Use confianca menor que 0.95 quando houver qualquer dúvida relevante.

Evidências obrigatórias:
- O campo evidencia_textual_total deve conter os trechos textuais que sustentam o valor total lido.
- Se houver múltiplos valores individuais, retorne cada um em valores_individuais com sua evidência.
- Cada item de valores_individuais deve ter valor, evidencia_textual e posicao_visual_aproximada próprios.
- Não use a mesma evidencia_textual ou a mesma posicao_visual_aproximada para justificar dois valores diferentes.

Retorne exatamente este JSON:

{
  "status": "OK | IA_NAO_CONFIAVEL",
  "valor_total_documental": null,
  "qtd_valores_considerados": 0,
  "valores_individuais": [
    {
      "valor": null,
      "evidencia_textual": "",
      "posicao_visual_aproximada": ""
    }
  ],
  "evidencia_textual_total": "",
  "alerta_qualidade": "",
  "confianca": 0
}
`;

  const payload = {
    contents: [
      {
        role: "user",
        parts: [
          {
            inline_data: {
              mime_type: mimeType || "application/pdf",
              data: base64Arquivo
            }
          },
          {
            text: prompt
          }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.05,
      response_mime_type: "application/json"
    }
  };

  const resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const statusCode = resp.getResponseCode();
  const txt = resp.getContentText();

  if (statusCode < 200 || statusCode >= 300) {
    throw new Error("Erro Gemini API HTTP " + statusCode + ": " + txt);
  }

  const json = JSON.parse(txt);

  smartSlipRegistrarCustoIa_({
  origem: "PRE_VALIDACAO_TOTAL_DOCUMENTAL",
  modelo: model,
  usage: json.usageMetadata || {},
  respostasUsuario: contextoCusto || {},
  httpStatus: statusCode
});

  const respostaTexto =
    json &&
    json.candidates &&
    json.candidates[0] &&
    json.candidates[0].content &&
    json.candidates[0].content.parts &&
    json.candidates[0].content.parts[0] &&
    json.candidates[0].content.parts[0].text;

  if (!respostaTexto) {
    throw new Error("Gemini não retornou texto válido na pré-validação: " + txt);
  }

  return JSON.parse(respostaTexto);
}

function smartSlipNumeroPreValidacaoIa_(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return 0;
  }

  if (typeof valor === "number") {
    return isNaN(valor) ? 0 : valor;
  }

  const txt = String(valor)
    .replace(/[R$\s]/g, "")
    .replace(/\./g, "")
    .replace(",", ".")
    .trim();

  const n = Number(txt);

  return isNaN(n) ? 0 : n;
}

function smartSlipAplicarRegrasComplementares_(resultado, respostasUsuario) {
  respostasUsuario = respostasUsuario || {};
  resultado = resultado || {};

  if (!resultado.dados_comprovante) {
    resultado.dados_comprovante = {};
  }

  if (!Array.isArray(resultado.pendencias)) {
    resultado.pendencias = [];
  }

  if (!Array.isArray(resultado.divergencias)) {
    resultado.divergencias = [];
  }

  if (!Array.isArray(resultado.perguntas_complementares)) {
    resultado.perguntas_complementares = [];
  }

  const dados = resultado.dados_comprovante;

  smartSlipNormalizarPeriodoMovimento(respostasUsuario, dados);

  // Se a loja foi respondida pelo usuário, usa essa loja.
  if (!dados.loja && respostasUsuario.loja) {
    dados.loja = smartSlipNormalizarLoja4(respostasUsuario.loja);
  }

  // Não aceitar razão social como empresa.
  if (
    dados.empresa &&
    dados.empresa !== "Empresa A" &&
    dados.empresa !== "Empresa B" &&
    dados.empresa !== "Nao identificado"
  ) {
    dados.empresa = "Nao identificado";
  }

  if (!dados.empresa) {
    dados.empresa = "Nao identificado";
  }

  // Código de autenticação não deve bloquear o fluxo.
  if (dados.codigo_autenticacao === null || dados.codigo_autenticacao === undefined) {
    dados.codigo_autenticacao = "";
  }

  if (dados.link_comprovante === null || dados.link_comprovante === undefined) {
    dados.link_comprovante = "";
  }

  // Data de movimento respondida pelo usuário.
  if (!dados.data_movimento && respostasUsuario.data_movimento) {
    dados.data_movimento = respostasUsuario.data_movimento;
  }

  // Informação de retirada respondida pelo usuário.
  if (
    (dados.houve_retirada === null || dados.houve_retirada === undefined) &&
    typeof respostasUsuario.houve_retirada === "boolean"
  ) {
    dados.houve_retirada = respostasUsuario.houve_retirada;
  }

  if (
    (dados.valor_retirada === null || dados.valor_retirada === undefined) &&
    respostasUsuario.valor_retirada !== undefined
  ) {
    dados.valor_retirada = Number(respostasUsuario.valor_retirada || 0);
  }

  if (!dados.motivo_retirada && respostasUsuario.motivo_retirada) {
    dados.motivo_retirada = respostasUsuario.motivo_retirada;
  }

  // Se não houve retirada, padroniza os campos.
  if (dados.houve_retirada === false) {
    dados.valor_retirada = 0;
    dados.motivo_retirada = dados.motivo_retirada || "Não houve retirada";
  }

  // Regras de pendência/pergunta.
  smartSlipGarantirPergunta_(
    !dados.loja,
    resultado,
    "Loja não informada.",
    "Qual o número da loja?"
  );

  smartSlipGarantirPergunta_(
    !dados.data_movimento,
    resultado,
    "Data de movimento não informada.",
    "Qual a data do movimento desse depósito?"
  );

  smartSlipGarantirPergunta_(
    dados.houve_retirada === null || dados.houve_retirada === undefined,
    resultado,
    "Informação sobre retirada não informada.",
    "Houve alguma retirada desse movimento para estorno, reembolso no ato ou algo do tipo?"
  );

  smartSlipGarantirPergunta_(
    dados.houve_retirada === true && (!dados.valor_retirada || !dados.motivo_retirada),
    resultado,
    "Retirada informada, mas valor ou motivo da retirada está ausente.",
    "Informe o valor e o motivo da retirada."
  );

  smartSlipGarantirPergunta_(
    !dados.data_deposito,
    resultado,
    "Data do depósito não identificada.",
    "Qual a data do depósito?"
  );

  smartSlipGarantirPergunta_(
    dados.valor_deposito === null || dados.valor_deposito === undefined || dados.valor_deposito === "",
    resultado,
    "Valor do depósito não identificado.",
    "Qual o valor do depósito?"
  );

  smartSlipValidarGuardrailMovimento(resultado, dados);

  // Se houver perguntas, o status precisa ser PRECISA_COMPLEMENTO.
  if (resultado.perguntas_complementares.length > 0) {
    resultado.status = "PRECISA_COMPLEMENTO";
  }

  // Se não houver perguntas nem divergências, pode ficar pronto para salvar.
  if (
    resultado.status !== "INELEGIVEL" &&
    resultado.divergencias.length === 0 &&
    resultado.perguntas_complementares.length === 0
  ) {
    resultado.status = "PRONTO_PARA_SALVAR";
  }

  return resultado;
}

function smartSlipGarantirPergunta_(condicao, resultado, pendencia, pergunta) {
  if (!condicao) return;

  if (resultado.pendencias.indexOf(pendencia) === -1) {
    resultado.pendencias.push(pendencia);
  }

  if (resultado.perguntas_complementares.indexOf(pergunta) === -1) {
    resultado.perguntas_complementares.push(pergunta);
  }
}

function smartSlipNormalizarLoja4(loja) {
  const digits = String(loja || "").replace(/\D/g, "");

  if (!digits) {
    return "";
  }

  return digits.padStart(4, "0").slice(-4);
}

function smartSlipNormalizarEmail_(email) {
  return String(email || "").trim().toLowerCase();
}

function smartSlipUsuarioEhGestao_(usuario) {
  usuario = usuario || {};
  return usuario.is_admin === true ||
    usuario.is_analista_pro === true ||
    usuario.is_regional === true;
}

function smartSlipUsuarioEhRegional_(usuario) {
  usuario = usuario || {};
  return usuario.is_regional === true;
}

function smartSlipGetBaseOperacionalLojas_() {

  const ss =
    SpreadsheetApp.openById(
      SMARTSLIP_BASE_LOJAS_SPREADSHEET_ID
    );

  const sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_BASE_LOJAS
    );

  if (!sh) {
    throw new Error(
      "Aba BASE_LOJAS não encontrada na planilha SmartSlip."
    );
  }

  const lastRow = sh.getLastRow();

  if (lastRow < 2) {
    return [];
  }

  const lastColumn =
    Math.max(
      14,
      sh.getLastColumn()
    );

  /*
   * BASE_LOJAS
   *
   * Cabeçalho: linha 1
   * Dados: linha 2 em diante
   */
  const values =
    sh.getRange(
      1,
      1,
      lastRow,
      lastColumn
    ).getValues();

  const headers =
    values[0].map(function(header) {
      return String(
        header || ""
      ).trim();
    });


  function coluna(nomes) {
    return smartSlipEncontrarIndiceHeader_(
      headers,
      nomes
    );
  }


  const idxLoja =
    coluna([
      "Loja"
    ]);

  const idxCodigo =
    coluna([
      "Codigo",
      "Código",
      "CODIGO"
    ]);

  const idxShopping =
    coluna([
      "Shopping"
    ]);

  const idxEndereco =
    coluna([
      "Endereço",
      "Endereco"
    ]);

  const idxTime =
    coluna([
      "Time"
    ]);

  const idxGerenteRegional =
    coluna([
      "Gerente Regional"
    ]);

  const idxEmailRegional =
    coluna([
      "E-mail Regional",
      "Email Regional"
    ]);

  const idxEmailGerenteLoja =
    coluna([
      "E-mail Gerente Loja",
      "Email Gerente Loja"
    ]);

  const idxEmailSupAuto =
    coluna([
      "E-mail Sup Auto",
      "Email Sup Auto"
    ]);

  const idxEmailSupVendas =
    coluna([
      "E-mail Sup Vendas",
      "Email Sup Vendas"
    ]);

  const idxLojaReforma =
    coluna([
      "Loja em Reforma?"
    ]);

  const idxLojaEncerrada =
    coluna([
      "Loja Encerrada?"
    ]);

  const idxTipoDeposito =
    coluna([
      "Tipo de Depósito",
      "Tipo de Deposito",
      "Tipo Depósito",
      "Tipo Deposito"
    ]);

  const idxFrequenciaCarroForte =
    coluna([
      "Frequencia Carro Forte",
      "Frequência Carro Forte"
    ]);


  /*
   * Código é obrigatório.
   */
  if (idxCodigo < 0) {
    throw new Error(
      "Coluna Codigo não encontrada na BASE_LOJAS."
    );
  }


  const lojas = [];


  for (
    let i = 1;
    i < values.length;
    i++
  ) {

    const row = values[i];


    const loja4 =
      smartSlipNormalizarLoja4(
        row[idxCodigo] || ""
      );


    if (!loja4) {
      continue;
    }


    lojas.push({

      loja:
        loja4,

      identificador_loja:
        idxLoja >= 0
          ? String(
              row[idxLoja] || ""
            ).trim()
          : "",

      shopping:
        idxShopping >= 0
          ? String(
              row[idxShopping] || ""
            ).trim()
          : "",

      endereco:
        idxEndereco >= 0
          ? String(
              row[idxEndereco] || ""
            ).trim()
          : "",

      time:
        idxTime >= 0
          ? String(
              row[idxTime] || ""
            ).trim()
          : "",

      gerente_regional:
        idxGerenteRegional >= 0
          ? String(
              row[idxGerenteRegional] || ""
            ).trim()
          : "",

      email_regional:
        idxEmailRegional >= 0
          ? smartSlipNormalizarEmail_(
              row[idxEmailRegional] || ""
            )
          : "",

      email_gerente_loja:
        idxEmailGerenteLoja >= 0
          ? smartSlipNormalizarEmail_(
              row[idxEmailGerenteLoja] || ""
            )
          : "",

      email_sup_auto:
        idxEmailSupAuto >= 0
          ? smartSlipNormalizarEmail_(
              row[idxEmailSupAuto] || ""
            )
          : "",

      email_sup_vendas:
        idxEmailSupVendas >= 0
          ? smartSlipNormalizarEmail_(
              row[idxEmailSupVendas] || ""
            )
          : "",

      loja_em_reforma:
        idxLojaReforma >= 0
          ? String(
              row[idxLojaReforma] || ""
            ).trim()
          : "",

      loja_encerrada:
        idxLojaEncerrada >= 0
          ? String(
              row[idxLojaEncerrada] || ""
            ).trim()
          : "",

      tipo_deposito:
        idxTipoDeposito >= 0
          ? smartSlipNormalizarTipoDeposito_(
              row[idxTipoDeposito] || ""
            )
          : "",

      tipo_deposito_original:
        idxTipoDeposito >= 0
          ? String(
              row[idxTipoDeposito] || ""
            ).trim()
          : "",

      frequencia_carro_forte:
        idxFrequenciaCarroForte >= 0
          ? String(
              row[
                idxFrequenciaCarroForte
              ] || ""
            ).trim()
          : "",

      /*
       * i começa em 1 porque values[0]
       * é o cabeçalho.
       */
      linha_base:
        i + 1
    });
  }


  return lojas;
}

function smartSlipGetLojasRegionaisDoUsuario_(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const email = smartSlipNormalizarEmail_(usuario.email || "");

  if (!email) {
    return [];
  }

  return smartSlipGetBaseOperacionalLojas_()
    .filter(function(item) {
      return smartSlipNormalizarEmail_(item.email_regional) === email;
    })
    .sort(function(a, b) {
      return String(a.loja).localeCompare(String(b.loja));
    });
}

var SMARTSLIP_MEMO_LOJAS_PERMITIDAS_ = SMARTSLIP_MEMO_LOJAS_PERMITIDAS_ || {};

function smartSlipGetChaveMemoLojasPermitidas_(usuario) {
  usuario = usuario || {};

  return [
    String(usuario.email || "").trim().toLowerCase(),
    String(usuario.perfil || "").trim(),
    usuario.is_admin === true ? "ADMIN" : "NAO_ADMIN",
    usuario.is_analista_pro === true ? "ANALISTA_PRO" : "NAO_ANALISTA_PRO",
    usuario.is_regional === true ? "REGIONAL" : "NAO_REGIONAL",
    smartSlipNormalizarLoja4(usuario.loja_padrao || "")
  ].join("|");
}

function smartSlipGetMapaLojasPermitidasUsuario_(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const chaveMemo = smartSlipGetChaveMemoLojasPermitidas_(usuario);
  const agora = new Date().getTime();

  /*
    Cache em memória para a mesma execução/instância.
    Evita reler a aba Base centenas/milhares de vezes durante o bootstrap.
    TTL curto para não manter escopo regional antigo por muito tempo.
  */
  if (
    SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo] &&
    (agora - SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo].ts) < 120000
  ) {
    return SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo].mapa;
  }

  let mapa = {};

  if (usuario.is_admin === true || usuario.is_analista_pro === true) {
    // null = pode ver todas as lojas.
    mapa = null;

    SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo] = {
      ts: agora,
      mapa: mapa
    };

    return mapa;
  }

  if (smartSlipUsuarioEhRegional_(usuario)) {
    smartSlipGetLojasRegionaisDoUsuario_(usuario).forEach(function(item) {
      const loja4 = smartSlipNormalizarLoja4(item.loja || "");

      if (loja4) {
        mapa[loja4] = true;
      }
    });

    SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo] = {
      ts: agora,
      mapa: mapa
    };

    return mapa;
  }

  const lojaPadrao = smartSlipNormalizarLoja4(usuario.loja_padrao || "");

  if (lojaPadrao) {
    mapa[lojaPadrao] = true;
  }

  SMARTSLIP_MEMO_LOJAS_PERMITIDAS_[chaveMemo] = {
    ts: agora,
    mapa: mapa
  };

  return mapa;
}

function smartSlipUsuarioPodeVerLoja_(usuario, loja) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const loja4 = smartSlipNormalizarLoja4(loja || "");

  if (!loja4) {
    return false;
  }

  const mapa = smartSlipGetMapaLojasPermitidasUsuario_(usuario);

  if (mapa === null) {
    return true;
  }

  return mapa[loja4] === true;
}

function smartSlipNormalizarTipoDeposito_(valor) {
  const raw = String(valor || "").trim();

  if (!raw) {
    return "";
  }

  const txt = raw
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  if (txt.includes("CARRO")) {
    return "Carro Forte";
  }

  if (txt.includes("BOLETO")) {
    return "Boleto";
  }

  if (
    txt.includes("DEP") ||
    txt.includes("DEPOSITO") ||
    txt.includes("BANCARIO") ||
    txt.includes("BANC")
  ) {
    return "Dep. Bancário";
  }

  return "";
}

function smartSlipConsultarDadosOperacionaisLoja_(
  lojaInformada
) {
  const loja4Busca = smartSlipNormalizarLoja4(
    lojaInformada || ""
  );

  if (!loja4Busca) {
    return {
      ok: false,
      erro:
        "Loja não informada para consulta operacional."
    };
  }

  const lojas = smartSlipGetBaseOperacionalLojas_();

  for (let i = 0; i < lojas.length; i++) {
    const item = lojas[i];

    if (item.loja !== loja4Busca) {
      continue;
    }

    return {
      ok: true,

      loja_normalizada:
        item.loja,

      shopping:
        item.shopping || "",

      endereco:
        item.endereco || "",

      tipo_deposito:
        item.tipo_deposito || "",

      tipo_deposito_original:
        item.tipo_deposito_original || "",

      time:
        item.time || "",

      gerente_regional:
        item.gerente_regional || "",

      email_regional:
        item.email_regional || "",

      email_gerente_loja:
        item.email_gerente_loja || "",

      linha_base:
        item.linha_base || ""
    };
  }

  return {
    ok: false,
    erro:
      "Loja não encontrada na aba Base operacional.",
    loja_normalizada_tentativa:
      loja4Busca
  };
}

function smartSlipConsultarDadosOperacionaisLojaJson(lojaInformada) {
  try {
    return JSON.stringify({
      ok: true,
      payload: smartSlipConsultarDadosOperacionaisLoja_(lojaInformada)
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipGetMapaEmpresaPorLoja_() {
  const mapa = {};

  const ss = SpreadsheetApp.openById(
    SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID
  );

  const sh = ss.getSheetByName(
    SMARTSLIP_ABA_INFO_LIMITES
  );

  if (!sh || sh.getLastRow() < 2) {
    return mapa;
  }

  const values = sh.getDataRange().getValues();

  const headers = values[0].map(function(header) {
    return String(header || "").trim();
  });

  const idxLoja = smartSlipEncontrarIndiceHeader_(
    headers,
    [
      "Norm_Loja",
      "NORM_LOJA",
      "Norm Loja",
      "Loja",
      "LOJA"
    ]
  );

  let idxEmpresa = smartSlipEncontrarIndiceHeader_(
    headers,
    [
      "EMPRESA0",
      "EMPRESA",
      "Empresa"
    ]
  );

  if (idxEmpresa < 0) {
    idxEmpresa = 6;
  }

  if (idxLoja < 0) {
    return mapa;
  }

  for (let i = 1; i < values.length; i++) {
    const row = values[i];

    const loja = smartSlipNormalizarLoja4(
      row[idxLoja] || ""
    );

    if (!loja) {
      continue;
    }

    mapa[loja] = smartSlipNormalizarEmpresa_(
      row[idxEmpresa] || ""
    );
  }

  return mapa;
}

function smartSlipConverterDataInatividade_(valor) {
  if (!valor) {
    return null;
  }

  if (
    Object.prototype.toString.call(valor) ===
      "[object Date]" &&
    !isNaN(valor.getTime())
  ) {
    return new Date(valor.getTime());
  }

  const texto = String(valor || "").trim();

  let match = texto.match(
    /^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?/
  );

  if (match) {
    return new Date(
      Number(match[3]),
      Number(match[2]) - 1,
      Number(match[1]),
      Number(match[4] || 0),
      Number(match[5] || 0),
      Number(match[6] || 0)
    );
  }

  match = texto.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/
  );

  if (match) {
    return new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3]),
      Number(match[4] || 0),
      Number(match[5] || 0),
      Number(match[6] || 0)
    );
  }

  const data = new Date(texto);

  return isNaN(data.getTime())
    ? null
    : data;
}

function smartSlipCalcularDiasSemEnvio_(
  ultimoEnvio,
  dataReferencia
) {
  if (
    !(ultimoEnvio instanceof Date) ||
    isNaN(ultimoEnvio.getTime())
  ) {
    return 0;
  }

  dataReferencia =
    dataReferencia instanceof Date
      ? dataReferencia
      : new Date();

  /*
    Calcula dias civis, desconsiderando a diferença
    de horário entre o envio e a execução da rotina.
  */
  const ultimoUtc = Date.UTC(
    ultimoEnvio.getFullYear(),
    ultimoEnvio.getMonth(),
    ultimoEnvio.getDate()
  );

  const referenciaUtc = Date.UTC(
    dataReferencia.getFullYear(),
    dataReferencia.getMonth(),
    dataReferencia.getDate()
  );

  return Math.max(
    0,
    Math.floor(
      (referenciaUtc - ultimoUtc) /
      (24 * 60 * 60 * 1000)
    )
  );
}

function smartSlipValidarDiasDisparoInatividade_(
  valor,
  nomeCampo
) {
  const numero = Number(
    String(valor || "")
      .replace(",", ".")
      .trim()
  );

  if (
    !Number.isInteger(numero) ||
    numero < 1 ||
    numero > 365
  ) {
    throw new Error(
      nomeCampo +
      " deve ser um número inteiro entre 1 e 365 dias."
    );
  }

  return numero;
}

function smartSlipGetConfigInatividade_() {
  if (SMARTSLIP_MEMO_CONFIG_INATIVIDADE_) {
    return Object.assign(
      {},
      SMARTSLIP_MEMO_CONFIG_INATIVIDADE_
    );
  }

  const properties =
    PropertiesService.getScriptProperties();

  function lerDias(
    nomePropriedade,
    valorPadrao
  ) {
    const raw =
      properties.getProperty(
        nomePropriedade
      );

    const numero =
      Number(raw);

    if (
      !Number.isInteger(numero) ||
      numero < 1 ||
      numero > 365
    ) {
      return valorPadrao;
    }

    return numero;
  }

  const config = {
    boleto:
      lerDias(
        SMARTSLIP_INATIVIDADE_PROP_BOLETO,
        SMARTSLIP_INATIVIDADE_PADRAO_BOLETO
      ),

    dep_bancario:
      lerDias(
        SMARTSLIP_INATIVIDADE_PROP_DEP_BANCARIO,
        SMARTSLIP_INATIVIDADE_PADRAO_DEP_BANCARIO
      ),

    carro_forte:
      lerDias(
        SMARTSLIP_INATIVIDADE_PROP_CARRO_FORTE,
        SMARTSLIP_INATIVIDADE_PADRAO_CARRO_FORTE
      ),

    atualizado_por:
      String(
        properties.getProperty(
          SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_POR
        ) || ""
      ).trim(),

    atualizado_em:
      String(
        properties.getProperty(
          SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_EM
        ) || ""
      ).trim()
  };

  SMARTSLIP_MEMO_CONFIG_INATIVIDADE_ =
    config;

  return Object.assign(
    {},
    config
  );
}

function smartSlipSalvarConfigInatividade_(
  dados
) {
  smartSlipAssertUsuarioAutorizado_();

  const usuario =
    smartSlipGetUsuarioAtual();

  const podeConfigurar =
    usuario.is_admin === true ||
    usuario.is_analista_pro === true;

  if (!podeConfigurar) {
    throw new Error(
      "Apenas Administrador ou Analista Pro pode alterar os parâmetros de inatividade."
    );
  }

  dados = dados || {};

  const config = {
    boleto:
      smartSlipValidarDiasDisparoInatividade_(
        dados.boleto,
        "O prazo de Boleto"
      ),

    dep_bancario:
      smartSlipValidarDiasDisparoInatividade_(
        dados.dep_bancario,
        "O prazo de Depósito Bancário"
      ),

    carro_forte:
      smartSlipValidarDiasDisparoInatividade_(
        dados.carro_forte,
        "O prazo de Carro Forte"
      )
  };

  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  const atualizadoEm =
    Utilities.formatDate(
      new Date(),
      timezone,
      "dd/MM/yyyy HH:mm:ss"
    );

  const atualizadoPor =
    String(
      usuario.email ||
      Session.getActiveUser().getEmail() ||
      ""
    )
      .trim()
      .toLowerCase();

  const properties =
    PropertiesService.getScriptProperties();

  const valores = {};

  valores[
    SMARTSLIP_INATIVIDADE_PROP_BOLETO
  ] = String(config.boleto);

  valores[
    SMARTSLIP_INATIVIDADE_PROP_DEP_BANCARIO
  ] = String(config.dep_bancario);

  valores[
    SMARTSLIP_INATIVIDADE_PROP_CARRO_FORTE
  ] = String(config.carro_forte);

  valores[
    SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_POR
  ] = atualizadoPor;

  valores[
    SMARTSLIP_INATIVIDADE_PROP_ATUALIZADO_EM
  ] = atualizadoEm;

  properties.setProperties(
    valores,
    false
  );

  SMARTSLIP_MEMO_CONFIG_INATIVIDADE_ = {
    boleto:
      config.boleto,

    dep_bancario:
      config.dep_bancario,

    carro_forte:
      config.carro_forte,

    atualizado_por:
      atualizadoPor,

    atualizado_em:
      atualizadoEm
  };

  return Object.assign(
    {},
    SMARTSLIP_MEMO_CONFIG_INATIVIDADE_
  );
}

function smartSlipGetLimiteInatividadePorTipo_(
  tipoDeposito
) {
  const tipo =
    smartSlipNormalizarTipoDeposito_(
      tipoDeposito
    );

  const config =
    smartSlipGetConfigInatividade_();

  if (tipo === "Boleto") {
    return config.boleto;
  }

  if (tipo === "Dep. Bancário") {
    return config.dep_bancario;
  }

  if (tipo === "Carro Forte") {
    return config.carro_forte;
  }

  return null;
}

function smartSlipClassificarInatividade_(
  tipoDeposito,
  diasSemEnvio
) {
  const limite =
    smartSlipGetLimiteInatividadePorTipo_(
      tipoDeposito
    );

  if (limite === null) {
    return "SEM_CRITERIO";
  }

  const dias =
    Number(diasSemEnvio || 0);

  /*
    O valor configurado representa exatamente
    o primeiro dia em que o alerta será crítico.
  */
  if (dias >= limite) {
    return "CRITICO";
  }

  /*
    Um dia antes do disparo, a loja entra
    em status de atenção.
  */
  if (
    limite > 1 &&
    dias === limite - 1
  ) {
    return "ATENCAO";
  }

  return "NORMAL";
}

function smartSlipGetConfigInatividadeAppJson() {
  try {
    smartSlipAssertUsuarioAutorizado_();

    const usuario =
      smartSlipGetUsuarioAtual();

    const podeConfigurar =
      usuario.is_admin === true ||
      usuario.is_analista_pro === true;

    if (!podeConfigurar) {
      throw new Error(
        "Acesso restrito a Administrador e Analista Pro."
      );
    }

    return JSON.stringify({
      ok: true,
      payload:
        smartSlipGetConfigInatividade_()
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(
        err && err.message
          ? err.message
          : err
      )
    });
  }
}

function smartSlipSalvarConfigInatividadeAppJson(
  dadosJson
) {
  try {
    smartSlipAssertUsuarioAutorizado_();

    let dados = dadosJson || {};

    if (typeof dadosJson === "string") {
      dados = JSON.parse(
        dadosJson || "{}"
      );
    }

    return JSON.stringify({
      ok: true,
      payload:
        smartSlipSalvarConfigInatividade_(
          dados
        )
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(
        err && err.message
          ? err.message
          : err
      )
    });
  }
}

function smartSlipMontarInatividadeLojas_(
  usuario,
  aplicarEscopoUsuario
) {
  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  const agora = new Date();

  const baseOperacional =
    smartSlipGetBaseOperacionalLojas_();

  const mapaBase = {};

  baseOperacional.forEach(function(item) {
    const loja = smartSlipNormalizarLoja4(
      item.loja || ""
    );

    if (loja) {
      mapaBase[loja] = item;
    }
  });

  const mapaEmpresa =
    smartSlipGetMapaEmpresaPorLoja_();

  const ss = SpreadsheetApp.openById(
    SMARTSLIP_DB_SPREADSHEET_ID
  );

  const sh = ss.getSheetByName(
    SMARTSLIP_ABA_FILA
  );

  const mapaUltimoEnvio = {};

  /*
    Somente lojas que já possuem registro na fila.
  */
  if (sh && sh.getLastRow() >= 2) {
    const lastColumn = Math.max(
      16,
      sh.getLastColumn()
    );

    const values = sh
      .getRange(
        2,
        1,
        sh.getLastRow() - 1,
        lastColumn
      )
      .getValues();

values.forEach(function(row) {

  /*
    REGRA SMARTSLIP:
    Para o monitoramento de inatividade,
    somente um comprovante efetivamente
    processado com Status Fila = SALVO
    pode ser considerado como envio válido.

    Portanto, NÃO atualizam o último envio:
    - RECEBIDO
    - PROCESSANDO
    - PENDENTE_INTERNO
    - SALVO_PARCIAL
    - ERRO_PROCESSAMENTO
    - EXCLUIDO
    - qualquer outro status diferente de SALVO

    Isso evita que uma tentativa de envio
    que não foi concluída zere os dias
    sem envio da loja.
  */
  const statusFila = String(
    row[13] || ""
  )
    .trim()
    .toUpperCase();

  if (statusFila !== "SALVO") {
    return;
  }

  const loja = smartSlipNormalizarLoja4(
    row[3] || ""
  );

  if (!loja) {
    return;
  }

      if (
        aplicarEscopoUsuario === true &&
        usuario &&
        !smartSlipUsuarioPodeVerLoja_(
          usuario,
          loja
        )
      ) {
        return;
      }

      const dataRegistro =
        smartSlipConverterDataInatividade_(
          row[0]
        );

      if (!dataRegistro) {
        return;
      }

      const anterior =
        mapaUltimoEnvio[loja];

      if (
        !anterior ||
        dataRegistro.getTime() >
          anterior.data.getTime()
      ) {
        mapaUltimoEnvio[loja] = {
          data: dataRegistro,
          respostas:
            smartSlipParseJsonSeguro_(
              row[15]
            )
        };
      }
    });
  }

  const rows = Object.keys(mapaUltimoEnvio)
    .map(function(loja) {
      const registro =
        mapaUltimoEnvio[loja];

      const dadosBase =
        mapaBase[loja] || {};

      const respostas =
        registro.respostas || {};

      const tipoDeposito =
        smartSlipNormalizarTipoDeposito_(
          dadosBase.tipo_deposito ||
          respostas.tipo_deposito ||
          ""
        );

      const diasSemEnvio =
        smartSlipCalcularDiasSemEnvio_(
          registro.data,
          agora
        );

      const limiteDias =
        smartSlipGetLimiteInatividadePorTipo_(
          tipoDeposito
        );

      const status =
        smartSlipClassificarInatividade_(
          tipoDeposito,
          diasSemEnvio
        );

      const empresa =
        mapaEmpresa[loja] ||
        smartSlipNormalizarEmpresa_(
          respostas.empresa || ""
        );

      const lojaExibicao =
        empresa === "Empresa A"
          ? "CE" + loja
          : loja;

      return {
        loja: loja,
        loja_exibicao: lojaExibicao,
        empresa: empresa,

        shopping: String(
          dadosBase.shopping || ""
        ).trim(),

        time: String(
          dadosBase.time ||
          respostas.time ||
          ""
        ).trim(),

        tipo_deposito:
          tipoDeposito,

        limite_dias:
          limiteDias,

        dias_sem_envio:
          diasSemEnvio,

        status:
          status,

        ultimo_envio:
          Utilities.formatDate(
            registro.data,
            timezone,
            "dd/MM/yyyy HH:mm"
          ),

        ultimo_envio_iso:
          Utilities.formatDate(
            registro.data,
            timezone,
            "yyyy-MM-dd'T'HH:mm:ss"
          ),

        gerente_regional: String(
          dadosBase.gerente_regional ||
          respostas.gerente_regional ||
          ""
        ).trim(),

        email_regional:
          smartSlipNormalizarEmail_(
            dadosBase.email_regional ||
            respostas.email_regional ||
            ""
          ),

        email_gerente_loja:
          smartSlipNormalizarEmail_(
            dadosBase.email_gerente_loja ||
            ""
          ),

        alerta_elegivel:
          status === "CRITICO"
      };
    })
    .sort(function(a, b) {
      const diferenca =
        Number(b.dias_sem_envio || 0) -
        Number(a.dias_sem_envio || 0);

      if (diferenca !== 0) {
        return diferenca;
      }

      return String(a.loja || "")
        .localeCompare(
          String(b.loja || "")
        );
    });

  return {
    atualizado_em:
      Utilities.formatDate(
        agora,
        timezone,
        "dd/MM/yyyy HH:mm"
      ),

    atualizado_hora:
      Utilities.formatDate(
        agora,
        timezone,
        "HH:mm"
      ),

    total_lojas:
      rows.length,

    total_criticas:
      rows.filter(function(item) {
        return item.status === "CRITICO";
      }).length,

    rows: rows
  };
}

function smartSlipGetInatividadeLojas(usuario) {
  usuario =
    usuario ||
    smartSlipGetUsuarioAtual();

  return smartSlipMontarInatividadeLojas_(
    usuario,
    true
  );
}

function smartSlipPrimeiroNomePessoa_(nome) {
  const primeiro = String(nome || "")
    .trim()
    .split(/\s+/)[0] || "Regional";

  return primeiro.charAt(0).toUpperCase() +
    primeiro.slice(1).toLowerCase();
}

function smartSlipEscaparHtmlEmail_(valor) {
  return String(valor || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function smartSlipIdentificadorLojaAlerta_(item) {
  item = item || {};

  const loja = smartSlipNormalizarLoja4(
    item.loja || ""
  );

  if (item.empresa === "Empresa A") {
    return "CE" + loja;
  }

  return loja;
}

function smartSlipMontarTextoAlertaInatividade_(item) {
  const regional =
    smartSlipPrimeiroNomePessoa_(
      item.gerente_regional
    );

  const loja =
    smartSlipIdentificadorLojaAlerta_(
      item
    );

  return [
    regional + ", bom dia!",
    "",
    "Este é um alerta automático do SmartSlip, gerado pela rotina de monitoramento com apoio de Inteligência Artificial.",
    "",
    "A loja " +
      loja +
      " está há " +
      item.dias_sem_envio +
      " dia(s) sem comprovante processado com sucesso pelo SmartSlip.",
    "",
    "Tipo de depósito: " +
      (
        item.tipo_deposito ||
        "Não identificado"
      ),
    "Último envio registrado: " +
      (
        item.ultimo_envio ||
        "Não identificado"
      ),
    "",
    "Solicitamos verificar o envio o mais rápido possível, para que a ausência dos comprovantes não prejudique o processo de conciliação financeira.",
    "",
    "Acesse o SmartSlip pela plataforma corporativa.",
    "",
    "Atenciosamente,",
    "Vektor - Empresa Exemplo"
  ].join("\n");
}

function smartSlipMontarHtmlAlertaInatividade_(
  item
) {
  const regional =
    smartSlipEscaparHtmlEmail_(
      smartSlipPrimeiroNomePessoa_(
        item.gerente_regional
      )
    );

  const loja =
    smartSlipEscaparHtmlEmail_(
      smartSlipIdentificadorLojaAlerta_(
        item
      )
    );

  const tipo =
    smartSlipEscaparHtmlEmail_(
      item.tipo_deposito ||
      "Não identificado"
    );

  const ultimoEnvio =
    smartSlipEscaparHtmlEmail_(
      item.ultimo_envio ||
      "Não identificado"
    );

  const dias =
    Number(item.dias_sem_envio || 0);

  return `
    <div style="
      margin:0;
      padding:24px;
      background:#f4f7f2;
      font-family:Arial,sans-serif;
    ">
      <div style="
        max-width:680px;
        margin:0 auto;
        background:#ffffff;
        border:1px solid #d9e5d4;
        border-radius:18px;
        overflow:hidden;
        box-shadow:0 14px 34px rgba(0,0,0,.08);
      ">
        <div style="
          padding:22px 26px;
          background:#050807;
          border-bottom:4px solid #B5FF20;
        ">
          <div style="
            color:#B5FF20;
            font-size:12px;
            font-weight:800;
            text-transform:uppercase;
            letter-spacing:.5px;
          ">
            Alerta automático SmartSlip
          </div>

          <div style="
            margin-top:7px;
            color:#ffffff;
            font-size:22px;
            font-weight:800;
          ">
            Loja sem envio de comprovante
          </div>
        </div>

        <div style="padding:26px;">
          <p style="
            margin:0 0 18px;
            color:#17211b;
            font-size:16px;
          ">
            <strong>${regional}, bom dia!</strong>
          </p>

          <p style="
            margin:0 0 18px;
            color:#475467;
            font-size:14px;
            line-height:1.6;
          ">
            Este é um alerta automático do SmartSlip,
            gerado pela rotina de monitoramento com apoio
            de Inteligência Artificial.
          </p>

          <div style="
            margin:20px 0;
            padding:18px;
            background:#fff1f0;
            border:1px solid #fecdca;
            border-radius:14px;
          ">
            <div style="
              color:#b42318;
              font-size:14px;
              font-weight:800;
            ">
              A loja ${loja} está há ${dias}
              dia(s) sem enviar comprovantes.
            </div>
          </div>

          <table style="
            width:100%;
            border-collapse:collapse;
            margin:18px 0;
          ">
            <tr>
              <td style="
                width:180px;
                padding:11px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:13px;
                font-weight:700;
              ">
                Loja
              </td>

              <td style="
                padding:11px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${loja}
              </td>
            </tr>

            <tr>
              <td style="
                padding:11px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:13px;
                font-weight:700;
              ">
                Tipo de depósito
              </td>

              <td style="
                padding:11px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${tipo}
              </td>
            </tr>

            <tr>
              <td style="
                padding:11px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:13px;
                font-weight:700;
              ">
                Último envio
              </td>

              <td style="
                padding:11px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${ultimoEnvio}
              </td>
            </tr>
          </table>

<p style="
  margin:20px 0 0;
  color:#34443a;
  font-size:14px;
  line-height:1.65;
">
  Solicitamos verificar o envio o mais rápido
  possível, para que a ausência dos comprovantes
  não prejudique o processo de conciliação
  financeira.
</p>

<div style="
  width:100%;
  height:1px;
  margin:22px 0;
  background:#dfe8db;
"></div>

<div style="
  text-align:center;
">
  <p style="
    margin:0 0 12px;
    color:#475467;
    font-size:13px;
    line-height:1.5;
  ">
    Acesse diretamente a plataforma para verificar
    e regularizar o envio:
  </p>

  <a
    href="${smartSlipEscaparHtmlEmail_(SMARTSLIP_URL_ACESSO)}"
    target="_blank"
    style="
      display:inline-block;
      padding:13px 22px;
      background:#050807;
      color:#B5FF20;
      border:1px solid #B5FF20;
      border-radius:10px;
      text-decoration:none;
      font-size:14px;
      font-weight:800;
    "
  >
    Acessar o SmartSlip
  </a>
</div>
        </div>

        <div style="
          padding:16px 26px;
          background:#005E27;
          color:#ffffff;
          font-size:12px;
        ">
          Vektor - Empresa Exemplo · Monitoramento SmartSlip
        </div>
      </div>
    </div>
  `;
}

function smartSlipLimparControlesAlertasAntigos_(
  properties,
  chaveHoje
) {
  const todas = properties.getProperties();

  const prefixoHoje =
    SMARTSLIP_ALERTA_INATIVIDADE_PREFIXO_PROP +
    chaveHoje +
    "_";

  Object.keys(todas).forEach(function(chave) {
    if (
      chave.indexOf(
        SMARTSLIP_ALERTA_INATIVIDADE_PREFIXO_PROP
      ) !== 0
    ) {
      return;
    }

    if (chave.indexOf(prefixoHoje) === 0) {
      return;
    }

    properties.deleteProperty(chave);
  });
}

function smartSlipCodificarAssuntoUtf8_(texto) {
  const caracteres = Array.from(
    String(texto || "")
  );

  const blocos = [];
  let blocoAtual = "";

  caracteres.forEach(function(caractere) {
    const candidato =
      blocoAtual + caractere;

    const quantidadeBytes =
      Utilities
        .newBlob(candidato)
        .getBytes()
        .length;

    /*
      Mantém cada bloco RFC 2047 dentro
      de um tamanho seguro.
    */
    if (
      quantidadeBytes > 42 &&
      blocoAtual
    ) {
      blocos.push(blocoAtual);
      blocoAtual = caractere;
    } else {
      blocoAtual = candidato;
    }
  });

  if (blocoAtual) {
    blocos.push(blocoAtual);
  }

  return blocos
    .map(function(bloco) {
      const base64 =
        Utilities.base64Encode(
          bloco,
          Utilities.Charset.UTF_8
        );

      return (
        "=?UTF-8?B?" +
        base64 +
        "?="
      );
    })
    .join("\r\n ");
}

function smartSlipQuebrarBase64Mime_(base64) {
  const partes = String(base64 || "")
    .match(/.{1,76}/g);

  return partes
    ? partes.join("\r\n")
    : "";
}

function smartSlipEnviarEmailUtf8_(opcoes) {
  opcoes = opcoes || {};

  const destinatario = String(
    opcoes.to || ""
  ).trim();

  const copia = String(
    opcoes.cc || ""
  ).trim();

  const remetente = String(
    opcoes.from ||
    "operacao@empresa.com.br"
  ).trim();

  const nomeRemetente = String(
    opcoes.name ||
    "Vektor - Empresa Exemplo"
  ).trim();

  const assunto = String(
    opcoes.subject || ""
  );

  const corpoTexto = String(
    opcoes.textBody || " "
  );

  const corpoHtml = String(
    opcoes.htmlBody || ""
  );

  if (!destinatario) {
    throw new Error(
      "Destinatário não informado."
    );
  }

  if (!assunto) {
    throw new Error(
      "Assunto não informado."
    );
  }

  const boundary =
    "smartslip_" +
    Utilities
      .getUuid()
      .replace(/-/g, "");

  const assuntoCodificado =
    smartSlipCodificarAssuntoUtf8_(
      assunto
    );

  const textoBase64 =
    smartSlipQuebrarBase64Mime_(
      Utilities.base64Encode(
        corpoTexto,
        Utilities.Charset.UTF_8
      )
    );

  const htmlBase64 =
    smartSlipQuebrarBase64Mime_(
      Utilities.base64Encode(
        corpoHtml,
        Utilities.Charset.UTF_8
      )
    );

  const cabecalhos = [
    "From: " +
      nomeRemetente +
      " <" +
      remetente +
      ">",

    "To: " + destinatario
  ];

  if (copia) {
    cabecalhos.push(
      "Cc: " + copia
    );
  }

  cabecalhos.push(
    "Subject: " + assuntoCodificado
  );

  cabecalhos.push(
    "MIME-Version: 1.0"
  );

  cabecalhos.push(
    'Content-Type: multipart/alternative; boundary="' +
      boundary +
      '"'
  );

  const mensagemMime = [
    cabecalhos.join("\r\n"),
    "",

    "--" + boundary,
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    textoBase64,
    "",

    "--" + boundary,
    "Content-Type: text/html; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    htmlBase64,
    "",

    "--" + boundary + "--",
    ""
  ].join("\r\n");

  const mensagemRaw =
    Utilities
      .base64EncodeWebSafe(
        mensagemMime,
        Utilities.Charset.UTF_8
      )
      .replace(/=+$/g, "");

  return Gmail.Users.Messages.send(
    {
      raw: mensagemRaw
    },
    "me"
  );
}

function smartSlipStatusAvisoFalhaExibicao_(
  statusFila
) {
  const status = String(
    statusFila || ""
  )
    .trim()
    .toUpperCase();

  if (status === "SALVO_PARCIAL") {
    return "Processado parcialmente";
  }

  if (status === "PENDENTE_INTERNO") {
    return "Não processado";
  }

  if (status === "ERRO_PROCESSAMENTO") {
    return "Erro no processamento";
  }

  return status || "Não processado";
}


function smartSlipMotivoAvisoFalhaUsuario_(
  statusFila,
  mensagem,
  resultado
) {
  const status = String(
    statusFila || ""
  )
    .trim()
    .toUpperCase();

  let texto = String(
    mensagem || ""
  ).trim();

  /*
    Erro técnico não deve ser exposto
    diretamente para a loja.
  */
  if (status === "ERRO_PROCESSAMENTO") {
    return (
      "O SmartSlip encontrou uma falha durante " +
      "o processamento do comprovante e não " +
      "conseguiu concluir o salvamento. " +
      "Faça um novo envio do documento."
    );
  }

  /*
    SALVO_PARCIAL possui os detalhes das
    pendências dentro do retorno do processamento.
  */
if (status === "SALVO_PARCIAL") {

  let detalhes = "";

  if (
    resultado &&
    Array.isArray(resultado.pendencias) &&
    resultado.pendencias.length
  ) {
    detalhes =
      " Detalhes identificados: " +
      resultado.pendencias.join(" | ");
  }

  return (
    "O comprovante foi processado apenas parcialmente, " +
    "pois a IA não conseguiu realizar a leitura completa " +
    "do documento com segurança." +
    detalhes +
    " Para corrigir, acesse o Histórico do SmartSlip, " +
    "exclua este comprovante e faça um novo envio com " +
    "o documento totalmente legível, sem cortes, borrões " +
    "ou informações encobertas."
  );
}

  if (!texto) {
    return (
      "Não foi possível realizar a leitura e " +
      "validação do comprovante com segurança."
    );
  }

  /*
    Traduz termos internos para algo
    compreensível para o usuário.
  */
  texto = texto
    .replace(
      /BASE_SMARTSLIP/gi,
      "base do SmartSlip"
    )
    .replace(
      /valida[cç][aã]o anti-alucina[cç][aã]o/gi,
      "validação automática de segurança da IA"
    )
    .replace(
      /anti-alucina[cç][aã]o/gi,
      "segurança da leitura por IA"
    );

  return texto;
}


function smartSlipFormatarLojaAvisoFalha_(
  loja
) {
  const loja4 =
    smartSlipNormalizarLoja4(
      loja || ""
    );

  if (!loja4) {
    return "Não identificada";
  }

  try {
    const info =
      smartSlipConsultarInfoLoja_(
        loja4
      );

    if (
      info &&
      info.ok === true &&
      info.empresa === "Empresa A"
    ) {
      return "CE" + loja4;
    }

  } catch (err) {
    Logger.log(
      "Não foi possível identificar empresa da loja no aviso: " +
      String(
        err && err.message
          ? err.message
          : err
      )
    );
  }

  return loja4;
}

function smartSlipMontarTextoAvisoFalha_(
  dados
) {
  dados = dados || {};


  const problemaDocumental =
    dados.problema_documental === true;


  const tipoProblema =
    String(
      dados.tipo_problema || ""
    )
      .trim()
      .toUpperCase();


  /*
    A orientação agora é definida pela
    origem real do problema, e não apenas
    pelo Status_Fila.
  */
  let orientacao = "";


  if (problemaDocumental) {

    orientacao =
      "Para regularizar este envio, acesse o comprovante no Histórico do SmartSlip, " +
      "exclua o registro com problema e, em seguida, realize um novo envio " +
      "utilizando um comprovante completo, legível e sem informações encobertas.";

  } else if (
    tipoProblema === "FALHA_TECNICA" ||
    tipoProblema === "FALHA_INTERNA"
  ) {

    orientacao =
      "O processamento não pôde ser concluído por uma ocorrência técnica do SmartSlip. " +
      "Você pode realizar uma nova tentativa de envio. " +
      "Não é necessário excluir o comprovante anterior para continuar.";

  } else {

    orientacao =
      "O processamento deste envio não pôde ser concluído. " +
      "Você pode acessar o SmartSlip e realizar uma nova tentativa de envio.";

  }


  const textoAcao =
    String(
      dados.texto_botao ||
      (
        problemaDocumental
          ? "Acessar comprovante e excluir"
          : "Tentar novo envio no SmartSlip"
      )
    ).trim();


  return [
    "Olá, " +
      (
        dados.primeiro_nome ||
        "tudo bem"
      ) +
      "!",

    "",

    "Identificamos que um comprovante enviado por você não pôde ser concluído no SmartSlip.",

    "",

    "DETALHES DO ENVIO",

    "",

    "Loja: " +
      (
        dados.loja_exibicao ||
        "-"
      ),

    "Protocolo: " +
      (
        dados.protocolo ||
        "-"
      ),

    "Data do envio: " +
      (
        dados.data_envio ||
        "-"
      ),

    "Arquivo: " +
      (
        dados.nome_arquivo ||
        "-"
      ),

    "Status: " +
      (
        dados.status_exibicao ||
        "Não processado"
      ),

    "",

    "MOTIVO",

    "",

    dados.motivo ||
      "Não foi possível concluir o processamento.",

    "",

    dados.link_comprovante
      ? (
          "Abrir comprovante enviado: " +
          dados.link_comprovante
        )
      : "",

    "",

    "ORIENTAÇÃO",

    "",

    orientacao,

    "",

    textoAcao + ":",

    dados.url_reenvio ||
      SMARTSLIP_URL_ACESSO,

    "",

    "Este é um aviso automático do SmartSlip.",

    "",

    "Vektor | Empresa Exemplo",
    "Contas a Receber"

  ]
    .filter(function(item) {
      return (
        item !== null &&
        item !== undefined
      );
    })
    .join("\n");
}

function smartSlipMontarHtmlAvisoFalha_(
  dados
) {
  dados = dados || {};


  const problemaDocumental =
    dados.problema_documental === true;


  const tipoProblema =
    String(
      dados.tipo_problema || ""
    )
      .trim()
      .toUpperCase();


  const ehFalhaTecnica =
    tipoProblema === "FALHA_TECNICA" ||
    tipoProblema === "FALHA_INTERNA";


  const primeiroNome =
    smartSlipEscaparHtmlEmail_(
      dados.primeiro_nome ||
      "Olá"
    );


  const loja =
    smartSlipEscaparHtmlEmail_(
      dados.loja_exibicao ||
      "-"
    );


  const protocolo =
    smartSlipEscaparHtmlEmail_(
      dados.protocolo ||
      "-"
    );


  const dataEnvio =
    smartSlipEscaparHtmlEmail_(
      dados.data_envio ||
      "-"
    );


  const nomeArquivo =
    smartSlipEscaparHtmlEmail_(
      dados.nome_arquivo ||
      "-"
    );


  const status =
    smartSlipEscaparHtmlEmail_(
      dados.status_exibicao ||
      "Não processado"
    );


  const motivo =
    smartSlipEscaparHtmlEmail_(
      dados.motivo ||
      "Não foi possível concluir o processamento."
    );


  const linkComprovante =
    smartSlipEscaparHtmlEmail_(
      dados.link_comprovante ||
      ""
    );


  const urlReenvio =
    smartSlipEscaparHtmlEmail_(
      dados.url_reenvio ||
      SMARTSLIP_URL_ACESSO
    );


  const textoBotao =
    smartSlipEscaparHtmlEmail_(
      dados.texto_botao ||
      (
        problemaDocumental
          ? "Acessar comprovante e excluir"
          : "Tentar novo envio no SmartSlip"
      )
    );


  /*
    Texto principal do alerta visual.
  */
  let tituloFaixa =
    "SmartSlip | Atenção";


  let tituloEmail =
    "Comprovante não processado";


  let avisoDestaque =
    "O processamento deste envio não foi concluído.";


  let orientacao =
    "Você pode acessar o SmartSlip e realizar uma nova tentativa de envio.";


  let corAvisoFundo =
    "#fff7e6";


  let corAvisoBorda =
    "#fedf89";


  let corAvisoTexto =
    "#8a4b08";


  let corMotivoFundo =
    "#fff7e6";


  let corMotivoBorda =
    "#fedf89";


  let corMotivoTitulo =
    "#8a4b08";


  let corMotivoTexto =
    "#693108";


  /*
    Problema no comprovante:
    usuário deve revisar, excluir e reenviar.
  */
  if (problemaDocumental) {

    tituloFaixa =
      "SmartSlip | Regularização necessária";


    tituloEmail =
      "Comprovante não processado";


    avisoDestaque =
      "O comprovante anterior precisa ser regularizado.";


    orientacao =
      "Para regularizar este envio, acesse o comprovante no Histórico do SmartSlip, " +
      "<strong>exclua o registro com problema</strong> e depois realize um novo envio " +
      "utilizando um documento completo, legível e sem informações encobertas.";


    corAvisoFundo =
      "#fff7e6";


    corAvisoBorda =
      "#fedf89";


    corAvisoTexto =
      "#8a4b08";


    corMotivoFundo =
      "#fff1f0";


    corMotivoBorda =
      "#fecdca";


    corMotivoTitulo =
      "#b42318";


    corMotivoTexto =
      "#7a271a";

  }


  /*
    Falha técnica:
    não atribuir responsabilidade à loja
    e não orientar exclusão.
  */
  else if (ehFalhaTecnica) {

    tituloFaixa =
      "SmartSlip | Ocorrência técnica";


    tituloEmail =
      "Processamento não concluído";


    avisoDestaque =
      "O SmartSlip encontrou uma ocorrência técnica durante o processamento.";


    orientacao =
      "Você pode realizar uma nova tentativa de envio. " +
      "<strong>Não é necessário excluir o comprovante anterior</strong> para continuar.";


    corAvisoFundo =
      "#eff8ff";


    corAvisoBorda =
      "#b2ddff";


    corAvisoTexto =
      "#175cd3";


    corMotivoFundo =
      "#eff8ff";


    corMotivoBorda =
      "#b2ddff";


    corMotivoTitulo =
      "#175cd3";


    corMotivoTexto =
      "#1849a9";

  }


  const blocoComprovante =
    linkComprovante
      ? `
        <div style="
          margin-top:18px;
          text-align:center;
        ">
          <a
            href="${linkComprovante}"
            target="_blank"
            style="
              display:inline-block;
              padding:11px 18px;
              background:#ffffff;
              color:#005E27;
              border:1px solid #005E27;
              border-radius:9px;
              text-decoration:none;
              font-size:13px;
              font-weight:800;
            "
          >
            Abrir comprovante enviado
          </a>
        </div>
      `
      : "";


  return `
    <div style="
      margin:0;
      padding:24px;
      background:#f4f7f2;
      font-family:Arial,sans-serif;
    ">

      <div style="
        max-width:680px;
        margin:0 auto;
        background:#ffffff;
        border:1px solid #d9e5d4;
        border-radius:18px;
        overflow:hidden;
        box-shadow:0 14px 34px rgba(0,0,0,.08);
      ">


        <!-- CABEÇALHO -->

        <div style="
          padding:22px 26px;
          background:#050807;
          border-bottom:4px solid #B5FF20;
        ">

          <div style="
            color:#B5FF20;
            font-size:12px;
            font-weight:800;
            text-transform:uppercase;
            letter-spacing:.5px;
          ">
            ${tituloFaixa}
          </div>


          <div style="
            margin-top:7px;
            color:#ffffff;
            font-size:22px;
            font-weight:800;
          ">
            ${tituloEmail}
          </div>

        </div>


        <!-- CONTEÚDO -->

        <div style="
          padding:26px;
        ">

          <p style="
            margin:0 0 18px;
            color:#17211b;
            font-size:16px;
          ">
            <strong>
              Olá, ${primeiroNome}!
            </strong>
          </p>


          <p style="
            margin:0 0 20px;
            color:#475467;
            font-size:14px;
            line-height:1.6;
          ">
            Identificamos que um comprovante enviado
            por você <strong>não pôde ter o processamento
            concluído no SmartSlip</strong>.
          </p>


          <!-- ALERTA PRINCIPAL -->

          <div style="
            margin-bottom:18px;
            padding:14px 16px;
            background:${corAvisoFundo};
            border:1px solid ${corAvisoBorda};
            border-radius:12px;
            color:${corAvisoTexto};
            font-size:13px;
            line-height:1.5;
            font-weight:800;
          ">
            ${avisoDestaque}
          </div>


          <!-- DETALHES -->

          <div style="
            margin:0 0 9px;
            color:#17211b;
            font-size:12px;
            font-weight:900;
            text-transform:uppercase;
            letter-spacing:.3px;
          ">
            Detalhes do envio
          </div>


          <table style="
            width:100%;
            border-collapse:collapse;
          ">

            <tr>

              <td style="
                width:165px;
                padding:10px 12px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:12px;
                font-weight:800;
              ">
                Loja
              </td>

              <td style="
                padding:10px 12px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${loja}
              </td>

            </tr>


            <tr>

              <td style="
                padding:10px 12px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:12px;
                font-weight:800;
              ">
                Protocolo
              </td>

              <td style="
                padding:10px 12px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${protocolo}
              </td>

            </tr>


            <tr>

              <td style="
                padding:10px 12px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:12px;
                font-weight:800;
              ">
                Data do envio
              </td>

              <td style="
                padding:10px 12px;
                border:1px solid #e0e9dc;
                font-size:13px;
              ">
                ${dataEnvio}
              </td>

            </tr>


            <tr>

              <td style="
                padding:10px 12px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:12px;
                font-weight:800;
              ">
                Arquivo
              </td>

              <td style="
                padding:10px 12px;
                border:1px solid #e0e9dc;
                font-size:13px;
                word-break:break-word;
              ">
                ${nomeArquivo}
              </td>

            </tr>


            <tr>

              <td style="
                padding:10px 12px;
                background:#f7faf5;
                border:1px solid #e0e9dc;
                font-size:12px;
                font-weight:800;
              ">
                Status
              </td>

              <td style="
                padding:10px 12px;
                border:1px solid #e0e9dc;
                font-size:13px;
                color:${corMotivoTitulo};
                font-weight:800;
              ">
                ${status}
              </td>

            </tr>

          </table>


          <!-- COMPROVANTE -->

          ${blocoComprovante}


          <!-- MOTIVO -->

          <div style="
            margin-top:22px;
            padding:17px;
            border-radius:12px;
            background:${corMotivoFundo};
            border:1px solid ${corMotivoBorda};
          ">

            <div style="
              margin-bottom:8px;
              color:${corMotivoTitulo};
              font-size:12px;
              font-weight:900;
              text-transform:uppercase;
            ">
              Motivo
            </div>


            <div style="
              color:${corMotivoTexto};
              font-size:14px;
              line-height:1.55;
              font-weight:650;
            ">
              ${motivo}
            </div>

          </div>


          <!-- ORIENTAÇÃO -->

          <div style="
            margin-top:22px;
          ">

            <div style="
              margin-bottom:7px;
              color:#17211b;
              font-size:12px;
              font-weight:900;
              text-transform:uppercase;
              letter-spacing:.3px;
            ">
              Orientação
            </div>


            <p style="
              margin:0;
              color:#34443a;
              font-size:14px;
              line-height:1.6;
            ">
              ${orientacao}
            </p>

          </div>


          <!-- AÇÃO PRINCIPAL -->

          <div style="
            text-align:center;
            margin-top:24px;
          ">

            <a
              href="${urlReenvio}"
              target="_blank"
              style="
                display:inline-block;
                padding:14px 24px;
                background:#050807;
                color:#B5FF20;
                border:1px solid #B5FF20;
                border-radius:10px;
                text-decoration:none;
                font-size:14px;
                font-weight:900;
              "
            >
              ${textoBotao}
            </a>

          </div>


          <p style="
            margin:22px 0 0;
            color:#667085;
            font-size:11px;
            line-height:1.5;
            text-align:center;
          ">
            Este é um aviso automático do SmartSlip.
          </p>

        </div>


        <!-- RODAPÉ -->

        <div style="
          padding:16px 26px;
          background:#005E27;
          color:#ffffff;
          font-size:12px;
        ">
          Vektor | Empresa Exemplo · Contas a Receber
        </div>

      </div>

    </div>
  `;
}

function smartSlipTentarEnviarAvisoFalhaProcessamento_(
  dados
) {
  dados = dados || {};

  const statusFila = String(
    dados.status_fila || ""
  )
    .trim()
    .toUpperCase();

  /*
    SALVO não recebe aviso.
  */
  if (!statusFila || statusFila === "SALVO") {
    return {
      enviado: false,
      motivo: "STATUS_SALVO"
    };
  }

  /*
    Esses status ainda não são conclusão.
  */
  if (
    statusFila === "RECEBIDO" ||
    statusFila === "PROCESSANDO"
  ) {
    return {
      enviado: false,
      motivo: "STATUS_NAO_FINAL"
    };
  }

  const destinatario =
    smartSlipNormalizarEmail_(
      dados.email_usuario || ""
    );

  if (
    !destinatario ||
    destinatario.indexOf("@") < 1
  ) {
    return {
      enviado: false,
      motivo: "EMAIL_INVALIDO"
    };
  }

  const rowIndex =
    Number(
      dados.row_index || 0
    );

  let sh = null;

  /*
    Se existir rowIndex, controla duplicidade
    pela própria SMARTSLIP_FILA.
  */
  if (rowIndex > 1) {
    try {
      sh =
        smartSlipGarantirCabecalhoFila();

      const avisoJaEnviado =
        sh
          .getRange(
            rowIndex,
            33
          )
          .getValue();

      if (avisoJaEnviado) {
        return {
          enviado: false,
          motivo: "JA_ENVIADO"
        };
      }

    } catch (errControle) {
      Logger.log(
        "Erro ao verificar controle do aviso de falha: " +
        String(
          errControle &&
          errControle.message
            ? errControle.message
            : errControle
        )
      );
    }
  }

  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  let dataEnvio = "-";

  if (
    dados.data_registro instanceof Date &&
    !isNaN(
      dados.data_registro.getTime()
    )
  ) {
    dataEnvio =
      Utilities.formatDate(
        dados.data_registro,
        timezone,
        "dd/MM/yyyy HH:mm"
      );
  }

  const lojaExibicao =
    smartSlipFormatarLojaAvisoFalha_(
      dados.loja || ""
    );

  const primeiroNome =
    smartSlipExtrairPrimeiroNome(
      destinatario
    );

  const statusExibicao =
    smartSlipStatusAvisoFalhaExibicao_(
      statusFila
    );

  const motivo =
    smartSlipMotivoAvisoFalhaUsuario_(
      statusFila,
      dados.mensagem || "",
      dados.resultado || null
    );

  /*
    Link direto para a página de Envio.
  */
/*
  Classifica a origem do problema usando
  a mesma regra criada para o aviso da tela.

  Assim o e-mail e o SmartSlip falam
  a mesma língua.
*/
const classificacaoAviso =
  smartSlipClassificarAvisoEnvioAnterior_(
    statusFila,
    dados.mensagem || ""
  );


const ehProblemaDocumento =
  classificacaoAviso &&
  classificacaoAviso.tipo ===
    "PROBLEMA_DOCUMENTO";


const protocoloEmail =
  String(
    dados.protocolo || ""
  ).trim();


/*
  PROBLEMA DOCUMENTAL:
  leva o usuário ao Histórico.

  Também enviamos o protocolo na URL.
  No próximo passo vamos fazer o HTML
  reconhecer esses parâmetros e abrir
  diretamente o comprovante correto.

  FALHA TÉCNICA:
  continua permitindo nova tentativa,
  sem mandar o usuário excluir nada.
*/
const urlReenvio =
  ehProblemaDocumento
    ? (
        SMARTSLIP_URL_ACESSO +
        "?view=historico" +
        "&acao=excluir" +
        "&protocolo=" +
        encodeURIComponent(
          protocoloEmail
        )
      )
    : (
        SMARTSLIP_URL_ACESSO +
        "?view=comprovantes"
      );


const textoBotao =
  ehProblemaDocumento
    ? "Acessar comprovante e excluir"
    : "Tentar novo envio no SmartSlip";

  const payloadEmail = {
    primeiro_nome:
      primeiroNome,

    loja_exibicao:
      lojaExibicao,

    protocolo:
      String(
        dados.protocolo || ""
      ).trim(),

    data_envio:
      dataEnvio,

    nome_arquivo:
      String(
        dados.nome_arquivo || ""
      ).trim(),

      status_original:
        statusFila,

      tipo_problema:
        classificacaoAviso
          ? classificacaoAviso.tipo
          : "NAO_CLASSIFICADO",

      problema_documental:
        ehProblemaDocumento,

    status_exibicao:
      statusExibicao,

    motivo:
      motivo,

    link_comprovante:
      String(
        dados.link_comprovante || ""
      ).trim(),

    url_reenvio:
      urlReenvio,

    texto_botao:
      textoBotao
  };

  const assunto =
    "⚠️ SMARTSLIP | Comprovante não processado | Loja " +
    lojaExibicao;

  try {
    smartSlipEnviarEmailUtf8_({
      to:
        destinatario,

      from:
        SMARTSLIP_EMAIL_VEKTOR,

      name:
        "Vektor - Empresa Exemplo",

      subject:
        assunto,

      textBody:
        smartSlipMontarTextoAvisoFalha_(
          payloadEmail
        ),

      htmlBody:
        smartSlipMontarHtmlAvisoFalha_(
          payloadEmail
        )
    });

    /*
      Registra sucesso na fila.
    */
    if (sh && rowIndex > 1) {
      sh
        .getRange(
          rowIndex,
          33,
          1,
          3
        )
        .setValues([[
          new Date(),
          destinatario,
          ""
        ]]);
    }

    return {
      enviado: true,
      destinatario:
        destinatario
    };

  } catch (errEmail) {
    const erroTexto =
      String(
        errEmail &&
        errEmail.message
          ? errEmail.message
          : errEmail
      );

    Logger.log(
      "Erro ao enviar aviso de falha SmartSlip: " +
      erroTexto
    );

    /*
      A falha do e-mail NÃO altera o status
      do processamento do comprovante.
    */
    if (sh && rowIndex > 1) {
      try {
        sh
          .getRange(
            rowIndex,
            35
          )
          .setValue(
            erroTexto
          );
      } catch (errLog) {}
    }

    return {
      enviado: false,
      motivo: "ERRO_EMAIL",
      erro: erroTexto
    };
  }
}

function smartSlipEnviarEmailTesteInatividadeParaMim() {
  /*
    Informe aqui o seu e-mail corporativo.
  */
  const emailTeste = "admin@empresa.com.br";

  if (
    !emailTeste ||
    emailTeste ===
      "usuario@empresa.com.br"
  ) {
    throw new Error(
      "Informe o seu e-mail corporativo na variável emailTeste."
    );
  }

  const itemTeste = {
    loja: "0072",
    loja_exibicao: "CE0072",
    empresa: "Empresa A",

    shopping: "Shopping Teste",
    time: "Regional Teste",

    tipo_deposito: "Boleto",
    limite_dias: 3,
    dias_sem_envio: 5,
    status: "CRITICO",

    ultimo_envio:
      "17/06/2026 08:25",

    ultimo_envio_iso:
      "2026-06-17T08:25:00",

    gerente_regional:
      "Administrador Exemplo",

    email_regional:
      emailTeste,

    email_gerente_loja:
      emailTeste,

    alerta_elegivel:
      true
  };

  const identificadorLoja =
    smartSlipIdentificadorLojaAlerta_(
      itemTeste
    );

  /*
    Emojis criados por código Unicode.
  */
  const emojiTeste =
    String.fromCodePoint(
      0x1F9EA
    );

  const emojiAlerta =
    String.fromCodePoint(
      0x1F6A8
    );

  const assunto =
    emojiTeste +
    " TESTE | " +
    emojiAlerta +
    " ALERTA SMARTSLIP | " +
    "LOJA SEM ENVIO DE COMPROVANTE: " +
    identificadorLoja +
    " " +
    emojiAlerta;

  const corpoTexto =
    smartSlipMontarTextoAlertaInatividade_(
      itemTeste
    );

  const corpoHtml =
    smartSlipMontarHtmlAlertaInatividade_(
      itemTeste
    );

  const retorno =
    smartSlipEnviarEmailUtf8_({
      to: emailTeste,

      from:
        "operacao@empresa.com.br",

      name:
        "Vektor - Empresa Exemplo",

      subject:
        assunto,

      textBody:
        corpoTexto,

      htmlBody:
        corpoHtml
    });

  return {
    ok: true,
    mensagem:
      "E-mail de teste UTF-8 enviado.",
    destinatario:
      emailTeste,
    assunto:
      assunto,
    message_id:
      retorno && retorno.id
        ? retorno.id
        : ""
  };
}

function smartSlipExecutarAlertasInatividadeDiarios() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(30000)) {
    return {
      ok: false,
      erro: "Já existe uma execução dos alertas em andamento."
    };
  }

  try {
    const timezone =
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo";

    const agora = new Date();

    const chaveHoje = Utilities.formatDate(
      agora,
      timezone,
      "yyyyMMdd"
    );

    const properties =
      PropertiesService.getScriptProperties();

    smartSlipLimparControlesAlertasAntigos_(
      properties,
      chaveHoje
    );

    const payload = smartSlipMontarInatividadeLojas_(
      null,
      false
    );

    const rows = Array.isArray(payload.rows)
      ? payload.rows
      : [];

    const resumo = {
      ok: true,
      avaliadas: rows.length,
      criticas: 0,
      enviados: 0,
      ignorados_ja_enviados: 0,
      sem_destinatario: 0,
      erros: []
    };

    rows.forEach(function(item) {
      if (
        String(item.status || "").toUpperCase() !==
        "CRITICO"
      ) {
        return;
      }

      resumo.criticas++;

      const loja = String(
        item.loja || ""
      ).trim();

      if (!loja) {
        resumo.erros.push(
          "Registro crítico encontrado sem código de loja."
        );

        return;
      }

      const chaveControle =
        SMARTSLIP_ALERTA_INATIVIDADE_PREFIXO_PROP +
        chaveHoje +
        "_" +
        loja;

      /*
        Impede mais de um envio para a mesma loja
        durante o mesmo dia.
      */
      if (properties.getProperty(chaveControle)) {
        resumo.ignorados_ja_enviados++;
        return;
      }

      const destinatarios = [];

      [
        item.email_regional,
        item.email_gerente_loja
      ].forEach(function(email) {
        const emailNormalizado =
          smartSlipNormalizarEmail_(
            email || ""
          );

        if (
          !emailNormalizado ||
          emailNormalizado.indexOf("@") < 1 ||
          destinatarios.indexOf(
            emailNormalizado
          ) >= 0
        ) {
          return;
        }

        destinatarios.push(
          emailNormalizado
        );
      });

      if (!destinatarios.length) {
        resumo.sem_destinatario++;

        resumo.erros.push(
          "Loja " +
          loja +
          ": regional e gerente sem e-mail válido."
        );

        return;
      }

      const identificador =
        smartSlipIdentificadorLojaAlerta_(
          item
        );

      /*
        Gera o emoji pelo código Unicode.
        O assunto será codificado como UTF-8 pela função
        smartSlipEnviarEmailUtf8_.
      */
      const emojiAlerta =
        String.fromCodePoint(0x1F6A8);

      const assunto =
        emojiAlerta +
        " ALERTA SMARTSLIP | " +
        "LOJA SEM ENVIO DE COMPROVANTE: " +
        identificador +
        " " +
        emojiAlerta;

      const ownerEmail =
        destinatarios.join(",");

      try {
        smartSlipEnviarEmailUtf8_({
          to: ownerEmail,

          cc:
            SMARTSLIP_EMAIL_ALERTA_INATIVIDADE_CC,

          from:
            SMARTSLIP_EMAIL_VEKTOR,

          name:
            "Vektor - Empresa Exemplo",

          subject:
            assunto,

          textBody:
            smartSlipMontarTextoAlertaInatividade_(
              item
            ),

          htmlBody:
            smartSlipMontarHtmlAlertaInatividade_(
              item
            )
        });

        properties.setProperty(
          chaveControle,
          Utilities.formatDate(
            new Date(),
            timezone,
            "dd/MM/yyyy HH:mm:ss"
          )
        );

        resumo.enviados++;

      } catch (erroEmail) {
        resumo.erros.push(
          "Loja " +
          loja +
          ": " +
          String(
            erroEmail &&
            erroEmail.message
              ? erroEmail.message
              : erroEmail
          )
        );
      }
    });

    return resumo;

  } finally {
    lock.releaseLock();
  }
}

function smartSlipInstalarTriggerAlertaInatividade() {
  const handler =
    SMARTSLIP_ALERTA_INATIVIDADE_HANDLER;

  /*
    Exclui trigger anterior da mesma função
    para não gerar execuções duplicadas.
  */
  ScriptApp.getProjectTriggers()
    .forEach(function(trigger) {
      if (
        trigger.getHandlerFunction() ===
        handler
      ) {
        ScriptApp.deleteTrigger(trigger);
      }
    });

  const trigger =
    ScriptApp.newTrigger(handler)
      .timeBased()
      .atHour(8)
      .nearMinute(0)
      .everyDays(1)
      .inTimezone(
        "America/Sao_Paulo"
      )
      .create();

  return {
    ok: true,
    mensagem:
      "Trigger diário criado para aproximadamente 08:00.",
    trigger_id:
      trigger.getUniqueId()
  };
}

function smartSlipDiagnosticarInatividadeLojas() {
  const payload =
    smartSlipMontarInatividadeLojas_(
      null,
      false
    );

  Logger.log(
    JSON.stringify(
      payload,
      null,
      2
    )
  );

  return payload;
}

function smartSlipResetarControleAlertasInatividadeHoje() {
  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  const chaveHoje =
    Utilities.formatDate(
      new Date(),
      timezone,
      "yyyyMMdd"
    );

  const properties =
    PropertiesService.getScriptProperties();

  const todas =
    properties.getProperties();

  const prefixoHoje =
    SMARTSLIP_ALERTA_INATIVIDADE_PREFIXO_PROP +
    chaveHoje +
    "_";

  Object.keys(todas).forEach(function(chave) {
    if (chave.indexOf(prefixoHoje) === 0) {
      properties.deleteProperty(chave);
    }
  });

  return {
    ok: true,
    mensagem:
      "Controle dos alertas de hoje removido."
  };
}

function smartSlipTesteSalvarCompleto() {
  const fileId = smartSlipGetScriptProperty("SMARTSLIP_TEST_FILE_ID");

const respostasUsuario = {
  loja: "0241",
  data_movimento_inicio: "01/05/2026",
   data_movimento_fim: "04/05/2026",
  houve_retirada: false,
  valor_retirada: 0,
  motivo_retirada: "Não houve retirada",
  mais_comprovantes: false
};

const protocolo = "SS-TESTE-SALVAR-COMPLETO";

const arquivoOrganizado = smartSlipCopiarArquivoParaPastaEstruturada(
  fileId,
  respostasUsuario,
  protocolo
);

  const file = DriveApp.getFileById(arquivoOrganizado.file_id);
  const linkComprovante = arquivoOrganizado.link_comprovante;
  const blob = file.getBlob();

  const base64 = Utilities.base64Encode(blob.getBytes());
  const mimeType = blob.getContentType();

  const resultado = smartSlipChamarGemini(base64, mimeType, respostasUsuario);

  Logger.log("RESULTADO GEMINI:");
  Logger.log(JSON.stringify(resultado, null, 2));

  const dados = resultado.dados_comprovante || {};

  // Usa respostas complementares do usuário como fonte de verdade quando o comprovante não traz o dado.
if (!dados.banco && respostasUsuario.banco) {
  dados.banco = respostasUsuario.banco;
}

if (!dados.data_movimento && respostasUsuario.data_movimento) {
  dados.data_movimento = respostasUsuario.data_movimento;
}

if (
  (dados.houve_retirada === null || dados.houve_retirada === undefined) &&
  typeof respostasUsuario.houve_retirada === "boolean"
) {
  dados.houve_retirada = respostasUsuario.houve_retirada;
}

if (
  (dados.valor_retirada === null || dados.valor_retirada === undefined) &&
  respostasUsuario.valor_retirada !== undefined
) {
  dados.valor_retirada = Number(respostasUsuario.valor_retirada || 0);
}

if (!dados.motivo_retirada && respostasUsuario.motivo_retirada) {
  dados.motivo_retirada = respostasUsuario.motivo_retirada;
}

if (dados.codigo_autenticacao === null || dados.codigo_autenticacao === undefined) {
  dados.codigo_autenticacao = "";
}

// 1. A loja informada pelo usuário é a fonte de verdade.
// Não confiar em número de loja inferido do comprovante.
if (respostasUsuario.loja) {
  dados.loja = String(respostasUsuario.loja).replace(/\D/g, "").padStart(4, "0").slice(-4);

  resultado.divergencias = (resultado.divergencias || []).filter(function(d) {
    const txt = String(d || "").toLowerCase();

    return !(
      txt.includes("número da loja no comprovante") ||
      txt.includes("numero da loja no comprovante") ||
      txt.includes("difere do número de loja informado") ||
      txt.includes("difere do numero de loja informado")
    );
  });
}

  // 2. Consulta Info_limites para obter empresa correta.
  if (dados.loja) {
    const infoLoja = smartSlipConsultarInfoLoja_(dados.loja);

    Logger.log("INFO LOJA:");
    Logger.log(JSON.stringify(infoLoja, null, 2));

    if (infoLoja.ok) {
      dados.loja = infoLoja.loja_normalizada;
      dados.empresa = infoLoja.empresa;
    } else {
      resultado.status = "PRECISA_COMPLEMENTO";
      resultado.pendencias = resultado.pendencias || [];
      resultado.perguntas_complementares = resultado.perguntas_complementares || [];

      resultado.pendencias.push("Loja não encontrada na Info_limites.");
      resultado.perguntas_complementares.push("Confirme o número correto da loja.");

      Logger.log("NÃO SALVOU: loja não encontrada na Info_limites.");
      Logger.log(JSON.stringify(resultado, null, 2));
      return;
    }
  }

  // Código de autenticação não bloqueia salvamento.
resultado.pendencias = (resultado.pendencias || []).filter(function(p) {
  const txt = String(p || "").toLowerCase();

  return !(
    txt.includes("código de autenticação") ||
    txt.includes("codigo de autenticacao")
  );
});

  // 3. Valida campos obrigatórios antes de salvar.
  const pendenciasBloqueantes = [];

  if (!dados.loja) pendenciasBloqueantes.push("Loja não informada.");
  if (!dados.empresa || dados.empresa === "Nao identificado") pendenciasBloqueantes.push("Empresa não identificada pela Info_limites.");
  if (!resultado.tipo_documento || resultado.tipo_documento === "nao_identificado") pendenciasBloqueantes.push("Tipo de documento não identificado.");
  if (!dados.data_deposito) pendenciasBloqueantes.push("Data do depósito não identificada.");
  if (dados.valor_deposito === null || dados.valor_deposito === undefined || dados.valor_deposito === "") pendenciasBloqueantes.push("Valor do depósito não identificado.");
  if (!dados.data_movimento) pendenciasBloqueantes.push("Data de movimento não informada.");
  if (dados.houve_retirada === null || dados.houve_retirada === undefined) pendenciasBloqueantes.push("Informação sobre retirada não informada.");
  if (!dados.data_geracao_documento) pendenciasBloqueantes.push("Data de geração do documento não identificada.");

  if (dados.houve_retirada === true) {
    if (!dados.valor_retirada) pendenciasBloqueantes.push("Valor da retirada não informado.");
    if (!dados.motivo_retirada) pendenciasBloqueantes.push("Motivo da retirada não informado.");
  }

  if (pendenciasBloqueantes.length > 0) {
    resultado.status = "PRECISA_COMPLEMENTO";
    resultado.pendencias = pendenciasBloqueantes;
    resultado.perguntas_complementares = smartSlipMontarPerguntasComplementares(pendenciasBloqueantes);

    Logger.log("NÃO SALVOU: existem pendências bloqueantes.");
    Logger.log(JSON.stringify(resultado, null, 2));
    return;
  }

  // 4. Monta payload final para salvar.
  const payloadSalvar = {
    loja: dados.loja,
    empresa: dados.empresa,
    tipo_documento: resultado.tipo_documento,
    data_deposito: dados.data_deposito,
    valor_deposito: Number(dados.valor_deposito || 0),
    banco: dados.banco || "Nao identificado",
    data_movimento: dados.data_movimento,
    houve_retirada: dados.houve_retirada === true,
    valor_retirada: Number(dados.valor_retirada || 0),
    motivo_retirada: dados.houve_retirada === true
      ? dados.motivo_retirada
      : "Não houve retirada",
    data_geracao_documento: dados.data_geracao_documento,
    codigo_autenticacao: dados.codigo_autenticacao || "",
    link_comprovante: linkComprovante,
    status_processamento: "PRONTO_PARA_SALVAR",
    pendencias: [],
    divergencias: resultado.divergencias || [],
    confianca_geral: Number(resultado.confianca_geral || 0)
  };

  Logger.log("PAYLOAD PARA SALVAR:");
  Logger.log(JSON.stringify(payloadSalvar, null, 2));

  // 5. Salva na BASE_SMARTSLIP.
  const retornoSalvar = smartSlipSalvarDadosComprovantePlanilha_(payloadSalvar);

  Logger.log("RETORNO SALVAMENTO:");
  Logger.log(JSON.stringify(retornoSalvar, null, 2));

  Logger.log("PROCESSO CONCLUÍDO. Verifique a aba BASE_SMARTSLIP.");
}

function smartSlipMontarPerguntasComplementares(pendencias) {
  const perguntas = [];

  pendencias.forEach(function(p) {
    const txt = String(p || "").toLowerCase();

    if (txt.includes("loja")) {
      perguntas.push("Qual o número da loja?");
    } else if (txt.includes("empresa")) {
      perguntas.push("Confirme o número da loja para consultar a empresa correta.");
    } else if (txt.includes("tipo de documento")) {
      perguntas.push("Qual é o tipo do comprovante?");
    } else if (txt.includes("data do depósito")) {
      perguntas.push("Qual a data do depósito?");
    } else if (txt.includes("valor do depósito")) {
      perguntas.push("Qual o valor do depósito?");
    } else if (txt.includes("banco")) {
      perguntas.push("Qual o banco do comprovante?");
    } else if (txt.includes("data de movimento")) {
      perguntas.push("Qual a data do movimento desse depósito?");
    } else if (txt.includes("retirada")) {
      perguntas.push("Houve alguma retirada desse movimento para estorno, reembolso no ato ou algo do tipo?");
    } else if (txt.includes("data de geração")) {
      perguntas.push("Qual a data de geração do documento?");
    }
  });

  return [...new Set(perguntas)];
}

function smartSlipGarantirAbaFila() {
  return smartSlipGarantirCabecalhoFila();
}

function smartSlipTesteFila() {
  const sh = smartSlipGarantirCabecalhoFila();

  const respostasUsuario = {
    loja: "0025",
    banco: "CARRO FORTE",
    data_movimento: "04/05/2026",
    houve_retirada: false,
    valor_retirada: 0,
    motivo_retirada: "Não houve retirada",
    mais_comprovantes: false
  };

  const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);

  sh.appendRow([
    new Date(),
    "SS-TESTE-001",
    Session.getActiveUser().getEmail() || "",
    smartSlipNormalizarLoja4(respostasUsuario.loja),
    respostasUsuario.banco || "",
    dataMovimentoTexto,
    respostasUsuario.houve_retirada ? "Sim" : "Não",
    respostasUsuario.valor_retirada,
    respostasUsuario.motivo_retirada,
    respostasUsuario.mais_comprovantes ? "Sim" : "Não",
    "FILE_ID_TESTE",
    "https://drive.google.com/file/d/ARQUIVO_EXEMPLO/view",
    "comprovante_teste.pdf",
    "RECEBIDO",
    "Linha de teste criada na fila.",
    JSON.stringify(respostasUsuario),
      "",
      "",
      "SS-TESTE-001",
      "SS-TESTE-001",
      1,
      "FECHADO",
      "Sim",
      0
  ]);

  Logger.log("Linha de teste criada na SMARTSLIP_FILA.");
}

function smartSlipGetScriptProperty(nome) {
  const valor = PropertiesService
    .getScriptProperties()
    .getProperty(nome);

  if (!valor) {
    throw new Error("Propriedade do script não configurada: " + nome);
  }

  return valor;
}

function smartSlipGetNumberScriptProperty_(nome, valorPadrao) {
  const raw = PropertiesService
    .getScriptProperties()
    .getProperty(nome);

  if (raw === null || raw === undefined || raw === "") {
    return Number(valorPadrao || 0);
  }

  const n = Number(String(raw).replace(",", ".").trim());

  return isNaN(n) ? Number(valorPadrao || 0) : n;
}

function smartSlipAtualizarCotacaoUsdBrl() {
  const url =
    "https://api.bcb.gov.br/dados/serie/" +
    "bcdata.sgs.1/dados/ultimos/1?formato=json";

  const properties =
    PropertiesService.getScriptProperties();

  const cotacaoAnterior =
    smartSlipGetNumberScriptProperty_(
      "SMARTSLIP_IA_USD_BRL",
      0
    );

  try {
    const response =
      UrlFetchApp.fetch(
        url,
        {
          method: "get",

          headers: {
            Accept: "application/json"
          },

          muteHttpExceptions: true
        }
      );

    const status =
      response.getResponseCode();

    const texto =
      response.getContentText();

    if (status !== 200) {
      throw new Error(
        "Banco Central retornou HTTP " +
        status +
        ": " +
        texto
      );
    }

    const dados =
      JSON.parse(texto || "[]");

    if (
      !Array.isArray(dados) ||
      !dados.length
    ) {
      throw new Error(
        "A API do Banco Central não retornou cotação."
      );
    }

    const cotacao =
      Number(
        String(
          dados[0].valor || ""
        )
          .replace(",", ".")
          .trim()
      );

    if (
      !Number.isFinite(cotacao) ||
      cotacao <= 0
    ) {
      throw new Error(
        "Cotação inválida retornada pelo Banco Central."
      );
    }

    const dataCotacao =
      String(
        dados[0].data || ""
      ).trim();

    const timezone =
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo";

    const atualizadoEm =
      Utilities.formatDate(
        new Date(),
        timezone,
        "dd/MM/yyyy HH:mm:ss"
      );

    properties.setProperties(
      {
        SMARTSLIP_IA_USD_BRL:
          cotacao.toFixed(4),

        SMARTSLIP_IA_USD_BRL_DATA:
          dataCotacao,

        SMARTSLIP_IA_USD_BRL_ATUALIZADO_EM:
          atualizadoEm,

        SMARTSLIP_IA_USD_BRL_FONTE:
          "Banco Central do Brasil - SGS série 1"
      },
      false
    );

    Logger.log(
      "Cotação USD/BRL atualizada: " +
      cotacao.toFixed(4) +
      " | Data BCB: " +
      dataCotacao
    );

    return {
      ok: true,
      cotacao: cotacao,
      data_cotacao: dataCotacao,
      atualizado_em: atualizadoEm,
      fonte:
        "Banco Central do Brasil"
    };

  } catch (err) {
    /*
      Em caso de indisponibilidade da API,
      mantém a última cotação válida gravada.
    */
    Logger.log(
      "Erro ao atualizar cotação USD/BRL: " +
      String(
        err && err.message
          ? err.message
          : err
      )
    );

    return {
      ok: false,

      cotacao_mantida:
        cotacaoAnterior,

      erro:
        String(
          err && err.message
            ? err.message
            : err
        )
    };
  }
}

function smartSlipInstalarTriggerCotacaoUsdBrl() {
  const handler =
    "smartSlipAtualizarCotacaoUsdBrl";

  /*
    Remove eventual acionador antigo da mesma função,
    evitando duplicidade.
  */
  ScriptApp
    .getProjectTriggers()
    .forEach(function(trigger) {
      if (
        trigger.getHandlerFunction() ===
        handler
      ) {
        ScriptApp.deleteTrigger(
          trigger
        );
      }
    });

  /*
    Consulta a última cotação publicada
    quatro vezes por dia.
  */
  ScriptApp
    .newTrigger(handler)
    .timeBased()
    .everyHours(6)
    .create();

  /*
    Já realiza a primeira atualização.
  */
  const resultado =
    smartSlipAtualizarCotacaoUsdBrl();

  return {
    ok: true,
    mensagem:
      "Acionador da cotação instalado.",
    primeira_atualizacao:
      resultado
  };
}

function smartSlipGetConfigCustoIa_() {
  return {
    preco_input_1m_usd: smartSlipGetNumberScriptProperty_("SMARTSLIP_IA_PRECO_INPUT_1M_USD", 0),
    preco_output_1m_usd: smartSlipGetNumberScriptProperty_("SMARTSLIP_IA_PRECO_OUTPUT_1M_USD", 0),
    usd_brl: smartSlipGetNumberScriptProperty_("SMARTSLIP_IA_USD_BRL", 0)
  };
}

function smartSlipGarantirCabecalhoCustosIa_() {
  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  let sh = ss.getSheetByName(SMARTSLIP_ABA_CUSTOS_IA);

  if (!sh) {
    sh = ss.insertSheet(SMARTSLIP_ABA_CUSTOS_IA);
  }

  const headers = [
    "Data Hora",
    "Data",
    "AnoMes",
    "Origem",
    "Modelo",
    "Email Usuário",
    "Loja",
    "Protocolo",
    "Prompt Tokens",
    "Output Tokens",
    "Total Tokens",
    "Input USD",
    "Output USD",
    "Total USD",
    "Cotação USD BRL",
    "Total BRL",
    "HTTP Status",
    "Observação"
  ];

  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    sh.setFrozenRows(1);
    return sh;
  }

  const primeira = String(sh.getRange(1, 1).getValue() || "").trim();

  if (primeira !== "Data Hora") {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    sh.setFrozenRows(1);
  }

  return sh;
}

function smartSlipRegistrarCustoIa_(args) {
  try {
    args = args || {};

    const usage = args.usage || {};
    const contexto = args.respostasUsuario || args.contexto || {};

    const promptTokens = Number(usage.promptTokenCount || 0);

    let outputTokens = Number(
      usage.candidatesTokenCount ||
      usage.outputTokenCount ||
      0
    );

    const totalTokensMetadata = Number(usage.totalTokenCount || 0);

    if (!outputTokens && totalTokensMetadata > promptTokens) {
      outputTokens = totalTokensMetadata - promptTokens;
    }

    const totalTokens = totalTokensMetadata || (promptTokens + outputTokens);

    const cfg = smartSlipGetConfigCustoIa_();

    const inputUsd = (promptTokens / 1000000) * cfg.preco_input_1m_usd;
    const outputUsd = (outputTokens / 1000000) * cfg.preco_output_1m_usd;
    const totalUsd = inputUsd + outputUsd;
    const totalBrl = totalUsd * cfg.usd_brl;

    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    const agora = new Date();

    const dataHora = Utilities.formatDate(agora, tz, "dd/MM/yyyy HH:mm:ss");
    const data = Utilities.formatDate(agora, tz, "yyyy-MM-dd");
    const anoMes = Utilities.formatDate(agora, tz, "yyyy-MM");

    const email = String(Session.getActiveUser().getEmail() || "").trim().toLowerCase();

    const loja = String(
      contexto.loja ||
      contexto.loja_padrao ||
      args.loja ||
      ""
    ).trim();

    const protocolo = String(
      contexto.protocolo ||
      args.protocolo ||
      ""
    ).trim();

    let observacao = String(args.observacao || "").trim();

    if (!usage || !Object.keys(usage).length) {
      observacao = observacao
        ? observacao + " | usageMetadata ausente no retorno."
        : "usageMetadata ausente no retorno.";
    }

    if (!cfg.preco_input_1m_usd || !cfg.preco_output_1m_usd || !cfg.usd_brl) {
      observacao = observacao
        ? observacao + " | Configuração de preço/cotação incompleta."
        : "Configuração de preço/cotação incompleta.";
    }

    const sh = smartSlipGarantirCabecalhoCustosIa_();

    sh.appendRow([
      dataHora,
      data,
      anoMes,
      String(args.origem || ""),
      String(args.modelo || ""),
      email,
      loja,
      protocolo,
      promptTokens,
      outputTokens,
      totalTokens,
      inputUsd,
      outputUsd,
      totalUsd,
      cfg.usd_brl,
      totalBrl,
      String(args.httpStatus || ""),
      observacao
    ]);

  } catch (err) {
    Logger.log("Erro ao registrar custo IA: " + String(err && err.message ? err.message : err));
  }
}

function smartSlipPad2_(n) {
  return String(n).padStart(2, "0");
}

function smartSlipNumeroCustosIa_(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return 0;
  }

  if (typeof valor === "number") {
    return isNaN(valor) ? 0 : valor;
  }

  let txt = String(valor).trim();

  if (!txt) {
    return 0;
  }

  // Remove moeda/espaço e normaliza pt-BR/en-US.
  txt = txt
    .replace(/[R$US$\s]/g, "")
    .replace(/\u00A0/g, "")
    .trim();

  // Caso venha como 1.234,56
  if (txt.indexOf(",") >= 0) {
    txt = txt.replace(/\./g, "").replace(",", ".");
  }

  const n = Number(txt);

  return isNaN(n) ? 0 : n;
}

function smartSlipNormalizarDataIsoCustos_(valorRaw, valorDisplay) {
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  if (valorRaw instanceof Date && !isNaN(valorRaw.getTime())) {
    return Utilities.formatDate(valorRaw, tz, "yyyy-MM-dd");
  }

  let txt = String(valorDisplay || valorRaw || "").trim();

  if (!txt) {
    return "";
  }

  // Já está yyyy-MM-dd
  let m = txt.match(/^(\d{4})-(\d{2})-(\d{2})$/);

  if (m) {
    return m[1] + "-" + m[2] + "-" + m[3];
  }

  // dd/mm/yyyy
  m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);

  if (m) {
    return m[3] + "-" + m[2] + "-" + m[1];
  }

  // dd/mm/yyyy hh:mm:ss
  m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+/);

  if (m) {
    return m[3] + "-" + m[2] + "-" + m[1];
  }

  return txt;
}

function smartSlipNormalizarAnoMesCustos_(valorRaw, valorDisplay, dataIso) {
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  if (valorRaw instanceof Date && !isNaN(valorRaw.getTime())) {
    return Utilities.formatDate(valorRaw, tz, "yyyy-MM");
  }

  let txt = String(valorDisplay || valorRaw || "").trim();

  if (txt) {
    // yyyy-MM
    let m = txt.match(/^(\d{4})-(\d{2})$/);

    if (m) {
      return m[1] + "-" + m[2];
    }

    // yyyy-MM-dd
    m = txt.match(/^(\d{4})-(\d{2})-\d{2}$/);

    if (m) {
      return m[1] + "-" + m[2];
    }

    // dd/mm/yyyy
    m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})/);

    if (m) {
      return m[3] + "-" + m[2];
    }
  }

  if (dataIso && String(dataIso).match(/^\d{4}-\d{2}-\d{2}$/)) {
    return String(dataIso).substring(0, 7);
  }

  return txt;
}

function smartSlipGetCustosIa_(options) {
  options = options || {};

  const hoje = new Date();
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  const anoAtual = Number(Utilities.formatDate(hoje, tz, "yyyy"));
  const mesAtual = Number(Utilities.formatDate(hoje, tz, "MM"));

  const ano = Number(options.ano || anoAtual);
  const mes = Number(options.mes || mesAtual);

  const sh = smartSlipGarantirCabecalhoCustosIa_();
  const cfg = smartSlipGetConfigCustoIa_();

  const serieMensal = [];
  const mapaMensal = {};

  for (let m = 1; m <= 12; m++) {
    const anoMes = ano + "-" + smartSlipPad2_(m);

    const item = {
      ano_mes: anoMes,
      label: smartSlipPad2_(m) + "/" + String(ano).slice(-2),
      chamadas: 0,
      prompt_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      custo_usd: 0,
      custo_brl: 0
    };

    serieMensal.push(item);
    mapaMensal[anoMes] = item;
  }

  const diasMes = new Date(ano, mes, 0).getDate();
  const serieDiaria = [];
  const mapaDiario = {};

  for (let d = 1; d <= diasMes; d++) {
    const data = ano + "-" + smartSlipPad2_(mes) + "-" + smartSlipPad2_(d);

    const itemDia = {
      data: data,
      label: smartSlipPad2_(d),
      chamadas: 0,
      prompt_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      custo_usd: 0,
      custo_brl: 0
    };

    serieDiaria.push(itemDia);
    mapaDiario[data] = itemDia;
  }

  const kpis = {
    chamadas: 0,
    prompt_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    custo_usd: 0,
    custo_brl: 0
  };

  const porOrigem = {};

  if (sh.getLastRow() >= 2) {
    const values = sh.getDataRange().getValues();
    const displayValues = sh.getDataRange().getDisplayValues();

    const headers = values[0].map(function(h) {
      return String(h || "").trim();
    });

    const idxData = smartSlipEncontrarIndiceHeader_(headers, ["Data"]);
    const idxAnoMes = smartSlipEncontrarIndiceHeader_(headers, ["AnoMes"]);
    const idxOrigem = smartSlipEncontrarIndiceHeader_(headers, ["Origem"]);
    const idxPrompt = smartSlipEncontrarIndiceHeader_(headers, ["Prompt Tokens"]);
    const idxOutput = smartSlipEncontrarIndiceHeader_(headers, ["Output Tokens"]);
    const idxTotal = smartSlipEncontrarIndiceHeader_(headers, ["Total Tokens"]);
    const idxUsd = smartSlipEncontrarIndiceHeader_(headers, ["Total USD"]);
    const idxBrl = smartSlipEncontrarIndiceHeader_(headers, ["Total BRL"]);

    const indicesObrigatorios = [
      idxData,
      idxAnoMes,
      idxOrigem,
      idxPrompt,
      idxOutput,
      idxTotal,
      idxUsd,
      idxBrl
    ];

    if (indicesObrigatorios.some(function(idx) { return idx < 0; })) {
      throw new Error(
        "Cabeçalhos da aba SMARTSLIP_CUSTOS_IA incompletos. Verifique: Data, AnoMes, Origem, Prompt Tokens, Output Tokens, Total Tokens, Total USD e Total BRL."
      );
    }

    for (let i = 1; i < values.length; i++) {
      const row = values[i];
      const rowDisplay = displayValues[i];

      const data = smartSlipNormalizarDataIsoCustos_(
        row[idxData],
        rowDisplay[idxData]
      );

      const anoMes = smartSlipNormalizarAnoMesCustos_(
        row[idxAnoMes],
        rowDisplay[idxAnoMes],
        data
      );

      const origem = String(rowDisplay[idxOrigem] || row[idxOrigem] || "Não informado").trim();

      const promptTokens = smartSlipNumeroCustosIa_(row[idxPrompt]);
      const outputTokens = smartSlipNumeroCustosIa_(row[idxOutput]);
      const totalTokens = smartSlipNumeroCustosIa_(row[idxTotal]);
      const totalUsd = smartSlipNumeroCustosIa_(row[idxUsd]);
      const totalBrl = smartSlipNumeroCustosIa_(row[idxBrl]);

      // Série mensal: considera todo o ano selecionado.
      if (mapaMensal[anoMes]) {
        mapaMensal[anoMes].chamadas += 1;
        mapaMensal[anoMes].prompt_tokens += promptTokens;
        mapaMensal[anoMes].output_tokens += outputTokens;
        mapaMensal[anoMes].total_tokens += totalTokens;
        mapaMensal[anoMes].custo_usd += totalUsd;
        mapaMensal[anoMes].custo_brl += totalBrl;
      }

      // KPIs, série diária e origem: considera apenas mês selecionado.
      if (mapaDiario[data]) {
        mapaDiario[data].chamadas += 1;
        mapaDiario[data].prompt_tokens += promptTokens;
        mapaDiario[data].output_tokens += outputTokens;
        mapaDiario[data].total_tokens += totalTokens;
        mapaDiario[data].custo_usd += totalUsd;
        mapaDiario[data].custo_brl += totalBrl;

        kpis.chamadas += 1;
        kpis.prompt_tokens += promptTokens;
        kpis.output_tokens += outputTokens;
        kpis.total_tokens += totalTokens;
        kpis.custo_usd += totalUsd;
        kpis.custo_brl += totalBrl;

        if (!porOrigem[origem]) {
          porOrigem[origem] = {
            origem: origem,
            chamadas: 0,
            prompt_tokens: 0,
            output_tokens: 0,
            total_tokens: 0,
            custo_usd: 0,
            custo_brl: 0
          };
        }

        porOrigem[origem].chamadas += 1;
        porOrigem[origem].prompt_tokens += promptTokens;
        porOrigem[origem].output_tokens += outputTokens;
        porOrigem[origem].total_tokens += totalTokens;
        porOrigem[origem].custo_usd += totalUsd;
        porOrigem[origem].custo_brl += totalBrl;
      }
    }
  }

  const porOrigemLista = Object.keys(porOrigem)
    .map(function(k) {
      return porOrigem[k];
    })
    .sort(function(a, b) {
      return Number(b.custo_brl || 0) - Number(a.custo_brl || 0);
    });

  return {
    atualizado_em: smartSlipFormatarDataHora(new Date()),
    ano: ano,
    mes: mes,
    config: cfg,
    kpis: kpis,
    mensal: serieMensal,
    diario: serieDiaria,
    por_origem: porOrigemLista
  };
}

function smartSlipGetCustosIaJson(optionsJson) {
  try {
    smartSlipAssertUsuarioAutorizado_();

    const usuario = smartSlipGetUsuarioAtual();

    if (!usuario.is_admin) {
      return JSON.stringify({
        ok: false,
        erro: "Acesso restrito. A página de Custos está disponível apenas para Administradores."
      });
    }

    let options = {};

    try {
      options = optionsJson ? JSON.parse(optionsJson) : {};
    } catch (e) {
      options = {};
    }

    return JSON.stringify({
      ok: true,
      payload: smartSlipGetCustosIa_(options)
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipPercentilPerformance_(lista, percentil) {
  const arr = (lista || [])
    .map(function(v) {
      return Number(v || 0);
    })
    .filter(function(v) {
      return v > 0;
    })
    .sort(function(a, b) {
      return a - b;
    });

  if (!arr.length) {
    return 0;
  }

  const pos = Math.ceil((percentil / 100) * arr.length) - 1;

  return arr[Math.max(0, Math.min(arr.length - 1, pos))];
}

function smartSlipMediaPerformance_(lista) {
  const arr = (lista || [])
    .map(function(v) {
      return Number(v || 0);
    })
    .filter(function(v) {
      return v > 0;
    });

  if (!arr.length) {
    return 0;
  }

  const soma = arr.reduce(function(acc, v) {
    return acc + v;
  }, 0);

  return soma / arr.length;
}

function smartSlipCriarBucketPerformance_(label, chave) {
  return {
    chave: chave,
    label: label,
    qtd: 0,
    processados: 0,
    lentos: 0,
    criticos: 0,
    fila_lista: [],
    leitura_lista: [],
    total_lista: [],
    fila_media_seg: 0,
    leitura_media_seg: 0,
    total_media_seg: 0,
    total_p95_seg: 0
  };
}

function smartSlipFinalizarBucketPerformance_(bucket) {
  bucket.fila_media_seg = smartSlipMediaPerformance_(bucket.fila_lista);
  bucket.leitura_media_seg = smartSlipMediaPerformance_(bucket.leitura_lista);
  bucket.total_media_seg = smartSlipMediaPerformance_(bucket.total_lista);
  bucket.total_p95_seg = smartSlipPercentilPerformance_(bucket.total_lista, 95);

  delete bucket.fila_lista;
  delete bucket.leitura_lista;
  delete bucket.total_lista;

  return bucket;
}

function smartSlipInferirStatusGeminiPerformance_(kpis, statusRows) {
  kpis = kpis || {};
  statusRows = Array.isArray(statusRows) ? statusRows : [];

  const totalEnvios = Number(kpis.total_envios || 0);
  const processados = Number(kpis.processados || 0);
  const pendentes = Number(kpis.pendentes || 0);
  const leituraMediaSeg = Number(kpis.leitura_media_seg || 0);
  const totalP95Seg = Number(kpis.total_p95_seg || 0);

  let errosProcessamento = 0;

  statusRows.forEach(function(item) {
    const status = String(item.status || "").toUpperCase();
    const qtd = Number(item.qtd || 0);

    /*
      Para medir saúde da chamada Gemini, considerar erro técnico.
      Não considerar PENDENTE_INTERNO como erro de API, pois pode ser regra de validação/anti-alucinação.
    */
    if (
      status.includes("ERRO_PROCESSAMENTO") ||
      status.includes("ERRO") ||
      status.includes("FALHA")
    ) {
      errosProcessamento += qtd;
    }
  });

  if (!totalEnvios) {
    return {
      status: "NAO_MEDIDO",
      label: "Não medido",
      latencia_ms: 0,
      latencia_operacional_seg: 0,
      detalhe: "Sem envios no período selecionado para inferir status do Gemini."
    };
  }

  if (!processados && pendentes > 0) {
    return {
      status: "ATENCAO",
      label: "Sem conclusão",
      latencia_ms: 0,
      latencia_operacional_seg: 0,
      detalhe: "Há envios no período, mas ainda sem Data Processamento."
    };
  }

  const taxaErro = totalEnvios > 0
    ? (errosProcessamento / totalEnvios) * 100
    : 0;

  if (taxaErro >= 20) {
    return {
      status: "ERRO",
      label: "Instável",
      latencia_ms: 0,
      latencia_operacional_seg: leituraMediaSeg,
      detalhe:
        "Alta taxa de erro técnico nos processamentos reais do período: " +
        taxaErro.toFixed(1).replace(".", ",") +
        "%."
    };
  }

  if (taxaErro > 0) {
    return {
      status: "ATENCAO",
      label: "Atenção",
      latencia_ms: 0,
      latencia_operacional_seg: leituraMediaSeg,
      detalhe:
        "Foram identificados erros técnicos em processamentos reais do período: " +
        taxaErro.toFixed(1).replace(".", ",") +
        "%."
    };
  }

  if (leituraMediaSeg >= 120 || totalP95Seg >= 300) {
    return {
      status: "ATENCAO",
      label: "Lentidão parcial",
      latencia_ms: 0,
      latencia_operacional_seg: leituraMediaSeg,
      detalhe:
        "Sem erro técnico relevante, mas com lentidão operacional na leitura IA do período."
    };
  }

  return {
    status: "OK",
    label: "Operacional",
    latencia_ms: 0,
    latencia_operacional_seg: leituraMediaSeg,
    detalhe:
      "Status inferido pelos processamentos reais da SMARTSLIP_FILA. Nenhuma chamada adicional ao Gemini foi feita."
  };
}

function smartSlipGetStatusPlataformaPerformance_(kpis, statusRows) {
  const google = smartSlipTestarGooglePerformance_();
  const gemini = smartSlipInferirStatusGeminiPerformance_(kpis, statusRows);

  return {
    atualizado_em: smartSlipFormatarDataHora(new Date()),
    google: google,
    gemini: gemini,
    modelo: {
      nome: "Sem health check direto",
      detalhe: "Modelo não consultado para evitar custo de tokens. Status do Gemini inferido pela fila real."
    }
  };
}


function smartSlipTestarGooglePerformance_() {
  const inicio = Date.now();

  try {
    const resp = UrlFetchApp.fetch("https://www.google.com/generate_204", {
      method: "get",
      muteHttpExceptions: true
    });

    const code = resp.getResponseCode();
    const latencia = Date.now() - inicio;

    if (code === 204 || (code >= 200 && code < 300)) {
      return {
        status: "OK",
        label: "Operacional",
        latencia_ms: latencia,
        detalhe: "Conectividade Google validada."
      };
    }

    return {
      status: "ATENCAO",
      label: "Atenção",
      latencia_ms: latencia,
      detalhe: "Google retornou HTTP " + code + "."
    };

  } catch (err) {
    return {
      status: "ERRO",
      label: "Erro",
      latencia_ms: 0,
      detalhe: String(err && err.message ? err.message : err)
    };
  }
}

function smartSlipDataIsoPerformance_(data) {
  if (!(data instanceof Date)) {
    return "";
  }

  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  return Utilities.formatDate(data, tz, "yyyy-MM-dd");
}

function smartSlipGetPerformance_(options) {
  options = options || {};

  const usuario = smartSlipGetUsuarioAtual();

  if (!(usuario.is_admin === true || usuario.is_analista_pro === true)) {
    throw new Error("Acesso restrito. Performance disponível apenas para Administrador ou Analista Pro.");
  }

  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  const hoje = new Date();

  const anoAtual = Number(Utilities.formatDate(hoje, tz, "yyyy"));
  const mesAtual = Number(Utilities.formatDate(hoje, tz, "MM"));

  let tipoPeriodo = String(options.tipo_periodo || "MENSAL").toUpperCase();

  if (tipoPeriodo !== "DIARIO" && tipoPeriodo !== "MENSAL" && tipoPeriodo !== "ANUAL") {
    tipoPeriodo = "MENSAL";
  }

  const ano = Number(options.ano || anoAtual);
  const mes = Number(options.mes || mesAtual);
  const diaSelecionado = String(
    options.dia ||
    Utilities.formatDate(hoje, tz, "yyyy-MM-dd")
  ).trim();

  const sh = smartSlipGarantirCabecalhoFila();

  const kpis = {
    total_envios: 0,
    processados: 0,
    pendentes: 0,
    lentos: 0,
    criticos: 0,
    fila_media_seg: 0,
    leitura_media_seg: 0,
    total_media_seg: 0,
    total_p95_seg: 0,
    total_max_seg: 0
  };

  const statusMap = {};
  const topLentos = [];

  const filaLista = [];
  const leituraLista = [];
  const totalLista = [];

  const serie = [];
  const mapaSerie = {};

if (tipoPeriodo === "DIARIO") {
  for (let h = 0; h <= 23; h++) {
    const hora = smartSlipPad2_(h);
    const chave = diaSelecionado + " " + hora;
    const label = hora + "h";
    const bucket = smartSlipCriarBucketPerformance_(label, chave);

    serie.push(bucket);
    mapaSerie[chave] = bucket;
  }

} else if (tipoPeriodo === "ANUAL") {
  for (let m = 1; m <= 12; m++) {
    const chave = ano + "-" + smartSlipPad2_(m);
    const label = smartSlipPad2_(m) + "/" + String(ano).slice(-2);
    const bucket = smartSlipCriarBucketPerformance_(label, chave);

    serie.push(bucket);
    mapaSerie[chave] = bucket;
  }

} else {
  const diasMes = new Date(ano, mes, 0).getDate();

  for (let d = 1; d <= diasMes; d++) {
    const chave = ano + "-" + smartSlipPad2_(mes) + "-" + smartSlipPad2_(d);
    const label = smartSlipPad2_(d);
    const bucket = smartSlipCriarBucketPerformance_(label, chave);

    serie.push(bucket);
    mapaSerie[chave] = bucket;
  }
}

  if (sh.getLastRow() >= 2) {
    const lastCol = Math.max(29, sh.getLastColumn());
    const values = sh.getRange(2, 1, sh.getLastRow() - 1, lastCol).getValues();

    values.forEach(function(row) {
      const dataRegistro = row[0];
      const protocolo = String(row[1] || "").trim();
      const email = String(row[2] || "").trim();
      const loja = String(row[3] || "").trim();
      const status = String(row[13] || "SEM_STATUS").trim() || "SEM_STATUS";
      const mensagem = String(row[14] || "").trim();
      const dataProcessamento = row[17];

      if (!(dataRegistro instanceof Date)) {
        return;
      }

      const rowAno = Number(Utilities.formatDate(dataRegistro, tz, "yyyy"));
      const rowMes = Number(Utilities.formatDate(dataRegistro, tz, "MM"));
      const rowDia = Number(Utilities.formatDate(dataRegistro, tz, "dd"));

      const rowIso = smartSlipDataIsoPerformance_(dataRegistro);

      if (tipoPeriodo === "DIARIO") {
        if (rowIso !== diaSelecionado) {
          return;
        }
      } else {
        if (rowAno !== ano) {
          return;
        }

        if (tipoPeriodo === "MENSAL" && rowMes !== mes) {
          return;
        }
      }

      let filaSeg = Number(row[25] || 0);
      let leituraSeg = Number(row[26] || 0);
      let totalSeg = Number(row[27] || 0);
      let flag = String(row[28] || "").trim();

      /*
        Linhas antigas:
        calcula apenas o total com Data Registro x Data Processamento.
        Não inventa tempo de fila nem tempo Gemini.
      */
      if (!totalSeg && dataProcessamento instanceof Date) {
        totalSeg = smartSlipDiffSegundos_(dataRegistro, dataProcessamento) || 0;
      }

      if (!flag && totalSeg) {
        flag = smartSlipClassificarPerformance_(filaSeg, leituraSeg, totalSeg);
      }

      const processado = dataProcessamento instanceof Date;

      kpis.total_envios += 1;

      if (processado) {
        kpis.processados += 1;
      } else {
        kpis.pendentes += 1;
      }

      if (flag === "LENTO") {
        kpis.lentos += 1;
      }

      if (flag === "CRITICO") {
        kpis.criticos += 1;
      }

      statusMap[status] = (statusMap[status] || 0) + 1;

      if (filaSeg > 0) filaLista.push(filaSeg);
      if (leituraSeg > 0) leituraLista.push(leituraSeg);
      if (totalSeg > 0) totalLista.push(totalSeg);

      if (totalSeg > kpis.total_max_seg) {
        kpis.total_max_seg = totalSeg;
      }

      let chaveSerie = "";

      if (tipoPeriodo === "DIARIO") {
        const rowHora = Utilities.formatDate(dataRegistro, tz, "HH");
        chaveSerie = rowIso + " " + rowHora;
      } else if (tipoPeriodo === "ANUAL") {
        chaveSerie = rowAno + "-" + smartSlipPad2_(rowMes);
      } else {
        chaveSerie = rowAno + "-" + smartSlipPad2_(rowMes) + "-" + smartSlipPad2_(rowDia);
      }

      const bucket = mapaSerie[chaveSerie];

      if (bucket) {
        bucket.qtd += 1;

        if (processado) {
          bucket.processados += 1;
        }

        if (flag === "LENTO") {
          bucket.lentos += 1;
        }

        if (flag === "CRITICO") {
          bucket.criticos += 1;
        }

        if (filaSeg > 0) bucket.fila_lista.push(filaSeg);
        if (leituraSeg > 0) bucket.leitura_lista.push(leituraSeg);
        if (totalSeg > 0) bucket.total_lista.push(totalSeg);
      }

      if (totalSeg > 0) {
        topLentos.push({
          protocolo: protocolo,
          data_registro: smartSlipFormatarDataHora(dataRegistro),
          data_processamento: smartSlipFormatarDataHora(dataProcessamento),
          loja: loja,
          email_usuario: email,
          status: status,
          mensagem: mensagem,
          fila_seg: filaSeg,
          leitura_ia_seg: leituraSeg,
          total_seg: totalSeg,
          flag: flag || "NORMAL"
        });
      }
    });
  }

  kpis.fila_media_seg = smartSlipMediaPerformance_(filaLista);
  kpis.leitura_media_seg = smartSlipMediaPerformance_(leituraLista);
  kpis.total_media_seg = smartSlipMediaPerformance_(totalLista);
  kpis.total_p95_seg = smartSlipPercentilPerformance_(totalLista, 95);

  const serieFinal = serie.map(smartSlipFinalizarBucketPerformance_);

  const statusRows = Object.keys(statusMap)
    .sort(function(a, b) {
      return statusMap[b] - statusMap[a];
    })
    .map(function(status) {
      return {
        status: status,
        qtd: statusMap[status]
      };
    });

  topLentos.sort(function(a, b) {
    return Number(b.total_seg || 0) - Number(a.total_seg || 0);
  });

  const diagnostico = [];

  if (kpis.pendentes > 0) {
    diagnostico.push("Existem envios ainda sem Data Processamento. Eles aparecem como pendentes e não entram nas médias finais.");
  }

  if (kpis.fila_media_seg >= 120) {
    diagnostico.push("Tempo médio de fila elevado. Pode indicar acúmulo de itens, trigger atrasado ou limitação temporária do Apps Script.");
  }

  if (kpis.leitura_media_seg >= 90) {
    diagnostico.push("Tempo médio de leitura IA elevado. Pode indicar lentidão na chamada Gemini, arquivo pesado ou comprovante complexo.");
  }

  if (kpis.total_p95_seg >= 300) {
    diagnostico.push("P95 do tempo total acima de 5 minutos. Há cauda de lentidão relevante no período.");
  }

  if (!diagnostico.length) {
    diagnostico.push("Performance operacional dentro do comportamento esperado para o período.");
  }

  return {
    atualizado_em: smartSlipFormatarDataHora(new Date()),
    tipo_periodo: tipoPeriodo,
    ano: ano,
    mes: mes,
    dia: diaSelecionado,
    kpis: kpis,
    serie: serieFinal,
    status: statusRows,
    top_lentos: topLentos.slice(0, 15),
    diagnostico: diagnostico,
    plataforma: smartSlipGetStatusPlataformaPerformance_(kpis, statusRows)
  };
}

function smartSlipGetPerformanceJson(optionsJson) {
  try {
    smartSlipAssertUsuarioAutorizado_();

    const usuario = smartSlipGetUsuarioAtual();

    if (!(usuario.is_admin === true || usuario.is_analista_pro === true)) {
      return JSON.stringify({
        ok: false,
        erro: "Acesso restrito. Performance disponível apenas para Administrador ou Analista Pro."
      });
    }

    let options = {};

    try {
      options = optionsJson ? JSON.parse(optionsJson) : {};
    } catch (e) {
      options = {};
    }

    return JSON.stringify({
      ok: true,
      payload: smartSlipGetPerformance_(options)
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipGetRootFolderComprovantes() {
  const folderId = smartSlipGetScriptProperty("SMARTSLIP_FOLDER_ID");
  return DriveApp.getFolderById(folderId);
}

function smartSlipGetOrCreateFolder(parentFolder, folderName) {
  const nome = smartSlipSanitizarNomePasta(folderName);
  const folders = parentFolder.getFoldersByName(nome);

  if (folders.hasNext()) {
    return folders.next();
  }

  return parentFolder.createFolder(nome);
}

function smartSlipSanitizarNomePasta(nome) {
  return String(nome || "")
    .trim()
    .replace(/[\\\/:*?"<>|#%{}~&]/g, "-")
    .replace(/\s+/g, " ")
    .substring(0, 120);
}

function smartSlipNormalizarLojaParaPasta(loja) {
  const digits = String(loja || "").replace(/\D/g, "");

  if (!digits) {
    throw new Error("Loja inválida para criação de pasta.");
  }

  return digits.padStart(4, "0").slice(-4);
}

function smartSlipObterAnoMes(dataMovimento) {
  const data = smartSlipParseDateBR(dataMovimento);

  if (data) {
    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    return {
      ano: Utilities.formatDate(data, tz, "yyyy"),
      mes: Utilities.formatDate(data, tz, "MM")
    };
  }

  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  const hoje = new Date();

  return {
    ano: Utilities.formatDate(hoje, tz, "yyyy"),
    mes: Utilities.formatDate(hoje, tz, "MM")
  };
}

function smartSlipObterPastaAnoMesLoja(dataMovimento, loja) {
  const root = smartSlipGetRootFolderComprovantes();
  const anoMes = smartSlipObterAnoMes(dataMovimento);
  const loja4 = smartSlipNormalizarLojaParaPasta(loja);

  const pastaAno = smartSlipGetOrCreateFolder(root, anoMes.ano);
  const pastaMes = smartSlipGetOrCreateFolder(pastaAno, anoMes.mes);
  const pastaLoja = smartSlipGetOrCreateFolder(pastaMes, loja4);

  return pastaLoja;
}

function smartSlipMontarNomeArquivoComprovante(protocolo, loja, dataMovimento, nomeOriginal) {
  const loja4 = smartSlipNormalizarLojaParaPasta(loja);
  const data = String(dataMovimento || "sem-data").trim();
  const nome = String(nomeOriginal || "comprovante.pdf").trim();

  const nomeLimpo = nome
    .replace(/[\\\/:*?"<>|#%{}~&]/g, "-")
    .replace(/\s+/g, "_")
    .substring(0, 120);

  return [
    protocolo || "SS-SEM-PROTOCOLO",
    loja4,
    data,
    nomeLimpo
  ].join("_");
}

function smartSlipSalvarUploadEmPastaEstruturada(form, respostasUsuario, protocolo) {
  if (!form || !form.arquivoBase64) {
    throw new Error("Arquivo não recebido.");
  }

  respostasUsuario = respostasUsuario || {};

  const loja = respostasUsuario.loja || form.loja;

  const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);

  const dataMovimentoReferencia =
    respostasUsuario.data_movimento_inicio ||
    respostasUsuario.data_movimento ||
    respostasUsuario.data_movimento_fim ||
    form.data_movimento ||
    "";

  if (!loja) {
    throw new Error("Loja não informada para salvar comprovante.");
  }

  if (!dataMovimentoTexto) {
    throw new Error("Data de movimento não informada para salvar comprovante.");
  }

  if (!dataMovimentoReferencia) {
    throw new Error("Data de referência do movimento não informada para salvar comprovante.");
  }

  const pastaDestino = smartSlipObterPastaAnoMesLoja(dataMovimentoReferencia, loja);

  const base64Limpo = String(form.arquivoBase64).split(",").pop();
  const bytes = Utilities.base64Decode(base64Limpo);

  const nomeArquivo = smartSlipMontarNomeArquivoComprovante(
    protocolo,
    loja,
    dataMovimentoTexto,
    form.nomeArquivo || "comprovante.pdf"
  );

  const mimeType = form.mimeType || "application/pdf";
  const blob = Utilities.newBlob(bytes, mimeType, nomeArquivo);

  const file = pastaDestino.createFile(blob);

  return {
    file_id: file.getId(),
    link_comprovante: file.getUrl(),
    nome_arquivo: file.getName(),
    pasta_id: pastaDestino.getId(),
    pasta_url: pastaDestino.getUrl()
  };
}

function smartSlipSalvarCupomRetiradaMarketing_(
  form,
  respostasUsuario,
  protocolo
) {
  form = form || {};
  respostasUsuario =
    respostasUsuario || {};

  /*
    Novo formato: vários anexos.

    O formato antigo continua aceito para evitar
    incompatibilidade com versões anteriores do HTML.
  */
  let anexos = Array.isArray(
    form.anexos_retirada
  )
    ? form.anexos_retirada.slice()
    : [];

  if (
    !anexos.length &&
    form.cupom_retirada_marketing_base64
  ) {
    anexos.push({
      base64:
        form.cupom_retirada_marketing_base64,

      nome:
        form.cupom_retirada_marketing_nome ||
        "anexo_retirada.pdf",

      mime_type:
        form.cupom_retirada_marketing_mime_type ||
        "application/pdf"
    });
  }

  anexos = anexos.filter(function(anexo) {
    return (
      anexo &&
      String(anexo.base64 || "").trim()
    );
  });

  if (!anexos.length) {
    return {
      file_id: "",
      link: "",
      nome: ""
    };
  }

  const limiteQuantidade = 5;
  const limiteArquivoBytes =
    10 * 1024 * 1024;

  const limiteTotalBytes =
    15 * 1024 * 1024;

  if (anexos.length > limiteQuantidade) {
    throw new Error(
      "É permitido anexar no máximo " +
      limiteQuantidade +
      " evidências da retirada."
    );
  }

  const loja =
    respostasUsuario.loja ||
    form.loja;

  const dataMovimentoTexto =
    smartSlipMontarDataMovimentoTexto(
      respostasUsuario
    );

  const dataMovimentoReferencia =
    respostasUsuario.data_movimento_inicio ||
    respostasUsuario.data_movimento ||
    respostasUsuario.data_movimento_fim ||
    form.data_movimento_inicio ||
    "";

  if (
    !loja ||
    !dataMovimentoReferencia
  ) {
    throw new Error(
      "Não foi possível definir a pasta dos anexos da retirada."
    );
  }

  /*
    Valida todos os arquivos antes de criar a pasta.
  */
  let totalBytes = 0;

  const anexosPreparados =
    anexos.map(function(anexo, indice) {
      const mimeType = String(
        anexo.mime_type ||
        "application/pdf"
      ).trim();

      const nomeOriginal = String(
        anexo.nome ||
        (
          "anexo_retirada_" +
          (indice + 1) +
          ".pdf"
        )
      ).trim();

      const extensaoPermitida =
        /\.(pdf|png|jpe?g|webp|heic)$/i
          .test(nomeOriginal);

      const mimePermitido =
        mimeType.indexOf("image/") === 0 ||
        mimeType === "application/pdf" ||
        extensaoPermitida;

      if (!mimePermitido) {
        throw new Error(
          "O arquivo " +
          nomeOriginal +
          " não é uma imagem ou PDF."
        );
      }

      const base64Limpo = String(
        anexo.base64 || ""
      )
        .split(",")
        .pop();

      const bytes =
        Utilities.base64Decode(
          base64Limpo
        );

      if (
        bytes.length >
        limiteArquivoBytes
      ) {
        throw new Error(
          "O arquivo " +
          nomeOriginal +
          " deve ter no máximo 10 MB."
        );
      }

      totalBytes += bytes.length;

      if (
        totalBytes >
        limiteTotalBytes
      ) {
        throw new Error(
          "O conjunto de anexos da retirada deve ter no máximo 15 MB."
        );
      }

      return {
        bytes: bytes,
        mime_type: mimeType,
        nome_original: nomeOriginal
      };
    });

  const pastaLoja =
    smartSlipObterPastaAnoMesLoja(
      dataMovimentoReferencia,
      loja
    );

  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  const timestamp =
    Utilities.formatDate(
      new Date(),
      timezone,
      "yyyyMMdd_HHmmss"
    );

  const identificador =
    Utilities
      .getUuid()
      .replace(/-/g, "")
      .substring(0, 8);

  const nomePasta =
    smartSlipSanitizarNomePasta(
      [
        "ANEXOS_RETIRADA",
        protocolo ||
          "SEM_PROTOCOLO",
        timestamp,
        identificador
      ].join("_")
    );

  const pastaAnexos =
    pastaLoja.createFolder(
      nomePasta
    );

  try {
    anexosPreparados.forEach(
      function(anexo, indice) {
        const sequencia =
          String(indice + 1)
            .padStart(2, "0");

        const nomeArquivo =
          smartSlipMontarNomeArquivoComprovante(
            "RET-" +
              protocolo +
              "-" +
              sequencia,

            loja,
            dataMovimentoTexto,
            anexo.nome_original
          );

        const blob =
          Utilities.newBlob(
            anexo.bytes,
            anexo.mime_type,
            nomeArquivo
          );

        pastaAnexos.createFile(
          blob
        );
      }
    );

  } catch (err) {
    /*
      Evita deixar uma pasta incompleta visível
      caso um arquivo falhe durante o salvamento.
    */
    try {
      pastaAnexos.setTrashed(true);
    } catch (errTrash) {
      Logger.log(
        "Não foi possível excluir a pasta incompleta: " +
        String(errTrash)
      );
    }

    throw err;
  }

  const quantidade =
    anexosPreparados.length;

  return {
    /*
      Agora o ID e o link representam a pasta,
      e não cada arquivo individual.
    */
    file_id:
      pastaAnexos.getId(),

    link:
      pastaAnexos.getUrl(),

    nome:
      quantidade === 1
        ? "1 anexo de retirada"
        : quantidade +
          " anexos de retirada"
  };
}

function smartSlipBuscarCupomRetiradaMarketingPorLote_(
  sh,
  protocoloLote
) {
  protocoloLote = String(
    protocoloLote || ""
  ).trim();

  if (
    !sh ||
    !protocoloLote ||
    sh.getLastRow() < 2
  ) {
    return {
      file_id: "",
      link: "",
      nome: ""
    };
  }

  const lastCol = Math.max(
    32,
    sh.getLastColumn()
  );

  const values = sh.getRange(
    2,
    1,
    sh.getLastRow() - 1,
    lastCol
  ).getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];

    const protocoloLoteRow = String(
      row[18] || ""
    ).trim();

    const linkCupom = String(
      row[30] || ""
    ).trim();

    if (
      protocoloLoteRow === protocoloLote &&
      linkCupom
    ) {
      return {
        file_id: String(row[29] || "").trim(),
        link: linkCupom,
        nome: String(row[31] || "").trim()
      };
    }
  }

  return {
    file_id: "",
    link: "",
    nome: ""
  };
}

function smartSlipCopiarArquivoParaPastaEstruturada(fileId, respostasUsuario, protocolo) {
  respostasUsuario = respostasUsuario || {};

  const loja = respostasUsuario.loja;

  const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);

  const dataMovimentoReferencia =
    respostasUsuario.data_movimento_inicio ||
    respostasUsuario.data_movimento ||
    respostasUsuario.data_movimento_fim ||
    "";

  if (!fileId) {
    throw new Error("fileId não informado.");
  }

  if (!loja) {
    throw new Error("Loja não informada.");
  }

  if (!dataMovimentoTexto) {
    throw new Error("Data de movimento não informada.");
  }

  if (!dataMovimentoReferencia) {
    throw new Error("Data de referência do movimento não informada.");
  }

  const fileOriginal = DriveApp.getFileById(fileId);

  // A pasta ano/mês/loja usa uma data única de referência.
  // Se for período, usa a data inicial.
  const pastaDestino = smartSlipObterPastaAnoMesLoja(dataMovimentoReferencia, loja);

  const nomeArquivo = smartSlipMontarNomeArquivoComprovante(
    protocolo,
    loja,
    dataMovimentoTexto,
    fileOriginal.getName()
  );

  const novoArquivo = fileOriginal.makeCopy(nomeArquivo, pastaDestino);

  return {
    file_id: novoArquivo.getId(),
    link_comprovante: novoArquivo.getUrl(),
    nome_arquivo: novoArquivo.getName(),
    pasta_id: pastaDestino.getId(),
    pasta_url: pastaDestino.getUrl()
  };
}

function smartSlipTesteCriarPastasComprovante() {
  const fileId = smartSlipGetScriptProperty("SMARTSLIP_TEST_FILE_ID");

  const respostasUsuario = {
    loja: "0178",
    data_movimento_inicio: "01/05/2026",
    data_movimento_fim: "04/05/2026",
    houve_retirada: false,
    valor_retirada: 0,
    motivo_retirada: "Não houve retirada",
    mais_comprovantes: false
  };

  const protocolo = "SS-TESTE-PASTAS";

  const arquivo = smartSlipCopiarArquivoParaPastaEstruturada(
    fileId,
    respostasUsuario,
    protocolo
  );

  Logger.log(JSON.stringify(arquivo, null, 2));
}

function smartSlipParseDateBR(valor) {
  if (!valor) return null;

  const txt = String(valor).trim();

  // Aceita dd/mm/aaaa
  let m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (m) {
    return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  }

  // Aceita yyyy-mm-dd também, para compatibilidade com input type="date"
  m = txt.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }

  return null;
}

function smartSlipCorrigirAnoDataDocumentoPeloMovimento_(dataDocumentoTexto, movInicioTexto, movFimTexto) {
  const dataDoc = smartSlipParseDateBR(dataDocumentoTexto);
  const movFim = smartSlipParseDateBR(movFimTexto || movInicioTexto);

  if (!dataDoc || !movFim) {
    return {
      data: dataDocumentoTexto || "",
      corrigida: false,
      motivo: ""
    };
  }

  // Se a data do documento já é maior ou igual ao fim do movimento, não corrige.
  if (dataDoc >= movFim) {
    return {
      data: dataDocumentoTexto || "",
      corrigida: false,
      motivo: ""
    };
  }

  const anoDoc = dataDoc.getFullYear();
  const anoMov = movFim.getFullYear();

  if (anoDoc >= anoMov) {
    return {
      data: dataDocumentoTexto || "",
      corrigida: false,
      motivo: ""
    };
  }

  const candidatos = [
    new Date(anoMov, dataDoc.getMonth(), dataDoc.getDate()),
    new Date(anoMov + 1, dataDoc.getMonth(), dataDoc.getDate())
  ];

  for (let i = 0; i < candidatos.length; i++) {
    const candidato = candidatos[i];

    const diffDias = Math.round(
      (candidato.getTime() - movFim.getTime()) / (1000 * 60 * 60 * 24)
    );

    /*
      Aceita correção só se a data corrigida ficar entre o fim do movimento
      e até 31 dias depois. Isso evita corrigir documentos realmente antigos.
    */
    if (diffDias >= 0 && diffDias <= 31) {
      return {
        data: smartSlipFormatDateBR(candidato),
        corrigida: true,
        motivo:
          "Ano da data do documento corrigido automaticamente de " +
          smartSlipFormatDateBR(dataDoc) +
          " para " +
          smartSlipFormatDateBR(candidato) +
          " com base no período de movimento."
      };
    }
  }

  return {
    data: dataDocumentoTexto || "",
    corrigida: false,
    motivo: ""
  };
}

function smartSlipFormatDateBR(date) {
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  return Utilities.formatDate(date, tz, "dd/MM/yyyy");
}

function smartSlipNormalizarPeriodoMovimento(respostasUsuario, dados) {
  respostasUsuario = respostasUsuario || {};
  dados = dados || {};

  let inicio =
    respostasUsuario.data_movimento_inicio ||
    respostasUsuario.data_movimento ||
    dados.data_movimento_inicio ||
    dados.data_movimento ||
    "";

  let fim =
    respostasUsuario.data_movimento_fim ||
    dados.data_movimento_fim ||
    inicio;

  dados.data_movimento_inicio = inicio || "";
  dados.data_movimento_fim = fim || "";

  if (inicio && fim && inicio === fim) {
    dados.data_movimento = inicio;
  } else if (inicio && fim) {
    dados.data_movimento = inicio + " a " + fim;
  } else {
    dados.data_movimento = inicio || "";
  }

  return dados;
}

function smartSlipValidarGuardrailMovimento(resultado, dados) {
  resultado = resultado || {};
  dados = dados || {};

  if (!Array.isArray(resultado.divergencias)) {
    resultado.divergencias = [];
  }

  const dataDeposito = smartSlipParseDateBR(dados.data_deposito);
  const movInicio = smartSlipParseDateBR(dados.data_movimento_inicio);
  const movFim = smartSlipParseDateBR(dados.data_movimento_fim);

  if (!dataDeposito || !movInicio || !movFim) {
    return resultado;
  }

  if (movInicio > movFim) {
    resultado.status = "DIVERGENCIA";
    resultado.divergencias.push(
      "Data inicial do movimento maior que a data final do movimento."
    );
  }

  if (movFim > dataDeposito) {
    resultado.status = "DIVERGENCIA";
    resultado.divergencias.push(
      "Data de movimento maior que a data do depósito/documento. Movimento: " +
      smartSlipFormatDateBR(movFim) +
      " | Depósito/documento: " +
      smartSlipFormatDateBR(dataDeposito)
    );
  }

  return resultado;
}

function smartSlipGarantirCabecalhoFila() {
  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  let sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh) {
    sh = ss.insertSheet(SMARTSLIP_ABA_FILA);
  }

  const headers = [
    "Data Registro",
    "Protocolo",
    "Email Usuário",
    "Loja Informada",
    "Banco",
    "Data Movimento",
    "Houve Retirada",
    "Valor Retirada",
    "Motivo Retirada",
    "Mais Comprovantes",
    "File ID",
    "Link Comprovante",
    "Nome Arquivo",
    "Status Fila",
    "Mensagem",
    "JSON Respostas",
    "JSON Resultado",
    "Data Processamento",

    // Controle de lote - não alterar A:R
    "Protocolo Lote",
    "Protocolo Envio",
    "Sequência Lote",
    "Status Lote",
    "Último Envio do Lote",
    "Total Movimento Lote",

    // Performance - novas colunas Y:AC
    "Data Início Processamento",
    "Tempo Fila (seg)",
    "Tempo Leitura IA (seg)",
    "Tempo Total (seg)",
    "Sinal Performance",

    // Evidência de retirada solicitada pelo Marketing
    "Anexos Retirada ID",
    "Link Anexos Retirada",
    "Resumo Anexos Retirada",

    // Aviso automático de falha de processamento
    "Aviso Falha Enviado Em",
    "Aviso Falha Destinatário",
    "Aviso Falha Erro",

    // Origem do dispositivo utilizado no envio
    "Dispositivo Envio"
  ];

  if (sh.getMaxColumns() < headers.length) {
    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length - sh.getMaxColumns()
    );
  }

  const primeiraCelula = String(sh.getRange(1, 1).getValue() || "").trim();

  if (primeiraCelula !== "Data Registro") {
    sh.insertRowBefore(1);
  }

  sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  sh.setFrozenRows(1);

  return sh;
}

function smartSlipTesteCabecalhoFila() {
  smartSlipGarantirCabecalhoFila();
  Logger.log("Cabeçalho da SMARTSLIP_FILA criado/verificado.");
}

function smartSlipMontarDataMovimentoTexto(respostasUsuario) {
  respostasUsuario = respostasUsuario || {};

  const inicio = respostasUsuario.data_movimento_inicio || respostasUsuario.data_movimento || "";
  const fim = respostasUsuario.data_movimento_fim || "";

  if (inicio && fim && inicio !== fim) {
    return inicio + " a " + fim;
  }

  return inicio || fim || "";
}

function smartSlipValidarValoresDiariosMovimento_(payload, dataInicioBR, dataFimBR) {
  const inicio = smartSlipParseDateBR(dataInicioBR);
  const fim = smartSlipParseDateBR(dataFimBR);

  if (!inicio || !fim) {
    throw new Error("Período de movimento inválido para validação dos valores diários.");
  }

  if (fim < inicio) {
    throw new Error("Data movimento final menor que a data movimento inicial.");
  }

  const datasEsperadas = smartSlipGerarRangeDatasBR_(inicio, fim);

  if (datasEsperadas.length > 31) {
    throw new Error("O intervalo de movimento não pode passar de 31 dias.");
  }

  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload || "{}");
    } catch (err) {
      throw new Error("Valores diários do movimento em formato inválido.");
    }
  }

  payload = payload || {};

  const itens = Array.isArray(payload.itens)
    ? payload.itens
    : Array.isArray(payload)
      ? payload
      : [];

  if (itens.length !== datasEsperadas.length) {
    throw new Error(
      "Quantidade de valores diários diferente do período informado. Esperado: " +
      datasEsperadas.length +
      " dia(s). Recebido: " +
      itens.length +
      "."
    );
  }

  const mapa = {};
  let total = 0;

  itens.forEach(function(item) {
    const data = String(item.data || "").trim();
    const valor = Number(item.valor || 0);

    if (!data) {
      throw new Error("Existe valor diário sem data informada.");
    }

    if (isNaN(valor) || valor <= 0) {
      throw new Error("Valor diário inválido para " + data + ". Informe valor maior que zero.");
    }

    if (valor < 0) {
      throw new Error("Valor diário negativo não é permitido para " + data + ".");
    }

    mapa[data] = valor;
    total += valor;
  });

  datasEsperadas.forEach(function(data) {
    if (!mapa[data]) {
      throw new Error("Valor diário não informado para " + data + ".");
    }
  });

  return {
    periodo_inicio: dataInicioBR,
    periodo_fim: dataFimBR,
    itens: datasEsperadas.map(function(data) {
      return {
        data: data,
        valor: mapa[data]
      };
    }),
    total: total
  };
}

function smartSlipGerarRangeDatasBR_(inicio, fim) {
  const datas = [];
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  const atual = new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate());
  const limite = new Date(fim.getFullYear(), fim.getMonth(), fim.getDate());

  while (atual <= limite) {
    datas.push(Utilities.formatDate(atual, tz, "dd/MM/yyyy"));
    atual.setDate(atual.getDate() + 1);
  }

  return datas;
}

function smartSlipTesteFilaPeriodo() {
  const sh = smartSlipGarantirCabecalhoFila();

  const respostasUsuario = {
    loja: "0171",
    banco: "",
    data_movimento_inicio: "01/05/2026",
    data_movimento_fim: "04/05/2026",
    houve_retirada: false,
    valor_retirada: 0,
    motivo_retirada: "Não houve retirada",
    mais_comprovantes: false
  };

  const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);

  sh.appendRow([
    new Date(),
    "SS-TESTE-PERIODO-001",
    Session.getActiveUser().getEmail() || "",
    smartSlipNormalizarLoja4(respostasUsuario.loja),
    respostasUsuario.banco || "",
    dataMovimentoTexto,
    respostasUsuario.houve_retirada ? "Sim" : "Não",
    respostasUsuario.valor_retirada,
    respostasUsuario.motivo_retirada,
    respostasUsuario.mais_comprovantes ? "Sim" : "Não",
    "FILE_ID_TESTE",
    "https://drive.google.com/file/d/ARQUIVO_EXEMPLO/view",
    "comprovante_teste_periodo.pdf",
    "RECEBIDO",
    "Linha de teste com período criada na fila.",
    JSON.stringify(respostasUsuario),
    "",
    ""
  ]);

  Logger.log("Linha de teste com período criada na SMARTSLIP_FILA.");
  Logger.log("Data Movimento gravada: " + dataMovimentoTexto);
}

function doGet(e) {
  const faviconUrl = "https://www.gstatic.com/images/branding/product/2x/apps_script_48dp.png";

  return HtmlService
    .createHtmlOutputFromFile("SmartSlipApp")
    .setTitle("SmartSlip - Envio de Comprovantes")
    .setFaviconUrl(faviconUrl)
    .addMetaTag("viewport", "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function smartSlipValidarCooldownEnvio_(emailUsuario) {
  emailUsuario = String(emailUsuario || "").trim().toLowerCase();

  if (!emailUsuario) {
    return;
  }

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh || sh.getLastRow() < 2) {
    return;
  }

  const agora = new Date();
  const limiteMs = SMARTSLIP_COOLDOWN_ENVIO_SEGUNDOS * 1000;

  const lastRow = sh.getLastRow();
  const qtdLinhas = Math.min(lastRow - 1, 80);

  // Lê só as últimas linhas para evitar pesar a planilha.
  const startRow = Math.max(2, lastRow - qtdLinhas + 1);
  const values = sh.getRange(startRow, 1, lastRow - startRow + 1, 18).getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];

    const dataRegistro = row[0];
    const emailRow = String(row[2] || "").trim().toLowerCase();

    if (emailRow !== emailUsuario) {
      continue;
    }

    if (!(dataRegistro instanceof Date)) {
      continue;
    }

    const diffMs = agora.getTime() - dataRegistro.getTime();

    if (diffMs >= 0 && diffMs < limiteMs) {
      const restante = Math.ceil((limiteMs - diffMs) / 1000);

      throw new Error(
        "Aguarde " +
        restante +
        " segundo(s) para enviar um novo comprovante. " +
        "Existe um envio recente registrado para este usuário."
      );
    }

    return;
  }
}

function smartSlipUsuarioPodeVerRegistroHistorico_(usuario, row, respostas) {
  usuario = usuario || smartSlipGetUsuarioAtual();
  row = row || [];
  respostas = respostas || {};

  const emailUsuario = String(usuario.email || "").trim().toLowerCase();
  const emailLinha = String(row[2] || "").trim().toLowerCase();

  const emailOriginal = String(
    respostas.email_usuario_original ||
    row[2] ||
    ""
  ).trim().toLowerCase();

  const lojaRow = smartSlipNormalizarLoja4(row[3] || "");

  if (usuario.is_admin === true || usuario.is_analista_pro === true) {
    return true;
  }

  if (usuario.is_regional === true) {
    return smartSlipUsuarioPodeVerLoja_(usuario, lojaRow);
  }

  /*
    Usuário comum:
    - vê o que ele mesmo enviou;
    - vê correção feita por admin se email_usuario_original for o e-mail dele.
  */
  return emailLinha === emailUsuario || emailOriginal === emailUsuario;
}

function smartSlipValidarContextoReenvioOrigem_(usuario, emailUsuario, protocoloOrigem) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  emailUsuario = String(
    emailUsuario ||
    usuario.email ||
    Session.getActiveUser().getEmail() ||
    ""
  ).trim().toLowerCase();

  protocoloOrigem = String(protocoloOrigem || "").trim();

  if (!protocoloOrigem) {
    throw new Error("Reenvio inválido: protocolo de origem não informado.");
  }

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh || sh.getLastRow() < 2) {
    throw new Error("Reenvio inválido: fila de comprovantes vazia.");
  }

  const encontrado = smartSlipBuscarLinhaFilaPorProtocolo_(sh, protocoloOrigem);

  if (!encontrado) {
    throw new Error("Reenvio inválido: protocolo de origem não encontrado na SMARTSLIP_FILA.");
  }

  const row = encontrado.row;
  const respostas = smartSlipParseJsonSeguro_(row[15]);
  const statusFila = String(row[13] || "").trim();

  if (!smartSlipUsuarioPodeVerRegistroHistorico_(usuario, row, respostas)) {
    throw new Error("Reenvio não permitido: o envio de origem não pertence ao usuário/perfil atual.");
  }

  if (!smartSlipStatusPermiteReenvio_(statusFila)) {
    throw new Error("Reenvio não permitido para o status atual: " + statusFila);
  }

  const protocoloRaiz = String(
    respostas.protocolo_raiz ||
    respostas.protocolo_original ||
    respostas.protocolo_reenvio_origem ||
    protocoloOrigem ||
    ""
  ).trim();

  const emailOriginal = String(
    respostas.email_usuario_original ||
    row[2] ||
    emailUsuario ||
    ""
  ).trim().toLowerCase();

  return {
    row_index: encontrado.row_index,
    row_origem: row,
    protocolo_reenvio_origem: protocoloOrigem,
    protocolo_original: protocoloOrigem,
    protocolo_raiz: protocoloRaiz || protocoloOrigem,
    email_usuario_original: emailOriginal,
    reenvio_origem_status: statusFila
  };
}

function smartSlipBuscarLinhaFilaPorProtocolo_(sh, protocolo) {
  protocolo = String(protocolo || "").trim();

  if (!sh || !protocolo || sh.getLastRow() < 2) {
    return null;
  }

  const lastCol = Math.max(29, sh.getLastColumn());
  const values = sh.getRange(2, 1, sh.getLastRow() - 1, lastCol).getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];
    const protocoloLinha = String(row[1] || "").trim();

    if (protocoloLinha === protocolo) {
      return {
        row_index: i + 2,
        row: row
      };
    }
  }

  return null;
}

function smartSlipNormalizarMotivoRetirada_(valor) {
  const raw = String(valor || "").trim();

  if (!raw) {
    return "";
  }

  const txt = raw
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  const mapa = {
    "FALTA": "FALTA",
    "CANCELAMENTO": "CANCELAMENTO",
    "ESTORNO": "ESTORNO",
    "REEMBOLSO": "REEMBOLSO",
    "MARKETING": "MARKETING (RETIRADA DE PRODUTOS)",
    "MARKETING (RETIRADA DE PRODUTOS)":
      "MARKETING (RETIRADA DE PRODUTOS)"
  };

  return mapa[txt] || "";
}

function smartSlipMotivoRetiradaEhMarketing_(valor) {
  return smartSlipNormalizarMotivoRetirada_(valor) ===
    "MARKETING (RETIRADA DE PRODUTOS)";
}

function smartSlipNormalizarDispositivoEnvio_(valor) {

  const dispositivo =
    String(
      valor || ""
    )
      .trim()
      .toUpperCase()
      .normalize("NFD")
      .replace(
        /[\u0300-\u036f]/g,
        ""
      );


  if (
    dispositivo === "CELULAR" ||
    dispositivo === "MOBILE" ||
    dispositivo === "SMARTPHONE" ||
    dispositivo === "TABLET"
  ) {
    return "CELULAR";
  }


  if (
    dispositivo === "DESKTOP" ||
    dispositivo === "PC" ||
    dispositivo === "COMPUTADOR" ||
    dispositivo === "NOTEBOOK"
  ) {
    return "DESKTOP";
  }


  return "NAO_IDENTIFICADO";
}

function smartSlipEnviarComprovanteApp(form) {
  try {
    smartSlipAssertUsuarioAutorizado_();

    if (!form) {
      throw new Error("Formulário não recebido.");
    }

    if (!form.arquivoBase64) {
      throw new Error("Arquivo não recebido.");
    }

    if (!form.loja) {
      throw new Error("Número da loja não informado.");
    }

    if (!form.data_movimento_inicio) {
      throw new Error("Data de movimento inicial não informada.");
    }

    if (!form.data_movimento_fim) {
      throw new Error("Data de movimento final não informada. Se for uma única data, repita a data inicial.");
    }

    const dataInicioObj = smartSlipParseDateBR(form.data_movimento_inicio);
    const dataFimObj = smartSlipParseDateBR(form.data_movimento_fim);

    if (!dataInicioObj) {
      throw new Error("Data de movimento inicial inválida.");
    }

    if (!dataFimObj) {
      throw new Error("Data de movimento final inválida.");
    }

    dataInicioObj.setHours(0, 0, 0, 0);
    dataFimObj.setHours(0, 0, 0, 0);

    if (dataFimObj < dataInicioObj) {
      throw new Error("A data movimento final não pode ser menor que a data movimento inicial.");
    }

    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);

    if (dataFimObj > hoje) {
      throw new Error("A data movimento final não pode ser maior que a data atual.");
    }

    const valoresDiariosMovimento = smartSlipValidarValoresDiariosMovimento_(
      form.valores_diarios_movimento,
      form.data_movimento_inicio,
      form.data_movimento_fim
    );

    let preValidacaoTotalIa = smartSlipNormalizarPreValidacaoTotalIa_(
      form.pre_validacao_total_ia,
      valoresDiariosMovimento.total
    );

    preValidacaoTotalIa = smartSlipAplicarBloqueioMultiploConfiavelBackend_(
      preValidacaoTotalIa,
      form
    );

    const usuarioAtual = smartSlipGetUsuarioAtual();

    const emailUsuario = String(
      usuarioAtual.email ||
      Session.getActiveUser().getEmail() ||
      ""
    ).trim().toLowerCase();

    const ignorarTravasIaAdminSolicitado =
      String(form.ignorar_travas_ia_admin || "").toLowerCase() === "true" ||
      String(form.modo_processamento_admin || "").toUpperCase() === "SEM_TRAVAS_IA";

    if (ignorarTravasIaAdminSolicitado && usuarioAtual.is_admin !== true) {
      throw new Error("A opção administrativa de ignorar travas da IA é permitida apenas para administradores.");
    }

    const ignorarTravasIaAdmin =
      ignorarTravasIaAdminSolicitado && usuarioAtual.is_admin === true;

    if (ignorarTravasIaAdmin && preValidacaoTotalIa) {
      preValidacaoTotalIa.bloquear_envio = false;
      preValidacaoTotalIa.bloqueio_ignorado_por_admin = true;
      preValidacaoTotalIa.override_admin = true;
      preValidacaoTotalIa.admin_override_por = emailUsuario;
    }

    const envioEmLoteForm =
      String(form.envio_lote || "") === "true" ||
      String(form.mais_comprovantes || "") === "true" ||
      String(form.protocolo_lote || "").trim() !== "";

    if (
      !ignorarTravasIaAdmin &&
      preValidacaoTotalIa &&
      preValidacaoTotalIa.bloquear_envio === true &&
      !envioEmLoteForm
    ) {
      throw new Error(
        "A soma dos valores diários não confere com o total lido pela IA no comprovante. " +
        "Revise os valores antes de enviar."
      );
    }

          /*
     * A informação principal é o campo houve_retirada.
     * O motivo só deve ser validado quando realmente houve retirada.
     */
    const houveRetiradaValidacao =
      String(form.houve_retirada || "")
        .trim()
        .toLowerCase() === "true";

    const motivoRetiradaRaw = houveRetiradaValidacao
      ? String(form.motivo_retirada || "").trim()
      : "";

    const motivoRetiradaValidacao = houveRetiradaValidacao
      ? smartSlipNormalizarMotivoRetirada_(motivoRetiradaRaw)
      : "";

    const valorRetiradaValidacao = Number(
      form.valor_retirada || 0
    );

    if (valorRetiradaValidacao < 0) {
      throw new Error(
        "O valor da retirada não pode ser negativo."
      );
    }

    if (
      houveRetiradaValidacao &&
      !motivoRetiradaRaw
    ) {
      throw new Error(
        "Informe o motivo da retirada."
      );
    }

    if (
      houveRetiradaValidacao &&
      !motivoRetiradaValidacao
    ) {
      throw new Error(
        "Motivo de retirada inválido. " +
        "Selecione uma das opções disponíveis."
      );
    }

    if (
      houveRetiradaValidacao &&
      (
        !valorRetiradaValidacao ||
        valorRetiradaValidacao <= 0
      )
    ) {
      throw new Error(
        "Informe o valor da retirada."
      );
    }

    if (
      !houveRetiradaValidacao &&
      valorRetiradaValidacao > 0
    ) {
      throw new Error(
        "Selecione o motivo correspondente à retirada."
      );
    }

    const ehContinuacaoLoteForm = String(form.protocolo_lote || "").trim() !== "";

    if (!ehContinuacaoLoteForm) {
      smartSlipValidarCooldownEnvio_(emailUsuario);
    }

    const lojaForm = smartSlipNormalizarLoja4(form.loja);
    const lojaPadraoUsuario = smartSlipNormalizarLoja4(usuarioAtual.loja_padrao || "");

    if (!usuarioAtual.is_admin) {
      if (!lojaPadraoUsuario) {
        throw new Error("Configure sua loja padrão antes de enviar comprovantes.");
      }

      if (lojaForm && lojaForm !== lojaPadraoUsuario) {
        throw new Error("A loja enviada não corresponde à loja padrão configurada para seu usuário.");
      }
    }

    const loja4 = usuarioAtual.is_admin ? lojaForm : lojaPadraoUsuario;

    if (!loja4) {
      throw new Error("Loja inválida para envio.");
    }

    const tipoDepositoUsuario = smartSlipNormalizarTipoDeposito_(usuarioAtual.tipo_deposito || "");
    const tipoDepositoForm = smartSlipNormalizarTipoDeposito_(form.tipo_deposito || "");
    const tipoDepositoFinal = tipoDepositoUsuario || tipoDepositoForm;

    if (!tipoDepositoFinal) {
      throw new Error("Configure o tipo de depósito da loja na página Configurações antes de enviar comprovantes.");
    }

    if (tipoDepositoForm && tipoDepositoUsuario && tipoDepositoForm !== tipoDepositoUsuario) {
      throw new Error("O tipo de depósito enviado não corresponde ao tipo configurado para a loja. Atualize em Configurações.");
    }

    const houveRetiradaResposta = houveRetiradaValidacao;

    const respostasUsuario = {
      loja: loja4,
      tipo_deposito: tipoDepositoFinal,
      time: usuarioAtual.time || "",
      gerente_regional: usuarioAtual.gerente_regional || "",
      email_regional: usuarioAtual.email_regional || "",
      data_movimento_inicio: form.data_movimento_inicio,
      data_movimento_fim: form.data_movimento_fim,
      houve_retirada: houveRetiradaResposta,
      valor_retirada: houveRetiradaResposta ? Number(form.valor_retirada || 0) : 0,
      motivo_retirada: houveRetiradaResposta
        ? motivoRetiradaValidacao
        : "Não houve retirada",
      valores_diarios_movimento: valoresDiariosMovimento,
      pre_validacao_total_ia: preValidacaoTotalIa,
      mais_comprovantes: String(form.mais_comprovantes) === "true",

      ignorar_travas_ia_admin: ignorarTravasIaAdmin,
      modo_processamento_admin: ignorarTravasIaAdmin ? "SEM_TRAVAS_IA" : "",
      admin_override_por: ignorarTravasIaAdmin ? emailUsuario : "",
      admin_override_em: ignorarTravasIaAdmin ? new Date().toISOString() : ""
    };

    const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);

const sh = smartSlipGarantirCabecalhoFila();

const protocoloReenvioOrigemForm = String(
  form.protocolo_reenvio_origem || ""
).trim();

const reenvioSolicitado =
  String(form.reenvio_ativo || "").toLowerCase() === "true" ||
  !!protocoloReenvioOrigemForm;

let contextoReenvio = null;

if (reenvioSolicitado) {
  contextoReenvio = smartSlipValidarContextoReenvioOrigem_(
    usuarioAtual,
    emailUsuario,
    protocoloReenvioOrigemForm
  );
}

const controleLote = contextoReenvio
  ? {
      eh_lote: false,
      eh_continuacao_lote: false,
      protocolo_lote: contextoReenvio.protocolo_reenvio_origem,
      protocolo_envio: contextoReenvio.protocolo_reenvio_origem,
      sequencia_lote: 1,
      proxima_sequencia_lote: 2,
      status_lote: "FECHADO",
      ultimo_envio_lote: true,
      total_movimento_lote: Number(valoresDiariosMovimento.total || 0)
    }
  : smartSlipMontarControleLoteEnvio_(
      form,
      valoresDiariosMovimento
    );

const protocolo = controleLote.protocolo_envio;

respostasUsuario.protocolo = protocolo;
respostasUsuario.protocolo_lote = controleLote.protocolo_lote;
respostasUsuario.protocolo_envio = controleLote.protocolo_envio;
respostasUsuario.sequencia_lote = controleLote.sequencia_lote;
respostasUsuario.status_lote = controleLote.status_lote;
respostasUsuario.ultimo_envio_lote = controleLote.ultimo_envio_lote;
respostasUsuario.total_movimento_lote = controleLote.total_movimento_lote;
respostasUsuario.envio_lote = controleLote.eh_lote;

respostasUsuario.reenvio_ativo = !!contextoReenvio;
respostasUsuario.tipo_envio = contextoReenvio ? "REENVIO_CORRECAO" : "ORIGINAL";
respostasUsuario.protocolo_reenvio_origem = contextoReenvio
  ? contextoReenvio.protocolo_reenvio_origem
  : "";

respostasUsuario.protocolo_original = contextoReenvio
  ? contextoReenvio.protocolo_original
  : protocolo;

respostasUsuario.protocolo_raiz = contextoReenvio
  ? contextoReenvio.protocolo_raiz
  : protocolo;

respostasUsuario.email_usuario_original = contextoReenvio
  ? contextoReenvio.email_usuario_original
  : emailUsuario;

respostasUsuario.reenviado_por = emailUsuario;

respostasUsuario.reenvio_origem_status = contextoReenvio
  ? contextoReenvio.reenvio_origem_status
  : "";

if (!contextoReenvio) {
  smartSlipValidarContinuidadeLote_(
    sh,
    controleLote,
    emailUsuario,
    loja4,
    dataMovimentoTexto
  );
}

const arquivo = smartSlipSalvarUploadEmPastaEstruturada(
  form,
  respostasUsuario,
  protocolo
);

const aplicarRetiradaNesteEnvio =
  houveRetiradaResposta &&
  (
    controleLote.eh_lote !== true ||
    Number(controleLote.sequencia_lote || 1) === 1
  );

  let anexosRetirada = {
  file_id: "",
  link: "",
  nome: ""
};

/*
  Em um reenvio, preserva os anexos já
  registrados quando o usuário não selecionar
  novos arquivos.
*/
if (
  contextoReenvio &&
  contextoReenvio.row_origem
) {
  const rowOrigem =
    contextoReenvio.row_origem;

  const respostasOrigem =
    smartSlipParseJsonSeguro_(
      rowOrigem[15]
    );

  anexosRetirada = {
    file_id: String(
      respostasOrigem
        .cupom_retirada_marketing_file_id ||
      rowOrigem[29] ||
      ""
    ).trim(),

    link: String(
      respostasOrigem
        .cupom_retirada_marketing_link ||
      rowOrigem[30] ||
      ""
    ).trim(),

    nome: String(
      respostasOrigem
        .cupom_retirada_marketing_nome ||
      rowOrigem[31] ||
      ""
    ).trim()
  };
}

/*
  Em envio com vários comprovantes principais,
  recupera a pasta de anexos registrada no
  primeiro envio do lote.
*/
if (
  !anexosRetirada.link &&
  controleLote.eh_lote === true &&
  Number(
    controleLote.sequencia_lote || 1
  ) > 1
) {
  anexosRetirada =
    smartSlipBuscarCupomRetiradaMarketingPorLote_(
      sh,
      controleLote.protocolo_lote
    );
}

const possuiNovosAnexosRetirada =
  (
    Array.isArray(
      form.anexos_retirada
    ) &&
    form.anexos_retirada.length > 0
  ) ||
  !!String(
    form.cupom_retirada_marketing_base64 ||
    ""
  ).trim();

/*
  Os anexos são aceitos para qualquer motivo
  de retirada.

  Eles são processados somente no primeiro
  comprovante principal do movimento.
*/
if (
  aplicarRetiradaNesteEnvio &&
  possuiNovosAnexosRetirada
) {
  anexosRetirada =
    smartSlipSalvarCupomRetiradaMarketing_(
      form,
      respostasUsuario,
      protocolo
    );
}

/*
  Somente Marketing exige anexos obrigatórios.
*/
if (
  smartSlipMotivoRetiradaEhMarketing_(
    motivoRetiradaValidacao
  ) &&
  aplicarRetiradaNesteEnvio &&
  !anexosRetirada.link
) {
  throw new Error(
    "Anexe ao menos uma evidência da retirada solicitada pelo Marketing."
  );
}

/*
  Em um lote com vários comprovantes principais,
  a retirada deve ser aplicada somente uma vez.
*/
respostasUsuario.houve_retirada =
  aplicarRetiradaNesteEnvio;

respostasUsuario.valor_retirada =
  aplicarRetiradaNesteEnvio
    ? valorRetiradaValidacao
    : 0;

respostasUsuario.motivo_retirada =
  aplicarRetiradaNesteEnvio
    ? motivoRetiradaValidacao
    : "Não houve retirada";

/*
  Apesar dos nomes internos antigos, estes campos
  agora armazenam a pasta única dos anexos.
*/
respostasUsuario.cupom_retirada_marketing_file_id =
  aplicarRetiradaNesteEnvio
    ? anexosRetirada.file_id
    : "";

respostasUsuario.cupom_retirada_marketing_link =
  aplicarRetiradaNesteEnvio
    ? anexosRetirada.link
    : "";

respostasUsuario.cupom_retirada_marketing_nome =
  aplicarRetiradaNesteEnvio
    ? anexosRetirada.nome
    : "";

const linhaFila = [
  new Date(),
  protocolo,
  emailUsuario,
  loja4,
  "",
  dataMovimentoTexto,
  respostasUsuario.houve_retirada ? "Sim" : "Não",
  respostasUsuario.valor_retirada,
  respostasUsuario.motivo_retirada,
  respostasUsuario.mais_comprovantes ? "Sim" : "Não",
  arquivo.file_id,
  arquivo.link_comprovante,
  arquivo.nome_arquivo,
  "RECEBIDO",
  ignorarTravasIaAdmin
    ? "Comprovante recebido em modo administrativo sem travas da IA."
    : contextoReenvio
      ? "Comprovante reenviado para nova leitura e aguardando processamento."
      : "Comprovante recebido e aguardando processamento.",
  JSON.stringify(respostasUsuario),
  "",
  "",

  controleLote.protocolo_lote,
  controleLote.protocolo_envio,
  controleLote.sequencia_lote,
  controleLote.status_lote,
  controleLote.ultimo_envio_lote ? "Sim" : "Não",
  controleLote.total_movimento_lote,

  "",
  "",
  "",
  "",
  "",

  respostasUsuario
    .cupom_retirada_marketing_file_id || "",

  respostasUsuario
    .cupom_retirada_marketing_link || "",

  respostasUsuario
    .cupom_retirada_marketing_nome || "",
  
  "",
  "",
  "",

  smartSlipNormalizarDispositivoEnvio_(
      form.dispositivo_envio
    )
  ];

if (contextoReenvio) {
  sh.getRange(contextoReenvio.row_index, 1, 1, linhaFila.length).setValues([linhaFila]);
} else {
  sh.appendRow(linhaFila);
}

    return {
      ok: true,
      protocolo: protocolo,
      protocolo_lote: controleLote.protocolo_lote,
      protocolo_envio: controleLote.protocolo_envio,
      sequencia_lote: controleLote.sequencia_lote,
      proxima_sequencia_lote: controleLote.proxima_sequencia_lote,
      continuar_lote: controleLote.ultimo_envio_lote !== true,
      status: "RECEBIDO",
      status_lote: controleLote.status_lote,
      mensagem: ignorarTravasIaAdmin
        ? "Comprovante recebido com sucesso em modo administrativo sem travas da IA."
        : "Comprovante recebido com sucesso.",
      cupom_retirada_marketing_file_id:
        respostasUsuario
          .cupom_retirada_marketing_file_id || "",

      cupom_retirada_marketing_link:
        respostasUsuario
          .cupom_retirada_marketing_link || "",

      cupom_retirada_marketing_nome:
        respostasUsuario
          .cupom_retirada_marketing_nome || "",  
    };

  } catch (err) {
    return {
      ok: false,
      erro: String(err && err.message ? err.message : err)
    };
  }
}

function smartSlipNormalizarPreValidacaoTotalIa_(valor, totalUsuario) {
  if (!valor) {
    return null;
  }

  if (typeof valor === "string") {
    try {
      valor = JSON.parse(valor || "{}");
    } catch (err) {
      return null;
    }
  }

  valor = valor || {};

  const totalIa = Number(valor.valor_total_ia || 0);
  const totalUser = Number(totalUsuario || valor.valor_total_usuario || 0);
  const diferenca = Math.abs(totalIa - totalUser);

  return {
    status_validacao: String(valor.status_validacao || ""),
  bloquear_envio:
    valor.bloquear_envio === true &&
    totalIa > 0 &&
    totalUser > 0 &&
    diferenca > SMARTSLIP_TOLERANCIA_TOTAL_IA,
    valor_total_usuario: totalUser,
    valor_total_ia: totalIa || null,
    diferenca: diferenca || null,
    confianca: Number(valor.confianca || 0),
    mensagem: String(valor.mensagem || "")
  };
}

function smartSlipAplicarBloqueioMultiploConfiavelBackend_(preValidacao, form) {
  if (!preValidacao) {
    return preValidacao;
  }

  form = form || {};

  const status = String(preValidacao.status_validacao || "").trim().toUpperCase();
  const mensagem = String(preValidacao.mensagem || "").trim().toLowerCase();

  const confianca = Number(preValidacao.confianca || 0);
  const diferenca = Math.abs(Number(preValidacao.diferenca || 0));

  const totalAnexosLote = Number(form.total_anexos_lote || 1);

  const ehFluxoComVariosAnexos =
    String(form.envio_lote || "") === "true" &&
    totalAnexosLote > 1;

  const pareceMultiplo =
    status.indexOf("MULTIPLO") >= 0 ||
    status.indexOf("MÚLTIPLO") >= 0 ||
    mensagem.indexOf("múltiplos comprovantes") >= 0 ||
    mensagem.indexOf("multiplos comprovantes") >= 0 ||
    mensagem.indexOf("múltiplos") >= 0 ||
    mensagem.indexOf("multiplos") >= 0;

  if (ehFluxoComVariosAnexos) {
    return preValidacao;
  }

  if (
    pareceMultiplo &&
    confianca >= 0.98 &&
    diferenca > 0.01
  ) {
    preValidacao.status_validacao = "DIVERGENTE_MULTIPLO_BLOQUEANTE";
    preValidacao.bloquear_envio = true;
    preValidacao.mensagem =
      "A IA identificou múltiplos comprovantes no arquivo e leu os valores com alta confiança, " +
      "mas a soma informada está diferente do total lido.";
  }

  return preValidacao;
}

function smartSlipGerarProtocolo() {
  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  const agora = new Date();
  const data = Utilities.formatDate(agora, tz, "yyyyMMdd-HHmmss");
  const rand = Math.floor(Math.random() * 9000) + 1000;

  return "SS-" + data + "-" + rand;
}

function smartSlipMontarControleLoteEnvio_(form, valoresDiariosMovimento) {
  form = form || {};
  valoresDiariosMovimento = valoresDiariosMovimento || {};

  const protocoloLoteInformado = String(form.protocolo_lote || "").trim();
  const temMaisComprovantes = String(form.mais_comprovantes) === "true";

  /*
    Envio em lote:
    - começa quando o usuário marca "Sim, vou enviar mais arquivos"
    - continua quando o front envia protocolo_lote já existente
  */
  const ehContinuacaoLote = !!protocoloLoteInformado;
  const ehLote = temMaisComprovantes || ehContinuacaoLote;

  const protocoloLote = protocoloLoteInformado || smartSlipGerarProtocolo();

  const sequenciaLote = ehLote
    ? Math.max(1, Number(form.sequencia_lote || 1))
    : 1;

  const protocoloEnvio = ehLote
    ? protocoloLote + "-P" + String(sequenciaLote).padStart(2, "0")
    : protocoloLote;

  const ultimoEnvioLote = !temMaisComprovantes;

  return {
    eh_lote: ehLote,
    eh_continuacao_lote: ehContinuacaoLote,
    protocolo_lote: protocoloLote,
    protocolo_envio: protocoloEnvio,
    sequencia_lote: sequenciaLote,
    proxima_sequencia_lote: sequenciaLote + 1,
    status_lote: ultimoEnvioLote ? "FECHADO" : "ABERTO",
    ultimo_envio_lote: ultimoEnvioLote,
    total_movimento_lote: Number(valoresDiariosMovimento.total || 0)
  };
}

function smartSlipValidarContinuidadeLote_(sh, controleLote, emailUsuario, loja4, dataMovimentoTexto) {
  controleLote = controleLote || {};

  const protocoloLote = String(controleLote.protocolo_lote || "").trim();

  if (!protocoloLote || !controleLote.eh_continuacao_lote) {
    return;
  }

  if (!sh || sh.getLastRow() < 2) {
    throw new Error("Não foi possível continuar o lote. Nenhum envio anterior foi encontrado.");
  }

  const values = sh.getDataRange().getValues();
  const headers = values[0].map(function(h) {
    return String(h || "").trim();
  });

  const idxProtocoloLote = smartSlipEncontrarIndiceHeader_(headers, ["Protocolo Lote"]);
  const idxEmail = smartSlipEncontrarIndiceHeader_(headers, ["Email Usuário"]);
  const idxLoja = smartSlipEncontrarIndiceHeader_(headers, ["Loja Informada"]);
  const idxDataMovimento = smartSlipEncontrarIndiceHeader_(headers, ["Data Movimento"]);
  const idxStatusLote = smartSlipEncontrarIndiceHeader_(headers, ["Status Lote"]);
  const idxTotalLote = smartSlipEncontrarIndiceHeader_(headers, ["Total Movimento Lote"]);

  if (
    idxProtocoloLote < 0 ||
    idxEmail < 0 ||
    idxLoja < 0 ||
    idxDataMovimento < 0 ||
    idxStatusLote < 0 ||
    idxTotalLote < 0
  ) {
    throw new Error("Cabeçalhos de controle de lote não encontrados na SMARTSLIP_FILA.");
  }

  let linhaEncontrada = null;

  for (let i = values.length - 1; i >= 1; i--) {
    const row = values[i];

    if (String(row[idxProtocoloLote] || "").trim() === protocoloLote) {
      linhaEncontrada = row;
      break;
    }
  }

  if (!linhaEncontrada) {
    throw new Error("Não foi possível continuar o lote. Protocolo Lote não encontrado na SMARTSLIP_FILA.");
  }

  const emailBase = String(linhaEncontrada[idxEmail] || "").trim().toLowerCase();
  const lojaBase = smartSlipNormalizarLoja4(linhaEncontrada[idxLoja] || "");
  const dataMovimentoBase = String(linhaEncontrada[idxDataMovimento] || "").trim();
  const statusLoteBase = String(linhaEncontrada[idxStatusLote] || "").trim().toUpperCase();
  const totalBase = Number(linhaEncontrada[idxTotalLote] || 0);
  const totalAtual = Number(controleLote.total_movimento_lote || 0);

  if (statusLoteBase === "FECHADO") {
    throw new Error("Este lote já está fechado. Para enviar outro comprovante, inicie um novo envio.");
  }

  if (emailBase !== String(emailUsuario || "").trim().toLowerCase()) {
    throw new Error("Este lote pertence a outro usuário. Não é possível continuar o envio.");
  }

  if (lojaBase !== smartSlipNormalizarLoja4(loja4 || "")) {
    throw new Error("A loja informada não corresponde à loja do lote iniciado.");
  }

  if (dataMovimentoBase !== String(dataMovimentoTexto || "").trim()) {
    throw new Error("O período de movimento não corresponde ao lote iniciado.");
  }

  if (Math.abs(totalBase - totalAtual) > 0.009) {
    throw new Error("O total dos valores diários não corresponde ao lote iniciado.");
  }
}

function smartSlipDiffSegundos_(inicio, fim) {
  if (!(inicio instanceof Date) || !(fim instanceof Date)) {
    return null;
  }

  const diff = Math.round((fim.getTime() - inicio.getTime()) / 1000);

  return diff >= 0 ? diff : null;
}

function smartSlipClassificarPerformance_(filaSeg, leituraSeg, totalSeg) {
  filaSeg = Number(filaSeg || 0);
  leituraSeg = Number(leituraSeg || 0);
  totalSeg = Number(totalSeg || 0);

  if (filaSeg >= 300 || leituraSeg >= 180 || totalSeg >= 420) {
    return "CRITICO";
  }

  if (filaSeg >= 120 || leituraSeg >= 90 || totalSeg >= 240) {
    return "LENTO";
  }

  if (filaSeg >= 60 || leituraSeg >= 45 || totalSeg >= 120) {
    return "ATENCAO";
  }

  return "NORMAL";
}

function smartSlipProtocoloJaSalvoNaBase_(
  protocolo
) {

  protocolo =
    String(
      protocolo || ""
    ).trim();

  if (!protocolo) {
    return false;
  }


  const ss =
    SpreadsheetApp.openById(
      SMARTSLIP_DB_SPREADSHEET_ID
    );


  const sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_DESTINO
    );


  if (
    !sh ||
    sh.getLastRow() < 2
  ) {
    return false;
  }


  /*
   * Coluna D da BASE_SMARTSLIP:
   * Protocolo
   */
  const encontrado =
    sh
      .getRange(
        2,
        4,
        sh.getLastRow() - 1,
        1
      )
      .createTextFinder(
        protocolo
      )
      .matchEntireCell(true)
      .findNext();


  return !!encontrado;
}

function smartSlipProcessarFila() {
  let itemProcessar = null;

  /*
    Lock curto somente para reservar 1 linha RECEBIDO.
    Não chama Gemini, Drive ou salvamento dentro do lock.
  */
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(1000)) {
    return;
  }

  try {
    const sh = smartSlipGarantirCabecalhoFila();
    const lastRow = sh.getLastRow();

    if (lastRow < 2) {
      return;
    }

    const lastCol = Math.max(29, sh.getLastColumn());
    const values = sh.getRange(2, 1, lastRow - 1, lastCol).getValues();

    for (let i = 0; i < values.length; i++) {
      const rowIndex = i + 2;
      const row = values[i];

      const dataRegistro = row[0];
      const protocolo = row[1];
      const emailUsuario = row[2];
      const lojaInformada = row[3];
      const fileId = row[10];
      const linkComprovante = row[11];
      const nomeArquivo = row[12];
      const statusFila =
        String(
          row[13] || ""
        )
          .trim()
          .toUpperCase();

    const jsonRespostas =
      row[15];


/*
 * ==================================================
 * RECUPERA PROCESSAMENTO ABANDONADO
 * ==================================================
 *
 * Se uma execução morrer depois de marcar
 * PROCESSANDO, o item não pode ficar preso
 * para sempre.
 *
 * Após 15 minutos:
 *
 * 1. se já existe na BASE_SMARTSLIP:
 *    considera concluído;
 *
 * 2. se não existe:
 *    volta para RECEBIDO e será processado
 *    novamente no próximo ciclo.
 */
if (
  statusFila ===
  "PROCESSANDO"
) {

  const inicioAnterior =
    row[24]; // coluna Y


  const referenciaTempo =
    inicioAnterior instanceof Date
      ? inicioAnterior
      : (
          dataRegistro instanceof Date
            ? dataRegistro
            : null
        );


  const minutosProcessando =
    referenciaTempo
      ? (
          (
            new Date().getTime() -
            referenciaTempo.getTime()
          ) /
          60000
        )
      : 0;


  if (
    minutosProcessando >= 15
  ) {

    const jaFoiSalvo =
      smartSlipProtocoloJaSalvoNaBase_(
        protocolo
      );


    /*
     * Evita duplicidade:
     * se a execução salvou na BASE mas morreu
     * antes de atualizar a fila.
     */
    if (jaFoiSalvo) {

      sh
        .getRange(
          rowIndex,
          14
        )
        .setValue(
          "SALVO"
        );

      sh
        .getRange(
          rowIndex,
          15
        )
        .setValue(
          "Processamento recuperado automaticamente. " +
          "Protocolo já encontrado na BASE_SMARTSLIP."
        );

      sh
        .getRange(
          rowIndex,
          18
        )
        .setValue(
          new Date()
        );

    } else {

      sh
        .getRange(
          rowIndex,
          14
        )
        .setValue(
          "RECEBIDO"
        );

      sh
        .getRange(
          rowIndex,
          15
        )
        .setValue(
          "Reenfileirado automaticamente após " +
          "processamento interrompido."
        );


      /*
       * Limpa resultado e métricas antigos
       * para o novo processamento.
       */
      sh
        .getRange(
          rowIndex,
          17,
          1,
          2
        )
        .clearContent();


      sh
        .getRange(
          rowIndex,
          25,
          1,
          5
        )
        .clearContent();

    }


    SpreadsheetApp.flush();

  }


  /*
   * Não processa nessa mesma execução.
   * No próximo trigger, a linha que voltou
   * para RECEBIDO será reservada normalmente.
   */
  continue;
}


if (
  statusFila !==
  "RECEBIDO"
) {
  continue;
}

      const inicioProcessamento = new Date();

      sh.getRange(rowIndex, 14).setValue("PROCESSANDO");
      sh.getRange(rowIndex, 15).setValue("Processando comprovante via Gemini.");
      sh.getRange(rowIndex, 25).setValue(inicioProcessamento); // Y
      SpreadsheetApp.flush();

    itemProcessar = {
      rowIndex: rowIndex,
      protocolo: protocolo,
      emailUsuario: String(emailUsuario || "").trim(),
      lojaInformada: lojaInformada,
      fileId: fileId,
      linkComprovante: String(linkComprovante || "").trim(),
      nomeArquivo: String(nomeArquivo || "").trim(),
      jsonRespostas: jsonRespostas,
      dataRegistro:
        dataRegistro instanceof Date
          ? dataRegistro
          : null,
      inicioProcessamento: inicioProcessamento
    };

      break;
    }

  } finally {
    try {
      lock.releaseLock();
    } catch (e) {}
  }

  if (!itemProcessar) {
    return;
  }

  try {
    const respostasUsuario = JSON.parse(itemProcessar.jsonRespostas || "{}");

    const resultado = smartSlipProcessarComprovanteFila(
      itemProcessar.fileId,
      respostasUsuario,
      itemProcessar.protocolo
    );

    const fimProcessamento = new Date();

    const filaSeg = smartSlipDiffSegundos_(
      itemProcessar.dataRegistro,
      itemProcessar.inicioProcessamento
    );

    const leituraSeg = smartSlipDiffSegundos_(
      itemProcessar.inicioProcessamento,
      fimProcessamento
    );

    const totalSeg = smartSlipDiffSegundos_(
      itemProcessar.dataRegistro,
      fimProcessamento
    );

    const sinalPerformance = smartSlipClassificarPerformance_(
      filaSeg,
      leituraSeg,
      totalSeg
    );

    const sh = smartSlipGarantirCabecalhoFila();

    sh.getRange(itemProcessar.rowIndex, 14).setValue(resultado.status_fila);
    sh.getRange(itemProcessar.rowIndex, 15).setValue(resultado.mensagem || "");
    sh.getRange(itemProcessar.rowIndex, 17).setValue(JSON.stringify(resultado));
    sh.getRange(itemProcessar.rowIndex, 18).setValue(fimProcessamento);

    sh.getRange(itemProcessar.rowIndex, 25, 1, 5).setValues([[
      itemProcessar.inicioProcessamento,
      filaSeg,
      leituraSeg,
      totalSeg,
      sinalPerformance
    ]]);

    SpreadsheetApp.flush();

    /*
  Se o processamento terminou com qualquer
  status diferente de SALVO, avisa o autor.
*/
if (
  String(
    resultado.status_fila || ""
  )
    .trim()
    .toUpperCase() !== "SALVO"
) {
  smartSlipTentarEnviarAvisoFalhaProcessamento_({
    row_index:
      itemProcessar.rowIndex,

    protocolo:
      itemProcessar.protocolo,

    email_usuario:
      itemProcessar.emailUsuario,

    loja:
      itemProcessar.lojaInformada,

    data_registro:
      itemProcessar.dataRegistro,

    nome_arquivo:
      itemProcessar.nomeArquivo,

    link_comprovante:
      itemProcessar.linkComprovante,

    status_fila:
      resultado.status_fila,

    mensagem:
      resultado.mensagem || "",

    resultado:
      resultado
  });
}

  } catch (err) {
    const fimErro = new Date();

    const filaSeg = smartSlipDiffSegundos_(
      itemProcessar.dataRegistro,
      itemProcessar.inicioProcessamento
    );

    const leituraSeg = smartSlipDiffSegundos_(
      itemProcessar.inicioProcessamento,
      fimErro
    );

    const totalSeg = smartSlipDiffSegundos_(
      itemProcessar.dataRegistro,
      fimErro
    );

    const sinalPerformance = smartSlipClassificarPerformance_(
      filaSeg,
      leituraSeg,
      totalSeg
    );

    const sh = smartSlipGarantirCabecalhoFila();

    const erroTexto =
      String(
        err && err.message
          ? err.message
          : err
      );

    sh
      .getRange(
        itemProcessar.rowIndex,
        14
      )
      .setValue(
        "ERRO_PROCESSAMENTO"
      );

    sh
      .getRange(
        itemProcessar.rowIndex,
        15
      )
      .setValue(
        erroTexto
      );
    sh.getRange(itemProcessar.rowIndex, 18).setValue(fimErro);

    sh.getRange(itemProcessar.rowIndex, 25, 1, 5).setValues([[
      itemProcessar.inicioProcessamento,
      filaSeg,
      leituraSeg,
      totalSeg,
      sinalPerformance
    ]]);

    SpreadsheetApp.flush();

    smartSlipTentarEnviarAvisoFalhaProcessamento_({
        row_index:
          itemProcessar.rowIndex,

        protocolo:
          itemProcessar.protocolo,

        email_usuario:
          itemProcessar.emailUsuario,

        loja:
          itemProcessar.lojaInformada,

        data_registro:
          itemProcessar.dataRegistro,

        nome_arquivo:
          itemProcessar.nomeArquivo,

        link_comprovante:
          itemProcessar.linkComprovante,

        status_fila:
          "ERRO_PROCESSAMENTO",

        mensagem:
          erroTexto,

        resultado:
          null
      });
  }
}

function smartSlipProcessarComprovanteFila(fileId, respostasUsuario, protocolo) {
  respostasUsuario = respostasUsuario || {};

  const file = DriveApp.getFileById(fileId);
  const linkComprovante = file.getUrl();
  const blob = file.getBlob();

  const base64 = Utilities.base64Encode(blob.getBytes());
  const mimeType = blob.getContentType();

  const loja4 = smartSlipNormalizarLoja4(respostasUsuario.loja);
  const dataMovimentoTexto = smartSlipMontarDataMovimentoTexto(respostasUsuario);
  const valoresDiariosMovimento = respostasUsuario.valores_diarios_movimento || null;

  const ignorarTravasIaAdmin = respostasUsuario.ignorar_travas_ia_admin === true;

    /*Cria uma cópia específica para a IA. Os metadados do cupom de retirada não são enviados ao Gemini, e o arquivo do cupom nunca é carregado aqui.*/

  const respostasUsuarioIa =
    Object.assign({}, respostasUsuario);

  delete respostasUsuarioIa
    .cupom_retirada_marketing_file_id;

  delete respostasUsuarioIa
    .cupom_retirada_marketing_link;

  delete respostasUsuarioIa
    .cupom_retirada_marketing_nome;

  let resultado = null;

  try {
    resultado = smartSlipChamarGemini(base64, mimeType, respostasUsuarioIa);
  } catch (errGemini) {
    if (!ignorarTravasIaAdmin) {
      throw errGemini;
    }

    resultado = {
      status: "PRONTO_PARA_SALVAR",
      qtd_comprovantes_detectados: 1,
      alerta_qualidade_imagem: "IA falhou, mas o modo administrativo sem travas permitiu fallback manual.",
      criterio_contagem: "Fallback administrativo",
      dados_arquivo: {
        loja: loja4,
        empresa: "Nao identificado",
        data_movimento: dataMovimentoTexto,
        data_movimento_inicio: respostasUsuario.data_movimento_inicio || "",
        data_movimento_fim: respostasUsuario.data_movimento_fim || "",
        houve_retirada: respostasUsuario.houve_retirada === true,
        valor_retirada: Number(respostasUsuario.valor_retirada || 0),
        motivo_retirada: respostasUsuario.motivo_retirada || "Não houve retirada",
        link_comprovante: linkComprovante
      },
      comprovantes: [
        smartSlipMontarComprovanteAdminFallback_(
          respostasUsuario,
          dataMovimentoTexto
        )
      ],
      pendencias: [],
      divergencias: [],
      perguntas_complementares: [],
      confianca_geral: 0,
      erro_ia_original: String(errGemini && errGemini.message ? errGemini.message : errGemini)
    };
  }

  const protocoloLote = String(respostasUsuario.protocolo_lote || protocolo || "").trim();
  const protocoloEnvio = String(respostasUsuario.protocolo_envio || protocolo || "").trim();
  const sequenciaLote = Number(respostasUsuario.sequencia_lote || 1);
  const statusLote = String(respostasUsuario.status_lote || "").trim();
  const ultimoEnvioLote = respostasUsuario.ultimo_envio_lote === true;
  const totalMovimentoLote = Number(respostasUsuario.total_movimento_lote || 0);

  const infoLoja = smartSlipConsultarInfoLoja_(loja4);

  if (!infoLoja.ok) {
    return {
      ok: false,
      status_fila: "PENDENTE_INTERNO",
      mensagem: "Loja não encontrada na Info_limites.",
      resultado: resultado
    };
  }

  const empresa = infoLoja.empresa;

  const houveRetirada = respostasUsuario.houve_retirada === true;
  const valorRetirada = Number(respostasUsuario.valor_retirada || 0);
  const motivoRetirada = houveRetirada
    ? respostasUsuario.motivo_retirada || ""
    : "Não houve retirada";

  let comprovantes = smartSlipExtrairComprovantesDoResultado(resultado);

  if (ignorarTravasIaAdmin && (!comprovantes || comprovantes.length === 0)) {
    comprovantes = [
      smartSlipMontarComprovanteAdminFallback_(
        respostasUsuario,
        dataMovimentoTexto
      )
    ];
  }

  if (!ignorarTravasIaAdmin && !comprovantes.length) {
    return {
      ok: false,
      status_fila: "PENDENTE_INTERNO",
      mensagem: "Nenhum comprovante legível foi identificado no arquivo.",
      resultado: resultado
    };
  }

  if (!ignorarTravasIaAdmin && comprovantes.length > 10) {
    return {
      ok: false,
      status_fila: "PENDENTE_INTERNO",
      mensagem:
        "Validação anti-alucinação bloqueou o lote. A IA retornou " +
        comprovantes.length +
        " comprovantes, acima do limite operacional de 10 por arquivo. Nenhum item foi salvo na BASE_SMARTSLIP.",
      resultado: resultado
    };
  }

  if (ignorarTravasIaAdmin && comprovantes.length > 10) {
    comprovantes = [
      smartSlipMontarComprovanteAdminFallback_(
        respostasUsuario,
        dataMovimentoTexto
      )
    ];

    if (!Array.isArray(resultado.observacoes)) {
      resultado.observacoes = [];
    }

    resultado.observacoes.push(
      "IA retornou mais de 10 itens. Modo administrativo usou fallback manual para evitar salvamento massivo por possível alucinação."
    );
  }

  if (!ignorarTravasIaAdmin) {
    const validacaoDuplicidadeEvidencia =
      smartSlipValidarDuplicidadeEvidenciaLote_(comprovantes);

    if (!validacaoDuplicidadeEvidencia.ok) {
      return {
        ok: false,
        status_fila: "PENDENTE_INTERNO",
        mensagem: validacaoDuplicidadeEvidencia.mensagem + " Nenhum item foi salvo na BASE_SMARTSLIP.",
        validacao_duplicidade_evidencia: validacaoDuplicidadeEvidencia,
        resultado: resultado
      };
    }
  }

  let salvos = 0;
  let pendentes = 0;
  const mensagens = [];

  let retiradaJaAplicada = false;

  comprovantes.forEach(function(item) {
    item = item || {};

    if (ignorarTravasIaAdmin) {
      item = smartSlipCompletarItemAdminSemTravas_(
        item,
        respostasUsuario,
        dataMovimentoTexto
      );
    }

    /*
 * NORMALIZAÇÃO DA DATA DE GERAÇÃO
 *
 * Alguns comprovantes, principalmente
 * Lotéricas CAIXA / boleto, apresentam
 * uma única data operacional:
 * DATA DE PAGAMENTO.
 *
 * Quando a IA identifica claramente essa
 * data como data_deposito, mas não encontra
 * uma data de geração/emissão separada,
 * utilizamos a própria data do pagamento.
 *
 * Só fazemos o fallback quando existe
 * evidência textual da data.
 */
if (
  !item.data_geracao_documento &&
  item.data_deposito &&
  item.evidencias &&
  String(
    item.evidencias.data_deposito_texto || ""
  ).trim()
) {

  item.data_geracao_documento =
    item.data_deposito;

  if (!Array.isArray(item.observacoes)) {
    item.observacoes = [];
  }

  item.observacoes.push(
    "Data de geração do documento preenchida automaticamente " +
    "com a data de depósito/pagamento identificada no comprovante."
  );
}

    const pendenciasItem = [];

    if (!item.tipo_documento || item.tipo_documento === "nao_identificado") {
      pendenciasItem.push("Tipo de documento não identificado.");
    }

    if (!item.data_deposito) {
      pendenciasItem.push("Data do depósito não identificada.");
    }

    if (item.valor_deposito === null || item.valor_deposito === undefined || item.valor_deposito === "") {
      pendenciasItem.push("Valor do depósito não identificado.");
    }

    if (!item.data_geracao_documento) {
      pendenciasItem.push("Data de geração do documento não identificada.");
    }

    const movInicioGuardrail =
      respostasUsuario.data_movimento_inicio ||
      respostasUsuario.data_movimento ||
      "";

    const movFimGuardrail =
      respostasUsuario.data_movimento_fim ||
      respostasUsuario.data_movimento_inicio ||
      respostasUsuario.data_movimento ||
      "";

    const correcaoDataDeposito = smartSlipCorrigirAnoDataDocumentoPeloMovimento_(
      item.data_deposito,
      movInicioGuardrail,
      movFimGuardrail
    );

    if (correcaoDataDeposito.corrigida) {
      item.data_deposito = correcaoDataDeposito.data;

      if (!Array.isArray(item.observacoes)) {
        item.observacoes = [];
      }

      item.observacoes.push(correcaoDataDeposito.motivo);
    }

    const correcaoDataGeracao = smartSlipCorrigirAnoDataDocumentoPeloMovimento_(
      item.data_geracao_documento,
      movInicioGuardrail,
      movFimGuardrail
    );

    if (correcaoDataGeracao.corrigida) {
      item.data_geracao_documento = correcaoDataGeracao.data;

      if (!Array.isArray(item.observacoes)) {
        item.observacoes = [];
      }

      item.observacoes.push(correcaoDataGeracao.motivo);
    }

    const dadosGuardrail = {
      data_deposito: item.data_deposito,
      data_movimento: dataMovimentoTexto,
      data_movimento_inicio: movInicioGuardrail,
      data_movimento_fim: movFimGuardrail
    };

    const resultadoGuardrail = {
      status: "PRONTO_PARA_SALVAR",
      divergencias: []
    };

    smartSlipValidarGuardrailMovimento(resultadoGuardrail, dadosGuardrail);

    if (resultadoGuardrail.divergencias.length > 0) {
      if (ignorarTravasIaAdmin) {
        if (!Array.isArray(item.observacoes)) {
          item.observacoes = [];
        }

        item.observacoes.push(
          "Guardrail de data ignorado por override administrativo: " +
          resultadoGuardrail.divergencias.join(" | ")
        );
      } else {
        pendenciasItem.push(resultadoGuardrail.divergencias.join(" | "));
      }
    }

    if (!ignorarTravasIaAdmin && (pendenciasItem.length > 0 || item.status === "INELEGIVEL")) {
      pendentes++;

      mensagens.push(
        "Comprovante " +
        (item.indice_comprovante || "?") +
        ": " +
        pendenciasItem.join(" | ")
      );

      return;
    }

    if (!ignorarTravasIaAdmin) {
      const validacaoEvidencia = smartSlipItemTemInferenciaOuBaixaEvidencia_(item);

      if (validacaoEvidencia.bloquear) {
        pendentes++;

        mensagens.push(
          "Comprovante " +
          (item.indice_comprovante || "?") +
          ": bloqueado por validação anti-alucinação. " +
          validacaoEvidencia.motivo
        );

        return;
      }
    }

    const aplicarRetiradaNestaLinha = houveRetirada && !retiradaJaAplicada;
    const indiceComprovante = item.indice_comprovante || (salvos + pendentes + 1);

    const idComprovante = smartSlipGerarIdComprovante(
      protocolo,
      indiceComprovante
    );

    const pendenciasSalvar = Array.isArray(item.observacoes)
      ? item.observacoes.slice()
      : [];

    if (ignorarTravasIaAdmin) {
      pendenciasSalvar.push(
        "Override administrativo: validações bloqueantes da IA foram ignoradas."
      );
      pendenciasSalvar.push(
        "Dados críticos podem ter sido preenchidos com informações digitadas manualmente na tela de envio."
      );
    }

    const payloadSalvar = {
      id_comprovante: idComprovante,
      hash_comprovante: "",
      protocolo: protocolo,
      protocolo_lote: protocoloLote,
      protocolo_envio: protocoloEnvio,
      sequencia_lote: sequenciaLote,
      status_lote: statusLote,
      ultimo_envio_lote: ultimoEnvioLote,
      total_movimento_lote: totalMovimentoLote,
      indice_comprovante: indiceComprovante,
      loja: loja4,
      empresa: empresa,
      tipo_documento: item.tipo_documento || "nao_identificado",
      data_deposito: item.data_deposito || "",
      valor_deposito: Number(item.valor_deposito || 0),
      banco: item.banco || "Nao identificado",
      data_movimento: dataMovimentoTexto,
      valores_diarios_movimento: valoresDiariosMovimento,
      houve_retirada: aplicarRetiradaNestaLinha,
      valor_retirada: aplicarRetiradaNestaLinha ? valorRetirada : 0,
      motivo_retirada: aplicarRetiradaNestaLinha ? motivoRetirada : "Não houve retirada",
      data_geracao_documento: item.data_geracao_documento || "",
      codigo_autenticacao: item.codigo_autenticacao || "",
      link_comprovante: linkComprovante,
      cupom_retirada_marketing_file_id:
        aplicarRetiradaNestaLinha
          ? (
              respostasUsuario
                .cupom_retirada_marketing_file_id || ""
            )
          : "",

      cupom_retirada_marketing_link:
        aplicarRetiradaNestaLinha
          ? (
              respostasUsuario
                .cupom_retirada_marketing_link || ""
            )
          : "",

      cupom_retirada_marketing_nome:
        aplicarRetiradaNestaLinha
          ? (
              respostasUsuario
                .cupom_retirada_marketing_nome || ""
            )
          : "",
      status_processamento: ignorarTravasIaAdmin
        ? "SALVO_ADMIN_SEM_TRAVAS_IA"
        : "PRONTO_PARA_SALVAR",
      pendencias: pendenciasSalvar,
      divergencias: [],
      confianca_geral: ignorarTravasIaAdmin
        ? Number(resultado.confianca_geral || item.confianca_item || 0)
        : Number(resultado.confianca_geral || 0)
    };

    payloadSalvar.hash_comprovante = smartSlipGerarHashComprovante(payloadSalvar);

    smartSlipSalvarDadosComprovantePlanilha_(payloadSalvar);

    if (aplicarRetiradaNestaLinha) {
      retiradaJaAplicada = true;
    }

    salvos++;
  });

  if (salvos > 0 && pendentes === 0) {
    return {
      ok: true,
      status_fila: "SALVO",
      mensagem: ignorarTravasIaAdmin
        ? salvos + " comprovante(s) salvo(s) em modo administrativo sem travas da IA."
        : salvos + " comprovante(s) processado(s) e salvo(s) na BASE_SMARTSLIP.",
      qtd_salvos: salvos,
      qtd_pendentes: pendentes,
      resultado: resultado
    };
  }

  if (salvos > 0 && pendentes > 0) {
    return {
      ok: true,
      status_fila: "SALVO_PARCIAL",
      mensagem: salvos + " comprovante(s) salvo(s). " + pendentes + " comprovante(s) com pendência.",
      qtd_salvos: salvos,
      qtd_pendentes: pendentes,
      pendencias: mensagens,
      resultado: resultado
    };
  }

  return {
    ok: false,
    status_fila: "PENDENTE_INTERNO",
    mensagem: "Nenhum comprovante foi salvo. " + mensagens.join(" | "),
    qtd_salvos: salvos,
    qtd_pendentes: pendentes,
    pendencias: mensagens,
    resultado: resultado
  };
}

function smartSlipTipoDocumentoFallbackAdmin_(tipoDeposito) {
  const tipo = smartSlipNormalizarTipoDeposito_(tipoDeposito || "");

  if (tipo === "Boleto") {
    return "boleto_bancario";
  }

  if (tipo === "Carro Forte") {
    return "comprovante_carro_forte";
  }

  if (tipo === "Dep. Bancário") {
    return "deposito_caixa_eletronico";
  }

  return "nao_identificado";
}

function smartSlipTotalMovimentoRespostas_(respostasUsuario) {
  respostasUsuario = respostasUsuario || {};

  const valores = respostasUsuario.valores_diarios_movimento || {};

  const total = Number(valores.total || 0);

  return isNaN(total) ? 0 : total;
}

function smartSlipDataFallbackAdmin_(respostasUsuario, dataMovimentoTexto) {
  respostasUsuario = respostasUsuario || {};

  return String(
    respostasUsuario.data_movimento_fim ||
    respostasUsuario.data_movimento_inicio ||
    respostasUsuario.data_movimento ||
    dataMovimentoTexto ||
    ""
  ).trim();
}

function smartSlipMontarComprovanteAdminFallback_(respostasUsuario, dataMovimentoTexto) {
  respostasUsuario = respostasUsuario || {};

  const dataFallback = smartSlipDataFallbackAdmin_(respostasUsuario, dataMovimentoTexto);
  const valorFallback = smartSlipTotalMovimentoRespostas_(respostasUsuario);

  return {
    status: "PRONTO_PARA_SALVAR",
    indice_comprovante: 1,
    tipo_documento: smartSlipTipoDocumentoFallbackAdmin_(respostasUsuario.tipo_deposito),
    data_deposito: dataFallback,
    valor_deposito: valorFallback,
    banco: "Nao identificado",
    data_geracao_documento: dataFallback,
    codigo_autenticacao: "",
    confianca_item: 0,
    posicao_visual_aproximada: "Fallback administrativo",
    evidencias: {
      valor_deposito_texto: "Valor usado da soma dos valores diários informados na tela.",
      data_deposito_texto: "Data usada do período de movimento informado na tela.",
      codigo_autenticacao_texto: "",
      controle_texto: "",
      bloco_textual_comprovante: "Modo administrativo sem travas de IA."
    },
    observacoes: [
      "Modo administrativo sem travas de IA: campos críticos ausentes foram preenchidos com dados informados manualmente na tela."
    ]
  };
}

function smartSlipCompletarItemAdminSemTravas_(item, respostasUsuario, dataMovimentoTexto) {
  item = item || {};

  const fallback = smartSlipMontarComprovanteAdminFallback_(
    respostasUsuario,
    dataMovimentoTexto
  );

  if (!item.tipo_documento || item.tipo_documento === "nao_identificado") {
    item.tipo_documento = fallback.tipo_documento;
  }

  if (!item.data_deposito) {
    item.data_deposito = fallback.data_deposito;
  }

  if (
    item.valor_deposito === null ||
    item.valor_deposito === undefined ||
    item.valor_deposito === ""
  ) {
    item.valor_deposito = fallback.valor_deposito;
  }

  if (!item.data_geracao_documento) {
    item.data_geracao_documento = item.data_deposito || fallback.data_geracao_documento;
  }

  if (!item.banco) {
    item.banco = "Nao identificado";
  }

  if (!item.codigo_autenticacao) {
    item.codigo_autenticacao = "";
  }

  if (!Array.isArray(item.observacoes)) {
    item.observacoes = [];
  }

  item.observacoes.push("Modo administrativo sem travas de IA aplicado.");
  item.status = "PRONTO_PARA_SALVAR";

  return item;
}

function smartSlipValidarBloqueiosFila(resultado, dados) {
  const pendencias = [];

  if (!dados.loja) pendencias.push("Loja não informada.");
  if (!dados.empresa || dados.empresa === "Nao identificado") pendencias.push("Empresa não identificada pela Info_limites.");
  if (!resultado.tipo_documento || resultado.tipo_documento === "nao_identificado") pendencias.push("Tipo de documento não identificado.");
  if (!dados.data_deposito) pendencias.push("Data do depósito não identificada.");
  if (dados.valor_deposito === null || dados.valor_deposito === undefined || dados.valor_deposito === "") pendencias.push("Valor do depósito não identificado.");
  if (!dados.data_movimento) pendencias.push("Data de movimento não informada.");
  if (dados.houve_retirada === null || dados.houve_retirada === undefined) pendencias.push("Informação sobre retirada não informada.");
  if (!dados.data_geracao_documento) pendencias.push("Data de geração do documento não identificada.");

  if (dados.houve_retirada === true) {
    if (!dados.valor_retirada) pendencias.push("Valor da retirada não informado.");
    if (!dados.motivo_retirada) pendencias.push("Motivo da retirada não informado.");
  }

  return pendencias;
}

function smartSlipInstalarTriggerFila() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === "smartSlipProcessarFila") {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger("smartSlipProcessarFila")
    .timeBased()
    .everyMinutes(1)
    .create();

  Logger.log("Trigger smartSlipProcessarFila instalado para rodar a cada minuto.");
}

function smartSlipExtrairListaComprovantes(resultado) {
  resultado = resultado || {};

  if (Array.isArray(resultado.comprovantes) && resultado.comprovantes.length > 0) {
    return resultado.comprovantes;
  }

  // Compatibilidade com o formato antigo, de 1 comprovante só.
  if (resultado.dados_comprovante) {
    return [{
      status: resultado.status || "PRONTO_PARA_SALVAR",
      indice_comprovante: 1,
      tipo_documento: resultado.tipo_documento || "nao_identificado",
      data_deposito: resultado.dados_comprovante.data_deposito || null,
      valor_deposito: resultado.dados_comprovante.valor_deposito || null,
      banco: resultado.dados_comprovante.banco || "Nao identificado",
      data_geracao_documento: resultado.dados_comprovante.data_geracao_documento || null,
      codigo_autenticacao: resultado.dados_comprovante.codigo_autenticacao || "",
      observacoes: resultado.pendencias || []
    }];
  }

  return [];
}

function smartSlipExtrairComprovantesDoResultado(resultado) {
  resultado = resultado || {};

  if (Array.isArray(resultado.comprovantes) && resultado.comprovantes.length > 0) {
    return resultado.comprovantes;
  }

  if (resultado.dados_comprovante) {
    return [{
      status: resultado.status || "PRONTO_PARA_SALVAR",
      indice_comprovante: 1,
      tipo_documento: resultado.tipo_documento || "nao_identificado",
      data_deposito: resultado.dados_comprovante.data_deposito || null,
      valor_deposito: resultado.dados_comprovante.valor_deposito || null,
      banco: resultado.dados_comprovante.banco || "Nao identificado",
      data_geracao_documento: resultado.dados_comprovante.data_geracao_documento || null,
      codigo_autenticacao: resultado.dados_comprovante.codigo_autenticacao || "",
      observacoes: resultado.pendencias || []
    }];
  }

  return [];
}

function smartSlipItemTemInferenciaOuBaixaEvidencia_(item) {
  item = item || {};

  const obs = Array.isArray(item.observacoes)
    ? item.observacoes.join(" | ")
    : String(item.observacoes || "");

  const obsNorm = obs
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  const evid = item.evidencias || {};

  const valorTexto = String(evid.valor_deposito_texto || "").trim();
  const dataTexto = String(evid.data_deposito_texto || "").trim();
  const blocoTexto = String(evid.bloco_textual_comprovante || "").trim();

  const valor = Number(item.valor_deposito || 0);
  const dataDeposito = String(item.data_deposito || "").trim();
  const dataGeracao = String(item.data_geracao_documento || "").trim();
  const tipoDocumento = String(item.tipo_documento || "").trim();
  const confiancaItem = Number(item.confianca_item || 0);

  if (!valor || valor <= 0) {
    return {
      bloquear: true,
      motivo: "Valor do depósito ausente ou inválido."
    };
  }

  if (!valorTexto) {
    return {
      bloquear: true,
      motivo: "Sem evidência textual do valor do depósito."
    };
  }

  if (!dataDeposito) {
    return {
      bloquear: true,
      motivo: "Data do depósito ausente."
    };
  }

  if (!dataTexto) {
    return {
      bloquear: true,
      motivo: "Sem evidência textual da data do depósito."
    };
  }

  if (!tipoDocumento || tipoDocumento === "nao_identificado") {
    return {
      bloquear: true,
      motivo: "Tipo de documento ausente ou não identificado."
    };
  }

  if (!blocoTexto || blocoTexto.length < 40) {
    return {
      bloquear: true,
      motivo: "Sem bloco textual suficiente do comprovante."
    };
  }

  const temEvidenciaForte =
    valor > 0 &&
    valorTexto.length >= 3 &&
    dataDeposito.length >= 8 &&
    dataTexto.length >= 6 &&
    blocoTexto.length >= 40;

  const confiancaForte =
    !confiancaItem || confiancaItem >= 0.95;

  /*
    Caso permitido:
    A IA ajustou somente o ANO da data de geração/documento
    por coerência com a data de pagamento e período de movimento.
    Isso não deve bloquear quando valor e data de pagamento estão claros.
  */
  const ajusteAnoDataGeracaoPermitido =
    (
      obsNorm.includes("ano da data de geracao") ||
      obsNorm.includes("ano da data de geração") ||
      obsNorm.includes("data de geracao do documento") ||
      obsNorm.includes("data de geração do documento")
    ) &&
    (
      obsNorm.includes("foi ajustado") ||
      obsNorm.includes("ano foi ajustado") ||
      obsNorm.includes("consistencia") ||
      obsNorm.includes("consistência")
    ) &&
    (
      obsNorm.includes("data de pagamento") ||
      obsNorm.includes("periodo de movimento") ||
      obsNorm.includes("período de movimento")
    );

  if (
    ajusteAnoDataGeracaoPermitido &&
    temEvidenciaForte &&
    confiancaForte &&
    dataGeracao
  ) {
    return {
      bloquear: false,
      motivo: ""
    };
  }

  const falaDeCodigoAutenticacao =
    obsNorm.includes("codigo de autenticacao") ||
    obsNorm.includes("autenticacao") ||
    obsNorm.includes("via do cliente");

  const falaDeCampoCriticoReal =
    obsNorm.includes("valor do deposito") ||
    obsNorm.includes("valor de deposito") ||
    obsNorm.includes("valor do pagamento") ||
    obsNorm.includes("valor_deposito") ||
    obsNorm.includes("data do deposito") ||
    obsNorm.includes("data de deposito") ||
    obsNorm.includes("data_deposito") ||
    obsNorm.includes("data do pagamento") ||
    obsNorm.includes("data de pagamento") ||
    obsNorm.includes("tipo de documento") ||
    obsNorm.includes("tipo_documento");

  const sinalInferenciaForte =
    obsNorm.includes("inferid") ||
    obsNorm.includes("nao esta claro") ||
    obsNorm.includes("não está claro") ||
    obsNorm.includes("duvida") ||
    obsNorm.includes("dúvida");

  const sinalLeituraParcial =
    obsNorm.includes("parcialmente visivel") ||
    obsNorm.includes("parcialmente visiveis") ||
    obsNorm.includes("trechos parcialmente");

  if (!falaDeCodigoAutenticacao) {
    if (sinalInferenciaForte && falaDeCampoCriticoReal) {
      return {
        bloquear: true,
        motivo: "Item possui observação de inferência ou dúvida em campo crítico."
      };
    }

    if (
      sinalLeituraParcial &&
      falaDeCampoCriticoReal &&
      !(temEvidenciaForte && confiancaForte)
    ) {
      return {
        bloquear: true,
        motivo: "Item possui leitura parcial em campo crítico sem evidência suficiente."
      };
    }
  }

  return {
    bloquear: false,
    motivo: ""
  };
}

function smartSlipValidarDuplicidadeEvidenciaLote_(comprovantes) {
  comprovantes = Array.isArray(comprovantes) ? comprovantes : [];

  const mapaEvidenciaForte = {};
  const mapaPosicaoValor = {};
  const duplicidades = [];
  const repeticoesSemEvidenciaDistinta = [];

  function assinaturaBloco_(txt) {
    txt = smartSlipTextoChave_(txt || "");

    if (!txt) {
      return "";
    }

    /*
      Usa trecho maior do bloco, porque comprovantes iguais em layout
      podem ter início muito parecido, mas diferir em controle/autenticação.
    */
    return txt.substring(0, 900);
  }

  function unicosNaoVazios_(arr) {
    const mapa = {};

    (arr || []).forEach(function(v) {
      v = String(v || "").trim();

      if (v) {
        mapa[v] = true;
      }
    });

    return Object.keys(mapa);
  }

  comprovantes.forEach(function(item) {
    item = item || {};

    const evid = item.evidencias || {};
    const indice = item.indice_comprovante || "?";

    const valorCentavos = smartSlipValorCentavos_(item.valor_deposito);
    const dataDeposito = smartSlipTextoChave_(item.data_deposito || "");
    const banco = smartSlipTextoChave_(item.banco || "");
    const tipo = smartSlipTextoChave_(item.tipo_documento || "");

    const posicao = smartSlipTextoChave_(item.posicao_visual_aproximada || "");
    const valorTexto = smartSlipTextoChave_(evid.valor_deposito_texto || "");
    const blocoTexto = smartSlipTextoChave_(evid.bloco_textual_comprovante || "");

    const controleTexto = smartSlipTextoChave_(
      evid.codigo_autenticacao_texto ||
      evid.controle_texto ||
      item.codigo_autenticacao ||
      ""
    );

    const assinaturaBloco = assinaturaBloco_(blocoTexto);

    /*
      Mesmo valor NÃO é duplicidade.
      Duplicidade só deve ocorrer quando a IA reutiliza a mesma evidência
      documental sem código/controle/bloco distinto.
    */
    if (valorCentavos && (controleTexto || assinaturaBloco)) {
      const chaveEvidenciaForte = [
        tipo,
        banco,
        dataDeposito,
        valorCentavos,
        controleTexto || assinaturaBloco
      ].join("|");

      if (!mapaEvidenciaForte[chaveEvidenciaForte]) {
        mapaEvidenciaForte[chaveEvidenciaForte] = [];
      }

      mapaEvidenciaForte[chaveEvidenciaForte].push({
        indice: indice,
        controle: controleTexto,
        bloco: assinaturaBloco,
        posicao: posicao
      });
    }

    /*
      Posição visual igual é apenas sinal de atenção.
      Não deve bloquear sozinha, porque a IA pode retornar posições genéricas
      para comprovantes reais parecidos.
    */
    if (posicao && valorCentavos) {
      const chavePosicaoValor = [
        tipo,
        banco,
        dataDeposito,
        valorCentavos,
        posicao
      ].join("|");

      if (!mapaPosicaoValor[chavePosicaoValor]) {
        mapaPosicaoValor[chavePosicaoValor] = [];
      }

      mapaPosicaoValor[chavePosicaoValor].push({
        indice: indice,
        controle: controleTexto,
        bloco: assinaturaBloco,
        posicao: posicao
      });
    }

    /*
      Falta de evidência mínima continua sendo risco.
      Aqui não bloqueia o lote diretamente, mas fica registrado no retorno
      para auditoria e eventual uso futuro.
    */
    if (valorCentavos && (!valorTexto || !blocoTexto || blocoTexto.length < 40)) {
      repeticoesSemEvidenciaDistinta.push({
        indice: indice,
        valor: item.valor_deposito,
        motivo: "valor informado sem evidência textual/bloco OCR suficiente"
      });
    }
  });

  /*
    Bloqueio forte:
    mesma evidência forte repetida para mais de um item.
    Se o controle/autenticação é diferente, a chave muda e não bloqueia.
  */
  Object.keys(mapaEvidenciaForte).forEach(function(chave) {
    const grupo = mapaEvidenciaForte[chave];

    if (grupo.length > 1) {
      duplicidades.push({
        tipo: "MESMA_EVIDENCIA_FORTE",
        indices: grupo.map(function(x) {
          return x.indice;
        })
      });
    }
  });

  /*
    Bloqueio por posição só acontece se os itens também não tiverem
    controles/blocos distintos. Isso evita falso bloqueio em comprovantes
    reais com mesmo valor.
  */
  Object.keys(mapaPosicaoValor).forEach(function(chave) {
    const grupo = mapaPosicaoValor[chave];

    if (grupo.length <= 1) {
      return;
    }

    const controlesDistintos = unicosNaoVazios_(grupo.map(function(x) {
      return x.controle;
    }));

    const blocosDistintos = unicosNaoVazios_(grupo.map(function(x) {
      return x.bloco;
    }));

    const temControleDistintoParaTodos =
      controlesDistintos.length === grupo.length;

    const temBlocoDistintoParaTodos =
      blocosDistintos.length === grupo.length;

    /*
      Se cada item tem controle ou bloco distinto, permite.
      Mesma posição visual, nesse caso, é só imprecisão da IA.
    */
    if (temControleDistintoParaTodos || temBlocoDistintoParaTodos) {
      return;
    }

    duplicidades.push({
      tipo: "MESMA_POSICAO_VISUAL_MESMO_VALOR_SEM_EVIDENCIA_DISTINTA",
      indices: grupo.map(function(x) {
        return x.indice;
      }),
      controles_distintos: controlesDistintos.length,
      blocos_distintos: blocosDistintos.length
    });
  });

  if (duplicidades.length) {
    return {
      ok: false,
      motivo: "DUPLICIDADE_EVIDENCIA_DOCUMENTAL",
      mensagem:
        "Validação anti-alucinação bloqueou o lote. A IA retornou comprovantes sem evidência documental distinta suficiente. Índices envolvidos: " +
        duplicidades.map(function(d) {
          return d.indices.join(", ");
        }).join(" | "),
      duplicidades: duplicidades
    };
  }

  return {
    ok: true,
    motivo: "",
    mensagem: "",
    repeticoes_sem_evidencia_distinta: repeticoesSemEvidenciaDistinta
  };
}

function smartSlipValorCentavos_(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return 0;
  }

  let n = 0;

  if (typeof valor === "number") {
    n = valor;
  } else {
    const txt = String(valor)
      .replace(/[R$\s]/g, "")
      .replace(/\./g, "")
      .replace(",", ".")
      .trim();

    n = Number(txt);
  }

  if (isNaN(n)) {
    return 0;
  }

  return Math.round(n * 100);
}

function smartSlipTextoChave_(valor) {
  return String(valor || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .replace(/[^\w\s.,:/-]/g, "")
    .trim();
}

function smartSlipGerarCodigoUnicoComprovante(protocolo, indiceComprovante) {
  const indice = String(indiceComprovante || 1).padStart(3, "0");
  const base = String(protocolo || "SS-SEM-PROTOCOLO").trim();

  return base + "-C" + indice;
}

function smartSlipGerarIdComprovante(protocolo, indiceComprovante) {
  const protocoloLimpo = String(protocolo || "SS-SEM-PROTOCOLO").trim();
  const indice = String(indiceComprovante || 1).padStart(3, "0");

  return protocoloLimpo + "-C" + indice;
}

function smartSlipGerarHashComprovante(dados) {
  const base = [
    dados.protocolo || "",
    dados.indice_comprovante || "",
    dados.loja || "",
    dados.empresa || "",
    dados.tipo_documento || "",
    dados.data_deposito || "",
    dados.valor_deposito || "",
    dados.banco || "",
    dados.data_movimento || "",
    dados.link_comprovante || ""
  ].join("|");

  const bytes = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    base,
    Utilities.Charset.UTF_8
  );

  return bytes.map(function(b) {
    const v = (b < 0 ? b + 256 : b).toString(16);
    return v.length === 1 ? "0" + v : v;
  }).join("");
}

function smartSlipObterUltimaLojaUsuario(email) {
  email = String(email || "").trim().toLowerCase();

  if (!email) return "";

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh || sh.getLastRow() < 2) {
    return "";
  }

  const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];

    const emailRow = String(row[2] || "").trim().toLowerCase();
    const loja = String(row[3] || "").trim();

    if (emailRow === email && loja) {
      return loja;
    }
  }

  return "";
}

function smartSlipGetAdocaoLojasSmartSlip(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const lojasEscopo = smartSlipListarLojasInfoLimites(usuario);
  const mapa = {};

  lojasEscopo.forEach(function(item) {
    const loja4 = smartSlipNormalizarLoja4(item.loja || "");

    if (!loja4) {
      return;
    }

    mapa[loja4] = {
      loja: loja4,
      time: item.time || "",
      gerente_regional: item.gerente_regional || "",
      email_regional: item.email_regional || "",
      quantidade_envios: 0,
      ultimo_envio: "",
      usando: false
    };
  });

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (sh && sh.getLastRow() >= 2) {
    const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();

    for (let i = 0; i < values.length; i++) {
      const row = values[i];
      if (
          smartSlipStatusEhExcluido_(
            row[13]
          )
        ) {
          continue;
        }

      const dataRegistro = row[0];
      const loja4 = smartSlipNormalizarLoja4(row[3] || "");

      if (!loja4) {
        continue;
      }

      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja4)) {
        continue;
      }

      if (!mapa[loja4]) {
        mapa[loja4] = {
          loja: loja4,
          time: "",
          gerente_regional: "",
          email_regional: "",
          quantidade_envios: 0,
          ultimo_envio: "",
          usando: false
        };
      }

      mapa[loja4].quantidade_envios++;
      mapa[loja4].usando = true;

      const dataFormatada = smartSlipFormatarDataHora(dataRegistro);

      if (dataFormatada) {
        mapa[loja4].ultimo_envio = dataFormatada;
      }
    }
  }

  const rows = Object.keys(mapa)
    .sort()
    .map(function(k) {
      return mapa[k];
    });

  const lojasUtilizando = rows.filter(function(item) {
    return item.usando === true;
  }).length;

  return {
    total_lojas_escopo: rows.length,
    lojas_utilizando: lojasUtilizando,
    lojas_sem_uso: Math.max(0, rows.length - lojasUtilizando),
    rows: rows
  };
}

/****************************************************
 * SMARTSLIP
 * PESQUISA TRIMESTRAL DE SATISFAÇÃO
 ****************************************************/


function smartSlipPesquisaObjetoVazio_() {
  return {
    ativo: false,
    usuario_elegivel: false,
    pendente_usuario: false,
    ciclo_pendente: "",
    ciclo_atual: "",
    data_primeiro_ciclo:
      SMARTSLIP_PESQUISA_PRIMEIRO_CICLO,

    resumo: {
      ciclo_id: "",
      data_ciclo: "",
      total_elegiveis: 0,
      total_respostas: 0,
      taxa_resposta_pct: 0,
      impacto_medio: null,
      apta_relatorio_executivo: false,
      avaliacao: []
    }
  };
}


/****************************************************
 * DATA ATUAL EM SÃO PAULO
 ****************************************************/

function smartSlipPesquisaHojeISO_() {

  return Utilities.formatDate(
    new Date(),
    SMARTSLIP_PESQUISA_TIMEZONE,
    "yyyy-MM-dd"
  );

}


/****************************************************
 * CONVERSÃO DE DATA ISO
 ****************************************************/

function smartSlipPesquisaDateFromISO_(
  iso
) {

  const partes =
    String(
      iso || ""
    )
      .split("-")
      .map(Number);

  if (
    partes.length !== 3 ||
    !partes[0] ||
    !partes[1] ||
    !partes[2]
  ) {
    return null;
  }

  return new Date(
    Date.UTC(
      partes[0],
      partes[1] - 1,
      partes[2]
    )
  );

}


function smartSlipPesquisaDateToISO_(
  data
) {

  if (
    !(data instanceof Date) ||
    isNaN(data.getTime())
  ) {
    return "";
  }

  return Utilities.formatDate(
    data,
    "UTC",
    "yyyy-MM-dd"
  );

}

/****************************************************
 * NORMALIZA CICLO DA PESQUISA
 *
 * Aceita:
 * - "2026-09-21"
 * - Date do Google Sheets
 * - "21/09/2026"
 *
 * Sempre retorna:
 * - "2026-09-21"
 ****************************************************/

function smartSlipPesquisaNormalizarCicloId_(valor) {

  if (
    valor === null ||
    valor === undefined ||
    valor === ""
  ) {
    return "";
  }


  /*
   * Quando o Google Sheets transforma
   * automaticamente 2026-09-21 em data.
   */
  if (
    Object.prototype.toString.call(valor) ===
      "[object Date]" &&
    !isNaN(valor.getTime())
  ) {

    return Utilities.formatDate(
      valor,
      SMARTSLIP_PESQUISA_TIMEZONE,
      "yyyy-MM-dd"
    );

  }


  const texto =
    String(valor)
      .trim();


  /*
   * Já está correto.
   */
  if (
    /^\d{4}-\d{2}-\d{2}$/.test(texto)
  ) {
    return texto;
  }


  /*
   * Caso venha como dd/MM/yyyy.
   */
  const br =
    texto.match(
      /^(\d{2})\/(\d{2})\/(\d{4})$/
    );


  if (br) {

    return (
      br[3] +
      "-" +
      br[2] +
      "-" +
      br[1]
    );

  }


  return texto;
}

function smartSlipPesquisaFormatarDataBR_(
  iso
) {

  const data =
    smartSlipPesquisaDateFromISO_(
      iso
    );

  if (!data) {
    return "";
  }

  return Utilities.formatDate(
    data,
    "UTC",
    "dd/MM/yyyy"
  );

}


/****************************************************
 * SOMA DE MESES DO CICLO
 ****************************************************/

function smartSlipPesquisaSomarMesesISO_(
  iso,
  meses
) {

  const data =
    smartSlipPesquisaDateFromISO_(
      iso
    );

  if (!data) {
    return "";
  }

  const diaOriginal =
    data.getUTCDate();

  const alvo =
    new Date(
      Date.UTC(
        data.getUTCFullYear(),
        data.getUTCMonth() +
          Number(
            meses || 0
          ),
        1
      )
    );

  /*
   * Mantém o dia 21.
   *
   * A proteção abaixo também permite
   * reutilizar a função com outros dias
   * sem estourar o mês.
   */
  const ultimoDiaMes =
    new Date(
      Date.UTC(
        alvo.getUTCFullYear(),
        alvo.getUTCMonth() + 1,
        0
      )
    )
      .getUTCDate();

  alvo.setUTCDate(
    Math.min(
      diaOriginal,
      ultimoDiaMes
    )
  );

  return smartSlipPesquisaDateToISO_(
    alvo
  );

}


/****************************************************
 * CICLOS JÁ LIBERADOS
 ****************************************************/

function smartSlipListarCiclosPesquisaAteHoje_() {

  const hoje =
    smartSlipPesquisaHojeISO_();

  const ciclos = [];

  let ciclo =
    SMARTSLIP_PESQUISA_PRIMEIRO_CICLO;

  /*
   * Segurança para impedir qualquer
   * possibilidade de loop infinito.
   */
  let contador =
    0;

  while (
    ciclo &&
    ciclo <= hoje &&
    contador < 200
  ) {

    ciclos.push(
      ciclo
    );

    ciclo =
      smartSlipPesquisaSomarMesesISO_(
        ciclo,
        SMARTSLIP_PESQUISA_INTERVALO_MESES
      );

    contador++;

  }

  return ciclos;
}


/****************************************************
 * ABA DE RESPOSTAS
 ****************************************************/

function smartSlipGarantirAbaPesquisaSatisfacao_() {

  const ss =
    SpreadsheetApp.openById(
      SMARTSLIP_DB_SPREADSHEET_ID
    );

  let sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_PESQUISA_SATISFACAO
    );

  if (!sh) {

    sh =
      ss.insertSheet(
        SMARTSLIP_ABA_PESQUISA_SATISFACAO
      );

  }


  const headers = [

    "Data_Resposta",
    "Ciclo_ID",
    "Data_Ciclo",
    "Email_Usuario",
    "Loja",
    "Empresa",
    "Impacto_1_10",
    "Avaliacao_Codigo",
    "Avaliacao_Label",
    "Dispositivo"

  ];


  if (
    sh.getMaxColumns() <
    headers.length
  ) {

    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length -
        sh.getMaxColumns()
    );

  }


  if (
    sh.getLastRow() === 0
  ) {

    sh
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .setValues([
        headers
      ]);

    sh.setFrozenRows(
      1
    );

    return sh;

  }


  const atuais =
    sh
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .getValues()[0];


  headers.forEach(
    function(
      nome,
      idx
    ) {

      if (
        !String(
          atuais[idx] || ""
        ).trim()
      ) {

        sh
          .getRange(
            1,
            idx + 1
          )
          .setValue(
            nome
          );

      }

    }
  );


  sh.setFrozenRows(
    1
  );

  return sh;
}


/****************************************************
 * ABA DE CICLOS
 *
 * Essa aba congela o total de usuários
 * elegíveis no início de cada pesquisa.
 *
 * Assim a taxa de resposta de setembro,
 * por exemplo, não muda futuramente
 * porque novos usuários foram cadastrados.
 ****************************************************/

function smartSlipGarantirAbaPesquisaCiclos_() {

  const ss =
    SpreadsheetApp.openById(
      SMARTSLIP_DB_SPREADSHEET_ID
    );

  let sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_PESQUISA_CICLOS
    );

  if (!sh) {

    sh =
      ss.insertSheet(
        SMARTSLIP_ABA_PESQUISA_CICLOS
      );

  }


  const headers = [

    "Ciclo_ID",
    "Data_Ciclo",
    "Total_Usuarios_Elegiveis",
    "Criado_Em"

  ];


  if (
    sh.getMaxColumns() <
    headers.length
  ) {

    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length -
        sh.getMaxColumns()
    );

  }


  if (
    sh.getLastRow() === 0
  ) {

    sh
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .setValues([
        headers
      ]);

    sh.setFrozenRows(
      1
    );

    return sh;

  }


  const atuais =
    sh
      .getRange(
        1,
        1,
        1,
        headers.length
      )
      .getValues()[0];


  headers.forEach(
    function(
      nome,
      idx
    ) {

      if (
        !String(
          atuais[idx] || ""
        ).trim()
      ) {

        sh
          .getRange(
            1,
            idx + 1
          )
          .setValue(
            nome
          );

      }

    }
  );


  sh.setFrozenRows(
    1
  );

  return sh;
}


/****************************************************
 * USUÁRIO É DE LOJA?
 ****************************************************/

function smartSlipUsuarioElegivelPesquisa_(
  usuario
) {

  usuario =
    usuario || {};

  const emailUsuario =
  String(
    usuario.email || ""
  )
    .trim()
    .toLowerCase();


const usuarioTesteAdm =
  (
    SMARTSLIP_PESQUISA_TESTE_ADM_ATIVO ===
      true &&
    emailUsuario ===
      SMARTSLIP_PESQUISA_TESTE_ADM_EMAIL
  );


if (
  usuarioTesteAdm
) {
  return true;
}

  /*
   * Pesquisa destinada somente
   * a usuários operacionais das lojas.
   *
   * Administrador, Analista Pro e
   * Gerente Regional não respondem.
   */
  if (
    usuario.is_admin === true ||
    usuario.is_analista_pro === true ||
    usuario.is_regional === true
  ) {
    return false;
  }


  if (
    !String(
      usuario.email || ""
    ).trim()
  ) {
    return false;
  }


  if (
    !String(
      usuario.loja_padrao || ""
    ).trim()
  ) {
    return false;
  }


  return true;
}


/****************************************************
 * TOTAL DE USUÁRIOS DE LOJA ELEGÍVEIS
 ****************************************************/

function smartSlipContarUsuariosLojaElegiveisPesquisa_() {

  const sh =
    smartSlipGarantirAbaUsuarios();

  const lastRow =
    sh.getLastRow();

  if (
    lastRow < 2
  ) {
    return 0;
  }


  const values =
    sh
      .getRange(
        2,
        1,
        lastRow - 1,
        10
      )
      .getValues();


  let total =
    0;


  values.forEach(
    function(row) {

      const email =
        String(
          row[0] || ""
        )
          .trim()
          .toLowerCase();

      const loja =
        String(
          row[1] || ""
        ).trim();

      const ativo =
        smartSlipValorAtivoEhSim_(
          row[4]
        );


      if (
        !email ||
        !loja ||
        !ativo
      ) {
        return;
      }


      /*
       * Mantém exatamente a mesma
       * interpretação de perfil já usada
       * pelo SmartSlip.
       */
      let acesso =
        {};

      try {

        acesso =
          smartSlipGetAcessoUsuario(
            email
          ) || {};

      } catch (err) {

        /*
         * Se não for possível determinar
         * o perfil, não entra no denominador.
         */
        Logger.log(
          "Pesquisa SmartSlip: não foi possível " +
          "determinar perfil de " +
          email +
          ". " +
          String(
            err &&
            err.message
              ? err.message
              : err
          )
        );

        return;

      }


      if (
        acesso.is_admin === true ||
        acesso.is_analista_pro === true ||
        acesso.is_regional === true
      ) {
        return;
      }


      total++;

    }
  );


  return total;
}


/****************************************************
 * CRIA / LÊ UM CICLO
 ****************************************************/

function smartSlipGarantirCicloPesquisa_(
  cicloId
) {

  cicloId =
    smartSlipPesquisaNormalizarCicloId_(
      cicloId
    );


  if (!cicloId) {
    return null;
  }


  const lock =
    LockService.getScriptLock();

  lock.waitLock(
    10000
  );


  try {

    const sh =
      smartSlipGarantirAbaPesquisaCiclos_();

    const lastRow =
      sh.getLastRow();


    if (
      lastRow >= 2
    ) {

      const values =
        sh
          .getRange(
            2,
            1,
            lastRow - 1,
            4
          )
          .getValues();


      for (
        let i = 0;
        i < values.length;
        i++
      ) {

        const row =
          values[i];

        if (
          smartSlipPesquisaNormalizarCicloId_(
            row[0]
          ) === cicloId
        ) {

          return {
            ciclo_id:
              cicloId,

            data_ciclo:
              String(
                row[1] ||
                cicloId
              ).trim(),

            total_elegiveis:
              Number(
                row[2] || 0
              ),

            criado_em:
              row[3] || ""
          };

        }

      }

    }


    const totalElegiveis =
      smartSlipContarUsuariosLojaElegiveisPesquisa_();


    sh.appendRow([
      cicloId,
      cicloId,
      totalElegiveis,
      new Date()
    ]);


    return {
      ciclo_id:
        cicloId,

      data_ciclo:
        cicloId,

      total_elegiveis:
        totalElegiveis,

      criado_em:
        new Date()
    };


  } finally {

    lock.releaseLock();

  }
}


/****************************************************
 * USUÁRIO JÁ RESPONDEU?
 ****************************************************/

function smartSlipUsuarioJaRespondeuPesquisa_(
  email,
  cicloId
) {

  email =
    String(
      email || ""
    )
      .trim()
      .toLowerCase();

cicloId =
  smartSlipPesquisaNormalizarCicloId_(
    cicloId
  );


  if (
    !email ||
    !cicloId
  ) {
    return false;
  }


  const sh =
    smartSlipGarantirAbaPesquisaSatisfacao_();

  const lastRow =
    sh.getLastRow();


  if (
    lastRow < 2
  ) {
    return false;
  }


  const values =
    sh
      .getRange(
        2,
        1,
        lastRow - 1,
        10
      )
      .getValues();


  for (
    let i = 0;
    i < values.length;
    i++
  ) {

    const row =
      values[i];

    const cicloRow =
      smartSlipPesquisaNormalizarCicloId_(
        row[1]
      );

    const emailRow =
      String(
        row[3] || ""
      )
        .trim()
        .toLowerCase();


    if (
      cicloRow === cicloId &&
      emailRow === email
    ) {
      return true;
    }

  }


  return false;
}


/****************************************************
 * MAPA DAS 5 AVALIAÇÕES
 ****************************************************/

function smartSlipMapaAvaliacaoPesquisa_() {

  return {

    MUITO_RUIM: {
      label:
        "Muito ruim",
      emoji:
        "😡"
    },

    RUIM: {
      label:
        "Ruim",
      emoji:
        "☹️"
    },

    REGULAR: {
      label:
        "Regular",
      emoji:
        "😐"
    },

    BOM: {
      label:
        "Bom",
      emoji:
        "🙂"
    },

    EXCELENTE: {
      label:
        "Excelente",
      emoji:
        "😍"
    }

  };
}


/****************************************************
 * RESUMO DE UM CICLO
 ****************************************************/

function smartSlipGetResumoCicloPesquisa_(
  cicloId
) {

cicloId =
  smartSlipPesquisaNormalizarCicloId_(
    cicloId
  );


  if (!cicloId) {

    return {
      ciclo_id: "",
      data_ciclo: "",
      total_elegiveis: 0,
      total_respostas: 0,
      taxa_resposta_pct: 0,
      impacto_medio: null,
      apta_relatorio_executivo: false,
      avaliacao: []
    };

  }


  const ciclo =
    smartSlipGarantirCicloPesquisa_(
      cicloId
    );


  const totalElegiveis =
    Number(
      ciclo &&
      ciclo.total_elegiveis
        ? ciclo.total_elegiveis
        : 0
    );


  const mapaAvaliacao =
    smartSlipMapaAvaliacaoPesquisa_();


  const contagem = {

    MUITO_RUIM: 0,
    RUIM: 0,
    REGULAR: 0,
    BOM: 0,
    EXCELENTE: 0

  };


  const emailsRespondidos =
    {};

  let somaImpacto =
    0;

  let qtdImpacto =
    0;


  const sh =
    smartSlipGarantirAbaPesquisaSatisfacao_();

  const lastRow =
    sh.getLastRow();


  if (
    lastRow >= 2
  ) {

    const values =
      sh
        .getRange(
          2,
          1,
          lastRow - 1,
          10
        )
        .getValues();


    values.forEach(
      function(row) {

      const cicloRow =
        smartSlipPesquisaNormalizarCicloId_(
          row[1]
        );

        if (
          cicloRow !== cicloId
        ) {
          return;
        }


        const email =
          String(
            row[3] || ""
          )
            .trim()
            .toLowerCase();


        /*
         * Proteção contra eventual
         * duplicação manual na planilha.
         */
        if (
          email &&
          emailsRespondidos[email]
        ) {
          return;
        }


        if (email) {
          emailsRespondidos[email] =
            true;
        }


        const impacto =
          Number(
            row[6] || 0
          );


        if (
          impacto >= 1 &&
          impacto <= 10
        ) {

          somaImpacto +=
            impacto;

          qtdImpacto++;

        }


        const codigo =
          String(
            row[7] || ""
          )
            .trim()
            .toUpperCase();


        if (
          Object.prototype.hasOwnProperty.call(
            contagem,
            codigo
          )
        ) {

          contagem[codigo]++;

        }

      }
    );

  }


  const totalRespostas =
    Object.keys(
      emailsRespondidos
    ).length;


  const taxaResposta =
    totalElegiveis > 0
      ? (
          totalRespostas /
          totalElegiveis
        ) * 100
      : 0;


  const impactoMedio =
    qtdImpacto > 0
      ? (
          somaImpacto /
          qtdImpacto
        )
      : null;


  const ordem = [
    "MUITO_RUIM",
    "RUIM",
    "REGULAR",
    "BOM",
    "EXCELENTE"
  ];


  const avaliacao =
    ordem.map(
      function(codigo) {

        const quantidade =
          Number(
            contagem[codigo] || 0
          );


        const percentual =
          totalRespostas > 0
            ? (
                quantidade /
                totalRespostas
              ) * 100
            : 0;


        return {
          codigo:
            codigo,

          label:
            mapaAvaliacao[codigo].label,

          emoji:
            mapaAvaliacao[codigo].emoji,

          quantidade:
            quantidade,

          percentual:
            Math.round(
              percentual * 100
            ) / 100
        };

      }
    );


  return {

    ciclo_id:
      cicloId,

    data_ciclo:
      smartSlipPesquisaFormatarDataBR_(
        cicloId
      ),

    total_elegiveis:
      totalElegiveis,

    total_respostas:
      totalRespostas,

    taxa_resposta_pct:
      Math.round(
        taxaResposta * 100
      ) / 100,

    impacto_medio:
      impactoMedio === null
        ? null
        : (
            Math.round(
              impactoMedio * 100
            ) / 100
          ),

    apta_relatorio_executivo:
      taxaResposta >=
        SMARTSLIP_PESQUISA_MIN_RESPOSTA_EXECUTIVO_PCT,

    avaliacao:
      avaliacao

  };
}


/****************************************************
 * DADOS DA PESQUISA PARA O APP
 ****************************************************/

function smartSlipGetPesquisaSatisfacao_(
  usuario
) {

  usuario =
    usuario ||
    smartSlipGetUsuarioAtual();


  const base =
    smartSlipPesquisaObjetoVazio_();


  const ciclos =
    smartSlipListarCiclosPesquisaAteHoje_();


  if (
    !ciclos.length
  ) {

    /*
     * Antes de 21/09/2026.
     */
    return base;

  }


  const usuarioElegivel =
    smartSlipUsuarioElegivelPesquisa_(
      usuario
    );


  const cicloAtual =
    ciclos[
      ciclos.length - 1
    ];


  /*
   * Garante o snapshot do total
   * elegível assim que o ciclo existir.
   */
  smartSlipGarantirCicloPesquisa_(
    cicloAtual
  );


  let cicloPendente =
    "";


  if (
    usuarioElegivel
  ) {

    /*
     * Procura o ciclo mais antigo
     * ainda não respondido.
     *
     * Isso garante persistência real:
     * a pesquisa não desaparece porque
     * um novo trimestre começou.
     */
    for (
      let i = 0;
      i < ciclos.length;
      i++
    ) {

      const ciclo =
        ciclos[i];


      if (
        !smartSlipUsuarioJaRespondeuPesquisa_(
          usuario.email,
          ciclo
        )
      ) {

        cicloPendente =
          ciclo;

        break;

      }

    }

  }


  return {

    ativo:
      true,

    usuario_elegivel:
      usuarioElegivel,

    pendente_usuario:
      !!cicloPendente,

    ciclo_pendente:
      cicloPendente,

    ciclo_atual:
      cicloAtual,

    data_primeiro_ciclo:
      SMARTSLIP_PESQUISA_PRIMEIRO_CICLO,

    resumo:
      smartSlipGetResumoCicloPesquisa_(
        cicloAtual
      )

  };
}


/****************************************************
 * SALVAR RESPOSTA
 ****************************************************/

function smartSlipSalvarPesquisaSatisfacao_(
  payload
) {

  payload =
    payload || {};


  const acesso =
    smartSlipAssertUsuarioAutorizado_();


  const usuario =
    smartSlipGetUsuarioAtual();


  if (
    !smartSlipUsuarioElegivelPesquisa_(
      usuario
    )
  ) {

    throw new Error(
      "Esta pesquisa é destinada aos usuários de loja."
    );

  }


  const cicloId =
    String(
      payload.ciclo_id || ""
    ).trim();


  const ciclosDisponiveis =
    smartSlipListarCiclosPesquisaAteHoje_();


  if (
    ciclosDisponiveis.indexOf(
      cicloId
    ) === -1
  ) {

    throw new Error(
      "O ciclo informado ainda não está disponível."
    );

  }


  const impacto =
    Number(
      payload.impacto_1_10
    );


  if (
    !Number.isInteger(
      impacto
    ) ||
    impacto < 1 ||
    impacto > 10
  ) {

    throw new Error(
      "Selecione uma nota de impacto entre 1 e 10."
    );

  }


  const codigo =
    String(
      payload.avaliacao_codigo || ""
    )
      .trim()
      .toUpperCase();


  const mapaAvaliacao =
    smartSlipMapaAvaliacaoPesquisa_();


  if (
    !mapaAvaliacao[codigo]
  ) {

    throw new Error(
      "Selecione uma avaliação geral da plataforma."
    );

  }


  const email =
    String(
      acesso.email ||
      usuario.email ||
      ""
    )
      .trim()
      .toLowerCase();

  smartSlipGarantirCicloPesquisa_(
    cicloId
  );

  const lock =
    LockService.getScriptLock();


  lock.waitLock(
    10000
  );


  try {

    if (
      smartSlipUsuarioJaRespondeuPesquisa_(
        email,
        cicloId
      )
    ) {

      return {
        ok:
          true,

        ja_respondido:
          true,

        mensagem:
          "Sua resposta deste ciclo já foi registrada.",

        pesquisa:
          smartSlipGetPesquisaSatisfacao_(
            usuario
          )
      };

    }


    smartSlipGarantirCicloPesquisa_(
      cicloId
    );


    const sh =
      smartSlipGarantirAbaPesquisaSatisfacao_();


    sh.appendRow([

      new Date(),

      cicloId,

      cicloId,

      email,

      String(
        usuario.loja_padrao || ""
      ).trim(),

      String(
        usuario.empresa_padrao || ""
      ).trim(),

      impacto,

      codigo,

      mapaAvaliacao[codigo].label,

      String(
        payload.dispositivo || ""
      )
        .trim()
        .toUpperCase()

    ]);


  } finally {

    lock.releaseLock();

  }


  return {

    ok:
      true,

    mensagem:
      "Obrigado! Sua avaliação foi registrada.",

    pesquisa:
      smartSlipGetPesquisaSatisfacao_(
        usuario
      )

  };
}


/****************************************************
 * ENDPOINT PARA O HTML
 ****************************************************/

function smartSlipSalvarPesquisaSatisfacaoJson(
  payloadJson
) {

  try {

    let payload =
      {};


    if (
      typeof payloadJson ===
      "string"
    ) {

      payload =
        JSON.parse(
          payloadJson ||
          "{}"
        );

    } else {

      payload =
        payloadJson ||
        {};

    }


    return JSON.stringify({

      ok:
        true,

      payload:
        smartSlipSalvarPesquisaSatisfacao_(
          payload
        )

    });


  } catch (err) {

    return JSON.stringify({

      ok:
        false,

      erro:
        String(
          err &&
          err.message
            ? err.message
            : err
        )

    });

  }
}


/****************************************************
 * CONSULTA ISOLADA
 *
 * Útil para atualizar o painel depois
 * que alguém responder.
 ****************************************************/

function smartSlipGetPesquisaSatisfacaoJson() {

  try {

    smartSlipAssertUsuarioAutorizado_();


    return JSON.stringify({

      ok:
        true,

      payload:
        smartSlipGetPesquisaSatisfacao_(
          smartSlipGetUsuarioAtual()
        )

    });


  } catch (err) {

    return JSON.stringify({

      ok:
        false,

      erro:
        String(
          err &&
          err.message
            ? err.message
            : err
        )

    });

  }
}

function smartSlipGetBootstrapApp() {
  try {
    const usuario =
      smartSlipGetUsuarioAtual();

    let lojasDisponiveis = [];
    let resumoMensal = [];
    let historico = [];
    let resumoDiario = [];
    let resumoStatus = [];
    let storeSignupMensal = [];
    let storeSignupDiario = [];
    let lojasAtencao = [];

    let adocaoLojas = {
      total_lojas_escopo: 0,
      lojas_utilizando: 0,
      lojas_sem_uso: 0,
      rows: []
    };

    let inatividadeLojas = {
      atualizado_em: "",
      atualizado_hora: "",
      total_lojas: 0,
      total_criticas: 0,
      rows: []
    };

    let pesquisaSatisfacao =
      smartSlipPesquisaObjetoVazio_();

    try {
      lojasDisponiveis =
        smartSlipListarLojasInfoLimites(
          usuario
        );
    } catch (errLojas) {
      Logger.log(
        "Erro ao carregar lojas disponíveis: " +
        String(
          errLojas && errLojas.message
            ? errLojas.message
            : errLojas
        )
      );

      lojasDisponiveis = [];
    }

    try {
      resumoMensal =
        smartSlipGetResumoMensal(
          usuario
        );
    } catch (errResumo) {
      Logger.log(
        "Erro ao carregar resumo mensal: " +
        String(
          errResumo && errResumo.message
            ? errResumo.message
            : errResumo
        )
      );

      resumoMensal = [];
    }

    try {
      resumoDiario =
        smartSlipGetResumoDiario(
          usuario
        );
    } catch (errDiario) {
      Logger.log(
        "Erro ao carregar resumo diário: " +
        String(
          errDiario && errDiario.message
            ? errDiario.message
            : errDiario
        )
      );

      resumoDiario = [];
    }

    try {
      storeSignupMensal =
        smartSlipGetStoreSignupMensal(
          usuario
        );
    } catch (errStoreMensal) {
      Logger.log(
        "Erro ao carregar Store Sign-up mensal: " +
        String(
          errStoreMensal &&
          errStoreMensal.message
            ? errStoreMensal.message
            : errStoreMensal
        )
      );

      storeSignupMensal = [];
    }

    try {
      storeSignupDiario =
        smartSlipGetStoreSignupDiario(
          usuario
        );
    } catch (errStoreDiario) {
      Logger.log(
        "Erro ao carregar Store Sign-up diário: " +
        String(
          errStoreDiario &&
          errStoreDiario.message
            ? errStoreDiario.message
            : errStoreDiario
        )
      );

      storeSignupDiario = [];
    }

    try {
      historico =
        smartSlipGetHistorico(
          usuario
        );
    } catch (errHistorico) {
      Logger.log(
        "Erro ao carregar histórico: " +
        String(
          errHistorico &&
          errHistorico.message
            ? errHistorico.message
            : errHistorico
        )
      );

      historico = [];
    }

    try {
      resumoStatus =
        smartSlipGetResumoStatus(
          usuario
        );
    } catch (errStatus) {
      Logger.log(
        "Erro ao carregar resumo de status: " +
        String(
          errStatus && errStatus.message
            ? errStatus.message
            : errStatus
        )
      );

      resumoStatus = [];
    }

    try {
      adocaoLojas =
        smartSlipGetAdocaoLojasSmartSlip(
          usuario
        );
    } catch (errAdocao) {
      Logger.log(
        "Erro ao carregar adoção por loja: " +
        String(
          errAdocao && errAdocao.message
            ? errAdocao.message
            : errAdocao
        )
      );

      adocaoLojas = {
        total_lojas_escopo: 0,
        lojas_utilizando: 0,
        lojas_sem_uso: 0,
        rows: []
      };
    }

    try {

  pesquisaSatisfacao =
    smartSlipGetPesquisaSatisfacao_(
      usuario
    );

} catch (errPesquisa) {

  Logger.log(
    "Erro ao carregar pesquisa de satisfação: " +
    String(
      errPesquisa &&
      errPesquisa.message
        ? errPesquisa.message
        : errPesquisa
    )
  );

  pesquisaSatisfacao =
    smartSlipPesquisaObjetoVazio_();

}

    try {
      lojasAtencao =
        smartSlipGetLojasAtencaoOperacional(
          usuario
        );
    } catch (errLojasAtencao) {
      Logger.log(
        "Erro ao carregar lojas com atenção operacional: " +
        String(
          errLojasAtencao &&
          errLojasAtencao.message
            ? errLojasAtencao.message
            : errLojasAtencao
        )
      );

      lojasAtencao = [];
    }

    try {
      inatividadeLojas =
        smartSlipGetInatividadeLojas(
          usuario
        );
    } catch (errInatividade) {
      Logger.log(
        "Erro ao carregar inatividade por loja: " +
        String(
          errInatividade &&
          errInatividade.message
            ? errInatividade.message
            : errInatividade
        )
      );

      inatividadeLojas = {
        atualizado_em: "",
        atualizado_hora: "",
        total_lojas: 0,
        total_criticas: 0,
        rows: []
      };
    }

    return {
      ok: true,
      usuario: usuario,
      lojas: lojasDisponiveis,
      resumo_mensal: resumoMensal,
      resumo_diario: resumoDiario,
      store_signup_mensal: storeSignupMensal,
      store_signup_diario: storeSignupDiario,
      resumo_status: resumoStatus,
      adocao_lojas: adocaoLojas,
      pesquisa_satisfacao: pesquisaSatisfacao,
      lojas_atencao: lojasAtencao,
      inatividade_lojas: inatividadeLojas,
      historico: historico
    };

  } catch (err) {
    Logger.log(
      "Erro smartSlipGetBootstrapApp: " +
      String(
        err && err.message
          ? err.message
          : err
      )
    );

    return {
      ok: true,

      erro_bootstrap:
        String(
          err && err.message
            ? err.message
            : err
        ),

      usuario: {
        email: "",
        primeiro_nome: "Usuário",
        perfil: "Usuário",
        is_admin: false,
        is_analista_pro: false,
        is_regional: false,
        can_comp_hub: false,
        loja_padrao: ""
      },

      lojas: [],
      resumo_mensal: [],
      resumo_diario: [],
      resumo_status: [],
      store_signup_mensal: [],
      store_signup_diario: [],
      lojas_atencao: [],
      historico: [],
      pesquisa_satisfacao: smartSlipPesquisaObjetoVazio_(),

      inatividade_lojas: {
        atualizado_em: "",
        atualizado_hora: "",
        total_lojas: 0,
        total_criticas: 0,
        rows: []
      },

      adocao_lojas: {
        total_lojas_escopo: 0,
        lojas_utilizando: 0,
        lojas_sem_uso: 0,
        rows: []
      }
    };
  }
}

function smartSlipDiagnosticoBootstrap() {
  const resp = smartSlipGetBootstrapApp();
  Logger.log(JSON.stringify(resp, null, 2));
  return resp;
}

function smartSlipGetBootstrapAppJson() {
  try {
    smartSlipAssertUsuarioAutorizado_();

    const resp = smartSlipGetBootstrapApp();

    return JSON.stringify({
      ok: true,
      payload: resp
    });

  } catch (err) {
    const msg = String(err && err.message ? err.message : err);
    const acessoNegado = msg.indexOf("ACESSO_NAO_AUTORIZADO") >= 0;

    return JSON.stringify({
      ok: false,
      codigo: acessoNegado ? "ACESSO_NAO_AUTORIZADO" : "ERRO_BOOTSTRAP",
      erro: acessoNegado
        ? msg.replace("ACESSO_NAO_AUTORIZADO:", "").trim()
        : msg
    });
  }
}

function smartSlipGetCompHubJson(optionsJson) {
  try {
      smartSlipAssertUsuarioAutorizado_();
    const usuario = smartSlipGetUsuarioAtual();

    if (!usuario.can_comp_hub) {
      return JSON.stringify({
        ok: false,
        erro: "Acesso restrito. O Comp Hub está disponível apenas para Administrador ou Analista Pro."
      });
    }

    let options = {};

    try {
      options = optionsJson ? JSON.parse(optionsJson) : {};
    } catch (e) {
      options = {};
    }

    const dias = Number(options.dias || 60);

    const payload = smartSlipGetCompHub(usuario, {
      dias: dias
    });

    return JSON.stringify({
      ok: true,
      payload: payload
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipExtrairValoresDiariosCompHub_(jsonOriginal) {
  if (!jsonOriginal) {
    return null;
  }

  try {
    const obj = JSON.parse(String(jsonOriginal || "{}"));
    return obj.valores_diarios_movimento || null;
  } catch (err) {
    return null;
  }
}

function smartSlipMontarMapaFilaPorProtocolo_(ss) {
  const mapa = {};

  const shFila = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!shFila || shFila.getLastRow() < 2) {
    return mapa;
  }

  const values = shFila.getRange(2, 1, shFila.getLastRow() - 1, 18).getValues();

  values.forEach(function(row) {
    const protocolo = String(row[1] || "").trim();

    if (!protocolo) {
      return;
    }

    mapa[protocolo] = {
      dataRegistroFila: smartSlipFormatarDataHora(row[0]),
      emailUsuarioFila: String(row[2] || ""),
      lojaInformadaFila: String(row[3] || ""),
      statusFila: String(row[13] || "").trim(),
      mensagemFila: String(row[14] || "").trim(),
      dataProcessamentoFila: smartSlipFormatarDataHora(row[17])
    };
  });

  return mapa;
}

function smartSlipGetCompHub(usuario, options) {
  usuario = usuario || smartSlipGetUsuarioAtual();
  options = options || {};

  const dias = Number(options.dias || 60);

  const limiteData = new Date();
  limiteData.setDate(limiteData.getDate() - dias);
  limiteData.setHours(0, 0, 0, 0);

  if (!usuario.can_comp_hub) {
    throw new Error("Acesso restrito ao Comp Hub.");
  }

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_DESTINO);
  const mapaFilaPorProtocolo = smartSlipMontarMapaFilaPorProtocolo_(ss);

  if (!sh || sh.getLastRow() < 2) {
    return {
      rows: [],
      atualizado_em: smartSlipFormatarDataHora(new Date()),
      range_dias: dias
    };
  }

  const values = sh.getDataRange().getValues();

  const headers = values[0].map(function(h) {
    return String(h || "").trim();
  });

  const linhas = [];

  for (let i = values.length - 1; i >= 1; i--) {
    const row = values[i];

    const dataRegistroRaw = smartSlipGetValorHeaderCompHub(row, headers, ["Data Registro"]);
    const dataRegistroObj = smartSlipConverterDataCompHub_(dataRegistroRaw);

    if (dataRegistroObj && dataRegistroObj < limiteData) {
      continue;
    }

    const protocolo = String(
      smartSlipGetValorHeaderCompHub(row, headers, ["Protocolo"]) || ""
    ).trim();

    const filaInfo = mapaFilaPorProtocolo[protocolo] || {};

    const statusBase = String(
      smartSlipGetValorHeaderCompHub(row, headers, ["Status Processamento"]) || ""
    ).trim();

    const statusOperacional = String(
      filaInfo.statusFila || statusBase || ""
    ).trim();

    /*
  Comprovantes excluídos não podem
  voltar para o Comp Hub.
*/
if (
  smartSlipStatusEhExcluido_(
    statusOperacional
  ) ||
  smartSlipStatusEhExcluido_(
    statusBase
  )
) {
  continue;
}

    const jsonOriginalRaw = String(
  smartSlipGetValorHeaderCompHub(row, headers, ["JSON Original"]) || ""
);

const valoresDiarios = smartSlipExtrairValoresDiariosCompHub_(jsonOriginalRaw);

    const item = {
      dataRegistro: smartSlipFormatarDataHora(
        smartSlipGetValorHeaderCompHub(row, headers, ["Data Registro"])
      ),

      dataRegistroInput: smartSlipFormatarDataInputCompHub(
        smartSlipGetValorHeaderCompHub(row, headers, ["Data Registro"])
      ),

      idComprovante: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["ID Comprovante"]) || ""
      ),

      hashComprovante: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Hash Comprovante"]) || ""
      ),

      protocolo: protocolo,

      indiceComprovante: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Índice Comprovante", "Indice Comprovante"]) || ""
      ),

      loja: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Loja"]) || ""
      ),

      empresa: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Empresa"]) || ""
      ),

      tipoDocumento: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Tipo Documento"]) || ""
      ),

      dataDeposito: smartSlipFormatarDataMovimentoHistorico(
        smartSlipGetValorHeaderCompHub(row, headers, ["Data Depósito", "Data Deposito"])
      ),

      valorDeposito: smartSlipNumeroCompHub(
        smartSlipGetValorHeaderCompHub(row, headers, ["Valor Depósito", "Valor Deposito"])
      ),

      banco: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Banco"]) || ""
      ),

      dataMovimento: smartSlipFormatarDataMovimentoHistorico(
        smartSlipGetValorHeaderCompHub(row, headers, ["Data Movimento"])
      ),

      houveRetirada: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Houve Retirada"]) || ""
      ),

      valorRetirada: smartSlipNumeroCompHub(
        smartSlipGetValorHeaderCompHub(row, headers, ["Valor Retirada"])
      ),

      motivoRetirada: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Motivo Retirada"]) || ""
      ),

      dataGeracaoDocumento: smartSlipFormatarDataMovimentoHistorico(
        smartSlipGetValorHeaderCompHub(row, headers, ["Data Geração Documento", "Data Geracao Documento"])
      ),

      codigoAutenticacao: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Código Autenticação", "Codigo Autenticacao"]) || ""
      ),

      linkComprovante: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Link Comprovante"]) || ""
      ),

      cupomRetiradaMarketingId: String(
        smartSlipGetValorHeaderCompHub(
          row,
          headers,
          [
            "Anexos Retirada ID",
            "Cupom Retirada Marketing ID"
          ]
        ) || ""
      ),

      linkCupomRetiradaMarketing: String(
        smartSlipGetValorHeaderCompHub(
          row,
          headers,
          [
            "Link Anexos Retirada",
            "Link Cupom Retirada Marketing"
          ]
        ) || ""
      ),

      nomeCupomRetiradaMarketing: String(
        smartSlipGetValorHeaderCompHub(
          row,
          headers,
          [
            "Resumo Anexos Retirada",
            "Nome Cupom Retirada Marketing"
          ]
        ) || ""
      ),

      // Status operacional vindo da SMARTSLIP_FILA.
      // Se não encontrar protocolo na fila, usa o status da BASE_SMARTSLIP como fallback.
      statusProcessamento: statusOperacional,
      statusBaseProcessamento: statusBase,
      statusFila: filaInfo.statusFila || "",
      mensagemFila: filaInfo.mensagemFila || "",
      dataProcessamentoFila: filaInfo.dataProcessamentoFila || "",

      pendencias: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Pendências", "Pendencias"]) || ""
      ),

      divergencias: String(
        smartSlipGetValorHeaderCompHub(row, headers, ["Divergências", "Divergencias"]) || ""
      ),

      confiancaGeral: smartSlipNumeroCompHub(
        smartSlipGetValorHeaderCompHub(row, headers, ["Confiança Geral", "Confianca Geral"])
      ),

      valoresDiarios: valoresDiarios,
      jsonOriginal: jsonOriginalRaw
    };

    linhas.push(item);
  }

  return {
    rows: linhas,
    atualizado_em: smartSlipFormatarDataHora(new Date()),
    range_dias: dias
  };
}

function smartSlipGetValorHeaderCompHub(row, headers, nomes) {
  const idx = smartSlipEncontrarIndiceHeader_(headers, nomes);

  if (idx < 0) {
    return "";
  }

  return row[idx];
}

function smartSlipNumeroCompHub(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return 0;
  }

  if (typeof valor === "number") {
    return valor;
  }

  const txt = String(valor)
    .trim()
    .replace(/\./g, "")
    .replace(",", ".");

  const n = Number(txt);

  return isNaN(n) ? 0 : n;
}

function smartSlipFormatarDataInputCompHub(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    return Utilities.formatDate(valor, tz, "yyyy-MM-dd");
  }

  const txt = String(valor).trim();

  let m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (m) {
    return m[3] + "-" + m[2] + "-" + m[1];
  }

  m = txt.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) {
    return m[1] + "-" + m[2] + "-" + m[3];
  }

  return "";
}

function smartSlipConverterDataCompHub_(valor) {
  if (!valor) return null;

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    return valor;
  }

  const txt = String(valor).trim();

  let m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (m) {
    return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  }

  m = txt.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }

  return null;
}

function smartSlipUsuarioPodeVerHistoricoLoja_(
  usuario,
  row
) {
  usuario =
    usuario ||
    smartSlipGetUsuarioAtual();

  row = row || [];

  const lojaRow =
    smartSlipNormalizarLoja4(
      row[3] || ""
    );

  if (!lojaRow) {
    return false;
  }

  /*
    Admin e Analista Pro continuam
    vendo todas as lojas.
  */
  if (
    usuario.is_admin === true ||
    usuario.is_analista_pro === true
  ) {
    return true;
  }

  /*
    A própria função de lojas permitidas
    já resolve:

    Usuário comum:
    somente a loja configurada.

    Regional:
    todas as lojas do seu regional.
  */
  return smartSlipUsuarioPodeVerLoja_(
    usuario,
    lojaRow
  );
}

function smartSlipGetHistorico(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh || sh.getLastRow() < 2) {
    return [];
  }

  const lastCol = Math.max(24, sh.getLastColumn());
  const values = sh.getRange(2, 1, sh.getLastRow() - 1, lastCol).getValues();

  const historico = [];
  const chavesJaExibidas = {};

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];
    const respostas = smartSlipParseJsonSeguro_(row[15]);

if (
  !smartSlipUsuarioPodeVerHistoricoLoja_(
    usuario,
    row
  )
) {
  continue;
}

const statusFila =
  String(
    row[13] || ""
  ).trim();

/*
  Primeiro ignora registros excluídos.

  IMPORTANTE:
  isso precisa acontecer antes de reservar
  a chave de agrupamento do Histórico.
*/
if (
  smartSlipStatusEhExcluido_(
    statusFila
  )
) {
  continue;
}

const chaveHistorico =
  smartSlipMontarChaveHistorico_(
    row,
    respostas
  );

if (
  chavesJaExibidas[
    chaveHistorico
  ]
) {
  continue;
}

chavesJaExibidas[
  chaveHistorico
] = true;

const camposReenvio =
  smartSlipMontarCamposReenvioHistorico_(
    row
  );

    const ehReenvio =
      respostas.reenvio_ativo === true ||
      String(respostas.tipo_envio || "").toUpperCase() === "REENVIO_CORRECAO" ||
      String(respostas.protocolo_reenvio_origem || "").trim() !== "";

    historico.push({
      data_registro: smartSlipFormatarDataHora(row[0]),
      protocolo: row[1] || "",
      email_usuario: row[2] || "",
      loja: row[3] || "",
      data_movimento: smartSlipFormatarDataMovimentoHistorico(row[5]),
      link_comprovante: row[11] || "",
      nome_arquivo: row[12] || "",
      houve_retirada:
      camposReenvio.houve_retirada === true,
        valor_retirada:
          Number(camposReenvio.valor_retirada || 0),

        motivo_retirada:
          camposReenvio.motivo_retirada || "",

        cupom_retirada_marketing_file_id:
          camposReenvio
            .cupom_retirada_marketing_file_id || "",

        cupom_retirada_marketing_link:
          camposReenvio
            .cupom_retirada_marketing_link || "",

        cupom_retirada_marketing_nome:
          camposReenvio
            .cupom_retirada_marketing_nome || "",
      status_fila: statusFila,
      mensagem: row[14] || "",

      protocolo_raiz: respostas.protocolo_raiz ||
        respostas.protocolo_original ||
        respostas.protocolo_reenvio_origem ||
        row[1] ||
        "",

      protocolo_original: respostas.protocolo_original ||
        respostas.protocolo_reenvio_origem ||
        "",

      protocolo_reenvio_origem: respostas.protocolo_reenvio_origem || "",
      email_usuario_original: respostas.email_usuario_original || row[2] || "",
      reenviado_por: respostas.reenviado_por || row[2] || "",
      tipo_envio: respostas.tipo_envio || (ehReenvio ? "REENVIO_CORRECAO" : "ORIGINAL"),
      eh_reenvio: ehReenvio,

excluir_permitido:
  String(
    statusFila || ""
  )
    .trim()
    .toUpperCase() !==
    "PROCESSANDO" &&
  smartSlipUsuarioPodeExcluirRegistro_(
    usuario,
    row
  ),

reenviar_permitido:
  smartSlipStatusPermiteReenvio_(
    statusFila
  ),

campos_reenvio:
  camposReenvio
    });
  }

  return historico;
}

function smartSlipParseJsonSeguro_(valor) {
  try {
    if (!valor) {
      return {};
    }

    return JSON.parse(String(valor || "{}"));
  } catch (err) {
    return {};
  }
}

function smartSlipMontarChaveHistorico_(row, respostas) {
  row = row || [];
  respostas = respostas || {};

  const protocoloLinha = String(row[1] || "").trim();

  const protocoloAgrupador = String(
    respostas.protocolo_raiz ||
    respostas.protocolo_original ||
    respostas.protocolo_reenvio_origem ||
    protocoloLinha ||
    ""
  ).trim();

  if (protocoloAgrupador) {
    return "HISTORICO_PROTOCOLO|" + protocoloAgrupador;
  }

  return "HISTORICO_SEM_PROTOCOLO|" + protocoloLinha;
}

function smartSlipMontarChaveHistorico_(row, respostas) {
  row = row || [];
  respostas = respostas || {};

  /*
    Regra:
    Todas as linhas precisam cair no mesmo padrão de chave.

    Linha original antiga:
    - normalmente não tem protocolo_raiz no JSON
    - então usa o protocolo da própria linha

    Linha reenviada:
    - usa protocolo_raiz/protocolo_original/protocolo_reenvio_origem

    O prefixo precisa ser o MESMO para os dois casos.
    Se usar PROTOCOLO| em uma e PROTOCOLO_RAIZ| em outra,
    o Histórico mostra duplicado.
  */
  const protocoloLinha = String(row[1] || "").trim();

  const protocoloAgrupador = String(
    respostas.protocolo_raiz ||
    respostas.protocolo_original ||
    respostas.protocolo_reenvio_origem ||
    protocoloLinha ||
    ""
  ).trim();

  if (protocoloAgrupador) {
    return "HISTORICO_PROTOCOLO|" + protocoloAgrupador;
  }

  return "HISTORICO_SEM_PROTOCOLO|" + protocoloLinha;
}

function smartSlipUsuarioPodeVerRegistroHistorico_(usuario, row, respostas) {
  usuario = usuario || {};
  row = row || [];
  respostas = respostas || {};

  /*
    Gestão:
    Mantém Admin e Analista Pro com visão ampla.
    Não usar loja para usuário comum.
  */
  if (usuario.is_admin === true || usuario.is_analista_pro === true) {
    return true;
  }

  const emailAtual = smartSlipNormalizarEmail_(usuario.email || "");
  const emailLinha = smartSlipNormalizarEmail_(row[2] || "");

  const emailOriginal = smartSlipNormalizarEmail_(
    respostas.email_usuario_original ||
    respostas.email_original ||
    ""
  );

  if (!emailAtual) {
    return false;
  }

  /*
    Caso normal:
    usuário vê o que ele mesmo enviou.
  */
  if (emailAtual === emailLinha) {
    return true;
  }

  /*
    Caso correção por admin:
    a linha nova terá Email Usuário = e-mail do admin,
    mas email_usuario_original = e-mail da loja que enviou originalmente.
  */
  if (emailOriginal && emailAtual === emailOriginal) {
    return true;
  }

  return false;
}

function smartSlipParseJsonSeguro_(valor) {
  try {
    if (!valor) return {};
    return JSON.parse(String(valor || "{}"));
  } catch (err) {
    return {};
  }
}

function smartSlipMontarChaveHistorico_(row, respostas) {
  row = row || [];
  respostas = respostas || {};

  /*
    Se for reenvio, agrupa pelo protocolo raiz/original.
    Assim o histórico mostra só a versão mais recente.
  */
  const protocoloRaiz = String(
    respostas.protocolo_raiz ||
    respostas.protocolo_original ||
    respostas.protocolo_reenvio_origem ||
    ""
  ).trim();

  if (protocoloRaiz) {
    return "PROTOCOLO_RAIZ|" + protocoloRaiz;
  }

  /*
    Envio normal: mantém protocolo próprio.
    Não agrupar por loja+data+valor aqui, porque isso pode esconder
    dois comprovantes legítimos da mesma loja no mesmo dia.
  */
  return "PROTOCOLO|" + String(row[1] || "").trim();
}

function smartSlipUsuarioPodeVerRegistroHistorico_(usuario, row, respostas) {
  usuario = usuario || {};
  row = row || [];
  respostas = respostas || {};

  const emailUsuarioAtual = smartSlipNormalizarEmail_(usuario.email || "");
  const emailLinha = smartSlipNormalizarEmail_(row[2] || "");
  const emailOriginal = smartSlipNormalizarEmail_(respostas.email_usuario_original || "");
  const lojaRow = smartSlipNormalizarLoja4(row[3] || "");

  if (emailUsuarioAtual && emailUsuarioAtual === emailLinha) {
    return true;
  }

  if (emailUsuarioAtual && emailOriginal && emailUsuarioAtual === emailOriginal) {
    return true;
  }

  return smartSlipUsuarioPodeVerLoja_(usuario, lojaRow);
}

function smartSlipStatusPermiteReenvio_(status) {
  status = String(status || "").trim().toUpperCase();

  return [
    "PENDENTE_INTERNO",
    "SALVO_PARCIAL",
    "ERRO_PROCESSAMENTO",
    "INELEGIVEL",
    "DIVERGENCIA",
    "PRECISA_COMPLEMENTO",
    "PENDENCIA"
  ].includes(status);
}

function smartSlipClassificarAvisoEnvioAnterior_(
  statusFila,
  mensagem
) {
  const status = String(
    statusFila || ""
  )
    .trim()
    .toUpperCase();

  const texto = String(
    mensagem || ""
  )
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");


  /*
    Processamento concluído.
    Não existe aviso.
  */
  if (status === "SALVO") {
    return {
      tipo: "PROCESSADO",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    Registro excluído.
    Uma exclusão válida encerra o alerta.
  */
  if (
    status ===
    String(
      SMARTSLIP_STATUS_EXCLUIDO ||
      "EXCLUIDO"
    )
      .trim()
      .toUpperCase()
  ) {
    return {
      tipo: "EXCLUIDO",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    O processamento ainda não terminou.

    Não caracteriza problema do comprovante
    e não oferece exclusão/regularização.
  */
  if (
    status === "RECEBIDO" ||
    status === "PROCESSANDO"
  ) {
    return {
      tipo: "EM_PROCESSAMENTO",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    ERRO_PROCESSAMENTO é gerado pelo catch
    do worker/processamento.

    Portanto pode representar:
    - indisponibilidade da IA;
    - timeout;
    - API;
    - Drive;
    - Apps Script;
    - infraestrutura;
    - outra exceção técnica.

    Não responsabilizar a loja.
  */
  if (
    status ===
    "ERRO_PROCESSAMENTO"
  ) {
    return {
      tipo: "FALHA_TECNICA",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    Há pelo menos um cenário atualmente
    classificado como PENDENTE_INTERNO que
    não é problema do comprovante:
    loja inexistente na Info_limites.

    Ele deve continuar sendo tratado como
    problema interno/cadastral.
  */
  if (
    status === "PENDENTE_INTERNO" &&
    texto.includes(
      "LOJA NAO ENCONTRADA NA INFO_LIMITES"
    )
  ) {
    return {
      tipo: "FALHA_INTERNA",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    Proteção adicional para possíveis
    mensagens técnicas que no futuro
    possam acabar classificadas como
    PENDENTE_INTERNO.

    Não exibe o modal de regularização
    nesses casos.
  */
  const sinaisFalhaTecnica = [
    "SERVICE INVOKED",
    "TIMEOUT",
    "TIMED OUT",
    "URLFETCH",
    "DRIVEAPP",
    "SPREADSHEETAPP",
    "QUOTA EXCEEDED",
    "ERRO HTTP 429",
    "ERRO HTTP 500",
    "ERRO HTTP 502",
    "ERRO HTTP 503",
    "ERRO HTTP 504",
    "GEMINI API HTTP"
  ];

  const possuiSinalTecnico =
    sinaisFalhaTecnica.some(
      function(sinal) {
        return texto.includes(
          sinal
        );
      }
    );

  if (possuiSinalTecnico) {
    return {
      tipo: "FALHA_TECNICA",
      exibir_aviso_regularizacao: false
    };
  }


  /*
    Situações corrigíveis pela loja.

    Aqui sim o SmartSlip poderá apresentar:
    - abrir comprovante;
    - excluir e reenviar;
    - continuar com novo envio.
  */
  const statusProblemaDocumento = [
    "PENDENTE_INTERNO",
    "SALVO_PARCIAL",
    "INELEGIVEL",
    "DIVERGENCIA",
    "PRECISA_COMPLEMENTO",
    "PENDENCIA"
  ];

  if (
    statusProblemaDocumento.includes(
      status
    )
  ) {
    return {
      tipo: "PROBLEMA_DOCUMENTO",
      exibir_aviso_regularizacao: true
    };
  }


  /*
    Status desconhecido:
    por segurança, não atribuímos
    o problema à loja.
  */
  return {
    tipo: "NAO_CLASSIFICADO",
    exibir_aviso_regularizacao: false
  };
}


function smartSlipGetAvisoComprovanteAnteriorLoja_(
  lojaInformada
) {
  smartSlipAssertUsuarioAutorizado_();

  const usuario =
    smartSlipGetUsuarioAtual();

  const loja =
    smartSlipNormalizarLoja4(
      lojaInformada || ""
    );

  if (!loja) {
    return {
      ok: true,
      tem_aviso: false,
      total_pendencias_nao_regularizadas: 0,
      motivo:
        "Loja não informada."
    };
  }


  /*
    Garante que o usuário não consiga
    consultar livremente outra loja.
  */
  if (
    !smartSlipUsuarioPodeVerLoja_(
      usuario,
      loja
    )
  ) {
    throw new Error(
      "Usuário sem permissão para consultar esta loja."
    );
  }


  const ss =
    SpreadsheetApp.openById(
      SMARTSLIP_DB_SPREADSHEET_ID
    );

  const sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_FILA
    );

  if (
    !sh ||
    sh.getLastRow() < 2
  ) {
    return {
      ok: true,
      tem_aviso: false,
      total_pendencias_nao_regularizadas: 0
    };
  }


  /*
    Precisamos das colunas adicionais
    de protocolo/lote, portanto usamos
    todas as colunas existentes na fila.
  */
  const lastColumn =
    sh.getLastColumn();

  const values =
    sh
      .getRange(
        2,
        1,
        sh.getLastRow() - 1,
        lastColumn
      )
      .getValues();


  /*
    Estado das pendências por protocolo raiz.

    Isso permite que o aviso continue existindo
    mesmo que a loja faça OUTROS envios normais.

    O problema só deixa de existir quando:
    - o próprio registro é excluído; ou
    - um reenvio vinculado àquele protocolo
      chega a SALVO.
  */
  const pendenciasPorRaiz = {};


  values.forEach(
    function(row, indiceArray) {

      const lojaRow =
        smartSlipNormalizarLoja4(
          row[3] || ""
        );

      if (
        lojaRow !== loja
      ) {
        return;
      }


      const protocolo =
        String(
          row[1] || ""
        ).trim();

      if (!protocolo) {
        return;
      }


      const statusFila =
        String(
          row[13] || ""
        )
          .trim()
          .toUpperCase();

      const mensagem =
        String(
          row[14] || ""
        ).trim();


      const respostas =
        smartSlipParseJsonSeguro_(
          row[15]
        );


      /*
        Cada envio/reenvio possui uma raiz.

        Em envio normal sem os metadados
        mais novos, o próprio protocolo
        vira a raiz.
      */
      const protocoloRaiz =
        String(
          respostas.protocolo_raiz ||
          respostas.protocolo_original ||
          respostas.protocolo_reenvio_origem ||
          protocolo
        ).trim();


      const classificacao =
        smartSlipClassificarAvisoEnvioAnterior_(
          statusFila,
          mensagem
        );


      /*
        SALVO resolve aquela cadeia.

        Exemplo:
        original PENDENTE_INTERNO
        ↓
        reenvio vinculado
        ↓
        SALVO

        O aviso desaparece.
      */
      if (
        classificacao.tipo ===
        "PROCESSADO"
      ) {
        delete pendenciasPorRaiz[
          protocoloRaiz
        ];

        return;
      }


      /*
        Se o registro problemático foi
        excluído pelo fluxo normal,
        a pendência deixa de existir.
      */
      if (
        classificacao.tipo ===
        "EXCLUIDO"
      ) {
        delete pendenciasPorRaiz[
          protocoloRaiz
        ];

        return;
      }


      /*
        Falha técnica não cria uma nova
        pendência documental.

        Também não apaga uma pendência
        documental anterior da mesma raiz.
      */
      if (
        classificacao.tipo ===
          "FALHA_TECNICA" ||
        classificacao.tipo ===
          "FALHA_INTERNA" ||
        classificacao.tipo ===
          "EM_PROCESSAMENTO" ||
        classificacao.tipo ===
          "NAO_CLASSIFICADO"
      ) {
        return;
      }


      if (
        classificacao
          .exibir_aviso_regularizacao !==
        true
      ) {
        return;
      }


      const jsonResultado =
        smartSlipParseJsonSeguro_(
          row[16]
        );


      /*
        O retorno salvo na coluna JSON Resultado
        normalmente possui:
        {
          status_fila,
          qtd_salvos,
          qtd_pendentes,
          resultado: {...}
        }
      */
      const resultadoIa =
        (
          jsonResultado &&
          jsonResultado.resultado &&
          typeof jsonResultado.resultado ===
            "object"
        )
          ? jsonResultado.resultado
          : {};


      const qtdComprovantes =
        Number(
          resultadoIa
            .qtd_comprovantes_detectados ||
          0
        );


      const dataEnvio =
        smartSlipFormatarDataHora(
          row[0]
        );


      const motivoUsuario =
        smartSlipMotivoAvisoFalhaUsuario_(
          statusFila,
          mensagem,
          jsonResultado
        );


      pendenciasPorRaiz[
        protocoloRaiz
      ] = {
        ordem:
          indiceArray,

        protocolo:
          protocolo,

        protocolo_raiz:
          protocoloRaiz,

        protocolo_lote:
          String(
            row[18] || ""
          ).trim(),

        protocolo_envio:
          String(
            row[19] || ""
          ).trim(),

        loja:
          loja,

        status_fila:
          statusFila,

        status_exibicao:
          smartSlipStatusAvisoFalhaExibicao_(
            statusFila
          ),

        mensagem:
          mensagem,

        motivo_usuario:
          motivoUsuario,

        data_envio:
          dataEnvio,

        file_id:
          String(
            row[10] || ""
          ).trim(),

        link_comprovante:
          String(
            row[11] || ""
          ).trim(),

        nome_arquivo:
          String(
            row[12] || ""
          ).trim(),

        qtd_comprovantes_detectados:
          qtdComprovantes,

        multiplos_comprovantes:
          qtdComprovantes > 1,

        alerta_qualidade_imagem:
          String(
            resultadoIa
              .alerta_qualidade_imagem ||
            ""
          ).trim(),

        criterio_contagem:
          String(
            resultadoIa
              .criterio_contagem ||
            ""
          ).trim(),

        campos_reenvio:
          smartSlipMontarCamposReenvioHistorico_(
            row
          )
      };
    }
  );


  const pendencias =
    Object.keys(
      pendenciasPorRaiz
    )
      .map(
        function(chave) {
          return pendenciasPorRaiz[
            chave
          ];
        }
      )
      .sort(
        function(a, b) {
          return (
            Number(
              b.ordem || 0
            ) -
            Number(
              a.ordem || 0
            )
          );
        }
      );


  if (!pendencias.length) {
    return {
      ok: true,
      tem_aviso: false,
      loja: loja,
      total_pendencias_nao_regularizadas: 0
    };
  }


  /*
    O modal mostrará inicialmente o problema
    não regularizado mais recente.

    Se existirem outros anteriores,
    mantemos a quantidade disponível.
  */
  const principal =
    pendencias[0];


  return {
    ok: true,

    tem_aviso: true,

    loja:
      loja,

    total_pendencias_nao_regularizadas:
      pendencias.length,

    problema:
      principal
  };
}


function smartSlipGetAvisoComprovanteAnteriorLojaAppJson(
  lojaInformada
) {
  try {
    const resultado =
      smartSlipGetAvisoComprovanteAnteriorLoja_(
        lojaInformada
      );

    return JSON.stringify({
      ok: true,
      payload: resultado
    });

  } catch (err) {

    return JSON.stringify({
      ok: false,

      erro: String(
        err && err.message
          ? err.message
          : err
      )
    });
  }
}

function smartSlipMontarCamposReenvioHistorico_(row) {
  row = row || [];

  let respostas = {};

  try {
    respostas = JSON.parse(String(row[15] || "{}"));
  } catch (err) {
    respostas = {};
  }

  const movimentoRaw = row[5];

  const inicioRaw =
    respostas.data_movimento_inicio ||
    respostas.data_movimento ||
    smartSlipExtrairInicioMovimentoHistorico_(movimentoRaw);

  const fimRaw =
    respostas.data_movimento_fim ||
    respostas.data_movimento ||
    smartSlipExtrairFimMovimentoHistorico_(movimentoRaw) ||
    inicioRaw;

  const houveRetirada = typeof respostas.houve_retirada === "boolean"
    ? respostas.houve_retirada
    : String(row[6] || "").trim().toLowerCase() === "sim";

  const valorRetirada = respostas.valor_retirada !== undefined
    ? Number(respostas.valor_retirada || 0)
    : Number(row[7] || 0);

  const motivoRetirada = respostas.motivo_retirada !== undefined
    ? String(respostas.motivo_retirada || "").trim()
    : String(row[8] || "").trim();

    const cupomRetiradaMarketingFileId = String(
  respostas.cupom_retirada_marketing_file_id ||
  row[29] ||
  ""
).trim();

const cupomRetiradaMarketingLink = String(
  respostas.cupom_retirada_marketing_link ||
  row[30] ||
  ""
).trim();

const cupomRetiradaMarketingNome = String(
  respostas.cupom_retirada_marketing_nome ||
  row[31] ||
  ""
).trim();

  return {
    loja: smartSlipNormalizarLoja4(respostas.loja || row[3] || ""),
    data_movimento_inicio_input: smartSlipConverterDataParaInputHistorico_(inicioRaw),
    data_movimento_fim_input: smartSlipConverterDataParaInputHistorico_(fimRaw),

    houve_retirada: houveRetirada,
    valor_retirada: valorRetirada,
    motivo_retirada: houveRetirada
      ? motivoRetirada
      : "Não houve retirada",
    
    cupom_retirada_marketing_file_id:
    cupomRetiradaMarketingFileId,

  cupom_retirada_marketing_link:
    cupomRetiradaMarketingLink,

  cupom_retirada_marketing_nome:
    cupomRetiradaMarketingNome,

    // Novo: valores informados no envio original.
    // Para envios antigos que ainda não tinham essa estrutura, ficará null.
    valores_diarios_movimento: respostas.valores_diarios_movimento || null
  };
}

function smartSlipExtrairInicioMovimentoHistorico_(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    return valor;
  }

  const txt = String(valor || "").trim();

  if (txt.indexOf(" a ") > -1) {
    return txt.split(" a ")[0].trim();
  }

  return txt;
}

function smartSlipExtrairFimMovimentoHistorico_(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    return valor;
  }

  const txt = String(valor || "").trim();

  if (txt.indexOf(" a ") > -1) {
    return txt.split(" a ")[1].trim();
  }

  return txt;
}

function smartSlipConverterDataParaInputHistorico_(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    return Utilities.formatDate(valor, tz, "yyyy-MM-dd");
  }

  const txt = String(valor || "").trim();

  let m = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (m) {
    return m[3] + "-" + m[2] + "-" + m[1];
  }

  m = txt.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    return m[1] + "-" + m[2] + "-" + m[3];
  }

  return "";
}

/* =========================================================
   SMARTSLIP - EXCLUSÃO LÓGICA DE COMPROVANTES
   ========================================================= */

function smartSlipStatusEhExcluido_(status) {
  return String(status || "")
    .trim()
    .toUpperCase() === SMARTSLIP_STATUS_EXCLUIDO;
}


function smartSlipUsuarioPodeExcluirRegistro_(
  usuario,
  row
) {
  usuario =
    usuario ||
    smartSlipGetUsuarioAtual();

  row = row || [];

  /*
    Administrador e Analista Pro
    podem excluir qualquer comprovante.
  */
  if (
    usuario.is_admin === true ||
    usuario.is_analista_pro === true
  ) {
    return true;
  }

  const emailAtual =
    smartSlipNormalizarEmail_(
      usuario.email || ""
    );

  /*
    IMPORTANTE:
    usamos SOMENTE Email Usuário da linha.

    Não usamos:
    - loja
    - regional
    - email_usuario_original
    - smartSlipUsuarioPodeVerRegistroHistorico_

    Isso impede que outro usuário da mesma loja
    exclua um comprovante que não foi enviado por ele.
  */
  const emailAutorEnvio =
    smartSlipNormalizarEmail_(
      row[2] || ""
    );

  return (
    !!emailAtual &&
    emailAtual === emailAutorEnvio
  );
}


function smartSlipGerarProtocoloExclusao_() {
  const timezone =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  const agora =
    new Date();

  const dataHora =
    Utilities.formatDate(
      agora,
      timezone,
      "yyyyMMdd-HHmmss"
    );

  const sufixo =
    Utilities
      .getUuid()
      .replace(/-/g, "")
      .substring(0, 6)
      .toUpperCase();

  return (
    "SS-EXC-" +
    dataHora +
    "-" +
    sufixo
  );
}


function smartSlipGarantirAbaLogExclusoes_(
  ss
) {
  ss =
    ss ||
    SpreadsheetApp.openById(
      SMARTSLIP_DB_SPREADSHEET_ID
    );

  let sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_LOG_EXCLUSOES
    );

  if (!sh) {
    sh =
      ss.insertSheet(
        SMARTSLIP_ABA_LOG_EXCLUSOES
      );
  }

  const headers = [
    "Data Exclusão",
    "Protocolo Exclusão",
    "Protocolo Comprovante",
    "Protocolo Lote",
    "Protocolo Envio",
    "Email Autor Envio",
    "Email Responsável Exclusão",
    "Perfil Responsável",
    "Loja",
    "Status Anterior",
    "Registros BASE Afetados",
    "File ID",
    "Link Comprovante",
    "Nome Arquivo",
    "Origem",
    "JSON Auditoria"
  ];

  if (
    sh.getMaxColumns() <
    headers.length
  ) {
    sh.insertColumnsAfter(
      sh.getMaxColumns(),
      headers.length -
        sh.getMaxColumns()
    );
  }

  sh.getRange(
    1,
    1,
    1,
    headers.length
  ).setValues([headers]);

  sh.setFrozenRows(1);

  return sh;
}


function smartSlipMarcarBaseComprovanteExcluido_(
  ss,
  protocolo,
  auditoria
) {
  const sh =
    ss.getSheetByName(
      SMARTSLIP_ABA_DESTINO
    );

  if (
    !sh ||
    sh.getLastRow() < 2
  ) {
    return 0;
  }

  const values =
    sh.getDataRange()
      .getValues();

  const headers =
    values[0].map(
      function(h) {
        return String(
          h || ""
        ).trim();
      }
    );

  const idxProtocolo =
    smartSlipEncontrarIndiceHeader_(
      headers,
      [
        "Protocolo"
      ]
    );

  const idxStatus =
    smartSlipEncontrarIndiceHeader_(
      headers,
      [
        "Status Processamento"
      ]
    );

  const idxJson =
    smartSlipEncontrarIndiceHeader_(
      headers,
      [
        "JSON Original"
      ]
    );

  if (
    idxProtocolo < 0 ||
    idxStatus < 0
  ) {
    throw new Error(
      "BASE_SMARTSLIP sem as colunas necessárias para exclusão."
    );
  }

  let quantidade = 0;

  for (
    let i = 1;
    i < values.length;
    i++
  ) {
    const protocoloLinha =
      String(
        values[i][idxProtocolo] ||
        ""
      ).trim();

    if (
      protocoloLinha !==
      protocolo
    ) {
      continue;
    }

    /*
      Não apaga a linha.
      Apenas marca como excluída.
    */
    sh.getRange(
      i + 1,
      idxStatus + 1
    ).setValue(
      SMARTSLIP_STATUS_EXCLUIDO
    );

    /*
      Registra também a exclusão
      dentro do JSON original.
    */
    if (idxJson >= 0) {
      const jsonOriginal =
        smartSlipParseJsonSeguro_(
          values[i][idxJson]
        );

      jsonOriginal.smartslip_exclusao =
        auditoria;

      sh.getRange(
        i + 1,
        idxJson + 1
      ).setValue(
        JSON.stringify(
          jsonOriginal
        )
      );
    }

    quantidade++;
  }

  return quantidade;
}


function smartSlipRegistrarLogExclusao_(
  shLog,
  dados
) {
  dados = dados || {};

  shLog.appendRow([
    new Date(),

    dados.protocolo_exclusao ||
      "",

    dados.protocolo ||
      "",

    dados.protocolo_lote ||
      "",

    dados.protocolo_envio ||
      "",

    dados.email_autor_envio ||
      "",

    dados.excluido_por ||
      "",

    dados.perfil_responsavel ||
      "",

    dados.loja ||
      "",

    dados.status_anterior ||
      "",

    Number(
      dados.registros_base_afetados ||
      0
    ),

    dados.file_id ||
      "",

    dados.link_comprovante ||
      "",

    dados.nome_arquivo ||
      "",

    "HISTORICO",

    JSON.stringify(
      dados.auditoria ||
      {}
    )
  ]);
}


function smartSlipExcluirComprovante_(
  protocolo
) {
  smartSlipAssertUsuarioAutorizado_();

  protocolo =
    String(
      protocolo || ""
    ).trim();

  if (!protocolo) {
    throw new Error(
      "Protocolo do comprovante não informado."
    );
  }

  const usuario =
    smartSlipGetUsuarioAtual();

  const emailAtual =
    smartSlipNormalizarEmail_(
      usuario.email ||
      Session
        .getActiveUser()
        .getEmail() ||
      ""
    );

  const lock =
    LockService.getScriptLock();

  /*
    O mesmo lock usado pela fila evita
    que um comprovante em RECEBIDO seja
    reservado pelo processador enquanto
    a exclusão está sendo concluída.
  */
  if (
    !lock.tryLock(30000)
  ) {
    throw new Error(
      "Não foi possível concluir a exclusão agora. Tente novamente em alguns segundos."
    );
  }

  try {
    const ss =
      SpreadsheetApp.openById(
        SMARTSLIP_DB_SPREADSHEET_ID
      );

    const shFila =
      ss.getSheetByName(
        SMARTSLIP_ABA_FILA
      );

    if (
      !shFila ||
      shFila.getLastRow() < 2
    ) {
      throw new Error(
        "Fila de comprovantes não encontrada."
      );
    }

    const encontrado =
      smartSlipBuscarLinhaFilaPorProtocolo_(
        shFila,
        protocolo
      );

    if (!encontrado) {
      throw new Error(
        "Comprovante não encontrado para o protocolo informado."
      );
    }

    const row =
      encontrado.row;

    const rowIndex =
      encontrado.row_index;

    const statusAnterior =
      String(
        row[13] || ""
      )
        .trim()
        .toUpperCase();

    if (
      smartSlipStatusEhExcluido_(
        statusAnterior
      )
    ) {
      throw new Error(
        "Este comprovante já foi excluído."
      );
    }

    /*
      Se o worker já reservou a linha,
      esperamos ele terminar.

      Isso evita:
      EXCLUIDO -> worker termina -> SALVO
    */
    if (
      statusAnterior ===
      "PROCESSANDO"
    ) {
      throw new Error(
        "Este comprovante está sendo processado neste momento. Aguarde a conclusão do processamento e tente excluir novamente."
      );
    }

    if (
      !smartSlipUsuarioPodeExcluirRegistro_(
        usuario,
        row
      )
    ) {
      throw new Error(
        "Você não possui permissão para excluir este comprovante. Usuários comuns podem excluir somente comprovantes enviados pelo próprio usuário."
      );
    }

    /*
      Garante a existência do log
      antes de alterar os dados.
    */
    const shLog =
      smartSlipGarantirAbaLogExclusoes_(
        ss
      );

    const protocoloExclusao =
      smartSlipGerarProtocoloExclusao_();

    const timezone =
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo";

    const agora =
      new Date();

    const dataExclusao =
      Utilities.formatDate(
        agora,
        timezone,
        "dd/MM/yyyy HH:mm:ss"
      );

    const respostas =
      smartSlipParseJsonSeguro_(
        row[15]
      );

    const auditoria = {
      excluido: true,

      protocolo_exclusao:
        protocoloExclusao,

      protocolo_comprovante:
        protocolo,

      excluido_em:
        agora.toISOString(),

      excluido_em_formatado:
        dataExclusao,

      excluido_por:
        emailAtual,

      perfil_responsavel:
        usuario.perfil ||
        "",

      email_autor_envio:
        smartSlipNormalizarEmail_(
          row[2] || ""
        ),

      status_anterior:
        statusAnterior
    };

    respostas.smartslip_exclusao =
      auditoria;

    /*
      SMARTSLIP_FILA:
      N = Status Fila
      O = Mensagem
      P = JSON Respostas
    */
    shFila
      .getRange(
        rowIndex,
        14,
        1,
        3
      )
      .setValues([
        [
          SMARTSLIP_STATUS_EXCLUIDO,

          (
            "Comprovante excluído em " +
            dataExclusao +
            ". Protocolo de exclusão: " +
            protocoloExclusao
          ),

          JSON.stringify(
            respostas
          )
        ]
      ]);

    /*
      Pode existir mais de um comprovante
      físico C001, C002, C003 etc. para
      o mesmo protocolo.

      Todos são marcados como excluídos.
    */
    const registrosBaseAfetados =
      smartSlipMarcarBaseComprovanteExcluido_(
        ss,
        protocolo,
        auditoria
      );

    smartSlipRegistrarLogExclusao_(
      shLog,
      {
        protocolo_exclusao:
          protocoloExclusao,

        protocolo:
          protocolo,

        protocolo_lote:
          row[18] || "",

        protocolo_envio:
          row[19] || "",

        email_autor_envio:
          row[2] || "",

        excluido_por:
          emailAtual,

        perfil_responsavel:
          usuario.perfil || "",

        loja:
          smartSlipNormalizarLoja4(
            row[3] || ""
          ),

        status_anterior:
          statusAnterior,

        registros_base_afetados:
          registrosBaseAfetados,

        file_id:
          row[10] || "",

        link_comprovante:
          row[11] || "",

        nome_arquivo:
          row[12] || "",

        auditoria:
          auditoria
      }
    );

    SpreadsheetApp.flush();

    return {
      ok: true,

      protocolo_comprovante:
        protocolo,

      protocolo_exclusao:
        protocoloExclusao,

      excluido_em:
        dataExclusao,

      excluido_por:
        emailAtual,

      registros_base_afetados:
        registrosBaseAfetados
    };

  } finally {
    try {
      lock.releaseLock();
    } catch (e) {}
  }
}


function smartSlipExcluirComprovanteAppJson(
  protocolo
) {
  try {
    smartSlipAssertUsuarioAutorizado_();

    const resultado =
      smartSlipExcluirComprovante_(
        protocolo
      );

    return JSON.stringify({
      ok: true,
      payload: resultado
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(
        err && err.message
          ? err.message
          : err
      )
    });
  }
}

function smartSlipGetResumoStatus(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

  if (!sh || sh.getLastRow() < 2) {
    return [];
  }

  const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();
  const mapa = {};
  let total = 0;

  for (let i = 0; i < values.length; i++) {
    const row = values[i];

  const lojaRow = smartSlipNormalizarLoja4(row[3] || "");

  if (!smartSlipUsuarioPodeVerLoja_(usuario, lojaRow)) {
    continue;
  }

    const status = String(row[13] || "").trim() || "SEM_STATUS";

    if (
      smartSlipStatusEhExcluido_(
        status
      )
    ) {
      continue;
    }

    mapa[status] = (mapa[status] || 0) + 1;
    total++;
  }

  return Object.keys(mapa).sort().map(function(status) {
    const quantidade = mapa[status] || 0;

    return {
      status: status,
      quantidade: quantidade,
      percentual: total > 0
        ? Number(((quantidade / total) * 100).toFixed(2))
        : 0
    };
  });
}

function smartSlipGetLojasAtencaoOperacional(usuario) {
  try {
    usuario = usuario || smartSlipGetUsuarioAtual();

    const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
    const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

    if (!sh || sh.getLastRow() < 2) {
      return [];
    }

    const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();

    const statusCriticos = {
      PENDENTE_INTERNO: true,
      ERRO_PROCESSAMENTO: true,
      DIVERGENCIA: true,
      SALVO_PARCIAL: true,
      INELEGIVEL: true,
      PRECISA_COMPLEMENTO: true,
      PENDENCIA: true
    };

    const mapa = {};

    for (let i = 0; i < values.length; i++) {
      const row = values[i];

      const loja = smartSlipNormalizarLoja4(row[3] || "");
      const status = String(row[13] || "").trim().toUpperCase();

      if (!loja) {
        continue;
      }

      /*
        Regra correta de escopo:
        - Admin e Analista Pro veem todas as lojas.
        - Gerentes_Reg veem somente lojas em que o e-mail regional está associado na aba Base.
        - Usuário comum vê somente a loja padrão dele.
      */
      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja)) {
        continue;
      }

      if (!statusCriticos[status]) {
        continue;
      }

      if (!mapa[loja]) {
        mapa[loja] = {
          loja: loja,
          total: 0,
          status: {}
        };
      }

      mapa[loja].total++;
      mapa[loja].status[status] = (mapa[loja].status[status] || 0) + 1;
    }

    return Object.keys(mapa)
      .map(function(loja) {
        return mapa[loja];
      })
      .sort(function(a, b) {
        return Number(b.total || 0) - Number(a.total || 0);
      })
      .slice(0, 7);

  } catch (err) {
    Logger.log("Erro smartSlipGetLojasAtencaoOperacional: " + String(err && err.message ? err.message : err));
    return [];
  }
}

function smartSlipFormatarDataHora(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    return Utilities.formatDate(valor, tz, "dd/MM/yyyy HH:mm:ss");
  }

  return String(valor);
}

function smartSlipFormatarDataMovimentoHistorico(valor) {
  if (!valor) return "";

  if (Object.prototype.toString.call(valor) === "[object Date]") {
    const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    return Utilities.formatDate(valor, tz, "dd/MM/yyyy");
  }

  const txt = String(valor).trim();

  if (!txt) return "";

  if (txt.indexOf(" a ") > -1) {
    return txt
      .split(" a ")
      .map(function(parte) {
        return smartSlipFormatarDataMovimentoItem(parte);
      })
      .join(" a ");
  }

  return smartSlipFormatarDataMovimentoItem(txt);
}

function smartSlipFormatarDataMovimentoItem(valor) {
  const txt = String(valor || "").trim();

  if (!txt) return "";

  if (/^\d{2}\/\d{2}\/\d{4}$/.test(txt)) {
    return txt;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(txt) || /^\d{4}-\d{2}-\d{2}T/.test(txt)) {
    const d = new Date(txt);

    if (!isNaN(d.getTime())) {
      const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
      return Utilities.formatDate(d, tz, "dd/MM/yyyy");
    }
  }

  return txt;
}

function smartSlipGetResumoMensal(usuario) {
  try {
    usuario = usuario || smartSlipGetUsuarioAtual();

    const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
    const shBase = ss.getSheetByName(SMARTSLIP_ABA_DESTINO);
    const shFila = ss.getSheetByName(SMARTSLIP_ABA_FILA);

    if (!shBase || shBase.getLastRow() < 2 || !shFila || shFila.getLastRow() < 2) {
      return [];
    }

    const filaValues = shFila.getRange(2, 1, shFila.getLastRow() - 1, 18).getValues();
    const protocolosPermitidos = {};

    filaValues.forEach(function(row) {
              const statusFila =
          String(
            row[13] || ""
          ).trim();

        if (
          smartSlipStatusEhExcluido_(
            statusFila
          )
        ) {
          return;
        }
      const protocolo = String(row[1] || "").trim();
      const lojaFila = smartSlipNormalizarLoja4(row[3] || "");

      if (!protocolo) return;

      if (smartSlipUsuarioPodeVerLoja_(usuario, lojaFila)) {
        protocolosPermitidos[protocolo] = true;
      }
    });

    const baseValues = shBase.getDataRange().getValues();

    if (baseValues.length < 2) {
      return [];
    }

    const headers = baseValues[0].map(function(h) {
      return String(h || "").trim();
    });

    const idxDataRegistro = smartSlipEncontrarIndiceHeader_(headers, ["Data Registro"]);
    const idxProtocolo = smartSlipEncontrarIndiceHeader_(headers, ["Protocolo"]);
    const idxLoja = smartSlipEncontrarIndiceHeader_(headers, ["Loja"]);
    const idxValor = smartSlipEncontrarIndiceHeader_(headers, ["Valor Depósito"]);

    if (idxDataRegistro < 0 || idxProtocolo < 0 || idxValor < 0) {
      Logger.log("Resumo mensal: colunas necessárias não encontradas.");
      Logger.log(JSON.stringify(headers));
      return [];
    }

    const mapa = {};

    for (let i = 1; i < baseValues.length; i++) {
      const row = baseValues[i];

      const protocolo = String(row[idxProtocolo] || "").trim();

      if (!protocolosPermitidos[protocolo]) {
        continue;
      }

      const loja = idxLoja >= 0 ? smartSlipNormalizarLoja4(row[idxLoja] || "") : "";

      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja)) {
        continue;
      }

      const mes = smartSlipMesAno(row[idxDataRegistro]);

      const valor = smartSlipNumero(row[idxValor]);

      const chave = mes + "|" + loja;

      if (!mapa[chave]) {
        mapa[chave] = {
          mes: mes,
          loja: loja,
          quantidade: 0,
          valor_total: 0
        };
      }

      mapa[chave].quantidade++;
      mapa[chave].valor_total += valor;
      }

    return Object.keys(mapa)
      .sort()
      .map(function(k) {
        return mapa[k];
      });

  } catch (err) {
    Logger.log("Erro smartSlipGetResumoMensal: " + String(err && err.message ? err.message : err));
    return [];
  }
}

function smartSlipGetResumoDiario(usuario) {
  try {
    usuario = usuario || smartSlipGetUsuarioAtual();

    const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
    const shBase = ss.getSheetByName(SMARTSLIP_ABA_DESTINO);
    const shFila = ss.getSheetByName(SMARTSLIP_ABA_FILA);

    if (!shBase || shBase.getLastRow() < 2 || !shFila || shFila.getLastRow() < 2) {
      return [];
    }

    const filaValues = shFila.getRange(2, 1, shFila.getLastRow() - 1, 18).getValues();
    const protocolosPermitidos = {};

    filaValues.forEach(function(row) {
            const statusFila =
        String(
          row[13] || ""
        ).trim();

      if (
        smartSlipStatusEhExcluido_(
          statusFila
        )
      ) {
        return;
      }
      const protocolo = String(row[1] || "").trim();
      const lojaFila = smartSlipNormalizarLoja4(row[3] || "");

      if (!protocolo || !lojaFila) {
        return;
      }

      if (smartSlipUsuarioPodeVerLoja_(usuario, lojaFila)) {
        protocolosPermitidos[protocolo] = true;
      }
    });

    const baseValues = shBase.getDataRange().getValues();

    if (baseValues.length < 2) {
      return [];
    }

    const headers = baseValues[0].map(function(h) {
      return String(h || "").trim();
    });

    const idxDataRegistro = smartSlipEncontrarIndiceHeader_(headers, ["Data Registro"]);
    const idxProtocolo = smartSlipEncontrarIndiceHeader_(headers, ["Protocolo"]);
    const idxValor = smartSlipEncontrarIndiceHeader_(headers, ["Valor Depósito", "Valor Deposito"]);
    const idxLoja = smartSlipEncontrarIndiceHeader_(headers, ["Loja"]);

    if (idxDataRegistro < 0 || idxProtocolo < 0 || idxValor < 0 || idxLoja < 0) {
      Logger.log("Resumo diário: colunas necessárias não encontradas.");
      Logger.log(JSON.stringify(headers));
      return [];
    }

    const mapa = {};

    for (let i = 1; i < baseValues.length; i++) {
      const row = baseValues[i];

      const protocolo = String(row[idxProtocolo] || "").trim();
      const loja = smartSlipNormalizarLoja4(row[idxLoja] || "");

      if (!protocolo || !protocolosPermitidos[protocolo]) {
        continue;
      }

      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja)) {
        continue;
      }

      const dia = smartSlipDiaIso(row[idxDataRegistro]);
      const valor = smartSlipNumero(row[idxValor]);

      if (!dia) {
        continue;
      }

      const chave = dia + "|" + loja;

      if (!mapa[chave]) {
        mapa[chave] = {
          dia: dia,
          loja: loja,
          quantidade: 0,
          valor_total: 0
        };
      }

      mapa[chave].quantidade++;
      mapa[chave].valor_total += valor;
    }

    return Object.keys(mapa)
      .sort()
      .map(function(k) {
        return mapa[k];
      });

  } catch (err) {
    Logger.log("Erro smartSlipGetResumoDiario: " + String(err && err.message ? err.message : err));
    return [];
  }
}

function smartSlipGetStoreSignupMensal(usuario) {
  try {
    usuario = usuario || smartSlipGetUsuarioAtual();

    const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
    const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

    if (!sh || sh.getLastRow() < 2) {
      return [];
    }

    const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();
    const mapa = {};

    for (let i = 0; i < values.length; i++) {
      const row = values[i];

      const dataRegistro = row[0];
      const loja = smartSlipNormalizarLoja4(row[3] || "");

      if (!loja) {
        continue;
      }

      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja)) {
        continue;
      }

      const mes = smartSlipMesAno(dataRegistro);

      if (!mes) {
        continue;
      }

      const chave = mes + "|" + loja;

      if (!mapa[chave]) {
        mapa[chave] = {
          mes: mes,
          loja: loja,
          quantidade_envios: 0,
          lojas_mapa: {}
        };
      }

      mapa[chave].quantidade_envios++;
      mapa[chave].lojas_mapa[loja] = true;
    }

    return Object.keys(mapa)
      .sort()
      .map(function(k) {
        return {
          mes: mapa[k].mes,
          loja: mapa[k].loja,
          quantidade_envios: mapa[k].quantidade_envios || 0,
          lojas_unicas: Object.keys(mapa[k].lojas_mapa || {}).length
        };
      });

  } catch (err) {
    Logger.log("Erro smartSlipGetStoreSignupMensal: " + String(err && err.message ? err.message : err));
    return [];
  }
}

function smartSlipGetStoreSignupDiario(usuario) {
  try {
    usuario = usuario || smartSlipGetUsuarioAtual();

    const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
    const sh = ss.getSheetByName(SMARTSLIP_ABA_FILA);

    if (!sh || sh.getLastRow() < 2) {
      return [];
    }

    const values = sh.getRange(2, 1, sh.getLastRow() - 1, 18).getValues();
    const mapa = {};

    for (let i = 0; i < values.length; i++) {
      const row = values[i];

      const dataRegistro = row[0];
      const loja = smartSlipNormalizarLoja4(row[3] || "");

      if (!loja) {
        continue;
      }

      if (!smartSlipUsuarioPodeVerLoja_(usuario, loja)) {
        continue;
      }

      const dia = smartSlipDiaIso(dataRegistro);

      if (!dia) {
        continue;
      }

      const chave = dia + "|" + loja;

      if (!mapa[chave]) {
        mapa[chave] = {
          dia: dia,
          loja: loja,
          quantidade_envios: 0,
          lojas_mapa: {}
        };
      }

      mapa[chave].quantidade_envios++;
      mapa[chave].lojas_mapa[loja] = true;
    }

    return Object.keys(mapa)
      .sort()
      .map(function(k) {
        return {
          dia: mapa[k].dia,
          loja: mapa[k].loja,
          quantidade_envios: mapa[k].quantidade_envios || 0,
          lojas_unicas: Object.keys(mapa[k].lojas_mapa || {}).length
        };
      });

  } catch (err) {
    Logger.log("Erro smartSlipGetStoreSignupDiario: " + String(err && err.message ? err.message : err));
    return [];
  }
}

function smartSlipDiaIso(valor) {
  let d = valor;

  if (Object.prototype.toString.call(d) !== "[object Date]") {
    d = new Date(valor);
  }

  if (isNaN(d.getTime())) {
    return "";
  }

  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  return Utilities.formatDate(d, tz, "yyyy-MM-dd");
}

function smartSlipMesAno(valor) {
  let d = valor;

  if (Object.prototype.toString.call(d) !== "[object Date]") {
    d = new Date(valor);
  }

  if (isNaN(d.getTime())) {
    return "Sem data";
  }

  const tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  return Utilities.formatDate(d, tz, "yyyy-MM");
}

function smartSlipNumero(valor) {
  if (typeof valor === "number") return valor;

  const txt = String(valor || "")
    .replace(/[R$\s.]/g, "")
    .replace(",", ".");

  const n = Number(txt);

  return isNaN(n) ? 0 : n;
}

function smartSlipGarantirAbaUsuarios() {
  const ss = SpreadsheetApp.openById(SMARTSLIP_DB_SPREADSHEET_ID);
  let sh = ss.getSheetByName(SMARTSLIP_ABA_USUARIOS);

  if (!sh) {
    sh = ss.insertSheet(SMARTSLIP_ABA_USUARIOS);
  }

  const headers = [
    "Email",
    "Loja Padrao",
    "Empresa",
    "Data Atualizacao",
    "Ativo",
    "Tipo Deposito",
    "Tipo Deposito Origem",
    "Time",
    "Gerente Regional",
    "Email Regional"
  ];

  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, headers.length).setValues([headers]);
    sh.setFrozenRows(1);
    return sh;
  }

  const atuais = sh.getRange(1, 1, 1, Math.max(headers.length, sh.getLastColumn())).getValues()[0];

  headers.forEach(function(nome, idx) {
    if (!String(atuais[idx] || "").trim()) {
      sh.getRange(1, idx + 1).setValue(nome);
    }
  });

  return sh;
}

function smartSlipNormalizarTextoAcesso_(valor) {
  return String(valor || "")
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function smartSlipValorAtivoEhSim_(valor) {
  const txt = smartSlipNormalizarTextoAcesso_(valor);

  return [
    "SIM",
    "S",
    "TRUE",
    "1",
    "ATIVO",
    "YES",
    "Y"
  ].includes(txt);
}

function smartSlipEmailCorporativoValido_(email) {
  email = String(email || "").trim().toLowerCase();

  if (!email || email.indexOf("@") < 0) {
    return false;
  }

  const dominio = email.split("@").pop();

  return SMARTSLIP_DOMINIOS_CORPORATIVOS.indexOf(dominio) >= 0;
}

function smartSlipVerificarAcessoSmartSlip_(email) {
  email = String(email || "").trim().toLowerCase();

  if (!email) {
    return {
      autorizado: false,
      email: "",
      motivo: "Não foi possível identificar o e-mail do usuário."
    };
  }

  if (!smartSlipEmailCorporativoValido_(email)) {
    return {
      autorizado: false,
      email: email,
      motivo: "Acesso permitido apenas para e-mail corporativo autorizado."
    };
  }

  const sh = smartSlipGarantirAbaUsuarios();
  const lastRow = sh.getLastRow();

  if (lastRow < 2) {
    return {
      autorizado: false,
      email: email,
      motivo: "Usuário não cadastrado na whitelist SMARTSLIP_USUARIOS."
    };
  }

  const values = sh.getRange(2, 1, lastRow - 1, 5).getValues();

  for (let i = 0; i < values.length; i++) {
    const row = values[i];

    const emailRow = String(row[0] || "").trim().toLowerCase();

    if (emailRow !== email) {
      continue;
    }

    const ativo = smartSlipValorAtivoEhSim_(row[4]);

    if (!ativo) {
      return {
        autorizado: false,
        email: email,
        motivo: "Usuário cadastrado, porém inativo na SMARTSLIP_USUARIOS."
      };
    }

    return {
      autorizado: true,
      email: email,
      linha: i + 2,
      loja_padrao: String(row[1] || "").trim(),
      empresa_padrao: String(row[2] || "").trim()
    };
  }

  return {
    autorizado: false,
    email: email,
    motivo: "Usuário não autorizado para acessar o SmartSlip."
  };
}

function smartSlipAssertUsuarioAutorizado_() {
  const email = String(Session.getActiveUser().getEmail() || "").trim().toLowerCase();
  const acesso = smartSlipVerificarAcessoSmartSlip_(email);

  if (!acesso.autorizado) {
    throw new Error("ACESSO_NAO_AUTORIZADO: " + acesso.motivo);
  }

  return acesso;
}

function smartSlipValidarAcessoSmartSlipAppJson() {
  try {
    const email = String(Session.getActiveUser().getEmail() || "").trim().toLowerCase();
    const acesso = smartSlipVerificarAcessoSmartSlip_(email);

    if (!acesso.autorizado) {
      return JSON.stringify({
        ok: false,
        codigo: "ACESSO_NAO_AUTORIZADO",
        erro: acesso.motivo,
        email: email
      });
    }

    return JSON.stringify({
      ok: true,
      payload: acesso
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      codigo: "ERRO_VALIDACAO_ACESSO",
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipObterPreferenciasUsuario(email) {
  email = String(email || "").trim().toLowerCase();

  if (!email) {
    return {
      loja_padrao: "",
      empresa_padrao: "",
      tipo_deposito: "",
      time: "",
      gerente_regional: "",
      email_regional: "",
      ativo: false
    };
  }

  const sh = smartSlipGarantirAbaUsuarios();
  const lastRow = sh.getLastRow();

  if (lastRow < 2) {
    return {
      loja_padrao: "",
      empresa_padrao: "",
      tipo_deposito: "",
      time: "",
      gerente_regional: "",
      email_regional: "",
      ativo: false
    };
  }

  const values = sh.getRange(2, 1, lastRow - 1, 10).getValues();

  for (let i = values.length - 1; i >= 0; i--) {
    const row = values[i];
    const emailRow = String(row[0] || "").trim().toLowerCase();

    if (emailRow === email) {
      return {
        loja_padrao: String(row[1] || "").trim(),
        empresa_padrao: String(row[2] || "").trim(),
        ativo: smartSlipValorAtivoEhSim_(row[4]),
        tipo_deposito: smartSlipNormalizarTipoDeposito_(row[5]) || String(row[5] || "").trim(),
        tipo_deposito_origem: String(row[6] || "").trim(),
        time: String(row[7] || "").trim(),
        gerente_regional: String(row[8] || "").trim(),
        email_regional: String(row[9] || "").trim()
      };
    }
  }

  return {
    loja_padrao: "",
    empresa_padrao: "",
    tipo_deposito: "",
    time: "",
    gerente_regional: "",
    email_regional: "",
    ativo: false
  };
}

function smartSlipSalvarPreferenciasUsuario(lojaInformada, tipoDepositoInformado) {
  const acessoSmartSlip = smartSlipAssertUsuarioAutorizado_();

  const email = String(acessoSmartSlip.email || Session.getActiveUser().getEmail() || "")
    .trim()
    .toLowerCase();

  if (!email) {
    throw new Error("Não foi possível identificar o e-mail do usuário.");
  }

  const infoLoja = smartSlipConsultarInfoLoja_(lojaInformada);

  if (!infoLoja.ok) {
    throw new Error(infoLoja.erro || "Loja não encontrada na Info_limites.");
  }

  const usuarioAtual = smartSlipGetUsuarioAtual();

  const empresaPermitida = usuarioAtual.is_admin
    ? ""
    : smartSlipObterEmpresaPermitidaPorEmail(usuarioAtual.email);

  if (empresaPermitida && infoLoja.empresa !== empresaPermitida) {
    throw new Error(
      "Essa loja pertence à empresa " +
      infoLoja.empresa +
      ", mas seu perfil permite apenas lojas da empresa " +
      empresaPermitida +
      "."
    );
  }

  const loja4 = infoLoja.loja_normalizada;
  const empresa = infoLoja.empresa;

  const dadosBase = smartSlipConsultarDadosOperacionaisLoja_(loja4);

  const tipoDepositoBase = dadosBase.ok
    ? smartSlipNormalizarTipoDeposito_(dadosBase.tipo_deposito)
    : "";

  const tipoDepositoSelecionado = smartSlipNormalizarTipoDeposito_(tipoDepositoInformado);

  const tipoDepositoFinal = tipoDepositoSelecionado || tipoDepositoBase;

  if (!tipoDepositoFinal) {
    throw new Error("Tipo de depósito não identificado. Selecione Boleto, Carro Forte ou Dep. Bancário.");
  }

  const origemTipoDeposito =
    tipoDepositoBase && tipoDepositoFinal === tipoDepositoBase
      ? "BASE"
      : "MANUAL";

  const time = dadosBase.ok ? String(dadosBase.time || "").trim() : "";
  const gerenteRegional = dadosBase.ok ? String(dadosBase.gerente_regional || "").trim() : "";
  const emailRegional = dadosBase.ok ? String(dadosBase.email_regional || "").trim() : "";

  const sh = smartSlipGarantirAbaUsuarios();
  const lastRow = sh.getLastRow();

  if (lastRow >= 2) {
    const values = sh.getRange(2, 1, lastRow - 1, 10).getValues();

    for (let i = 0; i < values.length; i++) {
      const rowIndex = i + 2;
      const emailRow = String(values[i][0] || "").trim().toLowerCase();

      if (emailRow === email) {
        sh.getRange(rowIndex, 2).setValue(loja4);
        sh.getRange(rowIndex, 3).setValue(empresa);
        sh.getRange(rowIndex, 4).setValue(new Date());

        // Não altera coluna E = Ativo.
        sh.getRange(rowIndex, 6, 1, 5).setValues([[
          tipoDepositoFinal,
          origemTipoDeposito,
          time,
          gerenteRegional,
          emailRegional
        ]]);

        return {
          ok: true,
          email: email,
          loja_padrao: loja4,
          empresa_padrao: empresa,
          tipo_deposito: tipoDepositoFinal,
          tipo_deposito_origem: origemTipoDeposito,
          time: time,
          gerente_regional: gerenteRegional,
          email_regional: emailRegional
        };
      }
    }
  }

  sh.appendRow([
    email,
    loja4,
    empresa,
    new Date(),
    "Sim",
    tipoDepositoFinal,
    origemTipoDeposito,
    time,
    gerenteRegional,
    emailRegional
  ]);

  return {
    ok: true,
    email: email,
    loja_padrao: loja4,
    empresa_padrao: empresa,
    tipo_deposito: tipoDepositoFinal,
    tipo_deposito_origem: origemTipoDeposito,
    time: time,
    gerente_regional: gerenteRegional,
    email_regional: emailRegional
  };
}

function smartSlipSalvarPreferenciasUsuarioJson(lojaInformada, tipoDepositoInformado) {
  try {
    return JSON.stringify({
      ok: true,
      payload: smartSlipSalvarPreferenciasUsuario(lojaInformada, tipoDepositoInformado)
    });

  } catch (err) {
    return JSON.stringify({
      ok: false,
      erro: String(err && err.message ? err.message : err)
    });
  }
}

function smartSlipListarLojasInfoLimites(usuario) {
  usuario = usuario || smartSlipGetUsuarioAtual();

  if (smartSlipUsuarioEhRegional_(usuario)) {
    return smartSlipGetLojasRegionaisDoUsuario_(usuario).map(function(item) {
      return {
        loja: item.loja,
        empresa: "",
        empresa_original: "",
        time: item.time || "",
        gerente_regional: item.gerente_regional || "",
        email_regional: item.email_regional || ""
      };
    });
  }

  const empresaPermitida = usuario.is_admin
    ? ""
    : smartSlipObterEmpresaPermitidaPorEmail(usuario.email);

  const ss = SpreadsheetApp.openById(SMARTSLIP_INFO_LIMITES_SPREADSHEET_ID);
  const sh = ss.getSheetByName(SMARTSLIP_ABA_INFO_LIMITES);

  if (!sh) {
    throw new Error("Aba Info_limites não encontrada.");
  }

  const values = sh.getDataRange().getValues();

  if (values.length < 2) {
    return [];
  }

  const headers = values[0].map(function(h) {
    return String(h || "").trim();
  });

  const idxNormLoja = smartSlipEncontrarIndiceHeader_(headers, [
    "Norm_Loja",
    "NORM_LOJA",
    "Norm Loja",
    "Loja",
    "LOJA"
  ]);

  let idxEmpresa = smartSlipEncontrarIndiceHeader_(headers, [
    "EMPRESA0",
    "EMPRESA",
    "Empresa"
  ]);

  if (idxEmpresa < 0) {
    idxEmpresa = 6;
  }

  if (idxNormLoja < 0) {
    throw new Error("Coluna Norm_Loja não encontrada na Info_limites.");
  }

  const mapa = {};

  for (let i = 1; i < values.length; i++) {
    const row = values[i];

    const lojaRaw = row[idxNormLoja];
    const loja4 = smartSlipNormalizarLoja4(lojaRaw || "");

    if (!loja4) {
      continue;
    }

    const empresaRaw = String(row[idxEmpresa] || "").trim();
    const empresa = smartSlipNormalizarEmpresa_(empresaRaw);

    if (empresaPermitida && empresa !== empresaPermitida) {
      continue;
    }

    if (!mapa[loja4]) {
      mapa[loja4] = {
        loja: loja4,
        empresa: empresa,
        empresa_original: empresaRaw
      };
    }
  }

  return Object.keys(mapa)
    .sort()
    .map(function(k) {
      return mapa[k];
    });
}

function smartSlipObterEmpresaPermitidaPorEmail(email) {
  const txt = String(email || "").trim().toLowerCase();

  if (!txt) {
    return "";
  }

  if (
    txt.includes("@empresa b") ||
    txt.includes(".empresa b") ||
    txt.includes("+empresa b") ||
    txt.includes("empresa b")
  ) {
    return "Empresa B";
  }

  if (
    txt.includes("@empresa a") ||
    txt.includes(".empresa a") ||
    txt.includes("+empresa a") ||
    txt.includes("empresa a")
  ) {
    return "Empresa A";
  }

  return "";
}

/****************************************************
 * SMARTSLIP MOBILE - PATCH BACKEND PARA APPS SCRIPT
 *
 * Cole este bloco no Code.gs, abaixo das funções SmartSlip
 * que você já tem no projeto.
 *
 * Depende destas funções já existentes no seu backend:
 * - smartSlipChamarGemini(base64Arquivo, mimeType, respostasUsuario)
 * - smartSlipConsultarInfoLoja_(lojaInformada)
 * - smartSlipSalvarDadosComprovantePlanilha_(dados)
 * - smartSlipNormalizarLoja4(loja)
 * - smartSlipSafeErr_(err)
 ****************************************************/

function smartSlipMobileProcessarArquivo(payload) {
  try {
    payload = payload || {};

    var base64 = String(payload.base64 || "").trim();
    base64 = base64.replace(/^data:[^;]+;base64,/, "");

    if (!base64) {
      throw new Error("Arquivo não recebido em base64.");
    }

    var mimeType = String(payload.mimeType || "application/pdf").trim();
    var respostasUsuario = payload.respostasUsuario || {};

    respostasUsuario = smartSlipMobileNormalizarRespostasUsuario_(respostasUsuario);

    var resultado = smartSlipChamarGemini(base64, mimeType, respostasUsuario);
    resultado = resultado || {};
    resultado.nome_arquivo = String(payload.filename || "");

    smartSlipMobileAplicarRespostasUsuario_(resultado, respostasUsuario);
    smartSlipMobileConsultarEmpresaPorLoja_(resultado);
    smartSlipMobileNormalizarResultado_(resultado);

    return {
      ok: true,
      resultado: resultado,
      arquivo: {
        nome: String(payload.filename || ""),
        mimeType: mimeType
      }
    };

  } catch (err) {
    return {
      ok: false,
      erro: smartSlipSafeErr_(err)
    };
  }
}

function smartSlipMobileSalvarResultado(payload) {
  try {
    payload = payload || {};
    var resultado = payload.resultado || {};

    smartSlipMobileConsultarEmpresaPorLoja_(resultado);
    smartSlipMobileNormalizarResultado_(resultado);

    if (resultado.status !== "PRONTO_PARA_SALVAR") {
      return {
        ok: false,
        erro: "Resultado ainda não está pronto para salvar. Pendências: " + (resultado.pendencias || []).join(" | "),
        resultado: resultado
      };
    }

    var dados = resultado.dados_comprovante || {};

    var payloadSalvar = {
      loja: dados.loja || "",
      empresa: dados.empresa || "",
      tipo_documento: resultado.tipo_documento || "",
      data_deposito: dados.data_deposito || "",
      valor_deposito: Number(dados.valor_deposito || 0),
      banco: dados.banco || "",
      data_movimento: dados.data_movimento || "",
      houve_retirada: dados.houve_retirada === true,
      valor_retirada: Number(dados.valor_retirada || 0),
      motivo_retirada: dados.houve_retirada === true
        ? (dados.motivo_retirada || "")
        : "Não houve retirada",
      data_geracao_documento: dados.data_geracao_documento || "",
      codigo_autenticacao: dados.codigo_autenticacao || "",
      link_comprovante: dados.link_comprovante || payload.link_comprovante || "",
      status_processamento: "PRONTO_PARA_SALVAR",
      pendencias: [],
      divergencias: resultado.divergencias || [],
      confianca_geral: Number(resultado.confianca_geral || 0),
      nome_arquivo: resultado.nome_arquivo || ""
    };

    var retorno = smartSlipSalvarDadosComprovantePlanilha_(payloadSalvar);

    return {
      ok: true,
      retorno: retorno,
      payload_salvo: payloadSalvar
    };

  } catch (err) {
    return {
      ok: false,
      erro: smartSlipSafeErr_(err)
    };
  }
}

function smartSlipMobileNormalizarRespostasUsuario_(r) {
  r = r || {};

  if (r.loja) {
    r.loja = smartSlipNormalizarLoja4(r.loja);
  }

  if (r.houve_retirada === "sim") r.houve_retirada = true;
  if (r.houve_retirada === "nao") r.houve_retirada = false;
  if (r.houve_retirada === "") r.houve_retirada = null;

  if (r.valor_retirada !== undefined && r.valor_retirada !== null && r.valor_retirada !== "") {
    r.valor_retirada = Number(r.valor_retirada || 0);
  }

  return r;
}

function smartSlipMobileAplicarRespostasUsuario_(resultado, respostasUsuario) {
  resultado.dados_comprovante = resultado.dados_comprovante || {};
  var dados = resultado.dados_comprovante;

  if (respostasUsuario.loja) {
    dados.loja = respostasUsuario.loja;
  }

  if (!dados.banco && respostasUsuario.banco) {
    dados.banco = respostasUsuario.banco;
  }

  if (respostasUsuario.data_movimento) {
    dados.data_movimento = respostasUsuario.data_movimento;
  }

  if (typeof respostasUsuario.houve_retirada === "boolean") {
    dados.houve_retirada = respostasUsuario.houve_retirada;
  }

  if (dados.houve_retirada === false) {
    dados.valor_retirada = 0;
    dados.motivo_retirada = "Não houve retirada";
  }

  if (dados.houve_retirada === true) {
    if (respostasUsuario.valor_retirada !== undefined) {
      dados.valor_retirada = Number(respostasUsuario.valor_retirada || 0);
    }
    if (respostasUsuario.motivo_retirada) {
      dados.motivo_retirada = respostasUsuario.motivo_retirada;
    }
  }

  if (dados.codigo_autenticacao === null || dados.codigo_autenticacao === undefined) {
    dados.codigo_autenticacao = "";
  }

  if (dados.link_comprovante === null || dados.link_comprovante === undefined) {
    dados.link_comprovante = "";
  }
}

function smartSlipMobileConsultarEmpresaPorLoja_(resultado) {
  resultado = resultado || {};
  resultado.dados_comprovante = resultado.dados_comprovante || {};
  resultado.pendencias = Array.isArray(resultado.pendencias) ? resultado.pendencias : [];
  resultado.perguntas_complementares = Array.isArray(resultado.perguntas_complementares) ? resultado.perguntas_complementares : [];

  var dados = resultado.dados_comprovante;

  if (!dados.loja) return;

  var loja4 = smartSlipNormalizarLoja4(dados.loja);
  dados.loja = loja4;

  var info = smartSlipConsultarInfoLoja_(loja4);

  if (info && info.ok) {
    dados.loja = info.loja_normalizada || loja4;
    dados.empresa = info.empresa || "Nao identificado";
  } else {
    dados.empresa = "Nao identificado";
    smartSlipMobileAddUnico_(resultado.pendencias, "Loja não encontrada na Info_limites.");
    smartSlipMobileAddUnico_(resultado.perguntas_complementares, "Confirme o número correto da loja.");
  }
}

function smartSlipMobileNormalizarResultado_(resultado) {
  resultado = resultado || {};
  resultado.dados_comprovante = resultado.dados_comprovante || {};
  resultado.pendencias = [];
  resultado.perguntas_complementares = [];
  resultado.divergencias = Array.isArray(resultado.divergencias) ? resultado.divergencias : [];

  var dados = resultado.dados_comprovante;

  if (!dados.codigo_autenticacao) dados.codigo_autenticacao = "";
  if (!dados.link_comprovante) dados.link_comprovante = "";

  smartSlipMobilePerguntaSe_(resultado, !dados.loja, "Loja não informada.", "Qual o número da loja?");
  smartSlipMobilePerguntaSe_(resultado, !dados.empresa || dados.empresa === "Nao identificado", "Empresa não identificada pela Info_limites.", "Confirme o número da loja para consultar a empresa correta.");
  smartSlipMobilePerguntaSe_(resultado, !resultado.tipo_documento || resultado.tipo_documento === "nao_identificado", "Tipo de documento não identificado.", "Qual é o tipo do comprovante?");
  smartSlipMobilePerguntaSe_(resultado, !dados.data_deposito, "Data do depósito não identificada.", "Qual a data do depósito?");
  smartSlipMobilePerguntaSe_(resultado, dados.valor_deposito === null || dados.valor_deposito === undefined || dados.valor_deposito === "", "Valor do depósito não identificado.", "Qual o valor do depósito?");
  smartSlipMobilePerguntaSe_(resultado, !dados.banco, "Banco não identificado.", "Qual o banco do comprovante?");
  smartSlipMobilePerguntaSe_(resultado, !dados.data_movimento, "Data de movimento não informada.", "Qual a data do movimento desse depósito?");
  smartSlipMobilePerguntaSe_(resultado, dados.houve_retirada === null || dados.houve_retirada === undefined, "Informação sobre retirada não informada.", "Houve alguma retirada desse movimento para estorno, reembolso no ato ou algo do tipo?");
  smartSlipMobilePerguntaSe_(resultado, !dados.data_geracao_documento, "Data de geração do documento não identificada.", "Qual a data de geração do documento?");

  if (dados.houve_retirada === true) {
    smartSlipMobilePerguntaSe_(resultado, !dados.valor_retirada, "Valor da retirada não informado.", "Qual o valor da retirada?");
    smartSlipMobilePerguntaSe_(resultado, !dados.motivo_retirada, "Motivo da retirada não informado.", "Qual o motivo da retirada?");
  }

  if (dados.houve_retirada === false) {
    dados.valor_retirada = 0;
    dados.motivo_retirada = "Não houve retirada";
  }

  if (resultado.pendencias.length || resultado.perguntas_complementares.length) {
    resultado.status = "PRECISA_COMPLEMENTO";
  } else if (resultado.divergencias.length) {
    resultado.status = "DIVERGENCIA";
  } else if (resultado.status !== "INELEGIVEL") {
    resultado.status = "PRONTO_PARA_SALVAR";
  }

  return resultado;
}

function smartSlipMobilePerguntaSe_(resultado, condicao, pendencia, pergunta) {
  if (!condicao) return;
  smartSlipMobileAddUnico_(resultado.pendencias, pendencia);
  smartSlipMobileAddUnico_(resultado.perguntas_complementares, pergunta);
}

function smartSlipMobileAddUnico_(arr, value) {
  value = String(value || "").trim();
  if (!value) return;
  if (arr.indexOf(value) === -1) arr.push(value);
}

function smartSlipTesteHostLiteLlm() {
  const url =
    "https://seu-gateway-ia.example.com";

  try {
    const response =
      UrlFetchApp.fetch(
        url,
        {
          method: "get",
          muteHttpExceptions: true
        }
      );

    Logger.log(
      "HTTP: " +
      response.getResponseCode()
    );

    Logger.log(
      response.getContentText()
    );

  } catch (err) {
    Logger.log(
      "ERRO DE CONEXÃO: " +
      String(
        err && err.message
          ? err.message
          : err
      )
    );

    throw err;
  }
}