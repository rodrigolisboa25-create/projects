/******************************************************
 * VEKTOR | ENVIO POS — V3
 * Persistência operacional: arquivos JSON no Google Drive
 * Fontes de cadastro:
 *   - Nike: cadastro fixo controlado neste arquivo
 *   - Centauro: BigQuery + aba Base de Numerário
 * Front-end: pos_index.html
 ******************************************************/

var VEKTOR_POS_MODULE_KEY = "AR";
var VEKTOR_POS_SCHEMA_VERSION = 3;

// Storage JSON do módulo POS.
var VEKTOR_POS_STORAGE_FOLDER_ID = PropertiesService.getScriptProperties().getProperty("VEKTOR_POS_STORAGE_FOLDER_ID") || "";
var VEKTOR_POS_STORAGE_FOLDER_PROP = "VEKTOR_POS_STORAGE_FOLDER_ID";

// E-mail.
var VEKTOR_POS_EMAIL_FROM = PropertiesService.getScriptProperties().getProperty("VEKTOR_POS_EMAIL_FROM") || "";
var VEKTOR_POS_EMAIL_NAME = "Vektor - Grupo SBF";
var VEKTOR_POS_EMAIL_CC_DEFAULT = PropertiesService.getScriptProperties().getProperty("VEKTOR_POS_EMAIL_CC_DEFAULT") || "";

// Agente Pedro: a chave nunca deve ser gravada neste arquivo. A pagina de
// Configuracoes salva a integracao em uma unica propriedade JSON protegida.
var VEKTOR_POS_PEDRO_POLICY_VERSION = "22/06/2026";
var VEKTOR_POS_PEDRO_AI_CONFIG_PROP = "VEKTOR_POS_PEDRO_AI_CONFIG";
var VEKTOR_POS_PEDRO_PRICING_UPDATED_AT = "2026-07-21";
var VEKTOR_POS_PEDRO_PRICING_USD_PER_MILLION = {
  "gemini-3.6-flash": { input: 1.50, output: 7.50 },
  "gemini-3.5-flash": { input: 1.50, output: 9.00 },
  "gemini-3.5-flash-lite": { input: 0.30, output: 2.50 },
  "gemini-2.5-flash": { input: 0.30, output: 2.50 },
  "gemini-2.5-flash-lite": { input: 0.10, output: 0.40 }
};
var VEKTOR_POS_PEDRO_POLICY_RULES = [
  "O POS deve ser usado somente em contingencia real do TEF ou em eventos previamente justificados.",
  "Toda movimentacao deve ser finalizada no PDV no mesmo dia da transacao.",
  "Em POS 71, o NSU deve vir da boleta: CV na Getnet e DOC na Cielo.",
  "Cada transacao POS deve corresponder a exatamente uma finalizacao no PDV (regra 1 para 1).",
  "A loja deve manter justificativa, autorizacao e comprovacao documental da finalizacao.",
  "O CNPJ da maquina POS deve corresponder ao CNPJ da loja.",
  "Divergencias devem ser respondidas no proprio mes da cobranca; cobrancas dos dias 29, 30 e 31 podem ser respondidas ate o quinto dia util do mes seguinte.",
  "Pendencias sem retorno no prazo e repasses indevidos podem ser direcionados a perdas.",
  "E proibida a transferencia de equipamento POS entre lojas."
].join("\n");

// BigQuery: o projectId abaixo é o projeto de execução/faturamento da consulta.
// A tabela consultada permanece totalmente qualificada no SQL.
var VEKTOR_POS_BQ_BILLING_PROJECT_ID = PropertiesService.getScriptProperties().getProperty("VEKTOR_POS_BQ_BILLING_PROJECT_ID") || "";
var VEKTOR_POS_BQ_SQL = [
  "SELECT cod_loja, cod_loja_nova, bu, shoppping, nome_da_loja,",
  "       data_inauguracao, cnpj, logradouro, latitude, longitude, time, dat_chave",
  "FROM `CONFIGURE_VEKTOR_POS_BQ_BILLING_PROJECT_ID.trusted.sbf_trd_xls_0000_man_informacoes_lojas`",
  "WHERE dat_chave >= '2000-01-01'",
  "  AND UPPER(TRIM(bu)) = 'CENTAURO'"
].join("\n");

// Base externa usada apenas para complementar Time e E-mail Regional.
var VEKTOR_POS_REGIONAL_SS_ID = PropertiesService.getScriptProperties().getProperty("VEKTOR_POS_REGIONAL_SS_ID") || "";
var VEKTOR_POS_REGIONAL_SHEET = "Base";

var VEKTOR_POS_FILE_NAMES = {
  CENTAURO: "vektor_pos_centauro.json",
  NIKE: "vektor_pos_nike.json",
  LOJAS: "vektor_pos_lojas.json",
  CONFIG: "vektor_pos_config.json",
  DISPAROS: "vektor_pos_disparos.json",
  AI_USAGE: "vektor_pos_ai_usage.json",
  SAP_EXPORT_SNAPSHOT: "vektor_pos_sap_export_snapshot.json"
};

var VEKTOR_POS_HEADERS = {
  CENTAURO: [
    "CÓDIGO ENVIO EMAIL_ASSUNTO",
    "Status",
    "DATA COBRANÇA",
    "DATA FINAL (TRATATIVA)",
    "LOJA",
    "DATA VENDA",
    "NSU",
    "VALOR EQUALS (50)",
    "VALOR REGISTRADO (40)",
    "DIFERENÇA",
    "INFORMAÇÕES",
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)",
    "E-mail Gerente Grupo",
    "E-mail Sup Auto",
    "E-mail Sup Vendas",
    "E-mail Regional",
    "Enviar Para",
    "Time",
    "MÊS PENDÊNCIA",
    "QTD DIAS TRATATIVA",
    "STATUS ENVIO"
  ],
  NIKE: [
    "CÓDIGO ÚNICO_ASSUNTO",
    "STATUS",
    "DATA COBRANÇA",
    "DATA FINAL (TRATATIVA)",
    "LOJA",
    "DATA VENDA",
    "NSU TRANSAÇÃO",
    "VALOR EQUALS",
    "VALOR REGISTRADO",
    "DIFERENÇA",
    "OBSERVAÇÃO",
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)",
    "E-mail Loja",
    "TIPO",
    "MÊS PENDÊNCIA",
    "QTD DIAS TRATATIVA",
    "STATUS ENVIO"
  ],
  LOJAS: [
    "EMPRESA",
    "LOJA",
    "EMAILS",
    "NOMINAL",
    "RENAME",
    "TIPO",
    "COD_LOJA_NOVA",
    "BU",
    "SHOPPING",
    "NOME_LOJA",
    "DATA_INAUGURACAO",
    "CNPJ",
    "LOGRADOURO",
    "LATITUDE",
    "LONGITUDE",
    "TIME",
    "EMAIL_REGIONAL",
    "EMAIL_GERENTE_GRUPO",
    "EMAIL_SUP_AUTO",
    "EMAIL_SUP_VENDAS",
    "DAT_CHAVE",
    "ATIVO"
  ],
  DISPAROS: [
    "ID_DISPARO",
    "DATA_ENVIO",
    "USUARIO",
    "EMPRESA",
    "SEND_KEY",
    "LOJA",
    "ASSUNTO",
    "DESTINATARIOS",
    "CC",
    "ROW_IDS",
    "QTD_LINHAS",
    "STATUS",
    "ERRO",
    "HASH"
  ]
};

var VEKTOR_POS_LOJAS_VIEW_HEADERS = {
  NIKE: ["LOJA", "EMAILS", "NOMINAL", "RENAME", "TIPO"],
  CENTAURO: [
    "LOJA",
    "COD_LOJA_NOVA",
    "BU",
    "SHOPPING",
    "NOME_LOJA",
    "DATA_INAUGURACAO",
    "CNPJ",
    "LOGRADOURO",
    "LATITUDE",
    "LONGITUDE",
    "TIME",
    "EMAIL_REGIONAL",
    "EMAIL_GERENTE_GRUPO",
    "EMAIL_SUP_AUTO",
    "EMAIL_SUP_VENDAS",
    "EMAILS",
    "DAT_CHAVE",
    "ATIVO"
  ]
};

var VEKTOR_POS_STATUS_OPTIONS = [
  { value: "OK", color: "#16c96f", text: "#052e16" },
  { value: "PENDENTE", color: "#ef2b20", text: "#ffffff" },
  { value: "TRATATIVA - LOJA", color: "#efa1a5", text: "#111827" },
  { value: "TRATATIVA - FIN", color: "#5ed2df", text: "#111827" },
  { value: "TRATATIVA - T.I.", color: "#9aa1aa", text: "#111827" },
  { value: "PERDA", color: "#fff832", text: "#111827" }
];

var VEKTOR_POS_DEFAULT_CONFIG = {
  emailFrom: VEKTOR_POS_EMAIL_FROM,
  emailName: VEKTOR_POS_EMAIL_NAME,
  emailCc: VEKTOR_POS_EMAIL_CC_DEFAULT,
  maxSendPerRun: 100,
  allowSendWithoutStoreConfig: false
};

// Cadastro Nike informado pela operação.
var VEKTOR_POS_NIKE_STORES = [
  ["2084","usuario42@empresa.exemplo","NV2084 Place Outlet - Extra Anchieta","NV2084","NVS"],
  ["2086","usuario33@empresa.exemplo","NV2086 Shopping Nova América","NV2086","NVS"],
  ["2087","usuario43@empresa.exemplo","NV2087 São Gonçalo Shopping","NV2087","NVS"],
  ["2088","usuario35@empresa.exemplo","NV2088 Carrefour Osasco","NV2088","NVS"],
  ["2091","usuario29@empresa.exemplo","NV2091 Outlet Premium Itupeva","NV2091","NVS"],
  ["2092","usuario24@empresa.exemplo","NV2092 Só Marcas Outlet Contagem","NV2092","NVS"],
  ["2095","usuario30@empresa.exemplo","NV2095 Shopping Light","NV2095","NVS"],
  ["2099","usuario34@empresa.exemplo","NV2099 I Fashion Outlet Novo Hamburgo","NV2099","NVS"],
  ["2098","usuario13@empresa.exemplo","NV2098 Outlet Premium Brasília","NV2098","NVS"],
  ["2097","usuario41@empresa.exemplo","NV2097 Nike Santo André","NV2097","NVS"],
  ["2072","usuario26@empresa.exemplo","NV2072 Nike Curitiba","NV2072","NVS"],
  ["2075","usuario15@empresa.exemplo","NV2075 Araguaia Shopping","NV2075","NVS"],
  ["2077","usuario39@empresa.exemplo","NV2077 Outlet Premium Salvador","NV2077","NVS"],
  ["2076","usuario48@empresa.exemplo","NV2076 Boulevard Shopping Vila Velha","NV2076","NVS"],
  ["2032","usuario22@empresa.exemplo","NV2032 Catarina Outlet","NV2032","NVS"],
  ["2033","usuario27@empresa.exemplo","NV2033 Outlet Premium Fortaleza","NV2033","NVS"],
  ["2034","usuario38@empresa.exemplo","NV2034 Outlet Premium Rio De Janeiro","NV2034","NVS"],
  ["2055","usuario49@empresa.exemplo","NV2055 Shopping Metrô Itaquera","NV2055","NVS"],
  ["2090","usuario50@empresa.exemplo","NV2090 Só Marcas Outlet Guarulhos","NV2090","NVS"],
  ["2085","usuario37@empresa.exemplo","NV2085 Outlet Premium Grande São Paulo","NV2085","NVS"],
  ["2070","usuario40@empresa.exemplo","NV2070 I Fashion Outlet Santa Catarina","NV2070","NVS"],
  ["2058","usuario07@empresa.exemplo","NI2058 Ibirapuera","NI2058","NDIS"],
  ["2071","usuario06@empresa.exemplo","NI2071 Iguatemi Fortaleza","NI2071","NDIS"],
  ["2036","usuario16@empresa.exemplo","NV2036 Shopping Aricanduva","NV2036","NVS"],
  ["2056","usuario36@empresa.exemplo","NV2056 Passeio Das Águas","NV2056","NVS"],
  ["2029","usuario11@empresa.exemplo","NI2029 Shopping Vitória","NI2029","NDIS"],
  ["2078","usuario08@empresa.exemplo","NI2078 Iguatemi Porto Alegre","NI2078","NDIS"],
  ["2079","usuario32@empresa.exemplo","NV2079 Mangabeira","NV2079","NVS"],
  ["2054","usuario44@empresa.exemplo","NV2054 Shopping Da Ilha","NV2054","NVS"],
  ["2057","usuario21@empresa.exemplo","NV2057 City Center Outlet","NV2057","NVS"],
  ["2093","usuario05@empresa.exemplo","NI2093 Shopping Flamboyant","NI2093","NDIS"],
  ["2050","usuario47@empresa.exemplo","NV2050 Shopping Vale Sul","NV2050","NVS"],
  ["2089","usuario45@empresa.exemplo","NV2089 SP Market","NV2089","NVS"],
  ["2030","usuario31@empresa.exemplo","NV2030 Litoral Plaza","NV2030","NVS"],
  ["2052","usuario14@empresa.exemplo","NV2052 Ananindeua","NV2052","NVS"],
  ["2100","usuario19@empresa.exemplo","NV2100 Shopping Barra Sul","NV2100","NVS"],
  ["2094","usuario23@empresa.exemplo","NV2094 Shopping Center Norte","NV2094","NVS"],
  ["2035","usuario18@empresa.exemplo","NV2035 Shopping Barra Salvador","NV2035","NVS"],
  ["2102","usuario46@empresa.exemplo","NV2102 Shopping União Osasco","NV2102","NVS"],
  ["2083","usuario20@empresa.exemplo","NV2083 Bh Outlet","NV2083","NVS"],
  ["2101","usuario17@empresa.exemplo","NI2101 Barra Rio","NI2101","NDIS"],
  ["2110","usuario09@empresa.exemplo","NI2110 Praia de Belas","NI2110","NDIS"],
  ["2107","usuario25@empresa.exemplo","NV2107 Continente Shopping","NV2107","NVS"],
  ["2104","usuario04@empresa.exemplo","NI2104 Iguatemi SP","NI2104","NDIS"],
  ["2105","usuario28@empresa.exemplo","NV2105 Outlet Premium Imigrantes","NV2105","NVS"],
  ["2108","usuario10@empresa.exemplo","NI2108 RIO SUL","NI2108","NDIS"],
  ["2111","usuario03@empresa.exemplo","NI2111 Iguatemi Campinas","NI2111","NDIS"],
  ["2109","usuario51@empresa.exemplo","NV2109 RIBEIRÃO","NV2109","NVS"],
  ["2106","usuario02@empresa.exemplo","NI2106 Balneário Cambuirú","NI2106","NDIS"],
  ["2112","usuario12@empresa.exemplo","NI2112 Barigui","NI2112","NDIS"]
];

/* =====================================================
   RENDER / BOOTSTRAP
   ===================================================== */

function vektorRenderPosPage_() {
  try {
    var ctx = vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
    var template = HtmlService.createTemplateFromFile("pos_index");

    template.posUserEmail = String(ctx.email || "").trim().toLowerCase();
    template.posUserRole = String(ctx.role || "").trim();
    template.posIsAdmin = String(ctx.role || "").trim().toLowerCase() === "administrador";

    return template
      .evaluate()
      .setTitle("Vektor | Envio POS")
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  } catch (e) {
    var msg = e && e.message ? e.message : String(e);
    return HtmlService
      .createHtmlOutput(
        "<div style='font-family:Arial;padding:24px;color:#0f172a;'>" +
          "<h2>Acesso não disponível</h2>" +
          "<p>" + vektorPosEscape_(msg) + "</p>" +
        "</div>"
      )
      .setTitle("Vektor | Envio POS")
      .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
  }
}

function vektorPosGetWebAppUrl() {
  vektorAssertFunctionAllowed_("vektorPosGetWebAppUrl");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
  return { ok: true, url: ScriptApp.getService().getUrl() + "?view=pos" };
}

function vektorPosSetupStorage() {
  vektorAssertFunctionAllowed_("vektorPosSetupStorage");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
  vektorPosAssertAdmin_();

  var folder = vektorPosGetOrCreateStorageFolder_();
  vektorPosEnsureDataFile_("CENTAURO", VEKTOR_POS_HEADERS.CENTAURO);
  vektorPosEnsureDataFile_("NIKE", VEKTOR_POS_HEADERS.NIKE);
  vektorPosEnsureDataFile_("LOJAS", VEKTOR_POS_HEADERS.LOJAS);
  vektorPosEnsureDataFile_("DISPAROS", VEKTOR_POS_HEADERS.DISPAROS);
  vektorPosEnsureConfigFile_();
  vektorPosMigrateStorageV3_();

  // Não restaura nem sobrescreve o cadastro Nike se ele já existe.
  vektorPosSeedNikeStores_(false);

  return {
    ok: true,
    folderId: folder.getId(),
    message: "Storage POS V3 criado/validado sem recarregar cadastros existentes."
  };
}

function vektorPosGetBootstrapData() {
  vektorAssertFunctionAllowed_("vektorPosGetBootstrapData");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  var ctx = vektorGetUserRole_();
  vektorPosEnsureConfigFile_();
  var lojasData = vektorPosReadData_("LOJAS");
  var storeOptions = vektorPosBuildStoreOptions_(lojasData);

  return {
    ok: true,
    email: String(ctx.email || "").trim().toLowerCase(),
    role: String(ctx.role || "").trim(),
    isAdmin: String(ctx.role || "").trim().toLowerCase() === "administrador",
    headers: VEKTOR_POS_HEADERS,
    companies: ["CENTAURO", "NIKE"],
    statusOptions: VEKTOR_POS_STATUS_OPTIONS,
    storeOptions: storeOptions,
    lojas: vektorPosBuildAllLojasViews_(lojasData),
    config: vektorPosReadJson_("CONFIG").config || VEKTOR_POS_DEFAULT_CONFIG,
    ai: vektorPosPedroGetAiConfigStatus_(ctx)
  };
}

/* =====================================================
   CADASTRO DE LOJAS
   ===================================================== */

function vektorPosGetLojas(req) {
  vektorAssertFunctionAllowed_("vektorPosGetLojas");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  return vektorPosBuildLojasView_(empresa, vektorPosReadData_("LOJAS"));
}

function vektorPosBuildLojasView_(empresa, data) {
  empresa = vektorPosNormEmpresa_(empresa);
  data = data || { rows: [] };
  var header = VEKTOR_POS_LOJAS_VIEW_HEADERS[empresa];
  var rows = (data.rows || []).filter(function(r) {
    return String(r.EMPRESA || "").trim().toUpperCase() === empresa;
  });

  rows.sort(function(a, b) {
    return Number(vektorPosStoreDigits_(a.LOJA)) - Number(vektorPosStoreDigits_(b.LOJA));
  });

  return {
    ok: true,
    empresa: empresa,
    header: header,
    rows: vektorPosJsonSafe_(rows),
    editable: empresa === "NIKE",
    source: empresa === "NIKE" ? "CADASTRO_CONTROLADO" : "BIGQUERY_E_BASE_REGIONAL"
  };
}

function vektorPosBuildAllLojasViews_(data) {
  data = data || vektorPosReadData_("LOJAS");
  return {
    CENTAURO: vektorPosBuildLojasView_("CENTAURO", data),
    NIKE: vektorPosBuildLojasView_("NIKE", data)
  };
}

function vektorPosBuildStoreOptions_(data) {
  data = data || vektorPosReadData_("LOJAS");

  var out = {
    CENTAURO: [],
    NIKE: []
  };

  var seen = {};

  (data.rows || []).forEach(function(row) {
    var empresa = String(row.EMPRESA || "")
      .trim()
      .toUpperCase();

    if (
      empresa !== "CENTAURO" &&
      empresa !== "NIKE"
    ) {
      return;
    }

    var ativo = String(row.ATIVO || "SIM")
      .trim()
      .toUpperCase();

    if (
      ativo === "NÃO" ||
      ativo === "NAO" ||
      ativo === "N" ||
      ativo === "FALSE"
    ) {
      return;
    }

    var loja4 = vektorPosStoreCode4_(
      row.LOJA
    );

    if (!loja4) {
      return;
    }

    var key = empresa + "|" + loja4;

    if (seen[key]) {
      return;
    }

    seen[key] = true;

    var nome = empresa === "NIKE"
      ? String(
          row.NOMINAL ||
          row.RENAME ||
          row.TIPO ||
          ""
        ).trim()
      : String(
          row.NOME_LOJA ||
          row.SHOPPING ||
          row.COD_LOJA_NOVA ||
          ""
        ).trim();

    out[empresa].push({
      value: loja4,
      label: nome || ("Loja " + loja4)
    });
  });

  ["CENTAURO", "NIKE"].forEach(function(empresa) {
    out[empresa].sort(function(a, b) {
      return Number(a.value) - Number(b.value);
    });
  });

  return out;
}

function vektorPosSaveLojas(req) {
  vektorAssertFunctionAllowed_("vektorPosSaveLojas");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var rowsToSave = Array.isArray(req.rows) ? req.rows : [];
  if (!rowsToSave.length) return { ok: true, saved: 0 };

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_("LOJAS");
    var byId = {};
    (data.rows || []).forEach(function(r, idx) { byId[String(r.__id || "")] = idx; });

    var saved = 0;
    rowsToSave.forEach(function(inRow) {
      var id = String(inRow.__id || "").trim();
      if (!id || byId[id] === undefined) return;

      var target = data.rows[byId[id]];
      Object.keys(inRow).forEach(function(h) {
        if (h.indexOf("__") === 0) return;
        if (VEKTOR_POS_HEADERS.LOJAS.indexOf(h) < 0) return;
        target[h] = vektorPosCellToText_(inRow[h]);
      });

      target.__updatedAt = vektorPosNowText_();
      target.__updatedBy = String(ctx.email || "").trim().toLowerCase();
      saved++;
    });

    vektorPosWriteJson_("LOJAS", data);
    return { ok: true, saved: saved };
  } finally {
    lock.releaseLock();
  }
}

function vektorPosAddLoja(req) {
  vektorAssertFunctionAllowed_("vektorPosAddLoja");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  if (empresa !== "NIKE") {
    throw new Error("Inclusão manual de lojas está disponível apenas para Fisia/Nike.");
  }

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_("LOJAS");
    var obj = vektorPosBlankObject_(VEKTOR_POS_HEADERS.LOJAS);
    obj.EMPRESA = "NIKE";
    obj.ATIVO = "SIM";
    obj.__id = vektorPosRowId_("LOJAS", obj, (data.rows || []).length + 1);
    obj.__createdAt = vektorPosNowText_();
    obj.__updatedAt = vektorPosNowText_();
    obj.__updatedBy = String(ctx.email || "").trim().toLowerCase();

    data.rows = data.rows || [];
    data.rows.unshift(obj);
    vektorPosWriteJson_("LOJAS", data);
    return { ok: true, row: vektorPosJsonSafe_(obj) };
  } finally {
    lock.releaseLock();
  }
}


function vektorPosDeleteLoja(req) {
  vektorAssertFunctionAllowed_("vektorPosDeleteLoja");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var rowId = String(req.rowId || "").trim();
  if (!rowId) throw new Error("rowId obrigatório.");

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_("LOJAS");
    var index = -1;

    for (var i = 0; i < (data.rows || []).length; i++) {
      if (String(data.rows[i].__id || "") === rowId) {
        index = i;
        break;
      }
    }

    if (index < 0) {
      return { ok: true, deleted: false, message: "Loja já não existe no cadastro." };
    }

    var target = data.rows[index];
    if (String(target.EMPRESA || "").trim().toUpperCase() !== "NIKE") {
      throw new Error("Exclusão manual está disponível apenas para lojas Fisia/Nike.");
    }

    data.rows.splice(index, 1);
    data.meta = data.meta || {};
    data.meta.lastNikeStoreDeletedAt = vektorPosNowText_();
    data.meta.lastNikeStoreDeletedBy = String(ctx.email || "").trim().toLowerCase();

    vektorPosWriteJson_("LOJAS", data);

    return {
      ok: true,
      deleted: true,
      loja: String(target.LOJA || ""),
      message: "Loja Fisia/Nike excluída."
    };
  } finally {
    lock.releaseLock();
  }
}

function vektorPosResetNikeStores() {
  vektorAssertFunctionAllowed_("vektorPosResetNikeStores");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
  vektorPosAssertAdmin_();
  return vektorPosSeedNikeStores_(true);
}

/**
 * =====================================================
 * POS | SINCRONIZAÇÃO AUTOMÁTICA DE LOJAS CENTAURO
 * =====================================================
 *
 * Função destinada exclusivamente a trigger do
 * Apps Script.
 *
 * Não depende do usuário estar com o Vektor aberto.
 */
function vektorPosSyncCentauroStoresDaily() {

  try {

    console.log(
      "[POS LOJAS] Iniciando sincronização diária Centauro."
    );


    var result =
      vektorPosSyncCentauroStoresCore_();


    console.log(
      "[POS LOJAS] Sincronização concluída: " +
      JSON.stringify(result)
    );


    return result;


  } catch (error) {

    console.error(
      "[POS LOJAS] Erro na sincronização diária:",
      error
    );


    throw error;

  }

}

/**
 * Cria o trigger diário de atualização das lojas Centauro.
 *
 * Execute esta função MANUALMENTE apenas uma vez.
 */
function vektorPosInstallDailyStoresTrigger() {

  var functionName =
    "vektorPosSyncCentauroStoresDaily";


  /*
   * Remove triggers antigos da mesma função,
   * evitando criar duplicatas.
   */
  ScriptApp
    .getProjectTriggers()
    .forEach(
      function(trigger) {

        if (
          trigger.getHandlerFunction() ===
          functionName
        ) {

          ScriptApp.deleteTrigger(
            trigger
          );

        }

      }
    );


  /*
   * Executa diariamente pela manhã.
   *
   * atHour(6) significa aproximadamente
   * entre 06:00 e 07:00 no fuso do projeto.
   */
  var trigger =
    ScriptApp
      .newTrigger(
        functionName
      )
      .timeBased()
      .everyDays(1)
      .atHour(6)
      .create();


  console.log(
    "[POS LOJAS] Trigger diário criado: " +
    trigger.getUniqueId()
  );


  return {
    ok:
      true,

    handler:
      functionName,

    hour:
      6,

    triggerId:
      trigger.getUniqueId()
  };

}

function vektorPosSyncCentauroStores() {

  vektorAssertFunctionAllowed_(
    "vektorPosSyncCentauroStores"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_POS_MODULE_KEY
  );

  vektorPosAssertAdmin_();


  return vektorPosSyncCentauroStoresCore_();

}


/**
 * Núcleo da sincronização.
 *
 * Pode ser utilizado tanto pela interface
 * administrativa quanto pelo trigger automático.
 */
function vektorPosSyncCentauroStoresCore_() {

  if (
    typeof BigQuery === "undefined" ||
    !BigQuery.Jobs
  ) {

    throw new Error(
      "Serviço avançado BigQuery não habilitado no projeto Apps Script."
    );
  }

  if (typeof BigQuery === "undefined" || !BigQuery.Jobs) {
    throw new Error("Serviço avançado BigQuery não habilitado no projeto Apps Script.");
  }

  var bqRows = vektorPosRunBigQuery_(VEKTOR_POS_BQ_SQL, VEKTOR_POS_BQ_BILLING_PROJECT_ID);
  var regionalMap = vektorPosLoadRegionalMap_();
  var latestByStore = {};

  bqRows.forEach(function(r) {

    /*
    * Sempre usa primeiro o código novo da loja.
    * Se não existir, utiliza o código legado.
    */
    var loja = vektorPosStoreDigits_(
      r.cod_loja_nova ||
      r.cod_loja
    );
    if (!loja) return;

    var key = loja.padStart(4, "0");
    var current = latestByStore[key];
    var currentDate = current ? String(current.dat_chave || "") : "";
    var candidateDate = String(r.dat_chave || "");
    if (!current || candidateDate >= currentDate) latestByStore[key] = r;
  });

  var ctx = vektorGetUserRole_();
  var now = vektorPosNowText_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_("LOJAS");
    data.header = VEKTOR_POS_HEADERS.LOJAS;
    data.rows = data.rows || [];

    var existingCentauro = {};
    data.rows.forEach(function(r) {
      if (String(r.EMPRESA || "").trim().toUpperCase() !== "CENTAURO") return;
      var loja4 = vektorPosStoreCode4_(r.LOJA);
      if (loja4) existingCentauro[loja4] = true;
    });

    var inserted = 0;
    var skipped = 0;

    Object.keys(latestByStore).sort().forEach(function(loja4, idx) {
      if (existingCentauro[loja4]) {
        skipped++;
        return;
      }

      var r = latestByStore[loja4];
      var loja = String(Number(loja4));
      var regional = regionalMap[loja] || {};
      var emails = vektorPosBuildCentauroEmails_(loja, regional.emailRegional || "");

      var obj = vektorPosBlankObject_(VEKTOR_POS_HEADERS.LOJAS);
      obj.EMPRESA = "CENTAURO";
      obj.LOJA = String(Number(loja4));
      obj.COD_LOJA_NOVA = vektorPosCellToText_(r.cod_loja_nova);
      obj.BU = vektorPosCellToText_(r.bu);
      obj.SHOPPING = vektorPosCellToText_(r.shoppping);
      obj.NOME_LOJA = vektorPosCellToText_(r.nome_da_loja);
      obj.DATA_INAUGURACAO = vektorPosCellToText_(r.data_inauguracao);
      obj.CNPJ = vektorPosCellToText_(r.cnpj);
      obj.LOGRADOURO = vektorPosCellToText_(r.logradouro);
      obj.LATITUDE = vektorPosCellToText_(r.latitude);
      obj.LONGITUDE = vektorPosCellToText_(r.longitude);
      obj.TIME = regional.time || vektorPosCellToText_(r.time);
      obj.EMAIL_REGIONAL = regional.emailRegional || "";
      obj.EMAIL_GERENTE_GRUPO = emails.gerenteGrupo;
      obj.EMAIL_SUP_AUTO = emails.supAuto;
      obj.EMAIL_SUP_VENDAS = emails.supVendas;
      obj.EMAILS = emails.todos;
      obj.DAT_CHAVE = vektorPosCellToText_(r.dat_chave);
      obj.ATIVO = "SIM";
      obj.__id = "CENTAURO_LOJA_" + loja4;
      obj.__createdAt = now;
      obj.__updatedAt = now;
      obj.__updatedBy = String(ctx.email || "").trim().toLowerCase();
      obj.__source = "BIGQUERY_E_BASE_REGIONAL";

      data.rows.push(obj);
      existingCentauro[loja4] = true;
      inserted++;
    });

    data.meta = data.meta || {};
    data.meta.centauroLastIncrementalCheckAt = now;
    data.meta.centauroLastIncrementalCheckBy = String(ctx.email || "").trim().toLowerCase();
    data.meta.centauroInsertedLastCheck = inserted;
    data.meta.centauroSkippedExistingLastCheck = skipped;

    vektorPosWriteJson_("LOJAS", data);

    return {
      ok: true,
      inserted: inserted,
      skipped: skipped,
      queryRows: bqRows.length,
      regionalRows: Object.keys(regionalMap).length,
      message: inserted
        ? inserted + " nova(s) loja(s) Centauro adicionada(s). Registros existentes foram preservados."
        : "Nenhuma nova loja Centauro encontrada. Registros existentes foram preservados."
    };
  } finally {
    lock.releaseLock();
  }
}

/* =====================================================
   DISPAROS — CONSULTA, EDIÇÃO, ENRIQUECIMENTO
   ===================================================== */

function vektorPosGetRows(req) {
  vektorAssertFunctionAllowed_("vektorPosGetRows");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var data = vektorPosReadData_(empresa);
  var header = VEKTOR_POS_HEADERS[empresa];
  data.header = header;

  // Corrige bases antigas que acumularam várias linhas vazias.
  // A base mantém exatamente um único rascunho vazio no final.
  var draftInfo = vektorPosEnsureSingleDraftRow_(
    empresa,
    data,
    vektorGetUserRole_()
  );

  if (draftInfo.changed) {
    vektorPosWriteJson_(empresa, data);
  }

  (data.rows || []).forEach(function(row) {
  vektorPosSyncEmailStatusField_(row);
});

  var q = vektorPosNormSearch_(req.q || "");
  var statusFiltro = String(req.status || "").trim().toUpperCase();
  var onlyPendentes = req.onlyPendentes === true ||
    String(req.onlyPendentes || "").toUpperCase() === "TRUE";
  var onlyNotSent =
    req.onlyNotSent === true ||
    String(
      req.onlyNotSent || ""
    ).toUpperCase() === "TRUE";
  var filters = req.filters && typeof req.filters === "object"
    ? req.filters
    : {};
  var sortKey = header.indexOf(String(req.sortKey || "")) >= 0
    ? String(req.sortKey)
    : "";
  var sortDir = String(req.sortDir || "").toLowerCase() === "desc"
    ? "desc"
    : "asc";
  var page = Math.max(1, Number(req.page || 1));
  var pageSize = Math.min(500, Math.max(25, Number(req.pageSize || 150)));

  var filtered = (data.rows || []).filter(function(r) {
    if (statusFiltro && vektorPosGetStatus_(r, empresa) !== statusFiltro) {
      return false;
    }

    if (
      onlyPendentes &&
      vektorPosGetStatus_(r, empresa) !== "PENDENTE"
    ) {
      return false;
    }

    if (
      onlyNotSent &&
      vektorPosWasSent_(r)
    ) {
      return false;
    }

    var filterKeys = Object.keys(filters);
    for (var i = 0; i < filterKeys.length; i++) {
      var h = filterKeys[i];
      var wanted = vektorPosNormSearch_(filters[h]);
      if (!wanted) continue;

      var got = vektorPosNormSearch_(r[h]);
      if (got.indexOf(wanted) < 0) return false;
    }

    if (q) {
      var hay = header.map(function(h) { return r[h]; }).join(" ");
      if (vektorPosNormSearch_(hay).indexOf(q) < 0) return false;
    }

    return true;
  });

  // Ordena somente linhas preenchidas. O rascunho permanece no final.
  var draftRows = [];
  var filledRows = [];

  filtered.forEach(function(r) {
    if (vektorPosIsDraftRow_(r)) draftRows.push(r);
    else filledRows.push(r);
  });

  if (sortKey) {
    filledRows.sort(function(a, b) {
      var cmp = vektorPosCompareValues_(a[sortKey], b[sortKey]);
      return sortDir === "desc" ? -cmp : cmp;
    });
  }

  filtered = filledRows.concat(draftRows.slice(0, 1));

  var total = filtered.length;
  var totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (page > totalPages) page = totalPages;

  var start = (page - 1) * pageSize;
  var rows = filtered.slice(start, start + pageSize);

  return {
    ok: true,
    empresa: empresa,
    header: header,
    rows: vektorPosJsonSafe_(rows),
    total: total,
    page: page,
    pageSize: pageSize,
    totalPages: totalPages,
    draftRowId: draftInfo.draftRow
      ? String(draftInfo.draftRow.__id || "")
      : ""
  };
}

function vektorPosSaveRows(req) {
  vektorAssertFunctionAllowed_("vektorPosSaveRows");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var rowsToSave = Array.isArray(req.rows) ? req.rows : [];
  if (!rowsToSave.length) return { ok: true, saved: 0, rows: [] };

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);
    var byId = {};

    (data.rows || []).forEach(function(r, idx) {
      byId[String(r.__id || "")] = idx;
    });

    var lojasMap = vektorPosBuildStoreMap_(
      vektorPosReadData_("LOJAS").rows || []
    );
    var readOnly = vektorPosReadOnlyColumns_(empresa);
    var statusHeader = empresa === "NIKE" ? "STATUS" : "Status";
    var saved = 0;
    var updatedRows = [];

    rowsToSave.forEach(function(inRow) {
      var id = String(inRow.__id || "").trim();
      if (!id || byId[id] === undefined) return;

      var target = data.rows[byId[id]];
      var previousStatus = vektorPosGetStatus_(target, empresa);
      var sentLocked =
        vektorPosWasSent_(target);

      VEKTOR_POS_HEADERS[empresa].forEach(function(h) {
        if (
            sentLocked &&
            h !== statusHeader
          ) {
            return;
          }
        if (readOnly[h] && h !== statusHeader) return;

        if (inRow[h] !== undefined) {
          target[h] = vektorPosCellToText_(inRow[h]);
        }
      });

        if (sentLocked) {
          /*
          * Em linha enviada, apenas Status pode ser alterado.
          */
          vektorPosSyncEmailStatusField_(target);

        } else if (!vektorPosIsDraftRow_(target)) {
          vektorPosApplyOperationalFormats_(
            empresa,
            target,
            true
          );

          vektorPosApplyDerivedFields_(
            empresa,
            target,
            lojasMap,
            new Date()
          );

        } else {
          target.DIFERENÇA = "";
        }

      vektorPosApplyTimelineFields_(
        empresa,
        target,
        previousStatus,
        new Date(),
        { setFinalOnTransition: true, clearWhenReopened: true }
      );

      target.__updatedAt = vektorPosNowText_();
      target.__updatedBy = String(ctx.email || "").trim().toLowerCase();

      saved++;
      updatedRows.push(vektorPosJsonSafe_(target));
    });

    var draftInfo = vektorPosEnsureSingleDraftRow_(empresa, data, ctx);

    data.header = VEKTOR_POS_HEADERS[empresa];
    vektorPosWriteJson_(empresa, data);

    return {
      ok: true,
      saved: saved,
      rows: updatedRows,
      draftRow: vektorPosJsonSafe_(draftInfo.draftRow)
    };
  } finally {
    lock.releaseLock();
  }
}

function vektorPosAddRow(req) {
  vektorAssertFunctionAllowed_("vektorPosAddRow");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);
    data.header = VEKTOR_POS_HEADERS[empresa];

    // Nunca cria uma segunda linha vazia.
    var draftInfo = vektorPosEnsureSingleDraftRow_(empresa, data, ctx);

    if (draftInfo.changed) {
      vektorPosWriteJson_(empresa, data);
    }

    return {
      ok: true,
      row: vektorPosJsonSafe_(draftInfo.draftRow),
      reused: !draftInfo.created
    };
  } finally {
    lock.releaseLock();
  }
}

function vektorPosImportSapRows(req) {
  vektorAssertFunctionAllowed_("vektorPosImportSapRows");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var sapRows = Array.isArray(req.rows) ? req.rows : [];
  if (!sapRows.length) return { ok: true, inserted: 0, skipped: 0, rows: [] };

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);
    data.header = VEKTOR_POS_HEADERS[empresa];
    data.rows = Array.isArray(data.rows) ? data.rows : [];

    var lojasMap = vektorPosBuildStoreMap_(
      vektorPosReadData_("LOJAS").rows || []
    );

    var existingBySource = {};
    var existingByNatural = {};

    var nsuHeader = VEKTOR_POS_HEADERS[empresa][6];

    data.rows.forEach(function(row) {
      var sourceKey = String(row.__sapSourceKey || "").trim();
      if (sourceKey) existingBySource[sourceKey] = row;

      var natural = [
        vektorPosStoreCode4_(row.LOJA),
        String(row["DATA VENDA"] || "").trim(),
        String(row[nsuHeader] || "").trim()
      ].join("|");

      if (natural !== "||") {
        existingByNatural[natural] = row;
      }
    });

    var now = new Date();
    var inserted = 0;
    var skipped = 0;
    var outRows = [];

    sapRows.forEach(function(inRow, idx) {
      inRow = inRow || {};

      var loja = vektorPosStoreCode4_(inRow.loja);
      var dataVenda = vektorPosCellToText_(inRow.dataVenda);
      var nsu = vektorPosCellToText_(inRow.nsu);

      if (!loja || !dataVenda || !nsu) {
        skipped++;
        return;
      }

      if (!lojasMap[empresa + "|" + loja]) {
        throw new Error(
          "Loja " + loja +
          " não localizada no seletor de lojas de " +
          empresa +
          ". Atualize o cadastro de lojas antes de transferir."
        );
      }

      var sourceKey = String(inRow.sourceKey || "").trim();
      var naturalKey = [loja, dataVenda, nsu].join("|");
      var existing =
        (sourceKey && existingBySource[sourceKey]) ||
        existingByNatural[naturalKey];

      if (existing) {
        skipped++;
        outRows.push(vektorPosJsonSafe_(existing));
        return;
      }

      var obj = vektorPosBlankObject_(VEKTOR_POS_HEADERS[empresa]);
      var statusHeader = empresa === "NIKE" ? "STATUS" : "Status";

      obj[statusHeader] = "PENDENTE";
      obj.LOJA = empresa === "CENTAURO" ? loja : String(Number(loja));
      obj["DATA VENDA"] = dataVenda;
      obj[nsuHeader] = nsu;

      /*
       * Valor SAP fica guardado para ativar depois o preenchimento
       * de VALOR EQUALS / VALOR REGISTRADO sem reabrir o parser.
       */
      obj.__sapValor = vektorPosFormatNumberBr_(inRow.valorSap);
      obj.__sapSourceFile = vektorPosCellToText_(req.sourceFile);
      obj.__sapSourceRow = vektorPosCellToText_(inRow.sourceRow || idx + 2);
      obj.__sapSourceKey = sourceKey || (
        obj.__sapSourceFile + "|" + obj.__sapSourceRow + "|" + naturalKey
      );
      obj.__source = "SAP_EXPORT";
      obj.__createdAt = vektorPosNowText_();
      obj.__updatedAt = vektorPosNowText_();
      obj.__updatedBy = String(ctx.email || "").trim().toLowerCase();
      obj.__id = vektorPosRowId_(empresa, obj, new Date().getTime() + idx);

      vektorPosApplyOperationalFormats_(empresa, obj, true);
      vektorPosApplyDerivedFields_(empresa, obj, lojasMap, now);
      vektorPosApplyTimelineFields_(
        empresa,
        obj,
        "PENDENTE",
        now,
        { setFinalOnTransition: false, clearWhenReopened: false }
      );

      data.rows.unshift(obj);
      existingBySource[obj.__sapSourceKey] = obj;
      existingByNatural[naturalKey] = obj;
      inserted++;
      outRows.push(vektorPosJsonSafe_(obj));
    });

    var draftInfo = vektorPosEnsureSingleDraftRow_(empresa, data, ctx);

    data.meta = data.meta || {};
    data.meta.lastSapImportAt = vektorPosNowText_();
    data.meta.lastSapImportBy = String(ctx.email || "").trim().toLowerCase();
    data.meta.lastSapImportInserted = inserted;
    data.meta.lastSapImportSkipped = skipped;
    data.meta.lastSapImportSourceFile = vektorPosCellToText_(req.sourceFile);

    vektorPosWriteJson_(empresa, data);

    return {
      ok: true,
      inserted: inserted,
      skipped: skipped,
      rows: outRows,
      draftRow: vektorPosJsonSafe_(draftInfo.draftRow)
    };
  } finally {
    lock.releaseLock();
  }
}


function vektorPosDeleteRow(req) {
  vektorAssertFunctionAllowed_("vektorPosDeleteRow");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var rowId = String(req.rowId || "").trim();
  if (!rowId) throw new Error("rowId obrigatório.");

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);
    var index = -1;

    for (var i = 0; i < (data.rows || []).length; i++) {
      if (String(data.rows[i].__id || "") === rowId) {
        index = i;
        break;
      }
    }

    if (
        index >= 0 &&
        vektorPosWasSent_(data.rows[index])
      ) {
        throw new Error(
          "Esta linha já foi enviada e não pode ser excluída."
        );
      }

    var removed = null;
    if (index >= 0) {
      removed = data.rows.splice(index, 1)[0];
    }

    // Depois da exclusão, permanece somente um rascunho vazio.
    var draftInfo = vektorPosEnsureSingleDraftRow_(empresa, data, ctx);

    data.meta = data.meta || {};
    data.meta.lastDeletedAt = vektorPosNowText_();
    data.meta.lastDeletedBy = String(ctx.email || "").trim().toLowerCase();

    vektorPosWriteJson_(empresa, data);

    return {
      ok: true,
      deleted: index >= 0,
      rowId: rowId,
      loja: String((removed && removed.LOJA) || ""),
      draftRow: vektorPosJsonSafe_(draftInfo.draftRow)
    };
  } finally {
    lock.releaseLock();
  }
}

function vektorPosEnrichRow(req) {
  vektorAssertFunctionAllowed_("vektorPosEnrichRow");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var rowId = String(req.rowId || "").trim();
  var lojaInput = String(req.loja || "").trim();

  if (!rowId) throw new Error("rowId obrigatório.");

  if (!lojaInput) {
    return vektorPosDeleteRow({
      empresa: empresa,
      rowId: rowId
    });
  }

  var ctx = vektorGetUserRole_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);
    var target = null;

    for (var i = 0; i < (data.rows || []).length; i++) {
      if (String(data.rows[i].__id || "") === rowId) {
        target = data.rows[i];
        break;
      }
    }

    if (!target) throw new Error("Linha não encontrada.");

    if (vektorPosWasSent_(target)) {
      throw new Error(
        "Esta linha já foi enviada. Somente a coluna Status pode ser alterada."
      );
    }

    var digits = vektorPosStoreDigits_(lojaInput);
    target.LOJA = empresa === "CENTAURO" && digits
      ? digits.padStart(4, "0")
      : digits;

    var lojasMap = vektorPosBuildStoreMap_(
      vektorPosReadData_("LOJAS").rows || []
    );
    var result = vektorPosApplyDerivedFields_(
      empresa,
      target,
      lojasMap,
      new Date()
    );
    vektorPosApplyOperationalFormats_(empresa, target, false);

    vektorPosApplyTimelineFields_(
      empresa,
      target,
      vektorPosGetStatus_(target, empresa),
      new Date(),
      { setFinalOnTransition: false, clearWhenReopened: false }
    );

    target.__updatedAt = vektorPosNowText_();
    target.__updatedBy = String(ctx.email || "").trim().toLowerCase();

    var draftInfo = null;

    // A nova linha nasce apenas depois que a loja foi validada.
    if (result.valid) {
      draftInfo = vektorPosEnsureSingleDraftRow_(empresa, data, ctx);
    }

    vektorPosWriteJson_(empresa, data);

    return {
      ok: true,
      valid: result.valid,
      error: result.error || "",
      row: vektorPosJsonSafe_(target),
      store: result.store ? vektorPosJsonSafe_(result.store) : null,
      draftRow: draftInfo
        ? vektorPosJsonSafe_(draftInfo.draftRow)
        : null
    };
  } finally {
    lock.releaseLock();
  }
}

/* =====================================================
   ENVIO AGRUPADO: CENTAURO E FISIA POR LOJA/DATA
   ===================================================== */

function vektorPosSendSelected(req) {
  vektorAssertFunctionAllowed_("vektorPosSendSelected");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};

  var empresa = vektorPosNormEmpresa_(req.empresa);

  var ids = Array.isArray(req.rowIds)
    ? req.rowIds
        .map(function(x) {
          return String(x || "").trim();
        })
        .filter(Boolean)
    : [];

  if (!ids.length) {
    throw new Error("Nenhuma linha selecionada.");
  }

  var config = vektorPosGetConfig_();
  var ctx = vektorGetUserRole_();

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var data = vektorPosReadData_(empresa);

    data.header = VEKTOR_POS_HEADERS[empresa];
    data.rows = data.rows || [];

    var idxById = {};

    data.rows.forEach(function(row, index) {
      idxById[String(row.__id || "")] = index;
    });

    var lojasMap = vektorPosBuildStoreMap_(
      vektorPosReadData_("LOJAS").rows || []
    );

    var disparos = vektorPosReadData_("DISPAROS");

    disparos.header = VEKTOR_POS_HEADERS.DISPAROS;
    disparos.rows = disparos.rows || [];

    var tz =
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo";

    var now = new Date();

    var sendDateIso = Utilities.formatDate(
      now,
      tz,
      "yyyy-MM-dd"
    );

    var sendDateBr = Utilities.formatDate(
      now,
      tz,
      "dd/MM/yyyy"
    );

    var selected = [];
    var preIgnored = [];

    ids.forEach(function(id) {
      var idx = idxById[id];

      if (idx === undefined) {
        preIgnored.push({
          rowId: id,
          status: "IGNORADO",
          error: "Linha não encontrada."
        });

        return;
      }

      var row = data.rows[idx];

      /*
       * Uma linha enviada não pode ser disparada novamente.
       */
      if (vektorPosWasSent_(row)) {
        preIgnored.push({
          rowId: id,
          loja: String(row.LOJA || ""),
          status: "IGNORADO",
          error: "Esta linha já possui envio concluído."
        });

        return;
      }

      /*
       * Linhas encerradas ou fora das condições de envio
       * passam a mostrar ERRO na tabela.
       */
      if (!vektorPosIsSendPending_(row, empresa)) {
        var pendingError =
          "Linha não está pendente para envio.";

        vektorPosSetEmailStatus_(
          row,
          "ERRO",
          pendingError
        );

        row.__updatedAt =
          vektorPosNowText_();

        row.__updatedBy =
          String(ctx.email || "")
            .trim()
            .toLowerCase();

        preIgnored.push({
          rowId: id,
          loja: String(row.LOJA || ""),
          status: "ERRO",
          error: pendingError
        });

        return;
      }

      var loja4 = vektorPosStoreCode4_(
        vektorPosGetLoja_(row)
      );

      if (!loja4) {
        var storeNumberError =
          "Número de loja inválido.";

        vektorPosSetEmailStatus_(
          row,
          "ERRO",
          storeNumberError
        );

        row.__updatedAt =
          vektorPosNowText_();

        row.__updatedBy =
          String(ctx.email || "")
            .trim()
            .toLowerCase();

        preIgnored.push({
          rowId: id,
          status: "ERRO",
          error: storeNumberError
        });

        return;
      }

      var derived;
      var store;

      /*
       * Trata erros de validação desta linha sem interromper
       * o processamento das demais linhas selecionadas.
       */
      try {
        /*
         * Normaliza data e valores e calcula DIFERENÇA.
         */
        vektorPosApplyOperationalFormats_(
          empresa,
          row,
          true
        );

        /*
         * Confere os campos obrigatórios depois
         * que a DIFERENÇA já foi calculada.
         */
        vektorPosValidateRequiredSendFields_(
          empresa,
          row
        );

        /*
         * Valida a loja e preenche os campos derivados.
         */
        derived = vektorPosApplyDerivedFields_(
          empresa,
          row,
          lojasMap,
          now
        );

        store =
          derived && derived.store
            ? derived.store
            : lojasMap[empresa + "|" + loja4];

      } catch (validationError) {
        var validationMessage =
          validationError &&
          validationError.message
            ? validationError.message
            : String(validationError);

        vektorPosSetEmailStatus_(
          row,
          "ERRO",
          validationMessage
        );

        row.__updatedAt =
          vektorPosNowText_();

        row.__updatedBy =
          String(ctx.email || "")
            .trim()
            .toLowerCase();

        preIgnored.push({
          rowId: id,
          loja: loja4,
          status: "ERRO",
          error: validationMessage
        });

        return;
      }

      if (
        (
          !derived ||
          derived.valid !== true ||
          !store
        ) &&
        config.allowSendWithoutStoreConfig !== true
      ) {
        var storeError =
          derived && derived.error
            ? derived.error
            : "Loja não cadastrada na página Lojas.";

        vektorPosSetEmailStatus_(
          row,
          "ERRO",
          storeError
        );

        row.__updatedAt =
          vektorPosNowText_();

        row.__updatedBy =
          String(ctx.email || "")
            .trim()
            .toLowerCase();

        preIgnored.push({
          rowId: id,
          loja: loja4,
          status: "ERRO",
          error: storeError
        });

        return;
      }

      selected.push({
        id: id,
        row: row,
        loja4: loja4,
        store: store || {},
        groupKey: "LOJA|" + loja4,
        groupLabel: loja4
      });
    });

    var groups = {};

    selected.forEach(function(item) {
      if (!groups[item.groupKey]) {
        groups[item.groupKey] = {
          key: item.groupKey,
          label: item.groupLabel,
          loja4: item.loja4,
          items: [],
          store: item.store || {}
        };
      }

      groups[item.groupKey]
        .items
        .push(item);
    });

    var groupKeys =
      Object.keys(groups);

    var maxSend = Math.max(
      1,
      Math.min(
        Number(config.maxSendPerRun || 100),
        100
      )
    );

    if (groupKeys.length > maxSend) {
      throw new Error(
        "Limite por execução: " +
        maxSend +
        " lojas/e-mails agrupados."
      );
    }

    var existingSendKeys = {};

    disparos.rows.forEach(function(disparo) {
      var status = String(
        disparo.STATUS || ""
      )
        .trim()
        .toUpperCase();

      if (status !== "ENVIADO") {
        return;
      }

      var existingKey = String(
        disparo.SEND_KEY || ""
      ).trim();

      if (existingKey) {
        existingSendKeys[existingKey] = true;
      }
    });

    var emailsEnviados = 0;
    var linhasEnviadas = 0;

    var erros = preIgnored.filter(function(item) {
      return String(
        item.status || ""
      ).toUpperCase() === "ERRO";
    }).length;

    var ignorados = preIgnored.filter(function(item) {
      return String(
        item.status || ""
      ).toUpperCase() !== "ERRO";
    }).length;

    var details =
      preIgnored.slice();

    groupKeys.forEach(function(key) {
      var group = groups[key];
      var items = group.items;
      var loja4 = group.loja4;

      var rows = items.map(function(item) {
        return item.row;
      });

      var rowIds = items.map(function(item) {
        return item.id;
      });

      var store =
        group.store || {};

      /*
       * Define o destinatário.
       *
       * Para lojas de teste, utiliza o destinatário
       * definido em vektorPosGetTestConfig_().
       */
      var routing = vektorPosResolveSendRouting_(
        empresa,
        loja4,
        rows,
        store,
        config
      );

      var to = String(
        routing.to || ""
      ).trim();

      var cc = String(
        routing.cc || ""
      ).trim();

      /*
       * Testes recebem chave única para não serem
       * bloqueados pelo controle diário da loja.
       */
      var sendKey =
        empresa +
        "|LOJA|" +
        loja4 +
        "|" +
        sendDateIso;

      var assunto =
        vektorPosBuildGroupSubjectForDate_(
          empresa,
          {
            loja4: loja4,
            store: store,
            items: items
          },
          now
        );

      var hash =
        vektorPosBuildGroupHash_(
          sendKey,
          rowIds,
          to
        );

      /*
       * O bloqueio por loja/data continua funcionando
       * somente para envios reais.
       */
        if (
          existingSendKeys[sendKey]
        ) {
        var duplicateError =
          "Já existe envio concluído para a loja " +
          loja4 +
          " na data " +
          sendDateBr +
          ".";

        rows.forEach(function(row) {
          vektorPosSetEmailStatus_(
            row,
            "ERRO",
            duplicateError
          );

          row.__updatedAt =
            vektorPosNowText_();

          row.__updatedBy =
            String(ctx.email || "")
              .trim()
              .toLowerCase();
        });

        erros++;

        vektorPosAppendDisparo_(
          disparos,
          ctx,
          empresa,
          sendKey,
          loja4,
          assunto,
          to,
          cc,
          rowIds,
          "ERRO",
          duplicateError,
          hash
        );

        details.push({
          agrupamento: loja4,
          tipoAgrupamento: "LOJA",
          status: "ERRO",
          error: duplicateError,
          rowIds: rowIds
        });

        return;
      }

      if (!to) {
        var recipientError =
          "Destinatário vazio.";

        rows.forEach(function(row) {
          vektorPosSetEmailStatus_(
            row,
            "ERRO",
            recipientError
          );

          row.__updatedAt =
            vektorPosNowText_();

          row.__updatedBy =
            String(ctx.email || "")
              .trim()
              .toLowerCase();
        });

        erros++;

        vektorPosAppendDisparo_(
          disparos,
          ctx,
          empresa,
          sendKey,
          loja4,
          assunto,
          "",
          cc,
          rowIds,
          "ERRO",
          recipientError,
          hash
        );

        details.push({
          agrupamento: loja4,
          tipoAgrupamento: "LOJA",
          status: "ERRO",
          error: recipientError,
          rowIds: rowIds
        });

        return;
      }

      try {
        /*
         * Monta o corpo HTML do e-mail.
         */
        var htmlBody =
          vektorPosBuildGroupedEmailHtml_(
            empresa,
            rows,
            assunto,
            {
              loja4: loja4,
              lojas: [loja4],
              store: store
            },
            ctx.email
          );

        /*
 * Remetente configurado para o POS.
 */
var requestedFrom = String(
  config.emailFrom ||
  VEKTOR_POS_EMAIL_FROM ||
  ""
)
  .trim()
  .toLowerCase();

var requestedFromName = String(
  config.emailName ||
  VEKTOR_POS_EMAIL_NAME ||
  "Vektor"
).trim();

/*
 * Registra os dados preparados antes do disparo.
 */
console.log(
  JSON.stringify({
    evento:
      "EMAIL_PREPARADO_PARA_ENVIO",
    empresa:
      empresa,
    loja:
      loja4,
    destinatario:
      to,
    cc:
      cc,
    contaExecutora:
      Session.getEffectiveUser().getEmail(),
    remetenteUsado:
      requestedFrom,
    canal:
      "GMAIL_API"
  })
);

/*
 * Envia pela Gmail API.
 *
 * IMPORTANTE:
 * não utiliza GmailApp.getAliases()
 * nem GmailApp.sendEmail().
 */
vektorPosSendViaGmailApi_({
  to: to,
  cc: cc,
  subject: assunto,
  htmlBody: htmlBody,
  from: requestedFrom,
  fromName: requestedFromName,
  replyTo:
    "usuario01@empresa.exemplo"
});

        /*
         * Este log só é executado depois que
         * GmailApp.sendEmail termina sem lançar erro.
         */
        console.log(
          JSON.stringify({
            evento:
              "EMAIL_ENVIADO_PELA_GMAIL_API",
            data:
              new Date().toISOString(),
            empresa:
              empresa,
            loja:
              loja4,
            destinatario:
              to,
            remetente:
              requestedFrom || "",
            assunto:
              assunto
          })
        );

        rows.forEach(function(row) {
          var subjectHeader =
            VEKTOR_POS_HEADERS[empresa][0];

          row[subjectHeader] =
            assunto;

          row["DATA COBRANÇA"] =
            sendDateBr;

          vektorPosApplyTimelineFields_(
            empresa,
            row,
            vektorPosGetStatus_(
              row,
              empresa
            ),
            now,
            {
              setFinalOnTransition: false,
              clearWhenReopened: false
            }
          );

          /*
          * PRODUÇÃO:
          * todo envio concluído recebe trava definitiva.
          */
          row.__sentAt =
            vektorPosNowText_();

          row.__sendKey =
            sendKey;

          /*
          * Limpa eventuais marcas deixadas
          * pelos testes realizados anteriormente.
          */
          delete row.__testMode;
          delete row.__testSentAt;
          delete row.__testSendKey;

          vektorPosSetEmailStatus_(
            row,
            "ENVIADO",
            ""
          );

          row.__updatedAt =
            vektorPosNowText_();

          row.__updatedBy =
            String(ctx.email || "")
              .trim()
              .toLowerCase();
        });

        emailsEnviados++;
        linhasEnviadas +=
          rows.length;

        existingSendKeys[sendKey] =
          true;

        vektorPosAppendDisparo_(
          disparos,
          ctx,
          empresa,
          sendKey,
          loja4,
          assunto,
          to,
          cc,
          rowIds,
          "ENVIADO",
          "",
          hash
        );

        details.push({
          agrupamento:
            loja4,
          tipoAgrupamento:
            "LOJA",
          loja:
            loja4,
          status:
            "ENVIADO",
          assunto:
            assunto,
          to:
            to,
          cc:
            cc,
          qtdLinhas:
            rows.length,
          rowIds:
            rowIds
        });

      } catch (sendErr) {
        var errMsg =
          sendErr &&
          sendErr.message
            ? sendErr.message
            : String(sendErr);

        console.error(
          JSON.stringify({
            evento:
              "ERRO_NO_GMAILAPP",
            empresa:
              empresa,
            loja:
              loja4,
            destinatario:
              to,
            erro:
              errMsg
          })
        );

        rows.forEach(function(row) {
          vektorPosSetEmailStatus_(
            row,
            "ERRO",
            errMsg
          );

          row.__updatedAt =
            vektorPosNowText_();

          row.__updatedBy =
            String(ctx.email || "")
              .trim()
              .toLowerCase();
        });

        erros++;

        vektorPosAppendDisparo_(
          disparos,
          ctx,
          empresa,
          sendKey,
          loja4,
          assunto,
          to,
          cc,
          rowIds,
          "ERRO",
          errMsg,
          hash
        );

        details.push({
          agrupamento:
            loja4,
          tipoAgrupamento:
            "LOJA",
          loja:
            loja4,
          status:
            "ERRO",
          error:
            errMsg,
          to:
            to,
          cc:
            cc,
          rowIds:
            rowIds
        });
      }
    });

    data.header =
      VEKTOR_POS_HEADERS[empresa];

    vektorPosWriteJson_(
      empresa,
      data
    );

    vektorPosWriteJson_(
      "DISPAROS",
      disparos
    );

    return {
      ok: true,

      criterioAgrupamento:
        "LOJA_DATA_ENVIO",

      enviados:
        emailsEnviados,

      linhasEnviadas:
        linhasEnviadas,

      erros:
        erros,

      ignorados:
        ignorados,

      details:
        details
    };

  } finally {
    lock.releaseLock();
  }
}

/**
 * POS | Envio de e-mail pela Gmail API
 *
 * Evita GmailApp.sendEmail / GmailApp.getAliases,
 * que estão sujeitos ao bloqueio "premium gmail".
 */
function vektorPosSendViaGmailApi_(params) {
  params = params || {};

  var to = String(params.to || "").trim();
  var cc = String(params.cc || "").trim();
  var subject = String(params.subject || "").trim();
  var htmlBody = String(params.htmlBody || "");
  var from = String(
    params.from ||
    VEKTOR_POS_EMAIL_FROM ||
    ""
  ).trim().toLowerCase();

  var fromName = String(
    params.fromName ||
    VEKTOR_POS_EMAIL_NAME ||
    "Vektor"
  ).trim();

  var replyTo = String(
    params.replyTo ||
    VEKTOR_POS_EMAIL_CC_DEFAULT ||
    ""
  ).trim();

  if (!to) {
    throw new Error(
      "Gmail API: destinatário não informado."
    );
  }

  if (!from) {
    throw new Error(
      "Gmail API: remetente não informado."
    );
  }

  /*
   * Protege os cabeçalhos contra quebra de linha.
   */
  to = vektorPosEmailHeaderSafe_(to);
  cc = vektorPosEmailHeaderSafe_(cc);
  from = vektorPosEmailHeaderSafe_(from);
  replyTo = vektorPosEmailHeaderSafe_(replyTo);
  subject = vektorPosEmailHeaderSafe_(subject);
  fromName = vektorPosEmailHeaderSafe_(fromName);

  /*
   * Codificação RFC 2047 para acentos no nome e assunto.
   */
  var encodedFromName =
    vektorPosMimeHeaderUtf8_(fromName);

  var encodedSubject =
    vektorPosMimeHeaderUtf8_(subject);

  /*
   * Corpo HTML em Base64.
   */
  var bodyBase64 =
    Utilities.base64Encode(
      htmlBody,
      Utilities.Charset.UTF_8
    );

  /*
   * Quebra em linhas MIME de até 76 caracteres.
   */
  var bodyLines =
    bodyBase64.match(/.{1,76}/g) || [];

  var mime = [
    "MIME-Version: 1.0",
    "From: " +
      encodedFromName +
      " <" +
      from +
      ">",
    "To: " + to
  ];

  if (cc) {
    mime.push(
      "Cc: " + cc
    );
  }

  if (replyTo) {
    mime.push(
      "Reply-To: " + replyTo
    );
  }

  mime.push(
    "Subject: " + encodedSubject,
    'Content-Type: text/html; charset="UTF-8"',
    "Content-Transfer-Encoding: base64",
    "",
    bodyLines.join("\r\n")
  );

  var rawMime =
    mime.join("\r\n");

  /*
   * A Gmail API exige mensagem RFC 2822
   * codificada em Base64 URL-safe.
   */
  var raw =
    Utilities
      .base64EncodeWebSafe(
        rawMime,
        Utilities.Charset.UTF_8
      )
      .replace(/=+$/g, "");

  var response =
    UrlFetchApp.fetch(
      "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
      {
        method: "post",
        contentType: "application/json",
        headers: {
          Authorization:
            "Bearer " +
            ScriptApp.getOAuthToken()
        },
        payload: JSON.stringify({
          raw: raw
        }),
        muteHttpExceptions: true
      }
    );

  var statusCode =
    response.getResponseCode();

  var responseText =
    response.getContentText() || "";

  if (
    statusCode < 200 ||
    statusCode >= 300
  ) {
    var apiMessage = responseText;

    try {
      var apiJson =
        JSON.parse(responseText);

      if (
        apiJson &&
        apiJson.error &&
        apiJson.error.message
      ) {
        apiMessage =
          apiJson.error.message;
      }
    } catch (ignore) {}

    throw new Error(
      "Gmail API retornou HTTP " +
      statusCode +
      ": " +
      apiMessage
    );
  }

  var result = {};

  try {
    result =
      JSON.parse(responseText || "{}");
  } catch (ignore) {}

  console.log(
    JSON.stringify({
      evento:
        "EMAIL_ENVIADO_PELA_GMAIL_API",
      messageId:
        String(result.id || ""),
      threadId:
        String(result.threadId || ""),
      destinatario:
        to,
      cc:
        cc,
      remetente:
        from,
      assunto:
        subject
    })
  );

  return {
    ok: true,
    id: String(result.id || ""),
    threadId:
      String(result.threadId || "")
  };
}


function vektorPosMimeHeaderUtf8_(value) {
  value =
    String(value || "");

  return (
    "=?UTF-8?B?" +
    Utilities.base64Encode(
      value,
      Utilities.Charset.UTF_8
    ) +
    "?="
  );
}


function vektorPosEmailHeaderSafe_(value) {
  return String(value || "")
    .replace(/[\r\n]+/g, " ")
    .trim();
}

/* =====================================================
   IMPORTAÇÃO / CONFIG / RELATÓRIOS
   ===================================================== */

function vektorPosImportData(req) {
  vektorAssertFunctionAllowed_("vektorPosImportData");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};
  var kind = String(req.kind || "").trim().toUpperCase();

  // A última extração SAP pertence ao módulo POS, não a uma sessão do
  // navegador. Leitura e gravação ficam disponíveis aos usuários do módulo;
  // as importações cadastrais abaixo continuam exclusivas do Administrador.
  if (kind === "SAP_EXPORT_SNAPSHOT_GET") {
    return vektorPosGetSapExportSnapshot_();
  }
  if (kind === "SAP_EXPORT_SNAPSHOT_SAVE") {
    return vektorPosSaveSapExportSnapshot_(req.snapshot || {});
  }

  vektorPosAssertAdmin_();

  if (kind !== "CENTAURO" && kind !== "NIKE" && kind !== "LOJAS") {
    throw new Error("Tipo de importação inválido: " + kind);
  }

  var inputHeader = Array.isArray(req.header)
    ? req.header.map(function(h) { return String(h || "").trim(); }).filter(Boolean)
    : [];
  var rowsArr = Array.isArray(req.rows) ? req.rows : [];
  var targetHeader = VEKTOR_POS_HEADERS[kind] || VEKTOR_POS_HEADERS.LOJAS;
  var ctx = vektorGetUserRole_();
  var now = vektorPosNowText_();

  var rows = rowsArr.map(function(line, idx) {
    var source = {};
    if (Array.isArray(line)) {
      inputHeader.forEach(function(h, c) { source[h] = vektorPosCellToText_(line[c]); });
    } else if (line && typeof line === "object") {
      Object.keys(line).forEach(function(h) { source[h] = vektorPosCellToText_(line[h]); });
    }

    var obj = vektorPosBlankObject_(targetHeader);
    targetHeader.forEach(function(h) {
      obj[h] = vektorPosGetSourceValue_(source, h);
    });
    obj.__id = vektorPosRowId_(kind, obj, idx + 1);
    obj.__createdAt = now;
    obj.__updatedAt = now;
    obj.__updatedBy = String(ctx.email || "").trim().toLowerCase();
    vektorPosCarryLegacyInternalFields_(kind, source, obj);
    if (kind === "CENTAURO" || kind === "NIKE") {
      vektorPosApplyOperationalFormats_(kind, obj, false);
    }
    if (kind === "CENTAURO" || kind === "NIKE") {
      vektorPosApplyTimelineFields_(
        kind,
        obj,
        vektorPosGetStatus_(obj, kind),
        new Date(),
        { setFinalOnTransition: false, clearWhenReopened: false }
      );
    }
    return obj;
  });

  vektorPosWriteJson_(kind, {
    meta: {
      version: VEKTOR_POS_SCHEMA_VERSION,
      kind: kind,
      importedAt: now,
      importedBy: String(ctx.email || "").trim().toLowerCase(),
      source: "HTML_IMPORT",
      totalRows: rows.length
    },
    header: targetHeader,
    rows: rows
  });

  return { ok: true, kind: kind, rowsImported: rows.length, header: targetHeader };
}

function vektorPosGetSapExportSnapshot_() {
  var data = vektorPosReadJson_("SAP_EXPORT_SNAPSHOT") || {};
  var snapshot = data.snapshot;

  if (
    !snapshot ||
    !Array.isArray(snapshot.header) ||
    !Array.isArray(snapshot.rows) ||
    !snapshot.header.length
  ) {
    return {
      ok: true,
      found: false,
      snapshot: null
    };
  }

  return {
    ok: true,
    found: true,
    snapshot: vektorPosJsonSafe_({
      header: snapshot.header,
      rows: snapshot.rows,
      arquivo: snapshot.arquivo || "",
      nomeArquivo: snapshot.nomeArquivo || "",
      loadedAt: snapshot.loadedAt || "",
      clientVersion: Number(snapshot.clientVersion || 0),
      savedAt: (data.meta && data.meta.savedAt) || ""
    })
  };
}

function vektorPosSaveSapExportSnapshot_(snapshot) {
  snapshot = snapshot || {};

  var header = Array.isArray(snapshot.header)
    ? snapshot.header.map(function(h) {
        return String(h || "").trim();
      }).filter(Boolean)
    : [];

  if (!header.length) {
    throw new Error("A planilha SAP não possui cabeçalho para ser salva.");
  }

  var inputRows = Array.isArray(snapshot.rows) ? snapshot.rows : [];
  var rows = inputRows.map(function(line) {
    var out = {};
    header.forEach(function(h, columnIndex) {
      var value = Array.isArray(line)
        ? line[columnIndex]
        : line && typeof line === "object"
          ? line[h]
          : "";
      out[h] = vektorPosCellToText_(value);
    });
    return out;
  });

  var ctx = vektorGetUserRole_();
  var savedAt = vektorPosNowText_();
  var clientVersion = Math.max(0, Number(snapshot.clientVersion || 0));
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var current = vektorPosReadJson_("SAP_EXPORT_SNAPSHOT") || {};
    var currentVersion = Number(
      current.snapshot && current.snapshot.clientVersion || 0
    );

    // Protege a última base quando duas exportações terminam quase juntas:
    // uma resposta mais antiga nunca pode sobrescrever a mais recente.
    if (clientVersion && currentVersion > clientVersion) {
      return {
        ok: true,
        stale: true,
        savedAt: String(current.meta && current.meta.savedAt || ""),
        totalRows: Number(current.meta && current.meta.totalRows || 0)
      };
    }

    vektorPosWriteJson_("SAP_EXPORT_SNAPSHOT", {
      meta: {
        version: VEKTOR_POS_SCHEMA_VERSION,
        kind: "SAP_EXPORT_SNAPSHOT",
        savedAt: savedAt,
        savedBy: String(ctx.email || "").trim().toLowerCase(),
        totalRows: rows.length
      },
      snapshot: {
        header: header,
        rows: rows,
        arquivo: String(snapshot.arquivo || "").trim(),
        nomeArquivo: String(snapshot.nomeArquivo || "").trim(),
        loadedAt: String(snapshot.loadedAt || "").trim(),
        clientVersion: clientVersion
      }
    });
  } finally {
    lock.releaseLock();
  }

  return {
    ok: true,
    savedAt: savedAt,
    totalRows: rows.length
  };
}

function vektorPosGetConfig() {
  vektorAssertFunctionAllowed_("vektorPosGetConfig");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
  var ctx = vektorGetUserRole_();
  return {
    ok: true,
    config: vektorPosGetConfig_(),
    ai: vektorPosPedroGetAiConfigStatus_(ctx)
  };
}

function vektorPosSaveConfig(req) {
  vektorAssertFunctionAllowed_("vektorPosSaveConfig");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);
  vektorPosAssertAdmin_();

  req = req || {};
  var config = req.config || {};
  var current = vektorPosGetConfig_();
  var ctx = vektorGetUserRole_();

  if (
    req.aiConfig &&
    typeof req.aiConfig === "object" &&
    !vektorPosPedroCanManageAi_(ctx, vektorPosPedroGetAiConfig_())
  ) {
    throw new Error("Apenas o responsavel pelo Agente POS pode alterar esta configuracao.");
  }

  Object.keys(VEKTOR_POS_DEFAULT_CONFIG).forEach(function(k) {
    if (config[k] !== undefined) current[k] = config[k];
  });
  current.maxSendPerRun = Math.max(1, Math.min(Number(current.maxSendPerRun || 100), 100));

  vektorPosWriteJson_("CONFIG", {
    meta: {
      version: VEKTOR_POS_SCHEMA_VERSION,
      updatedAt: vektorPosNowText_(),
      updatedBy: String(ctx.email || "").trim().toLowerCase()
    },
    config: current
  });

  if (req.aiConfig && typeof req.aiConfig === "object") {
    vektorPosPedroSaveAiConfig_(req.aiConfig, ctx);
  }

  return {
    ok: true,
    config: current,
    ai: vektorPosPedroGetAiConfigStatus_(ctx)
  };
}

function vektorPosGetReports(req) {
  vektorAssertFunctionAllowed_(
    "vektorPosGetReports"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_POS_MODULE_KEY
  );

  req = req || {};

  var empresaSelecionada =
    vektorPosNormEmpresa_(
      req.empresa
    );

  var tz =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  var lojasMap =
    vektorPosBuildStoreMap_(
      vektorPosReadData_(
        "LOJAS"
      ).rows || []
    );

  var disparos =
    vektorPosReadData_(
      "DISPAROS"
    ).rows || [];

  function getMonthLabel_(row) {
    var monthValue = String(
      row["MÊS PENDÊNCIA"] || ""
    ).trim();

    var monthMatch =
      monthValue.match(
        /^(0[1-9]|1[0-2])\/(\d{4})$/
      );

    if (monthMatch) {
      return monthValue;
    }

    /*
     * Pendências ainda não enviadas normalmente
     * não possuem DATA COBRANÇA. Nesses casos,
     * usa o mês da DATA VENDA.
     */
    var saleDate =
      vektorPosParseDate_(
        row["DATA VENDA"]
      );

    if (saleDate) {
      return Utilities.formatDate(
        saleDate,
        tz,
        "MM/yyyy"
      );
    }

    return "SEM MÊS";
  }

  function monthOrder_(label) {
    var match = String(
      label || ""
    ).match(
      /^(\d{2})\/(\d{4})$/
    );

    if (!match) {
      return 999999;
    }

    return (
      Number(match[2]) * 12 +
      Number(match[1])
    );
  }

  function countMapToArray_(
    map,
    alphabetical
  ) {
    return Object.keys(map || {})
      .map(function(label) {
        return {
          label: label,
          value: Number(
            map[label] || 0
          )
        };
      })
      .sort(function(a, b) {
        if (b.value !== a.value) {
          return b.value - a.value;
        }

        return alphabetical
          ? a.label.localeCompare(
              b.label,
              "pt-BR",
              {
                numeric: true,
                sensitivity: "base"
              }
            )
          : 0;
      });
  }

  function buildCompanyReport_(
    empresa
  ) {
    var allRows =
      vektorPosReadData_(
        empresa
      ).rows || [];

    /*
     * A linha de rascunho vazia não deve
     * ser contada no relatório.
     */
    var rows =
      allRows.filter(function(row) {
        return !vektorPosIsDraftRow_(
          row
        );
      });

    var byStatus = {};
    var pendingByMonthMap = {};
    var pendingByStoreMap = {};
    var pendingByTimeMap = {};

    var pendentes = 0;
    var emTratativa = 0;
    var finalizados = 0;
    var enviados = 0;
    var valorDiferenca = 0;
    var hasTimeData = false;

    rows.forEach(function(row) {
      var status =
        vektorPosGetStatus_(
          row,
          empresa
        ) || "SEM STATUS";

      byStatus[status] =
        (byStatus[status] || 0) + 1;

      if (
        status.indexOf(
          "TRATATIVA"
        ) === 0
      ) {
        emTratativa++;
      }

      if (
        status === "OK" ||
        status === "PERDA"
      ) {
        finalizados++;
      }

      var emailStatus = String(
        row["STATUS ENVIO"] ||
        row.__emailStatus ||
        ""
      )
        .trim()
        .toUpperCase();

      if (
        emailStatus === "ENVIADO" ||
        String(
          row.__sentAt ||
          row.__sendKey ||
          ""
        ).trim()
      ) {
        enviados++;
      }

      valorDiferenca +=
        vektorPosParseNumber_(
          row.DIFERENÇA
        );

      /*
       * Os rankings solicitados consideram
       * exclusivamente o status PENDENTE.
       */
      if (status !== "PENDENTE") {
        return;
      }

      pendentes++;

      var monthLabel =
        getMonthLabel_(row);

      pendingByMonthMap[
        monthLabel
      ] =
        (
          pendingByMonthMap[
            monthLabel
          ] || 0
        ) + 1;

      var loja4 =
        vektorPosStoreCode4_(
          vektorPosGetLoja_(row)
        ) || "SEM LOJA";

      pendingByStoreMap[
        loja4
      ] =
        (
          pendingByStoreMap[
            loja4
          ] || 0
        ) + 1;

      /*
       * A base Nike não possui a coluna Time.
       * Portanto, esse ranking é calculado
       * somente para a Centauro.
       */
      if (empresa === "CENTAURO") {
        var store =
          lojasMap[
            empresa +
            "|" +
            loja4
          ] || {};

        var time = String(
          row.Time ||
          store.TIME ||
          ""
        ).trim();

        if (time) {
          hasTimeData = true;

          pendingByTimeMap[
            time
          ] =
            (
              pendingByTimeMap[
                time
              ] || 0
            ) + 1;
        }
      }
    });

    var pendingByMonth =
      Object.keys(
        pendingByMonthMap
      )
        .map(function(label) {
          return {
            label: label,
            value: Number(
              pendingByMonthMap[
                label
              ] || 0
            )
          };
        })
        .sort(function(a, b) {
          return (
            monthOrder_(a.label) -
            monthOrder_(b.label)
          );
        });

    var pendingByStore =
      countMapToArray_(
        pendingByStoreMap,
        true
      );

    var pendingByTime =
      countMapToArray_(
        pendingByTimeMap,
        true
      );

    var disparosEmpresa =
      disparos.filter(
        function(disparo) {
          return String(
            disparo.EMPRESA || ""
          )
            .trim()
            .toUpperCase() ===
            empresa;
        }
      );

    var errosDisparo =
      disparosEmpresa.filter(
        function(disparo) {
          return String(
            disparo.STATUS || ""
          )
            .trim()
            .toUpperCase() ===
            "ERRO";
        }
      ).length;

    return {
      empresa: empresa,
      total: rows.length,
      pendentes: pendentes,
      emTratativa: emTratativa,
      enviados: enviados,
      conciliados: finalizados,
      valorDiferenca:
        valorDiferenca,
      disparos:
        disparosEmpresa.length,
      errosDisparo:
        errosDisparo,
      byStatus:
        byStatus,
      pendingByMonth:
        pendingByMonth,
      pendingByStore:
        pendingByStore,
      pendingByTime:
        pendingByTime,

      topPendingStore:
        pendingByStore.length
          ? pendingByStore[0]
          : null,

      topPendingTime:
        pendingByTime.length
          ? pendingByTime[0]
          : null,

      hasTimeData:
        hasTimeData
    };
  }

  /*
   * A mesma requisição monta as duas empresas
   * para permitir o gráfico comparativo.
   */
  var companies = {
    CENTAURO:
      buildCompanyReport_(
        "CENTAURO"
      ),

    NIKE:
      buildCompanyReport_(
        "NIKE"
      )
  };

  var selected =
    companies[
      empresaSelecionada
    ];

  var statusSet = {};

  Object.keys(
    companies.CENTAURO.byStatus || {}
  ).forEach(function(status) {
    statusSet[status] = true;
  });

  Object.keys(
    companies.NIKE.byStatus || {}
  ).forEach(function(status) {
    statusSet[status] = true;
  });

  var statusOrder = {
    "PENDENTE": 1,
    "TRATATIVA - LOJA": 2,
    "TRATATIVA - FIN": 3,
    "TRATATIVA - T.I.": 4,
    "OK": 5,
    "PERDA": 6,
    "SEM STATUS": 7
  };

  var statusComparison =
    Object.keys(statusSet)
      .sort(function(a, b) {
        var orderA =
          statusOrder[a] || 99;

        var orderB =
          statusOrder[b] || 99;

        if (orderA !== orderB) {
          return orderA - orderB;
        }

        return a.localeCompare(
          b,
          "pt-BR",
          {
            sensitivity: "base"
          }
        );
      })
      .map(function(status) {
        return {
          status: status,

          CENTAURO: Number(
            companies
              .CENTAURO
              .byStatus[
                status
              ] || 0
          ),

          NIKE: Number(
            companies
              .NIKE
              .byStatus[
                status
              ] || 0
          )
        };
      });

  return {
    ok: true,
    empresa:
      empresaSelecionada,

    /*
     * Compatibilidade com os campos antigos.
     */
    total:
      selected.total,

    pendentes:
      selected.pendentes,

    enviados:
      selected.enviados,

    conciliados:
      selected.conciliados,

    valorDiferenca:
      selected.valorDiferenca,

    disparos:
      selected.disparos,

    errosDisparo:
      selected.errosDisparo,

    byStatus:
      selected.byStatus,

    /*
     * Nova estrutura completa.
     */
    selected:
      selected,

    companies:
      companies,

    statusComparison:
      statusComparison,

    pendingByMonth:
      selected.pendingByMonth,

    pendingByStore:
      selected.pendingByStore,

    pendingByTime:
      selected.pendingByTime,

    topPendingStore:
      selected.topPendingStore,

    topPendingTime:
      selected.topPendingTime,

    hasTimeData:
      selected.hasTimeData
  };
}

/* =====================================================
   PEDRO — AGENTE DE CONCILIACAO POS
   ===================================================== */

function vektorPosPedroAnalyze(req) {
  vektorAssertFunctionAllowed_("vektorPosPedroAnalyze");
  vektorAssertModuleAllowed_(VEKTOR_POS_MODULE_KEY);

  req = req || {};

  if (String(req.action || "").trim().toUpperCase() === "COST_PERF") {
    return vektorPosJsonSafe_(vektorPosPedroGetCostPerf_(req));
  }

  var analysis = vektorPosPedroBuildAnalysis_(req);
  var aiConfig = vektorPosPedroGetAiConfig_();
  var ai = {
    configured: aiConfig.configured,
    provider: aiConfig.provider,
    model: aiConfig.model,
    projectId: aiConfig.projectId,
    text: "",
    error: "",
    usage: null
  };

  if (aiConfig.configured) {
    var apiStartedAt = new Date().getTime();

    try {
      var callResult = vektorPosPedroCallAi_(
        aiConfig,
        analysis,
        String(req.question || "").trim()
      );

      ai.text = String(callResult && callResult.text || "");
      ai.usage = callResult && callResult.usage || {};
      ai.usage.latencyMs = Math.max(
        0,
        Number(ai.usage.latencyMs || (new Date().getTime() - apiStartedAt))
      );

      try {
        vektorPosPedroAppendUsage_(
          analysis.empresa,
          aiConfig,
          ai.usage,
          "OK"
        );
      } catch (_) {}
    } catch (error) {
      ai.error = String(
        error && error.message
          ? error.message
          : error
      );

      ai.usage = {
        promptTokens: 0,
        outputTokens: 0,
        thoughtsTokens: 0,
        totalTokens: 0,
        latencyMs: Math.max(0, new Date().getTime() - apiStartedAt)
      };

      try {
        vektorPosPedroAppendUsage_(
          analysis.empresa,
          aiConfig,
          ai.usage,
          "ERROR"
        );
      } catch (_) {}
    }
  }

  return vektorPosJsonSafe_({
    ok: true,
    generatedAt: new Date().toISOString(),
    policyVersion: VEKTOR_POS_PEDRO_POLICY_VERSION,
    analysis: analysis,
    ai: ai
  });
}

function vektorPosPedroBuildAnalysis_(req) {
  var empresa = vektorPosNormEmpresa_(req.empresa);
  var allowedPeriods = {
    "30": true,
    "90": true,
    "180": true,
    "365": true,
    "0": true
  };

  var periodDays = String(req.periodDays || "90");
  if (!allowedPeriods[periodDays]) periodDays = "90";

  var today = new Date();
  var cutoff = null;
  if (Number(periodDays) > 0) {
    cutoff = new Date(today.getTime());
    cutoff.setHours(0, 0, 0, 0);
    cutoff.setDate(cutoff.getDate() - Number(periodDays));
  }

  var normalizedRows = [];
  var rows = vektorPosReadData_(empresa).rows || [];

  rows.forEach(function(row) {
      if (vektorPosIsDraftRow_(row)) return;

      var saleDate = vektorPosParseDate_(row["DATA VENDA"]);
      var chargeDate = vektorPosParseDate_(row["DATA COBRANCA"] || row["DATA COBRANÇA"]);
      var referenceDate = saleDate || chargeDate;

      if (cutoff && referenceDate && referenceDate < cutoff) return;

      var nsu = empresa === "NIKE"
        ? row["NSU TRANSAÇÃO"]
        : row.NSU;

      var evidence = String(
        row["INFORMAÇÕES"] ||
        row["OBSERVAÇÃO"] ||
        ""
      ).trim();

      var complementary = String(
        row["INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)"] ||
        ""
      ).trim();

      normalizedRows.push({
        id: String(row.__id || ""),
        empresa: empresa,
        loja: vektorPosStoreCode4_(vektorPosGetLoja_(row)) || "",
        status: vektorPosGetStatus_(row, empresa) || "SEM STATUS",
        dataVenda: saleDate,
        dataCobranca: chargeDate,
        nsu: String(nsu || "").trim(),
        valorEquals: vektorPosParseNumber_(
          row[empresa === "NIKE" ? "VALOR EQUALS" : "VALOR EQUALS (50)"]
        ),
        valorRegistrado: vektorPosParseNumber_(
          row[empresa === "NIKE" ? "VALOR REGISTRADO" : "VALOR REGISTRADO (40)"]
        ),
        diferenca: vektorPosParseNumber_(row["DIFERENÇA"]),
        evidencia: evidence || complementary,
        qtdDiasTratativa: Number(row["QTD DIAS TRATATIVA"] || 0),
        statusEnvio: String(row["STATUS ENVIO"] || row.__emailStatus || "").trim().toUpperCase()
      });
  });

  var totals = {
    all: normalizedRows.length,
    centauro: 0,
    fisia: 0,
    pending: 0,
    sent: 0,
    missingNsu: 0,
    missingSaleDate: 0,
    missingStore: 0,
    missingEvidence: 0,
    overdue: 0,
    differenceAmount: 0
  };

  var byStore = {};
  var signatures = {};
  var samples = [];

  normalizedRows.forEach(function(row) {
    if (row.empresa === "CENTAURO") totals.centauro++;
    if (row.empresa === "NIKE") totals.fisia++;
    if (row.status === "PENDENTE") totals.pending++;
    if (row.statusEnvio === "ENVIADO") totals.sent++;
    if (!row.nsu) totals.missingNsu++;
    if (!row.dataVenda) totals.missingSaleDate++;
    if (!row.loja) totals.missingStore++;
    if (!row.evidencia) totals.missingEvidence++;
    totals.differenceAmount += Number(row.diferenca || 0);

    var storeKey = row.empresa + "|" + (row.loja || "SEM LOJA");
    if (!byStore[storeKey]) {
      byStore[storeKey] = {
        empresa: row.empresa,
        loja: row.loja || "SEM LOJA",
        total: 0,
        pending: 0,
        differenceAmount: 0
      };
    }

    byStore[storeKey].total++;
    byStore[storeKey].differenceAmount += Number(row.diferenca || 0);
    if (row.status === "PENDENTE") byStore[storeKey].pending++;

    if (row.empresa && row.loja && row.nsu && row.dataVenda) {
      var signature = [
        row.empresa,
        row.loja,
        Utilities.formatDate(
          row.dataVenda,
          Session.getScriptTimeZone() || "America/Sao_Paulo",
          "yyyy-MM-dd"
        ),
        row.nsu
      ].join("|");

      if (!signatures[signature]) signatures[signature] = [];
      signatures[signature].push(row);
    }

    if (
      row.status === "PENDENTE" &&
      row.dataCobranca &&
      vektorPosPedroIsOverdue_(row.dataCobranca, today)
    ) {
      totals.overdue++;
    }

    if (
      samples.length < 60 &&
      (
        row.status === "PENDENTE" ||
        !row.nsu ||
        !row.evidencia ||
        Math.abs(Number(row.diferenca || 0)) > 0
      )
    ) {
      samples.push(vektorPosPedroPublicRow_(row));
    }
  });

  var duplicateGroups = Object.keys(signatures)
    .filter(function(key) {
      return signatures[key].length > 1;
    })
    .map(function(key) {
      return {
        signature: key,
        count: signatures[key].length,
        rows: signatures[key].slice(0, 5).map(vektorPosPedroPublicRow_)
      };
    })
    .sort(function(a, b) {
      return b.count - a.count;
    })
    .slice(0, 20);

  var recurringStores = Object.keys(byStore)
    .map(function(key) {
      return byStore[key];
    })
    .sort(function(a, b) {
      if (b.total !== a.total) return b.total - a.total;
      return b.pending - a.pending;
    })
    .slice(0, 15);

  var findings = [];

  if (duplicateGroups.length) {
    findings.push({
      severity: "high",
      title: "Possiveis duplicidades na regra 1 para 1",
      count: duplicateGroups.length,
      detail: "Mesma empresa, loja, data de venda e NSU aparecem em mais de um lancamento. Exige validacao antes de concluir duplicidade."
    });
  }

  if (totals.missingNsu) {
    findings.push({
      severity: "high",
      title: "Lancamentos sem NSU",
      count: totals.missingNsu,
      detail: "A politica exige o NSU da boleta para POS 71: CV na Getnet e DOC na Cielo."
    });
  }

  if (totals.overdue) {
    findings.push({
      severity: "high",
      title: "Pendencias potencialmente fora do prazo",
      count: totals.overdue,
      detail: "Triagem por data de cobranca. O calculo considera dias uteis de segunda a sexta e nao desconta feriados."
    });
  }

  if (totals.missingEvidence) {
    findings.push({
      severity: "medium",
      title: "Registros sem justificativa ou evidencia textual",
      count: totals.missingEvidence,
      detail: "A ausencia de texto nao prova falta de documento, mas indica necessidade de verificacao."
    });
  }

  if (totals.missingSaleDate || totals.missingStore) {
    findings.push({
      severity: "medium",
      title: "Campos essenciais incompletos",
      count: totals.missingSaleDate + totals.missingStore,
      detail: "Ha registros sem data de venda ou loja, reduzindo a confiabilidade da conciliacao."
    });
  }

  return {
    empresa: empresa,
    periodDays: Number(periodDays),
    totals: totals,
    findings: findings,
    duplicateGroups: duplicateGroups,
    recurringStores: recurringStores,
    samples: samples,
    evidenceGaps: [
      "A base de Disparos nao informa a data de finalizacao no PDV; por isso Pedro nao confirma a regra de finalizacao no mesmo dia.",
      "A base nao informa CNPJ da maquina, adquirente, codigo de autorizacao nem unidade fisica do equipamento.",
      "Recorrencia e duplicidade sao sinais para investigacao e nao comprovacao de erro ou fraude.",
      "O prazo do quinto dia util nao considera feriados nesta triagem automatica."
    ]
  };
}

function vektorPosPedroPublicRow_(row) {
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  return {
    empresa: row.empresa,
    loja: row.loja,
    status: row.status,
    dataVenda: row.dataVenda
      ? Utilities.formatDate(row.dataVenda, tz, "yyyy-MM-dd")
      : "",
    dataCobranca: row.dataCobranca
      ? Utilities.formatDate(row.dataCobranca, tz, "yyyy-MM-dd")
      : "",
    nsu: row.nsu,
    diferenca: row.diferenca,
    possuiEvidenciaTextual: !!row.evidencia,
    qtdDiasTratativa: row.qtdDiasTratativa,
    statusEnvio: row.statusEnvio
  };
}

function vektorPosPedroIsOverdue_(chargeDate, today) {
  var due;
  var day = chargeDate.getDate();

  if (day >= 29) {
    due = new Date(
      chargeDate.getFullYear(),
      chargeDate.getMonth() + 1,
      1
    );

    var businessDays = 0;
    while (businessDays < 5) {
      var weekday = due.getDay();
      if (weekday !== 0 && weekday !== 6) businessDays++;
      if (businessDays < 5) due.setDate(due.getDate() + 1);
    }
  } else {
    due = new Date(
      chargeDate.getFullYear(),
      chargeDate.getMonth() + 1,
      0
    );
  }

  due.setHours(23, 59, 59, 999);
  return today.getTime() > due.getTime();
}

function vektorPosPedroGetAiConfig_() {
  var props = PropertiesService.getScriptProperties();
  var saved = {};

  try {
    saved = JSON.parse(
      props.getProperty(VEKTOR_POS_PEDRO_AI_CONFIG_PROP) || "{}"
    );
  } catch (_) {
    saved = {};
  }

  var provider = String(
    saved.provider ||
    props.getProperty("PEDRO_AI_PROVIDER") ||
    "GEMINI"
  ).trim().toUpperCase();

  var endpoint = String(
    saved.endpoint ||
    props.getProperty("PEDRO_AI_ENDPOINT") ||
    ""
  ).trim();

  var apiKey = String(
    saved.apiKey ||
    props.getProperty("PEDRO_AI_API_KEY") ||
    ""
  ).trim();

  var model = String(
    saved.model ||
    props.getProperty("PEDRO_AI_MODEL") ||
    (provider === "LM_STUDIO" ? "" : "gemini-3.6-flash")
  ).trim();

  var projectId = String(
    saved.projectId ||
    props.getProperty("PEDRO_AI_PROJECT_ID") ||
    ""
  ).trim();

  var ownerEmail = String(
    saved.ownerEmail ||
    saved.updatedBy ||
    ""
  ).trim().toLowerCase();

  if (provider === "GEMINI" && !endpoint && model) {
    endpoint =
      "https://generativelanguage.googleapis.com/v1beta/models/" +
      encodeURIComponent(model) +
      ":generateContent";
  }

  return {
    provider: provider,
    endpoint: endpoint,
    apiKey: apiKey,
    model: model,
    projectId: projectId,
    ownerEmail: ownerEmail,
    configured: !!(
      endpoint &&
      model &&
      (provider === "LM_STUDIO" || apiKey)
    )
  };
}

function vektorPosPedroCanManageAi_(ctx, config) {
  var email = String(ctx && ctx.email || "").trim().toLowerCase();
  var role = String(ctx && ctx.role || "").trim().toLowerCase();
  var ownerEmail = String(config && config.ownerEmail || "").trim().toLowerCase();

  return !!(
    email &&
    role === "administrador" &&
    (!ownerEmail || ownerEmail === email)
  );
}

function vektorPosPedroGetAiConfigStatus_(ctx) {
  var config = vektorPosPedroGetAiConfig_();
  ctx = ctx || vektorGetUserRole_();
  var canManage = vektorPosPedroCanManageAi_(ctx, config);

  return {
    configured: config.configured,
    provider: config.provider,
    model: canManage ? config.model : "",
    projectId: canManage ? config.projectId : "",
    hasApiKey: canManage && !!config.apiKey,
    canManage: canManage,
    storage: VEKTOR_POS_PEDRO_AI_CONFIG_PROP
  };
}

function vektorPosPedroSaveAiConfig_(input, ctx) {
  input = input || {};

  var current = vektorPosPedroGetAiConfig_();
  var email = String(ctx && ctx.email || "").trim().toLowerCase();
  var role = String(ctx && ctx.role || "").trim().toLowerCase();
  var ownerEmail = String(current.ownerEmail || "").trim().toLowerCase();

  if (role !== "administrador") {
    throw new Error("Apenas o responsavel pelo Agente POS pode alterar esta configuracao.");
  }

  if (ownerEmail && ownerEmail !== email) {
    throw new Error("A configuracao do Agente POS pertence a outro usuario e nao pode ser alterada por esta conta.");
  }

  ownerEmail = ownerEmail || email;

  if (!ownerEmail) {
    throw new Error("Nao foi possivel identificar o usuario responsavel pelo Agente POS.");
  }

  var apiKey = String(input.apiKey || "").trim() || current.apiKey;
  var model = String(input.model || "gemini-3.6-flash").trim();
  var projectId = String(input.projectId || "").trim();

  if (!apiKey) {
    throw new Error("Informe a chave da Gemini API para configurar o Agente POS.");
  }

  if (!/^gemini-[a-z0-9.\-]+$/i.test(model)) {
    throw new Error("Modelo Gemini invalido: " + model);
  }

  var props = PropertiesService.getScriptProperties();
  props.setProperty(
    VEKTOR_POS_PEDRO_AI_CONFIG_PROP,
    JSON.stringify({
      provider: "GEMINI",
      apiKey: apiKey,
      model: model,
      projectId: projectId,
      ownerEmail: ownerEmail,
      updatedAt: new Date().toISOString(),
      updatedBy: email
    })
  );

  // Remove apenas eventuais chaves antigas do proprio agente. As demais
  // propriedades do projeto permanecem intactas.
  [
    "PEDRO_AI_PROVIDER",
    "PEDRO_AI_ENDPOINT",
    "PEDRO_AI_API_KEY",
    "PEDRO_AI_MODEL",
    "PEDRO_AI_PROJECT_ID"
  ].forEach(function(key) {
    props.deleteProperty(key);
  });

  return vektorPosPedroGetAiConfig_();
}

function vektorPosPedroCallAi_(config, analysis, question) {
  var aiPayload = vektorPosPedroBuildAiPayload_(analysis);

  var prompt = [
    "Voce e Pedro, especialista em conciliacao de POS do Grupo SBF.",
    "Analise exclusivamente a empresa " + (analysis.empresa === "NIKE" ? "Fisia" : "Centauro") + ".",
    "Nao compare, misture ou use dados da outra empresa.",
    "Trabalhe com rigor, sem afirmar fraude ou erro sem evidencia.",
    "Diferencie: fato observado, hipotese, risco e acao recomendada.",
    "Nao invente dados ausentes. Use explicitamente as lacunas de evidencia.",
    "Politica interna, versao " + VEKTOR_POS_PEDRO_POLICY_VERSION + ":",
    VEKTOR_POS_PEDRO_POLICY_RULES,
    "Resumo deterministico dos lancamentos:",
    JSON.stringify(aiPayload),
    question
      ? "Pergunta adicional do usuario: " + question
      : "Produza um diagnostico executivo com padroes prioritarios e possibilidades de correcao.",
    "Responda em portugues do Brasil, com secoes: Resumo, Padroes encontrados, Possiveis correcoes e Limitacoes."
  ].join("\n\n");

  if (config.provider === "LM_STUDIO") {
    return vektorPosPedroCallLmStudio_(config, prompt);
  }

  return vektorPosPedroCallGemini_(config, prompt);
}

function vektorPosPedroBuildAiPayload_(analysis) {
  analysis = analysis || {};

  return {
    empresa: analysis.empresa,
    periodDays: analysis.periodDays,
    totals: analysis.totals || {},
    findings: analysis.findings || [],
    recurringStores: (analysis.recurringStores || []).slice(0, 15),
    duplicateGroups: (analysis.duplicateGroups || []).slice(0, 20).map(function(group) {
      var parts = String(group.signature || "").split("|");

      return {
        empresa: parts[0] || "",
        loja: parts[1] || "",
        dataVenda: parts[2] || "",
        quantidade: Number(group.count || 0)
      };
    }),
    samples: (analysis.samples || []).slice(0, 40).map(function(row) {
      return {
        empresa: row.empresa,
        loja: row.loja,
        status: row.status,
        dataVenda: row.dataVenda,
        dataCobranca: row.dataCobranca,
        diferenca: row.diferenca,
        nsuInformado: !!row.nsu,
        possuiEvidenciaTextual: !!row.possuiEvidenciaTextual,
        qtdDiasTratativa: row.qtdDiasTratativa,
        statusEnvio: row.statusEnvio
      };
    }),
    evidenceGaps: analysis.evidenceGaps || []
  };
}

function vektorPosPedroCallGemini_(config, prompt) {
  var startedAt = new Date().getTime();
  var response = UrlFetchApp.fetch(config.endpoint, {
    method: "post",
    contentType: "application/json",
    headers: {
      "x-goog-api-key": config.apiKey
    },
    payload: JSON.stringify({
      contents: [{
        role: "user",
        parts: [{ text: prompt }]
      }],
      generationConfig: {
        maxOutputTokens: 1800
      }
    }),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  var bodyText = response.getContentText();
  var body;

  try {
    body = JSON.parse(bodyText);
  } catch (_) {
    body = {};
  }

  if (code < 200 || code >= 300) {
    throw new Error(
      body && body.error && body.error.message
        ? body.error.message
        : "Gemini API retornou HTTP " + code + "."
    );
  }

  var parts = body && body.candidates && body.candidates[0] &&
    body.candidates[0].content && body.candidates[0].content.parts;

  var text = (parts || []).map(function(part) {
    return String(part.text || "");
  }).join("\n").trim();

  if (!text) throw new Error("Gemini nao retornou texto para a analise.");
  var usage = body && body.usageMetadata || {};

  return {
    text: text,
    usage: {
      promptTokens: Number(usage.promptTokenCount || 0),
      outputTokens: Number(usage.candidatesTokenCount || 0),
      thoughtsTokens: Number(usage.thoughtsTokenCount || 0),
      totalTokens: Number(usage.totalTokenCount || 0),
      latencyMs: Math.max(0, new Date().getTime() - startedAt)
    }
  };
}

function vektorPosPedroCallLmStudio_(config, prompt) {
  var startedAt = new Date().getTime();
  var response = UrlFetchApp.fetch(config.endpoint, {
    method: "post",
    contentType: "application/json",
    headers: config.apiKey
      ? { Authorization: "Bearer " + config.apiKey }
      : {},
    payload: JSON.stringify({
      model: config.model,
      messages: [
        { role: "system", content: "Voce e Pedro, especialista em conciliacao de POS." },
        { role: "user", content: prompt }
      ],
      temperature: 0.2,
      max_tokens: 1800,
      stream: false
    }),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  var bodyText = response.getContentText();
  var body;

  try {
    body = JSON.parse(bodyText);
  } catch (_) {
    body = {};
  }

  if (code < 200 || code >= 300) {
    throw new Error(
      body && body.error && body.error.message
        ? body.error.message
        : "LM Studio retornou HTTP " + code + "."
    );
  }

  var text = body && body.choices && body.choices[0] &&
    body.choices[0].message && body.choices[0].message.content;

  text = String(text || "").trim();
  if (!text) throw new Error("LM Studio nao retornou texto para a analise.");
  var usage = body && body.usage || {};

  return {
    text: text,
    usage: {
      promptTokens: Number(usage.prompt_tokens || 0),
      outputTokens: Number(usage.completion_tokens || 0),
      thoughtsTokens: 0,
      totalTokens: Number(usage.total_tokens || 0),
      latencyMs: Math.max(0, new Date().getTime() - startedAt)
    }
  };
}

function vektorPosPedroGetPricing_(model) {
  var normalized = String(model || "").trim().toLowerCase();
  var price = VEKTOR_POS_PEDRO_PRICING_USD_PER_MILLION[normalized];

  if (!price) {
    Object.keys(VEKTOR_POS_PEDRO_PRICING_USD_PER_MILLION).some(function(key) {
      if (normalized.indexOf(key) === 0) {
        price = VEKTOR_POS_PEDRO_PRICING_USD_PER_MILLION[key];
        return true;
      }
      return false;
    });
  }

  return {
    known: !!price,
    input: Number(price && price.input || 0),
    output: Number(price && price.output || 0)
  };
}

function vektorPosPedroAppendUsage_(empresa, config, usage, status) {
  usage = usage || {};
  var now = new Date();
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  var pricing = vektorPosPedroGetPricing_(config && config.model);
  var promptTokens = Math.max(0, Number(usage.promptTokens || 0));
  var outputTokens = Math.max(0, Number(usage.outputTokens || 0));
  var thoughtsTokens = Math.max(0, Number(usage.thoughtsTokens || 0));
  var totalTokens = Math.max(
    0,
    Number(usage.totalTokens || (promptTokens + outputTokens + thoughtsTokens))
  );
  var costUsd = pricing.known
    ? (
        (promptTokens * pricing.input) +
        ((outputTokens + thoughtsTokens) * pricing.output)
      ) / 1000000
    : 0;

  var event = {
    id: Utilities.getUuid(),
    createdAt: now.toISOString(),
    day: Utilities.formatDate(now, tz, "yyyy-MM-dd"),
    month: Utilities.formatDate(now, tz, "yyyy-MM"),
    empresa: vektorPosNormEmpresa_(empresa),
    provider: String(config && config.provider || "").trim().toUpperCase(),
    model: String(config && config.model || "").trim(),
    status: String(status || "OK").trim().toUpperCase() === "ERROR"
      ? "ERROR"
      : "OK",
    promptTokens: promptTokens,
    outputTokens: outputTokens,
    thoughtsTokens: thoughtsTokens,
    totalTokens: totalTokens,
    latencyMs: Math.max(0, Number(usage.latencyMs || 0)),
    pricingKnown: pricing.known,
    inputRateUsdPerMillion: pricing.input,
    outputRateUsdPerMillion: pricing.output,
    costUsd: Number(costUsd.toFixed(10))
  };

  var lock = LockService.getScriptLock();
  lock.waitLock(15000);

  try {
    var data = vektorPosReadJson_("AI_USAGE");
    var events = Array.isArray(data.events) ? data.events : [];
    var cutoff = new Date(now.getTime());
    cutoff.setDate(cutoff.getDate() - 730);

    events = events.filter(function(item) {
      var createdAt = new Date(String(item && item.createdAt || ""));
      return !isNaN(createdAt.getTime()) && createdAt.getTime() >= cutoff.getTime();
    });

    events.push(event);
    if (events.length > 10000) events = events.slice(events.length - 10000);

    vektorPosWriteJson_("AI_USAGE", {
      meta: {
        version: 1,
        updatedAt: now.toISOString(),
        retentionDays: 730,
        content: "TECHNICAL_USAGE_ONLY"
      },
      events: events
    });
  } finally {
    lock.releaseLock();
  }

  return event;
}

function vektorPosPedroGetCurrentUsdBrl_() {
  var now = new Date();
  var start = new Date(now.getTime());
  start.setDate(start.getDate() - 10);
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  var startText = Utilities.formatDate(start, tz, "MM-dd-yyyy");
  var endText = Utilities.formatDate(now, tz, "MM-dd-yyyy");
  var url =
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/" +
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)" +
    "?%40dataInicial=%27" + startText + "%27" +
    "&%40dataFinalCotacao=%27" + endText + "%27" +
    "&%24orderby=dataHoraCotacao%20desc" +
    "&%24top=1" +
    "&%24format=json" +
    "&%24select=cotacaoVenda%2CdataHoraCotacao";

  try {
    var response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    var code = response.getResponseCode();
    var body = code >= 200 && code < 300
      ? JSON.parse(response.getContentText() || "{}")
      : {};
    var row = body && body.value && body.value[0] || {};
    var rate = Number(row.cotacaoVenda || 0);

    if (!(rate > 0)) throw new Error("PTAX indisponivel.");

    var result = {
      rate: rate,
      quoteAt: String(row.dataHoraCotacao || ""),
      fetchedAt: now.toISOString(),
      source: "BCB_PTAX_VENDA"
    };

    return result;
  } catch (error) {
    return {
      rate: 0,
      quoteAt: "",
      fetchedAt: now.toISOString(),
      source: "BCB_PTAX_VENDA",
      error: String(error && error.message || error || "Cotacao indisponivel.")
    };
  }
}

function vektorPosPedroSummarizeUsage_(events, usdBrl) {
  events = Array.isArray(events) ? events : [];
  var latency = [];
  var summary = {
    requests: events.length,
    successes: 0,
    failures: 0,
    promptTokens: 0,
    outputTokens: 0,
    thoughtsTokens: 0,
    totalTokens: 0,
    costUsd: 0,
    costBrl: 0,
    avgLatencyMs: 0,
    p95LatencyMs: 0,
    fastestLatencyMs: 0,
    slowestLatencyMs: 0
  };

  events.forEach(function(item) {
    if (String(item && item.status || "").toUpperCase() === "ERROR") {
      summary.failures++;
    } else {
      summary.successes++;
    }

    summary.promptTokens += Number(item && item.promptTokens || 0);
    summary.outputTokens += Number(item && item.outputTokens || 0);
    summary.thoughtsTokens += Number(item && item.thoughtsTokens || 0);
    summary.totalTokens += Number(item && item.totalTokens || 0);
    summary.costUsd += Number(item && item.costUsd || 0);

    var latencyMs = Math.max(0, Number(item && item.latencyMs || 0));
    if (latencyMs > 0) latency.push(latencyMs);
  });

  summary.costUsd = Number(summary.costUsd.toFixed(8));
  summary.costBrl = Number((summary.costUsd * Number(usdBrl || 0)).toFixed(6));

  if (latency.length) {
    latency.sort(function(a, b) { return a - b; });
    summary.avgLatencyMs = Math.round(
      latency.reduce(function(total, value) { return total + value; }, 0) /
      latency.length
    );
    summary.p95LatencyMs = Math.round(
      latency[Math.max(0, Math.ceil(latency.length * 0.95) - 1)]
    );
    summary.fastestLatencyMs = Math.round(latency[0]);
    summary.slowestLatencyMs = Math.round(latency[latency.length - 1]);
  }

  return summary;
}

function vektorPosPedroMonthKey_(date) {
  var year = date.getFullYear();
  var month = String(date.getMonth() + 1);
  return year + "-" + (month.length < 2 ? "0" + month : month);
}

function vektorPosPedroGetCostPerf_(req) {
  req = req || {};
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  var currentMonth = Utilities.formatDate(new Date(), tz, "yyyy-MM");
  var selectedMonth = String(req.month || currentMonth).trim();

  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(selectedMonth)) {
    selectedMonth = currentMonth;
  }

  var company = String(req.empresa || "ALL").trim().toUpperCase();
  if (company !== "CENTAURO" && company !== "NIKE") company = "ALL";

  var data = vektorPosReadJson_("AI_USAGE");
  var allEvents = Array.isArray(data.events) ? data.events : [];
  var companyEvents = allEvents.filter(function(item) {
    return company === "ALL" || String(item && item.empresa || "") === company;
  });
  var selectedEvents = companyEvents.filter(function(item) {
    return String(item && item.month || "") === selectedMonth;
  });
  var exchange = vektorPosPedroGetCurrentUsdBrl_();
  var usdBrl = Number(exchange.rate || 0);
  var dailyMap = {};

  selectedEvents.forEach(function(item) {
    var key = String(item && item.day || "");
    if (!dailyMap[key]) dailyMap[key] = [];
    dailyMap[key].push(item);
  });

  var daily = Object.keys(dailyMap).sort().map(function(day) {
    var summary = vektorPosPedroSummarizeUsage_(dailyMap[day], usdBrl);
    summary.day = day;
    return summary;
  });

  var parts = selectedMonth.split("-");
  var selectedDate = new Date(Number(parts[0]), Number(parts[1]) - 1, 1);
  var monthly = [];

  for (var offset = 11; offset >= 0; offset--) {
    var monthDate = new Date(
      selectedDate.getFullYear(),
      selectedDate.getMonth() - offset,
      1
    );
    var monthKey = vektorPosPedroMonthKey_(monthDate);
    var monthEvents = companyEvents.filter(function(item) {
      return String(item && item.month || "") === monthKey;
    });
    var monthSummary = vektorPosPedroSummarizeUsage_(monthEvents, usdBrl);
    monthSummary.month = monthKey;
    monthly.push(monthSummary);
  }

  return {
    ok: true,
    generatedAt: new Date().toISOString(),
    filter: {
      month: selectedMonth,
      empresa: company
    },
    exchange: exchange,
    pricing: {
      currency: "USD",
      updatedAt: VEKTOR_POS_PEDRO_PRICING_UPDATED_AT,
      basis: "STANDARD_PAID_TIER",
      models: VEKTOR_POS_PEDRO_PRICING_USD_PER_MILLION
    },
    summary: vektorPosPedroSummarizeUsage_(selectedEvents, usdBrl),
    daily: daily,
    monthly: monthly,
    historyStartedAt: allEvents.length
      ? String(allEvents[0].createdAt || "")
      : ""
  };
}

/* =====================================================
   STORAGE JSON NO DRIVE
   ===================================================== */

function vektorPosGetOrCreateStorageFolder_() {
  var id = String(VEKTOR_POS_STORAGE_FOLDER_ID || "").trim();
  if (!id) id = PropertiesService.getScriptProperties().getProperty(VEKTOR_POS_STORAGE_FOLDER_PROP) || "";

  if (id) {
    try { return DriveApp.getFolderById(id); } catch (_) {}
  }

  var folderName = "VEKTOR_POS_STORAGE_JSON";
  var folders = DriveApp.getFoldersByName(folderName);
  var folder = folders.hasNext() ? folders.next() : DriveApp.createFolder(folderName);
  PropertiesService.getScriptProperties().setProperty(VEKTOR_POS_STORAGE_FOLDER_PROP, folder.getId());
  return folder;
}

function vektorPosGetFile_(kind) {
  var folder = vektorPosGetOrCreateStorageFolder_();
  var name = VEKTOR_POS_FILE_NAMES[kind];
  if (!name) throw new Error("Arquivo POS inválido: " + kind);

  var it = folder.getFilesByName(name);
  if (it.hasNext()) return it.next();
  return folder.createFile(name, "{}", MimeType.PLAIN_TEXT);
}

function vektorPosReadJson_(kind) {
  var file = vektorPosGetFile_(kind);
  var txt = file.getBlob().getDataAsString("UTF-8");
  if (!String(txt || "").trim()) return {};
  try {
    return JSON.parse(txt);
  } catch (e) {
    throw new Error("JSON inválido no arquivo " + VEKTOR_POS_FILE_NAMES[kind] + ": " + (e.message || e));
  }
}

function vektorPosWriteJson_(kind, obj) {
  var file = vektorPosGetFile_(kind);
  file.setContent(JSON.stringify(obj || {}, null, 2));
}

function vektorPosReadData_(kind) {
  var data = vektorPosReadJson_(kind);
  if (!data || !Array.isArray(data.rows)) {
    data = vektorPosEnsureDataFile_(kind, VEKTOR_POS_HEADERS[kind] || []);
  }
  if (VEKTOR_POS_HEADERS[kind]) data.header = VEKTOR_POS_HEADERS[kind];
  return data;
}

function vektorPosEnsureDataFile_(kind, header) {
  var data = vektorPosReadJson_(kind);
  if (!data || !Array.isArray(data.rows)) {
    data = {
      meta: {
        version: VEKTOR_POS_SCHEMA_VERSION,
        kind: kind,
        createdAt: vektorPosNowText_(),
        storage: "DRIVE_JSON"
      },
      header: header || [],
      rows: []
    };
    vektorPosWriteJson_(kind, data);
  } else {
    data.header = header || data.header || [];
  }
  return data;
}

function vektorPosEnsureConfigFile_() {
  var data = vektorPosReadJson_("CONFIG");
  if (!data || !data.config) {
    data = {
      meta: {
        version: VEKTOR_POS_SCHEMA_VERSION,
        createdAt: vektorPosNowText_(),
        storage: "DRIVE_JSON"
      },
      config: VEKTOR_POS_DEFAULT_CONFIG
    };
    vektorPosWriteJson_("CONFIG", data);
  }
  return data;
}

function vektorPosGetConfig_() {
  var data = vektorPosEnsureConfigFile_();
  var cfg = data.config || {};
  var out = {};
  Object.keys(VEKTOR_POS_DEFAULT_CONFIG).forEach(function(k) {
    out[k] = cfg[k] !== undefined && cfg[k] !== "" ? cfg[k] : VEKTOR_POS_DEFAULT_CONFIG[k];
  });
  return out;
}

function vektorPosMigrateStorageV3_() {
  ["CENTAURO", "NIKE"].forEach(function(kind) {
    var data = vektorPosReadData_(kind);
    var targetHeader = VEKTOR_POS_HEADERS[kind];

    data.rows = (data.rows || []).map(function(oldRow, idx) {
      var out = vektorPosBlankObject_(targetHeader);

      targetHeader.forEach(function(h) {
        out[h] = vektorPosGetSourceValue_(oldRow, h);
      });

      Object.keys(oldRow || {}).forEach(function(k) {
        if (k.indexOf("__") === 0) out[k] = oldRow[k];
      });

      vektorPosCarryLegacyInternalFields_(kind, oldRow, out);

      // Mantém a loja Centauro no padrão visual de quatro dígitos.
      var lojaDigits = vektorPosStoreDigits_(out.LOJA);
      if (lojaDigits) {
        out.LOJA = kind === "CENTAURO"
          ? lojaDigits.padStart(4, "0")
          : lojaDigits;
      }

      vektorPosApplyTimelineFields_(
        kind,
        out,
        vektorPosGetStatus_(out, kind),
        new Date(),
        { setFinalOnTransition: false, clearWhenReopened: false }
      );

      if (!out.__id) out.__id = vektorPosRowId_(kind, out, idx + 1);
      return out;
    });

    data.header = targetHeader;
    data.meta = data.meta || {};
    data.meta.version = VEKTOR_POS_SCHEMA_VERSION;
    data.meta.migratedAt = vektorPosNowText_();
    vektorPosWriteJson_(kind, data);
  });

  var lojas = vektorPosReadData_("LOJAS");
  lojas.header = VEKTOR_POS_HEADERS.LOJAS;
  lojas.meta = lojas.meta || {};
  lojas.meta.version = VEKTOR_POS_SCHEMA_VERSION;
  vektorPosWriteJson_("LOJAS", lojas);

  var disparos = vektorPosReadData_("DISPAROS");
  disparos.header = VEKTOR_POS_HEADERS.DISPAROS;
  disparos.meta = disparos.meta || {};
  disparos.meta.version = VEKTOR_POS_SCHEMA_VERSION;
  vektorPosWriteJson_("DISPAROS", disparos);
}

/* =====================================================
   REGRAS DE NEGÓCIO
   ===================================================== */

function vektorPosNormEmpresa_(empresa) {
  var e = String(empresa || "").trim().toUpperCase();
  return e === "NIKE" ? "NIKE" : "CENTAURO";
}

function vektorPosGetStatus_(r, empresa) {
  return String((empresa === "NIKE" ? r.STATUS : r.Status) || "").trim().toUpperCase();
}

function vektorPosGetLoja_(r) {
  return String(r.LOJA || r.Loja || r.loja || "").trim();
}

function vektorPosStoreDigits_(v) {
  var s = String(v || "").trim();
  var m = s.match(/(\d{1,6})/);
  return m ? String(Number(m[1])) : "";
}

function vektorPosStoreCode4_(v) {
  var d = vektorPosStoreDigits_(v);
  return d ? d.padStart(4, "0") : "";
}

function vektorPosNormGroupKey_(value) {
  return vektorPosNormSearch_(value)
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "SEM_GRUPO";
}

function vektorPosBuildGroupSubjectForDate_(empresa, group, dateObj) {
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  var d = dateObj instanceof Date ? dateObj : new Date();
  var dateCode = Utilities.formatDate(d, tz, "ddMMyy");
  var loja = vektorPosStoreDigits_(group && group.loja4);
  if (!loja) return "";

  var loja4 = loja.padStart(4, "0");
  var store = group && group.items && group.items.length
    ? (group.items[0].store || {})
    : (group && group.store ? group.store : {});

  if (empresa === "NIKE") {
    var rename = String(store.RENAME || "").trim();
    if (!rename) rename = "NV" + loja4;
    return "FS" + loja + dateCode + " - PENDÊNCIA DE POS " + rename;
  }

  return "#" + loja + dateCode + " - PENDÊNCIA DE POS CE" + loja4;
}

function vektorPosBuildSubjectForDate_(empresa, lojaValue, dateObj, store) {
  var loja = vektorPosStoreDigits_(lojaValue);
  if (!loja) return "";

  return vektorPosBuildGroupSubjectForDate_(
    empresa,
    {
      loja4: loja.padStart(4, "0"),
      store: store || {},
      items: [{ store: store || {} }]
    },
    dateObj
  );
}

function vektorPosSetEmailStatus_(row, status, errorMessage) {
  if (!row) return row;

  var normalized = String(status || "")
    .trim()
    .toUpperCase();

  if (
    normalized !== "ENVIADO" &&
    normalized !== "ERRO"
  ) {
    normalized = "";
  }

  row["STATUS ENVIO"] = normalized;
  row.__emailStatus = normalized;

  if (normalized === "ERRO") {
    row.__emailError = String(
      errorMessage || "Erro não informado."
    ).trim();
  } else {
    delete row.__emailError;
  }

  return row;
}


function vektorPosSyncEmailStatusField_(row) {
  if (!row) return row;

  if (vektorPosWasSent_(row)) {
    row["STATUS ENVIO"] = "ENVIADO";
    row.__emailStatus = "ENVIADO";
    delete row.__emailError;
    return row;
  }

  var status = String(
    row.__emailStatus ||
    row["STATUS ENVIO"] ||
    ""
  )
    .trim()
    .toUpperCase();

  if (status === "ERRO") {
    row["STATUS ENVIO"] = "ERRO";
    row.__emailStatus = "ERRO";
  } else {
    row["STATUS ENVIO"] = "";
  }

  return row;
}

function vektorPosWasSent_(r) {
  if (!r) {
    return false;
  }

  var emailStatus = String(
    r["STATUS ENVIO"] ||
    r.__emailStatus ||
    ""
  )
    .trim()
    .toUpperCase();

  /*
   * STATUS ENVIO tem prioridade absoluta.
   * A regra também vale para disparos de teste.
   */
  if (emailStatus === "ENVIADO") {
    return true;
  }

  /*
   * Compatibilidade com registros enviados
   * antes da existência de STATUS ENVIO.
   */
  return !!String(
    r.__sentAt ||
    r.__sendKey ||
    r.__testSentAt ||
    r.__testSendKey ||
    ""
  ).trim();
}

function vektorPosIsSendPending_(r, empresa) {
  if (!r || vektorPosWasSent_(r)) return false;

  // Linhas de rascunho ainda sem loja continuam visíveis no filtro
  // "Somente pendentes" para permitir o início do preenchimento.
  var st = vektorPosGetStatus_(r, empresa);
  if (!st) return false;
  if (st === "OK" || st === "FINALIZADO" || st === "BAIXADO" || st === "PERDA") return false;
  return true;
}

function vektorPosValidateRequiredSendFields_(
  empresa,
  row
) {
  empresa=
    vektorPosNormEmpresa_(
      empresa
    );

  row=row||{};

  /*
   * INFORMAÇÕES COMPLEMENTARES deixou de ser
   * campo obrigatório para o envio.
   */
  var required=
    empresa==="NIKE"
      ? [
          {
            key:"LOJA",
            label:"LOJA"
          },
          {
            key:"DATA VENDA",
            label:"DATA VENDA"
          },
          {
            key:"NSU TRANSAÇÃO",
            label:"NSU TRANSAÇÃO"
          },
          {
            key:"VALOR EQUALS",
            label:"VALOR EQUALS"
          },
          {
            key:"VALOR REGISTRADO",
            label:"VALOR REGISTRADO"
          },
          {
            key:"DIFERENÇA",
            label:"DIFERENÇA"
          }
        ]
      : [
          {
            key:"LOJA",
            label:"LOJA"
          },
          {
            key:"DATA VENDA",
            label:"DATA VENDA"
          },
          {
            key:"NSU",
            label:"NSU"
          },
          {
            key:"VALOR EQUALS (50)",
            label:"VALOR EQUALS (50)"
          },
          {
            key:"VALOR REGISTRADO (40)",
            label:"VALOR REGISTRADO (40)"
          },
          {
            key:"DIFERENÇA",
            label:"DIFERENÇA"
          }
        ];

  var missing=[];

  required.forEach(function(field){
    var value=String(
      row[field.key] == null
        ? ""
        : row[field.key]
    ).trim();

    if(!value){
      missing.push(
        field.label
      );
    }
  });

  if(missing.length){
    throw new Error(
      "Preencha todos os campos obrigatórios antes do envio: "+
      missing.join(", ")+
      "."
    );
  }

  return true;
}

function vektorPosIsDraftRow_(row) {
  return !vektorPosStoreDigits_(vektorPosGetLoja_(row));
}

function vektorPosCreateDraftRow_(empresa, ctx) {
  var obj = vektorPosBlankObject_(VEKTOR_POS_HEADERS[empresa]);
  obj[empresa === "NIKE" ? "STATUS" : "Status"] = "PENDENTE";
  obj.__id = vektorPosRowId_(empresa, obj, new Date().getTime());
  obj.__createdAt = vektorPosNowText_();
  obj.__updatedAt = vektorPosNowText_();
  obj.__updatedBy = String((ctx && ctx.email) || "").trim().toLowerCase();
  obj.__draft = true;
  return obj;
}

function vektorPosEnsureSingleDraftRow_(empresa, data, ctx) {
  data = data || {};
  data.rows = Array.isArray(data.rows) ? data.rows : [];

  var before = JSON.stringify(data.rows);
  var filledRows = [];
  var firstDraft = null;

  data.rows.forEach(function(row) {
    if (vektorPosIsDraftRow_(row)) {
      if (!firstDraft) firstDraft = row;
      return;
    }

    filledRows.push(row);
  });

  var draft = firstDraft || vektorPosCreateDraftRow_(empresa, ctx);
  var cleanDraft = vektorPosBlankObject_(VEKTOR_POS_HEADERS[empresa]);

  cleanDraft[empresa === "NIKE" ? "STATUS" : "Status"] = "PENDENTE";
  cleanDraft.__id = String(draft.__id || "") ||
    vektorPosRowId_(empresa, cleanDraft, new Date().getTime());
  cleanDraft.__createdAt = String(draft.__createdAt || "") ||
    vektorPosNowText_();
  cleanDraft.__updatedAt = String(draft.__updatedAt || "") ||
    vektorPosNowText_();
  cleanDraft.__updatedBy = String(
    draft.__updatedBy || ((ctx && ctx.email) || "")
  ).trim().toLowerCase();
  cleanDraft.__draft = true;

  data.rows = filledRows.concat([cleanDraft]);

  return {
    draftRow: cleanDraft,
    created: !firstDraft,
    changed: before !== JSON.stringify(data.rows)
  };
}


function vektorPosReadOnlyColumns_(empresa) {
  var out = {};
  var comuns = [
    "DATA COBRANÇA",
    "DATA FINAL (TRATATIVA)",
    "MÊS PENDÊNCIA",
    "QTD DIAS TRATATIVA",
    "DIFERENÇA",
    "STATUS ENVIO"
  ];

var cols = empresa === "NIKE"
  ? [
      "CÓDIGO ÚNICO_ASSUNTO",
      "E-mail Loja",
      "TIPO"
    ].concat(comuns)
  : [
      "CÓDIGO ENVIO EMAIL_ASSUNTO",
      "E-mail Gerente Grupo",
      "E-mail Sup Auto",
      "E-mail Sup Vendas",
      "E-mail Regional",
      "Enviar Para",
      "Time"
    ].concat(comuns);

  cols.forEach(function(h) { out[h] = true; });
  return out;
}

function vektorPosApplyDerivedFields_(empresa, row, lojasMap, dateObj) {
  var loja = vektorPosStoreDigits_(vektorPosGetLoja_(row));
  if (!loja) {
    return { valid: false, error: "Número de loja inválido.", store: null };
  }

  var loja4 = loja.padStart(4, "0");
  row.LOJA = empresa === "CENTAURO" ? loja4 : loja;

  var store = lojasMap[empresa + "|" + loja4];
  if (!store) {
    return { valid: false, error: "Loja não localizada no cadastro de " + empresa + ".", store: null };
  }

  var statusHeader = empresa === "NIKE" ? "STATUS" : "Status";
  if (!String(row[statusHeader] || "").trim()) row[statusHeader] = "PENDENTE";

  /*
 * Remove o campo operacional antigo.
 * Os destinatários passam a usar apenas:
 * Nike: E-mail Loja
 * Centauro: Enviar Para
 */
delete row.EMAIL;

if (empresa === "NIKE") {
  /*
   * Nike envia exclusivamente pela coluna E-mail Loja.
   */
  row["E-mail Loja"] = String(
    store.EMAILS || ""
  ).trim().toLowerCase();

  row.TIPO = String(
    store.TIPO || ""
  ).trim();

} else {
  /*
   * Centauro envia exclusivamente pela coluna Enviar Para.
   */
  var emails = vektorPosBuildCentauroEmails_(
    loja,
    store.EMAIL_REGIONAL || ""
  );

  row["E-mail Gerente Grupo"] = emails.gerenteGrupo;
  row["E-mail Sup Auto"] = emails.supAuto;
  row["E-mail Sup Vendas"] = emails.supVendas;
  row["E-mail Regional"] = emails.regional;

  row["Enviar Para"] = emails.todos;

  row.Time = String(
    store.TIME || ""
  ).trim();
}

  var subjectHeader = VEKTOR_POS_HEADERS[empresa][0];
  if (!vektorPosWasSent_(row)) {
    row[subjectHeader] = vektorPosBuildSubjectForDate_(
      empresa,
      loja,
      dateObj || new Date(),
      store
    );
  }

  return { valid: true, error: "", store: store };
}


function vektorPosApplyTimelineFields_(empresa, row, previousStatus, dateObj, options) {
  options = options || {};
  var currentStatus = vektorPosGetStatus_(row, empresa);
  var previous = String(previousStatus || "").trim().toUpperCase();
  var now = dateObj instanceof Date ? dateObj : new Date();
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

  var chargeDate = vektorPosParseDate_(row["DATA COBRANÇA"]);
  if (chargeDate) {
    row["MÊS PENDÊNCIA"] = Utilities.formatDate(chargeDate, tz, "MM/yyyy");
  } else {
    row["MÊS PENDÊNCIA"] = "";
  }

  if (currentStatus !== "OK") {
    row["DATA FINAL (TRATATIVA)"] = "";
    row["QTD DIAS TRATATIVA"] = "";
    delete row.__closedAt;
    return row;
  }

  var finalDate = vektorPosParseDate_(row["DATA FINAL (TRATATIVA)"]);
  var transitionedToOk = previous !== "OK";

  if (
    !finalDate &&
    options.setFinalOnTransition === true &&
    transitionedToOk
  ) {
    row["DATA FINAL (TRATATIVA)"] = Utilities.formatDate(now, tz, "dd/MM/yyyy");
    row.__closedAt = vektorPosNowText_();
    finalDate = vektorPosParseDate_(row["DATA FINAL (TRATATIVA)"]);
  }

  if (chargeDate && finalDate) {
    var chargeUtc = Date.UTC(
      chargeDate.getFullYear(),
      chargeDate.getMonth(),
      chargeDate.getDate()
    );
    var finalUtc = Date.UTC(
      finalDate.getFullYear(),
      finalDate.getMonth(),
      finalDate.getDate()
    );

    row["QTD DIAS TRATATIVA"] = String(
      Math.max(0, Math.floor((finalUtc - chargeUtc) / 86400000))
    );
  } else {
    row["QTD DIAS TRATATIVA"] = "";
  }

  return row;
}

function vektorPosBuildCentauroEmails_(lojaValue, emailRegional) {
  var loja = vektorPosStoreDigits_(lojaValue);
  var gerenteGrupo = loja ? "gerce" + loja + "@marca.exemplo" : "";
  var supAuto = loja ? "supautoce" + loja + "@marca.exemplo" : "";
  var supVendas = loja ? "supvence" + loja + "@marca.exemplo" : "";
  var regional = String(emailRegional || "").trim().toLowerCase();
  var todos = vektorPosNormalizeEmailList_([gerenteGrupo, supAuto, supVendas, regional].join(","));
  return {
    gerenteGrupo: gerenteGrupo,
    supAuto: supAuto,
    supVendas: supVendas,
    regional: regional,
    todos: todos
  };
}

/**
 * Roteamento temporário para testes realizados
 * diretamente pela tabela do módulo POS.
 *
 * Quando a loja selecionada for uma das lojas abaixo,
 * o envio irá somente para Rodrigo, sem CC.
 *
 * Para encerrar os testes, altere TESTE_ATIVO para false.
 */
function vektorPosResolveSendRouting_(
  empresa,
  lojaValue,
  rows,
  store,
  config
) {
  empresa =
    vektorPosNormEmpresa_(
      empresa
    );

  /*
   * PRODUÇÃO
   *
   * Centauro:
   * usa exclusivamente a coluna Enviar Para.
   *
   * Nike/Fisia:
   * usa exclusivamente a coluna E-mail Loja.
   */
  return {
    to: vektorPosResolveGroupRecipients_(
      empresa,
      rows,
      store
    ),

    cc: String(
      config.emailCc ||
      VEKTOR_POS_EMAIL_CC_DEFAULT ||
      ""
    ).trim(),

    isTest: false
  };
}

function vektorPosResolveGroupRecipients_(empresa, rows, store) {
  var list = [];

  (rows || []).forEach(function(row) {
    if (empresa === "NIKE") {
      /*
       * Nike: somente a coluna E-mail Loja.
       */
      list.push(
        String(row["E-mail Loja"] || "").trim()
      );
    } else {
      /*
       * Centauro: somente a coluna Enviar Para.
       */
      list.push(
        String(row["Enviar Para"] || "").trim()
      );
    }
  });

  return vektorPosNormalizeEmailList_(
    list.join(",")
  );
}

function vektorPosBuildStoreMap_(rows) {
  var map = {};
  (rows || []).forEach(function(r) {
    var ativo = String(r.ATIVO || "SIM").trim().toUpperCase();
    if (ativo === "NÃO" || ativo === "NAO" || ativo === "N" || ativo === "FALSE") return;

    var empresa = vektorPosNormEmpresa_(r.EMPRESA);
    var loja4 = vektorPosStoreCode4_(r.LOJA);
    if (!loja4) return;
    map[empresa + "|" + loja4] = r;
  });
  return map;
}

function vektorPosBuildGroupedEmailHtml_(
  empresa,
  rows,
  assunto,
  groupMeta,
  solicitante
) {
  groupMeta = groupMeta || {};

  var lojasSet = {};

  (rows || []).forEach(function(row) {
    var loja = vektorPosStoreDigits_(
      vektorPosGetLoja_(row)
    );

    if (loja) {
      lojasSet[loja] = true;
    }
  });

  var lojas = Object.keys(lojasSet)
    .sort(function(a, b) {
      return Number(a) - Number(b);
    });

  /*
   * Coleta somente o texto preenchido na coluna:
   * INFORMAÇÕES COMPLEMENTARES
   *
   * Não adiciona título, loja, NSU, numeração
   * ou qualquer outra informação.
   */
  var complementos = [];

  (rows || []).forEach(function(row) {
    var texto = String(
      row[
        "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)"
      ] || ""
    ).trim();

    if (texto) {
      complementos.push(texto);
    }
  });

  /*
   * Mantém apenas os textos digitados,
   * na ordem das linhas selecionadas.
   */
  var complementoHtml = complementos
    .map(function(texto) {
      return vektorPosEscape_(texto)
        .replace(/\r?\n/g, "<br>");
    })
    .join(" ");

  /*
   * A tabela do e-mail terá somente:
   *
   * #
   * Loja
   * Data venda
   * NSU
   * Valor Equals
   * Valor registrado
   * Diferença
   */
  var bodyRows = (rows || [])
    .map(function(row, idx) {
      var loja =
        vektorPosGetLoja_(row);

      var dataVenda =
        vektorPosNormalizeDateBr_(
          row["DATA VENDA"],
          false
        );

      var nsu = row[
        empresa === "NIKE"
          ? "NSU TRANSAÇÃO"
          : "NSU"
      ];

      var valorEquals =
        vektorPosFormatNumberBr_(
          row[
            empresa === "NIKE"
              ? "VALOR EQUALS"
              : "VALOR EQUALS (50)"
          ]
        );

      var valorRegistrado =
        vektorPosFormatNumberBr_(
          row[
            empresa === "NIKE"
              ? "VALOR REGISTRADO"
              : "VALOR REGISTRADO (40)"
          ]
        );

      var diff =
        vektorPosFormatNumberBr_(
          row.DIFERENÇA
        );

      return "<tr>" +

        vektorPosEmailTd_(
          idx + 1,
          "center"
        ) +

        vektorPosEmailTd_(
          loja,
          "center"
        ) +

        vektorPosEmailTd_(
          dataVenda,
          "center"
        ) +

        vektorPosEmailTd_(
          nsu,
          "center"
        ) +

        vektorPosEmailTd_(
          valorEquals,
          "right"
        ) +

        vektorPosEmailTd_(
          valorRegistrado,
          "right"
        ) +

        vektorPosEmailTd_(
          diff,
          "right",
          "#fee2e2"
        ) +

      "</tr>";
    })
    .join("");

  /*
   * O texto complementar é acrescentado diretamente
   * depois do ponto final da frase padrão.
   */
  var intro =
    "Identificamos <b>" +
    rows.length +
    " pendência(s)</b> de POS para a loja <b>" +
    vektorPosEscape_(
      lojas.length
        ? lojas[0]
        : ""
    ) +
    "</b>. Favor verificar e retornar com a tratativa necessária.";

  if (complementoHtml) {
    intro += " " + complementoHtml;
  }

  return "" +

    "<div style='" +
      "font-family:Arial,sans-serif;" +
      "color:#0f172a;" +
      "line-height:1.45;" +
    "'>" +

      "<div style='" +
        "background:#061a3a;" +
        "color:#fff;" +
        "padding:18px 20px;" +
        "border-radius:14px 14px 0 0;" +
      "'>" +

        "<div style='" +
          "font-size:12px;" +
          "font-weight:800;" +
          "letter-spacing:.12em;" +
          "text-transform:uppercase;" +
          "color:#B5FF20;" +
        "'>" +

          "Vektor - Grupo SBF" +

        "</div>" +

        "<div style='" +
          "font-size:20px;" +
          "font-weight:900;" +
          "margin-top:6px;" +
        "'>" +

          "Pendência de POS | " +
          vektorPosEscape_(empresa) +

        "</div>" +

        "<div style='" +
          "font-size:13px;" +
          "font-weight:700;" +
          "margin-top:4px;" +
          "color:#e2e8f0;" +
        "'>" +

          vektorPosEscape_(assunto) +

        "</div>" +

      "</div>" +

      "<div style='" +
        "border:1px solid #e2e8f0;" +
        "border-top:0;" +
        "padding:18px 20px;" +
        "border-radius:0 0 14px 14px;" +
      "'>" +

        "<p>Prezados,</p>" +

        /*
         * Resultado:
         *
         * Favor verificar e retornar com a tratativa necessária.
         * Verifiquem com urgência!
         *
         * Tudo no mesmo parágrafo, sem bloco adicional.
         */
        "<p>" +
          intro +
        "</p>" +

        "<table style='" +
          "border-collapse:collapse;" +
          "width:100%;" +
          "margin-top:14px;" +
          "font-size:12px;" +
        "'>" +

          "<thead>" +

            "<tr style='" +
              "background:#061a3a;" +
              "color:#fff;" +
            "'>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "#" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "Loja" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "Data venda" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "NSU" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "Valor Equals" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "Valor registrado" +
              "</th>" +

              "<th style='" +
                "border:1px solid #cbd5e1;" +
                "padding:8px;" +
              "'>" +
                "Diferença" +
              "</th>" +

            "</tr>" +

          "</thead>" +

          "<tbody>" +
            bodyRows +
          "</tbody>" +

        "</table>" +

        "<p style='margin-top:18px;'>" +
          "Atenciosamente,<br>" +
          "<b>Vektor - Grupo SBF</b>" +
        "</p>" +

      "</div>" +

    "</div>";
}

function vektorPosEmailTd_(value, align, bg) {
  return "<td style='border:1px solid #e2e8f0;padding:8px 9px;text-align:" +
    vektorPosEscape_(align || "left") + ";background:" + vektorPosEscape_(bg || "#ffffff") + ";'>" +
    vektorPosEscape_(value) + "</td>";
}

function vektorPosAppendDisparo_(disparos, ctx, empresa, sendKey, loja, assunto, to, cc, rowIds, status, erro, hash) {
  var id = Utilities.getUuid();
  disparos.header = VEKTOR_POS_HEADERS.DISPAROS;
  disparos.rows = disparos.rows || [];
  disparos.rows.push({
    __id: id,
    ID_DISPARO: id,
    DATA_ENVIO: vektorPosNowText_(),
    USUARIO: String(ctx.email || "").trim().toLowerCase(),
    EMPRESA: empresa,
    SEND_KEY: sendKey,
    LOJA: loja,
    ASSUNTO: assunto,
    DESTINATARIOS: to,
    CC: cc,
    ROW_IDS: (rowIds || []).join(","),
    QTD_LINHAS: (rowIds || []).length,
    STATUS: status,
    ERRO: erro || "",
    HASH: hash || ""
  });
}

function vektorPosBuildGroupHash_(sendKey, rowIds, to) {
  var raw = [sendKey, (rowIds || []).slice().sort().join(","), to].join("|");
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, raw)
    .map(function(b) { return (b + 256).toString(16).slice(-2); })
    .join("");
}

/* =====================================================
   BIGQUERY / BASE REGIONAL / SEED NIKE
   ===================================================== */

function vektorPosRunBigQuery_(sql, billingProjectId) {
  var request = {
    query: String(sql || ""),
    useLegacySql: false,
    maxResults: 10000
  };

  var result = BigQuery.Jobs.query(request, billingProjectId);
  var jobId = result.jobReference && result.jobReference.jobId;
  if (!jobId) throw new Error("BigQuery não retornou jobId.");

  while (!result.jobComplete) {
    Utilities.sleep(500);
    result = BigQuery.Jobs.getQueryResults(billingProjectId, jobId, { maxResults: 10000 });
  }

  var schema = result.schema && result.schema.fields ? result.schema.fields : [];
  var out = vektorPosBigQueryRowsToObjects_(schema, result.rows || []);
  var pageToken = result.pageToken;

  while (pageToken) {
    var page = BigQuery.Jobs.getQueryResults(billingProjectId, jobId, {
      maxResults: 10000,
      pageToken: pageToken
    });
    out = out.concat(vektorPosBigQueryRowsToObjects_(schema, page.rows || []));
    pageToken = page.pageToken;
  }

  return out;
}

function vektorPosBigQueryRowsToObjects_(schema, rows) {
  return (rows || []).map(function(r) {
    var obj = {};
    var cells = r && r.f ? r.f : [];
    schema.forEach(function(field, idx) {
      obj[String(field.name || "")] = cells[idx] && cells[idx].v !== null ? cells[idx].v : "";
    });
    return obj;
  });
}

function vektorPosLoadRegionalMap_() {
  var sh = SpreadsheetApp.openById(VEKTOR_POS_REGIONAL_SS_ID).getSheetByName(VEKTOR_POS_REGIONAL_SHEET);
  if (!sh) throw new Error('Aba "' + VEKTOR_POS_REGIONAL_SHEET + '" não encontrada na planilha regional.');

  var values = sh.getDataRange().getDisplayValues();
  var headerRow = -1;
  for (var r = 0; r < Math.min(values.length, 30); r++) {
    var c = vektorPosNormHeader_(values[r][2]);
    var f = vektorPosNormHeader_(values[r][5]);
    var h = vektorPosNormHeader_(values[r][7]);
    if ((c === "codigo" || c === "cod") && f === "time" && h.indexOf("regional") >= 0 && h.indexOf("mail") >= 0) {
      headerRow = r;
      break;
    }
  }

  if (headerRow < 0) {
    throw new Error('Não encontrei na aba Base o cabeçalho esperado nas colunas C="Codigo", F="Time" e H="E-mail Regional".');
  }

  var map = {};
  for (var i = headerRow + 1; i < values.length; i++) {
    var loja = vektorPosStoreDigits_(values[i][2]);
    if (!loja) continue;
    map[loja] = {
      time: String(values[i][5] || "").trim(),
      emailRegional: String(values[i][7] || "").trim().toLowerCase()
    };
  }
  return map;
}

function vektorPosSeedNikeStores_(force) {
  var data = vektorPosReadData_("LOJAS");
  var existingNike = (data.rows || []).filter(function(r) {
    return String(r.EMPRESA || "").trim().toUpperCase() === "NIKE";
  });

  if (existingNike.length && !force) {
    return { ok: true, inserted: 0, existing: existingNike.length, message: "Cadastro Nike já existente." };
  }

  var ctx = vektorGetUserRole_();
  var now = vektorPosNowText_();
  var keep = (data.rows || []).filter(function(r) {
    return String(r.EMPRESA || "").trim().toUpperCase() !== "NIKE";
  });

  var nikeRows = VEKTOR_POS_NIKE_STORES.map(function(line) {
    var obj = vektorPosBlankObject_(VEKTOR_POS_HEADERS.LOJAS);
    obj.EMPRESA = "NIKE";
    obj.LOJA = line[0];
    obj.EMAILS = String(line[1] || "").trim().toLowerCase();
    obj.NOMINAL = line[2];
    obj.RENAME = line[3];
    obj.TIPO = line[4];
    obj.ATIVO = "SIM";
    obj.__id = "NIKE_LOJA_" + line[0];
    obj.__createdAt = now;
    obj.__updatedAt = now;
    obj.__updatedBy = String(ctx.email || "").trim().toLowerCase();
    obj.__source = "CADASTRO_CONTROLADO";
    return obj;
  });

  data.header = VEKTOR_POS_HEADERS.LOJAS;
  data.rows = keep.concat(nikeRows);
  data.meta = data.meta || {};
  data.meta.nikeSeededAt = now;
  data.meta.nikeRows = nikeRows.length;
  vektorPosWriteJson_("LOJAS", data);

  return { ok: true, inserted: nikeRows.length, existing: 0, message: "Cadastro Nike restaurado." };
}

/* =====================================================
   HELPERS
   ===================================================== */

function vektorPosAssertAdmin_() {
  var ctx = vektorGetUserRole_();
  if (String(ctx.role || "").trim().toLowerCase() !== "administrador") {
    throw new Error("Apenas Administrador pode executar esta operação.");
  }
  return ctx;
}

function vektorPosBlankObject_(header) {
  var obj = {};
  (header || []).forEach(function(h) { obj[h] = ""; });
  return obj;
}

function vektorPosRowId_(kind, obj, idx) {
  var seed = [
    kind, idx, obj.LOJA, obj.NSU, obj["NSU TRANSAÇÃO"], obj["DATA VENDA"],
    obj.DIFERENÇA, new Date().getTime(), Math.random()
  ].join("|");
  var digest = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, seed)
    .map(function(b) { return (b + 256).toString(16).slice(-2); })
    .join("")
    .slice(0, 16);
  return kind + "_" + digest;
}

function vektorPosNowText_() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone() || "America/Sao_Paulo", "yyyy-MM-dd HH:mm:ss");
}

function vektorPosCellToText_(v) {
  if (v === null || v === undefined) return "";
  if (Object.prototype.toString.call(v) === "[object Date]") {
    if (isNaN(v.getTime())) return "";
    return Utilities.formatDate(v, Session.getScriptTimeZone() || "America/Sao_Paulo", "dd/MM/yyyy");
  }
  return String(v).trim();
}

function vektorPosJsonSafe_(value) {
  if (value === null || value === undefined) return "";
  if (Object.prototype.toString.call(value) === "[object Date]") return vektorPosCellToText_(value);
  if (Array.isArray(value)) return value.map(vektorPosJsonSafe_);
  if (typeof value === "object") {
    var out = {};
    Object.keys(value).forEach(function(k) { out[k] = vektorPosJsonSafe_(value[k]); });
    return out;
  }
  return value;
}

function vektorPosEscape_(s) {
  return String(s === null || s === undefined ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function vektorPosNormSearch_(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .trim();
}

function vektorPosNormHeader_(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .toLowerCase()
    .trim();
}

function vektorPosNormalizeEmailList_(s) {
  var out = {};
  String(s || "")
    .replace(/;/g, ",")
    .split(",")
    .map(function(x) { return String(x || "").trim().toLowerCase(); })
    .filter(function(x) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(x); })
    .forEach(function(x) { out[x] = true; });
  return Object.keys(out).join(",");
}

function vektorPosParseNumber_(v) {
  var s = String(v || "").trim();
  if (!s) return 0;
  s = s.replace(/R\$/g, "").replace(/\s/g, "");
  if (s.indexOf(",") >= 0) s = s.replace(/\./g, "").replace(",", ".");
  var n = Number(s);
  return isFinite(n) ? n : 0;
}

function vektorPosNormalizeDateBr_(value, strict) {
  var raw = String(value === null || value === undefined ? "" : value).trim();
  if (!raw) return "";

  var dia = 0;
  var mes = 0;
  var ano = 0;

  var iso = raw.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/);
  var br = raw.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})$/);
  var digits = raw.replace(/\D/g, "");

  if (iso) {
    ano = Number(iso[1]);
    mes = Number(iso[2]);
    dia = Number(iso[3]);
  } else if (br) {
    dia = Number(br[1]);
    mes = Number(br[2]);
    ano = Number(br[3]);

    if (ano < 100) ano += 2000;
  } else if (/^\d{8}$/.test(digits)) {
    var firstFour = Number(digits.slice(0, 4));

    if (firstFour >= 1900 && firstFour <= 2200) {
      ano = firstFour;
      mes = Number(digits.slice(4, 6));
      dia = Number(digits.slice(6, 8));
    } else {
      dia = Number(digits.slice(0, 2));
      mes = Number(digits.slice(2, 4));
      ano = Number(digits.slice(4, 8));
    }
  } else {
    if (strict) {
      throw new Error(
        'Data inválida em "DATA VENDA": ' + raw +
        ". Informe a data no formato dd/mm/aaaa."
      );
    }

    return raw;
  }

  var date = new Date(ano, mes - 1, dia);

  var valid =
    date.getFullYear() === ano &&
    date.getMonth() === mes - 1 &&
    date.getDate() === dia;

  if (!valid) {
    if (strict) {
      throw new Error(
        'Data inválida em "DATA VENDA": ' + raw + "."
      );
    }

    return raw;
  }

  return String(dia).padStart(2, "0") + "/" +
    String(mes).padStart(2, "0") + "/" +
    String(ano).padStart(4, "0");
}


function vektorPosParseNumberBr_(value) {
  var raw = String(value === null || value === undefined ? "" : value)
    .trim()
    .replace(/R\$/gi, "")
    .replace(/\s/g, "");

  if (!raw) return null;

  var lastComma = raw.lastIndexOf(",");
  var lastDot = raw.lastIndexOf(".");
  var normalized = raw;

  if (lastComma >= 0 && lastDot >= 0) {
    if (lastComma > lastDot) {
      normalized = raw.replace(/\./g, "").replace(",", ".");
    } else {
      normalized = raw.replace(/,/g, "");
    }
  } else if (lastComma >= 0) {
    normalized = raw.replace(/\./g, "").replace(",", ".");
  } else if (lastDot >= 0) {
    if (/^-?\d{1,3}(\.\d{3})+$/.test(raw)) {
      normalized = raw.replace(/\./g, "");
    }
  }

  normalized = normalized.replace(/[^0-9.-]/g, "");

  var number = Number(normalized);
  return isFinite(number) ? number : null;
}


function vektorPosFormatNumberBr_(value) {
  var number = typeof value === "number"
    ? value
    : vektorPosParseNumberBr_(value);

  if (number === null || !isFinite(number)) return "";

  var negative = number < 0 ? "-" : "";
  var parts = Math.abs(number).toFixed(2).split(".");

  var integer = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");

  return negative + integer + "," + parts[1];
}


function vektorPosApplyOperationalFormats_(empresa, row, strict) {
  row = row || {};

  var equalsHeader = empresa === "NIKE"
    ? "VALOR EQUALS"
    : "VALOR EQUALS (50)";

  var registeredHeader = empresa === "NIKE"
    ? "VALOR REGISTRADO"
    : "VALOR REGISTRADO (40)";

  var rawDate = String(row["DATA VENDA"] || "").trim();

  if (rawDate) {
    row["DATA VENDA"] = vektorPosNormalizeDateBr_(rawDate, strict === true);
  } else {
    row["DATA VENDA"] = "";
  }

  var rawEquals = String(row[equalsHeader] || "").trim();
  var rawRegistered = String(row[registeredHeader] || "").trim();

  var equalsValue = vektorPosParseNumberBr_(rawEquals);
  var registeredValue = vektorPosParseNumberBr_(rawRegistered);

  if (rawEquals && equalsValue === null && strict === true) {
    throw new Error(
      'Valor inválido na coluna "' + equalsHeader + '": ' + rawEquals
    );
  }

  if (rawRegistered && registeredValue === null && strict === true) {
    throw new Error(
      'Valor inválido na coluna "' + registeredHeader + '": ' + rawRegistered
    );
  }

  row[equalsHeader] = equalsValue === null
    ? ""
    : vektorPosFormatNumberBr_(equalsValue);

  row[registeredHeader] = registeredValue === null
    ? ""
    : vektorPosFormatNumberBr_(registeredValue);

  if (equalsValue !== null && registeredValue !== null) {
    row.DIFERENÇA = vektorPosFormatNumberBr_(
      registeredValue - equalsValue
    );
  } else {
    row.DIFERENÇA = "";
  }

  return row;
}

function vektorPosCompareValues_(a, b) {
  var sa = String(a === null || a === undefined ? "" : a).trim();
  var sb = String(b === null || b === undefined ? "" : b).trim();

  var na = vektorPosParseNumber_(sa);
  var nb = vektorPosParseNumber_(sb);
  var looksNumericA = /^[-+]?\s*(R\$)?\s*[\d.,]+$/.test(sa);
  var looksNumericB = /^[-+]?\s*(R\$)?\s*[\d.,]+$/.test(sb);
  if (looksNumericA && looksNumericB) return na === nb ? 0 : (na < nb ? -1 : 1);

  var da = vektorPosParseDate_(sa);
  var db = vektorPosParseDate_(sb);
  if (da && db) return da.getTime() === db.getTime() ? 0 : (da < db ? -1 : 1);

  return sa.localeCompare(sb, "pt-BR", { numeric: true, sensitivity: "base" });
}

function vektorPosParseDate_(s) {
  var txt = String(s || "").trim();
  var br = txt.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (br) {
    var d1 = new Date(Number(br[3]), Number(br[2]) - 1, Number(br[1]));
    return isNaN(d1.getTime()) ? null : d1;
  }
  var iso = txt.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) {
    var d2 = new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
    return isNaN(d2.getTime()) ? null : d2;
  }
  return null;
}

function vektorPosCarryLegacyInternalFields_(kind, source, target) {
  source = source || {};
  target = target || {};

  var legacySent = String(source["STATUS EMAIL INICIAL"] || "").trim().toUpperCase();
  if (legacySent === "ENVIADO" || legacySent === "ENVIADA" || legacySent === "SENT") {
    target.__emailStatus = "ENVIADO";
    target.__sentAt = String(source["DATA COBRANÇA"] || source["ÚLTIMA ATUALIZAÇÃO"] || vektorPosNowText_());
  }

  var legacyConc = String(source.CONCILIADO || "").trim().toUpperCase();
  if (legacyConc === "SIM" || legacyConc === "S" || legacyConc === "TRUE" || legacyConc === "1" || legacyConc === "CONCILIADO") {
    var statusHeader = kind === "NIKE" ? "STATUS" : "Status";
    target[statusHeader] = "OK";
  }

  return target;
}

function vektorPosGetSourceValue_(source, targetHeader) {
  if (!source) return "";
  if (source[targetHeader] !== undefined) return vektorPosCellToText_(source[targetHeader]);

  var aliases = {
    "INFORMAÇÕES": [" INFORMAÇÕES", "INFORMACOES"],
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)": [
      "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL",
      "INFORMACOES COMPLEMENTARES"
    ],
    "EMAILS": ["EMAIL_LOJA", "EMAILS_EXTRA", "E-mail Loja"],
    "NOMINAL": ["NOME_LOJA", "NOME LOJA"],
    "RENAME": ["CODIGO_EXIBICAO"],
    "EMAIL_REGIONAL": ["E-mail Regional"],
    "EMAIL_GERENTE_GRUPO": ["E-mail Gerente Grupo"],
    "EMAIL_SUP_AUTO": ["E-mail Sup Auto"],
    "EMAIL_SUP_VENDAS": ["E-mail Sup Vendas"]
  };

  var list = aliases[targetHeader] || [];
  for (var i = 0; i < list.length; i++) {
    if (source[list[i]] !== undefined) return vektorPosCellToText_(source[list[i]]);
  }
  return "";
}

function vektorPosDiagnosticoCotaEmail() {
  var quota = MailApp.getRemainingDailyQuota();

  var resultado = {
    quotaRestanteDestinatarios: quota,
    contaExecutora: Session.getEffectiveUser().getEmail(),
    usuarioAtivo: Session.getActiveUser().getEmail(),
    verificadoEm: new Date().toISOString()
  };

  console.log(JSON.stringify(resultado));

  return resultado;
}

function testeGmailPos() {

  var resultado = {
    conta: Session.getEffectiveUser().getEmail(),
    quotaDestinatarios: MailApp.getRemainingDailyQuota(),
    getAliases: null,
    sendEmail: null
  };

  // TESTE 1
  try {
    var aliases = GmailApp.getAliases();

    resultado.getAliases = {
      ok: true,
      aliases: aliases
    };

  } catch (e) {

    resultado.getAliases = {
      ok: false,
      erro: e.message
    };
  }

  // TESTE 2
  try {

    GmailApp.sendEmail(
      Session.getEffectiveUser().getEmail(),
      "TESTE VEKTOR POS",
      "Teste de diagnóstico do GmailApp."
    );

    resultado.sendEmail = {
      ok: true
    };

  } catch (e) {

    resultado.sendEmail = {
      ok: false,
      erro: e.message
    };
  }

  console.log(JSON.stringify(resultado));

  return resultado;
}

function testeEnvioAliasVektor() {

  var destino =
    Session.getEffectiveUser().getEmail();

  try {

    GmailApp.sendEmail(
      destino,
      "TESTE VEKTOR - ALIAS",
      "Teste de envio usando diretamente o alias do Vektor.",
      {
        from: "usuario52@empresa.exemplo",
        name: "Vektor - Grupo SBF"
      }
    );

    console.log(
      JSON.stringify({
        ok: true,
        from: "usuario52@empresa.exemplo",
        to: destino
      })
    );

  } catch (e) {

    console.log(
      JSON.stringify({
        ok: false,
        erro: e.message
      })
    );
  }
}

function testeGmailApiVektor() {

  var destino =
    Session
      .getEffectiveUser()
      .getEmail();

  var resultado =
    vektorPosSendViaGmailApi_({
      to: destino,
      cc: "",
      subject:
        "TESTE VEKTOR - GMAIL API",
      htmlBody:
        "<h2>Teste Vektor</h2>" +
        "<p>Envio realizado pela Gmail API.</p>",
      from:
        "usuario52@empresa.exemplo",
      fromName:
        "Vektor - Grupo SBF",
      replyTo:
        "usuario01@empresa.exemplo"
    });

  console.log(
    JSON.stringify(resultado)
  );

  return resultado;
}