var VEKTOR_AR_MODULE_KEY = "AR";
var VEKTOR_AR_TITLE = "AR | Contas a Receber";

var VEKTOR_AR_JOB_PREFIX = "VEKTOR_AR_JOB_";
var VEKTOR_AR_JOB_TTL_HOURS = 6;

var VEKTOR_AR_PROSEGUR_CFG = {
  ID_PASTA_DRIVE: PropertiesService.getScriptProperties().getProperty("VEKTOR_AR_ID_PASTA_DRIVE") || "",
  ID_PASTA_PROCESSADOS_RAIZ: PropertiesService.getScriptProperties().getProperty("VEKTOR_AR_ID_PASTA_PROCESSADOS_RAIZ") || "",
  NOME_SUBMARCADOR: "CONTAS A RECEBER/Prosegur",
  REMETENTE_EMAIL: "usuario03@empresa.exemplo",
  ALIAS_PERMITIDO: "PROSEGUR CASH",
  ALIAS_BLOQUEADO: "SEGURPRO VIGILANCIA",
  DIA_INICIAL: 5,
  DIA_FINAL: 15,
  JANELA_DIAS_BUSCA: 90
};

var VEKTOR_AR_ANALYTICS_CFG = {
  SISTEMA_PROSEGUR_FOLDER_ID: PropertiesService.getScriptProperties().getProperty("VEKTOR_AR_SISTEMA_PROSEGUR_FOLDER_ID") || "",
  METRICS_FILE_NAME: "vektor_ar_metricas.json"
};

// =====================================================
// PROSEGUR - RELATÓRIO MENSAL DE INDICADORES POR E-MAIL
// =====================================================

var VEKTOR_AR_PROSEGUR_EMAIL_CFG = {

  // TESTE INICIAL
  // Depois da aprovação, basta trocar este endereço.
  DESTINATARIOS: [
    "usuario01@empresa.exemplo",
    "usuario02@empresa.exemplo",
    "usuario04@empresa.exemplo"
  ],

  ASSUNTO: "Indicadores Prosegur - Fisia e Centauro",

  NOME_REMETENTE: "Vektor",

  // Será utilizado somente se estiver configurado como alias
  // na conta Google que executar o gatilho.
  EMAIL_REMETENTE_PREFERIDO: "usuario05@empresa.exemplo",

  DIA_ENVIO: 25,

  // O exemplo abaixo deixa o envio na faixa das 08h.
  HORA_ENVIO: 8,

  TIMEZONE: "America/Sao_Paulo",

  // Evita envio duplicado no mesmo mês.
  PROP_ULTIMO_ENVIO:
    "VEKTOR_AR_PROSEGUR_RELATORIO_ULTIMO_MES"
};

var VEKTOR_RPA_SS_ID = PropertiesService.getScriptProperties().getProperty("VEKTOR_RPA_SS_ID") || "";
var VEKTOR_RPA_SHEET_NAME = "RPA";

function vektorRpaGetSheet_() {
  var ss = SpreadsheetApp.openById(VEKTOR_RPA_SS_ID);
  var sh = ss.getSheetByName(VEKTOR_RPA_SHEET_NAME);
  if (!sh) throw new Error('Aba "' + VEKTOR_RPA_SHEET_NAME + '" não encontrada.');
  return sh;
}

function vektorRpaEnsureHeader_() {
  var sh = vektorRpaGetSheet_();

  var exp = [
    "ID",
    "DATA_SOLICITACAO",
    "ORIGEM",
    "TIPO_ROBO",
    "STATUS",
    "DATA_INICIO",
    "DATA_FIM",
    "MENSAGEM",
    "LOG_PATH"
  ];

  var lastCol = Math.max(sh.getLastColumn(), exp.length);
  var hdr = sh.getRange(1, 1, 1, lastCol).getValues()[0].map(function (h) {
    return String(h || "").trim();
  });

  var ok = exp.every(function (name) {
    return hdr.indexOf(name) >= 0;
  });

  if (!ok) {
    sh.getRange(1, 1, 1, exp.length).setValues([exp]);
    sh.getRange(1, 1, 1, exp.length).setFontWeight("bold");
    sh.setFrozenRows(1);
  }

  return sh;
}

function vektorRpaNextId_(sh) {
  var lastRow = sh.getLastRow();
  if (lastRow < 2) return 1;

  var values = sh.getRange(2, 1, lastRow - 1, 1).getValues();
  var maxId = 0;

  values.forEach(function (r) {
    var n = Number(r[0] || 0);
    if (isFinite(n) && n > maxId) maxId = n;
  });

  return maxId + 1;
}

function vektorRpaSolicitarClara() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    var sh = vektorRpaEnsureHeader_();
    var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    var now = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd HH:mm:ss");
    var id = vektorRpaNextId_(sh);

    sh.appendRow([
      id,
      now,
      "VEKTOR",
      "CLARA",
      "PENDENTE",
      "",
      "",
      "Solicitação criada pelo Vektor por " + String(ctx.email || "").trim().toLowerCase(),
      ""
    ]);

    return {
      ok: true,
      id: id,
      status: "PENDENTE",
      dataSolicitacao: now,
      mensagem: "Solicitação enviada para a fila local do Robô Vektor."
    };

  } catch (e) {
    return {
      ok: false,
      error: e && e.message ? e.message : String(e)
    };
  }
}

function vektorRpaGetUltimoClara() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    var sh = vektorRpaEnsureHeader_();
    var lastRow = sh.getLastRow();

    if (lastRow < 2) {
      return {
        ok: true,
        found: false
      };
    }

    var values = sh.getRange(2, 1, lastRow - 1, 9).getValues();

    for (var i = values.length - 1; i >= 0; i--) {
      var r = values[i];

      if (String(r[2] || "").trim().toUpperCase() !== "VEKTOR") continue;
      if (String(r[3] || "").trim().toUpperCase() !== "CLARA") continue;

      return {
        ok: true,
        found: true,
        rowNumber: i + 2,
        id: r[0],
        dataSolicitacao: String(r[1] || ""),
        origem: String(r[2] || ""),
        tipoRobo: String(r[3] || ""),
        status: String(r[4] || ""),
        dataInicio: String(r[5] || ""),
        dataFim: String(r[6] || ""),
        mensagem: String(r[7] || ""),
        logPath: String(r[8] || "")
      };
    }

    return {
      ok: true,
      found: false
    };

  } catch (e) {
    return {
      ok: false,
      error: e && e.message ? e.message : String(e)
    };
  }
}

function vektorNumerarioGetWebAppUrl() {
  vektorAssertFunctionAllowed_("vektorNumerarioGetWebAppUrl");
  vektorAssertModuleAllowed_("AR");

  return {
    ok: true,
    url: ScriptApp.getService().getUrl() + "?view=numerario"
  };
}

var VEKTOR_RPA_API_TOKEN_PROP = "VEKTOR_RPA_API_TOKEN";

function vektorRpaApiValidateToken_(token) {
  var expected = PropertiesService.getScriptProperties().getProperty(VEKTOR_RPA_API_TOKEN_PROP);
  if (!expected) throw new Error("Token RPA não configurado nas Script Properties.");
  if (String(token || "") !== String(expected)) throw new Error("Token RPA inválido.");
}

function vektorRpaApiJson_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function vektorRpaApiHandleGet_(p) {
  try {
    vektorRpaApiValidateToken_(p.token);

    var action = String(p.rpa_action || "").trim();

    if (action === "next") {
      return vektorRpaApiJson_(vektorRpaApiGetNextPendingClara_());
    }

    if (action === "update") {
      return vektorRpaApiJson_(vektorRpaApiUpdateClara_(p));
    }

    return vektorRpaApiJson_({
      ok: false,
      error: "Ação RPA inválida."
    });

  } catch (e) {
    return vektorRpaApiJson_({
      ok: false,
      error: e && e.message ? e.message : String(e)
    });
  }
}

function vektorRpaApiGetNextPendingClara_() {
  var sh = vektorRpaEnsureHeader_();
  var lastRow = sh.getLastRow();

  if (lastRow < 2) {
    return { ok: true, found: false };
  }

  var values = sh.getRange(2, 1, lastRow - 1, 9).getValues();

  for (var i = 0; i < values.length; i++) {
    var r = values[i];

    if (String(r[2] || "").trim().toUpperCase() !== "VEKTOR") continue;
    if (String(r[3] || "").trim().toUpperCase() !== "CLARA") continue;
    if (String(r[4] || "").trim().toUpperCase() !== "PENDENTE") continue;

    return {
      ok: true,
      found: true,
      rowNumber: i + 2,
      id: r[0],
      dataSolicitacao: String(r[1] || ""),
      origem: String(r[2] || ""),
      tipoRobo: String(r[3] || ""),
      status: String(r[4] || "")
    };
  }

  return { ok: true, found: false };
}

function vektorRpaApiUpdateClara_(p) {
  var rowNumber = Number(p.rowNumber || 0);
  if (!rowNumber || rowNumber < 2) throw new Error("rowNumber inválido.");

  var status = String(p.status || "").trim().toUpperCase();
  var allowed = {
    "EM_EXECUCAO": true,
    "CONCLUIDO": true,
    "ERRO": true
  };

  if (!allowed[status]) throw new Error("Status inválido: " + status);

  var sh = vektorRpaEnsureHeader_();
  var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
  var now = Utilities.formatDate(new Date(), tz, "yyyy-MM-dd HH:mm:ss");

  sh.getRange(rowNumber, 5).setValue(status);
  sh.getRange(rowNumber, 8).setValue(String(p.mensagem || ""));
  sh.getRange(rowNumber, 9).setValue(String(p.logPath || ""));

  if (status === "EM_EXECUCAO") {
    sh.getRange(rowNumber, 6).setValue(now);
  }

  if (status === "CONCLUIDO" || status === "ERRO") {
    sh.getRange(rowNumber, 7).setValue(now);
  }

  return {
    ok: true,
    rowNumber: rowNumber,
    status: status
  };
}

function vektorArGetProsegurDashboard() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    var elegiveis = vektorArCountEmailsElegiveisProsegur_();
    var pendentes = vektorArCountEmailsPendentesMarcador_();
    var pastaStats = vektorArGetDriveStatsProsegur_();
    var ultimoJob = vektorArGetLastJobSnapshot_();

    return {
      ok: true,
      modulo: VEKTOR_AR_MODULE_KEY,
      title: VEKTOR_AR_TITLE,
      email: ctx.email,
      role: ctx.role,
      resumo: {
        emailsElegiveisInbox: elegiveis,
        emailsPendentesMarcador: pendentes,
        arquivosNaPastaDestino: pastaStats.totalDestino,
        arquivosNaPastaProcessadosMes: pastaStats.totalProcessadosMes,
        ultimaExecucao: ultimoJob && ultimoJob.startedAt ? ultimoJob.startedAt : "",
        ultimoStatus: ultimoJob && ultimoJob.status ? ultimoJob.status : ""
      }
    };
  } catch (e) {
    return {
      ok: false,
      error: (e && e.message) ? e.message : String(e)
    };
  }
}

function vektorArStartProsegurJob() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var ativo = vektorArFindRunningJob_();
    if (ativo && ativo.jobId) {
      return {
        ok: true,
        alreadyRunning: true,
        jobId: ativo.jobId,
        status: ativo.status || "RUNNING",
        startedAt: ativo.startedAt || ""
      };
    }

    var jobId = Utilities.getUuid();
    var now = new Date();
    var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";

    var snapshot = {
      jobId: jobId,
      modulo: VEKTOR_AR_MODULE_KEY,
      status: "QUEUED",
      stageKey: "queued",
      stageLabel: "Execução preparada.",
      progressPct: 4,
      startedAt: Utilities.formatDate(now, tz, "yyyy-MM-dd HH:mm:ss"),
      startedAtIso: now.toISOString(),
      finishedAt: "",
      finishedAtIso: "",
      userEmail: String(ctx.email || "").trim().toLowerCase(),
      userRole: String(ctx.role || "").trim(),
      details: [
        {
          at: now.toISOString(),
          label: "Execução preparada."
        }
      ],
      metrics: {
        emailsElegiveisInbox: 0,
        emailsPendentesMarcador: 0,
        arquivosNaPastaDestino: 0,
        arquivosNaPastaProcessadosMes: 0,
        totalEmailsVistos: 0,
        totalArquivosSalvos: 0,
        totalArquivosIgnorados: 0,
        totalThreadsLote: 0
      }
    };

    try {
      snapshot.metrics.emailsElegiveisInbox = vektorArCountEmailsElegiveisProsegur_();
    } catch (_) {}

    try {
      snapshot.metrics.emailsPendentesMarcador = vektorArCountEmailsPendentesMarcador_();
    } catch (_) {}

    try {
      var pastaStats = vektorArGetDriveStatsProsegur_();
      snapshot.metrics.arquivosNaPastaDestino = pastaStats.totalDestino;
      snapshot.metrics.arquivosNaPastaProcessadosMes = pastaStats.totalProcessadosMes;
    } catch (_) {}

    vektorArSaveJobSnapshot_(snapshot);
    vektorArSetLastJobId_(jobId);

    return {
      ok: true,
      alreadyRunning: false,
      jobId: jobId,
      status: snapshot.status,
      startedAt: snapshot.startedAt
    };
  } finally {
    lock.releaseLock();
  }
}

function vektorArRunProsegurJob(jobId) {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    jobId = String(jobId || "").trim();
    if (!jobId) throw new Error("JobId não informado.");

    var snapshot = vektorArGetJobSnapshot_(jobId);
    if (!snapshot || !snapshot.jobId) {
      throw new Error("Job não encontrado.");
    }

    if (snapshot.status === "RUNNING") {
      return snapshot;
    }

    if (snapshot.status === "DONE") {
      return snapshot;
    }

    if (snapshot.status === "ERROR") {
      return snapshot;
    }

    snapshot.status = "RUNNING";
    snapshot.stageKey = "starting";
    snapshot.stageLabel = "Iniciando processamento Prosegur...";
    snapshot.progressPct = 8;
    vektorArPushJobDetail_(snapshot, "Iniciando processamento Prosegur...");
    vektorArSaveJobSnapshot_(snapshot);

    var logsAuditoria = {
      data_geracao: new Date().toISOString(),
      total_threads_lote: 0,
      total_emails_vistos: 0,
      total_arquivos_salvos: 0,
      total_arquivos_ignorados: 0,
      detalhes: []
    };

    snapshot.stageKey = "labeling";
    snapshot.stageLabel = "Etapa 1/3 • Rotulando e arquivando e-mails elegíveis...";
    snapshot.progressPct = 26;
    vektorArPushJobDetail_(snapshot, snapshot.stageLabel);
    vektorArSaveJobSnapshot_(snapshot);

    Maker_PDF.libRotularEmailsProsegur(logsAuditoria);

    try {
      snapshot.metrics.emailsPendentesMarcador = vektorArCountEmailsPendentesMarcador_();
    } catch (_) {}

    snapshot.stageKey = "saving";
    snapshot.stageLabel = "Etapa 2/3 • Salvando anexos PDF no Drive...";
    snapshot.progressPct = 68;
    vektorArPushJobDetail_(snapshot, snapshot.stageLabel);
    vektorArSaveJobSnapshot_(snapshot);

    Maker_PDF.libSalvarAnexosProsegur(logsAuditoria);

    snapshot.stageKey = "audit";
    snapshot.stageLabel = "Etapa 3/3 • Gerando auditoria final...";
    snapshot.progressPct = 92;
    vektorArPushJobDetail_(snapshot, snapshot.stageLabel);
    vektorArSaveJobSnapshot_(snapshot);

    Maker_PDF.libSalvarRelatorioAuditoriaProsegur(logsAuditoria);

    snapshot.status = "DONE";
    snapshot.stageKey = "done";
    snapshot.stageLabel = "Processamento concluído com sucesso.";
    snapshot.progressPct = 100;

    snapshot.metrics.totalEmailsVistos = Number(logsAuditoria.total_emails_vistos || 0);
    snapshot.metrics.totalArquivosSalvos = Number(logsAuditoria.total_arquivos_salvos || 0);
    snapshot.metrics.totalArquivosIgnorados = Number(logsAuditoria.total_arquivos_ignorados || 0);
    snapshot.metrics.totalThreadsLote = Number(logsAuditoria.total_threads_lote || 0);

    try {
      var pastaStatsFim = vektorArGetDriveStatsProsegur_();
      snapshot.metrics.arquivosNaPastaDestino = pastaStatsFim.totalDestino;
      snapshot.metrics.arquivosNaPastaProcessadosMes = pastaStatsFim.totalProcessadosMes;
    } catch (_) {}

    var dtFim = new Date();
    var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    snapshot.finishedAt = Utilities.formatDate(dtFim, tz, "yyyy-MM-dd HH:mm:ss");
    snapshot.finishedAtIso = dtFim.toISOString();

    vektorArPushJobDetail_(snapshot, "Processamento concluído com sucesso.");
    vektorArSaveJobSnapshot_(snapshot);

    return snapshot;

  } catch (e) {
    var err = (e && e.message) ? e.message : String(e);

    try {
      var snapErr = vektorArGetJobSnapshot_(jobId) || {};
      snapErr.jobId = jobId;
      snapErr.status = "ERROR";
      snapErr.stageKey = "error";
      snapErr.stageLabel = err;
      snapErr.progressPct = Math.min(Number(snapErr.progressPct || 0), 96);

      var dtErr = new Date();
      var tzErr = Session.getScriptTimeZone() || "America/Sao_Paulo";
      snapErr.finishedAt = Utilities.formatDate(dtErr, tzErr, "yyyy-MM-dd HH:mm:ss");
      snapErr.finishedAtIso = dtErr.toISOString();

      vektorArPushJobDetail_(snapErr, "Erro na execução: " + err);
      vektorArSaveJobSnapshot_(snapErr);

      return snapErr;
    } catch (_) {
      return {
        ok: false,
        status: "ERROR",
        error: err
      };
    }
  }
}

function vektorArGetProsegurJobStatus(jobId) {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    jobId = String(jobId || "").trim();
    if (!jobId) throw new Error("JobId não informado.");

    var snapshot = vektorArGetJobSnapshot_(jobId);
    if (!snapshot || !snapshot.jobId) {
      throw new Error("Job não encontrado.");
    }

    return {
      ok: true,
      job: snapshot
    };
  } catch (e) {
    return {
      ok: false,
      error: (e && e.message) ? e.message : String(e)
    };
  }
}

function vektorArGetProsegurManifestPreview(limit) {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    limit = Number(limit || 20);
    if (limit < 1) limit = 1;
    if (limit > 100) limit = 100;

    var pasta = DriveApp.getFolderById(VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_DRIVE);
    var files = pasta.getFilesByName("AUDITORIA_EMAIL.json");
    if (!files.hasNext()) {
      return { ok: true, rows: [] };
    }

    var jsonTxt = files.next().getBlob().getDataAsString("UTF-8");
    var obj = JSON.parse(jsonTxt || "{}");
    var detalhes = Array.isArray(obj.detalhes) ? obj.detalhes : [];

    var rows = detalhes.slice(-limit).reverse().map(function (d) {
      var arquivos = Array.isArray(d.arquivos) ? d.arquivos : [];
      return {
        assunto: String(d.assunto || ""),
        data: String(d.data || ""),
        status: String(d.status || ""),
        arquivos: arquivos.map(function (a) {
          return {
            nome: String((a && a.nome) || ""),
            status: String((a && a.status) || "")
          };
        })
      };
    });

    return {
      ok: true,
      rows: rows
    };
  } catch (e) {
    return {
      ok: false,
      error: (e && e.message) ? e.message : String(e)
    };
  }
}

function vektorArGetProsegurAnalytics(req) {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    req = req || {};
    var mode = String(req.mode || "latest").trim().toLowerCase(); // latest | full
    var empresa = String(req.empresa || "").trim().toUpperCase();
    var periodo = String(req.periodo || "").trim();

    var folder = DriveApp.getFolderById(VEKTOR_AR_ANALYTICS_CFG.SISTEMA_PROSEGUR_FOLDER_ID);
    var files = folder.getFilesByName(VEKTOR_AR_ANALYTICS_CFG.METRICS_FILE_NAME);

    if (!files.hasNext()) {
      return { ok: false, error: "Arquivo analítico não encontrado na pasta SISTEMA_PROSEGUR." };
    }

    var txt = files.next().getBlob().getDataAsString("UTF-8");
    var obj = JSON.parse(txt || "{}");

    var root = (mode === "full") ? (obj.full_base || {}) : (obj.latest_execution || {});
    var rows = Array.isArray(root.by_periodo_empresa) ? root.by_periodo_empresa.slice() : [];
    var tipos = Array.isArray(root.by_tipo) ? root.by_tipo.slice() : [];
    var cards = root.cards || {};

    if (empresa) {
      rows = rows.filter(function (r) {
        return String(r.empresa || "").trim().toUpperCase() === empresa;
      });
      tipos = tipos.filter(function (r) {
        return String(r.empresa || "").trim().toUpperCase() === empresa;
      });
    }

    if (periodo) {
      rows = rows.filter(function (r) {
        return String(r.periodo || "").trim() === periodo;
      });
      tipos = tipos.filter(function (r) {
        return String(r.periodo || "").trim() === periodo;
      });
    }

    var periodos = {};
    var empresas = {};
    rows.forEach(function (r) {
      var p = String(r.periodo || "").trim();
      var e = String(r.empresa || "").trim().toUpperCase();
      if (p) periodos[p] = true;
      if (e) empresas[e] = true;
    });

    return {
      ok: true,
      generatedAt: String(obj.generated_at || ""),
      executionId: String(obj.execution_id || ""),
      mode: mode,
      cards: cards,
      periodos: Object.keys(periodos).sort(),
      empresas: Object.keys(empresas).sort(),
      rows: rows,
      tipos: tipos
    };

  } catch (e) {
    return {
      ok: false,
      error: (e && e.message) ? e.message : String(e)
    };
  }
}

// =====================================================
// PROSEGUR - RELATÓRIO MENSAL DE INDICADORES
// =====================================================

function vektorArEmailGetFullAnalytics_() {

  var folder = DriveApp.getFolderById(
    VEKTOR_AR_ANALYTICS_CFG.SISTEMA_PROSEGUR_FOLDER_ID
  );

  var files = folder.getFilesByName(
    VEKTOR_AR_ANALYTICS_CFG.METRICS_FILE_NAME
  );

  if (!files.hasNext()) {
    throw new Error(
      "Arquivo analítico da Prosegur não encontrado."
    );
  }

  var txt = files
    .next()
    .getBlob()
    .getDataAsString("UTF-8");

  var obj = JSON.parse(txt || "{}");

  // IMPORTANTE:
  // O relatório mensal SEMPRE utiliza full_base.
  var root = obj.full_base || {};

  return {
    ok: true,
    generatedAt: String(obj.generated_at || ""),
    executionId: String(obj.execution_id || ""),
    cards: root.cards || {},
    rows: Array.isArray(root.by_periodo_empresa)
      ? root.by_periodo_empresa.slice()
      : [],
    tipos: Array.isArray(root.by_tipo)
      ? root.by_tipo.slice()
      : []
  };
}


// -----------------------------------------------------
// Helpers de formatação
// -----------------------------------------------------

function vektorArEmailEscapeHtml_(value) {
  return String(
    value === null || value === undefined
      ? ""
      : value
  )
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


function vektorArEmailFmtBrl_(value) {

  var n = Number(value || 0);

  if (!isFinite(n)) {
    n = 0;
  }

  var negativo = n < 0;

  n = Math.abs(n);

  var partes = n
    .toFixed(2)
    .split(".");

  partes[0] = partes[0].replace(
    /\B(?=(\d{3})+(?!\d))/g,
    "."
  );

  return (
    (negativo ? "-" : "") +
    "R$ " +
    partes[0] +
    "," +
    partes[1]
  );
}


function vektorArEmailFmtInt_(value) {

  var n = Number(value || 0);

  if (!isFinite(n)) {
    n = 0;
  }

  return String(
    Math.round(n)
  ).replace(
    /\B(?=(\d{3})+(?!\d))/g,
    "."
  );
}


function vektorArEmailFmtDateTime_(value) {

  if (!value) {
    return "—";
  }

  try {

    var d = new Date(value);

    if (isNaN(d.getTime())) {
      return String(value);
    }

    return Utilities.formatDate(
      d,
      VEKTOR_AR_PROSEGUR_EMAIL_CFG.TIMEZONE,
      "dd/MM/yyyy HH:mm:ss"
    );

  } catch (_) {

    return String(value);

  }
}


function vektorArEmailPeriodoKey_(periodo) {

  var txt = String(
    periodo || ""
  ).trim();

  var m = txt.match(
    /^(\d{2})[-\/](\d{4})$/
  );

  if (!m) {
    return txt;
  }

  return m[2] + "-" + m[1];
}


// -----------------------------------------------------
// Montagem do modelo
// -----------------------------------------------------

function vektorArEmailBuildModel_(data) {

  data = data || {};

  var cards = data.cards || {};

  var rows = Array.isArray(data.rows)
    ? data.rows.slice()
    : [];

  rows.sort(function(a, b) {

    var pa = vektorArEmailPeriodoKey_(
      a.periodo
    );

    var pb = vektorArEmailPeriodoKey_(
      b.periodo
    );

    if (pa < pb) return -1;
    if (pa > pb) return 1;

    return String(
      a.empresa || ""
    ).localeCompare(
      String(b.empresa || "")
    );
  });


  var byEmpresa = {};
  var byPeriodo = {};
  var periodoMap = {};
  var empresasMap = {};

  var somaDocs = 0;
  var somaValor = 0;


  rows.forEach(function(r) {

    var empresa = String(
      r.empresa || "—"
    ).trim() || "—";

    var periodo = String(
      r.periodo || "—"
    ).trim() || "—";

    var valor = Number(
      r.valor || 0
    );

    var docs = Number(
      r.docs || 0
    );

    if (!isFinite(valor)) {
      valor = 0;
    }

    if (!isFinite(docs)) {
      docs = 0;
    }

    somaDocs += docs;
    somaValor += valor;

    empresasMap[empresa] = true;

    byEmpresa[empresa] =
      (byEmpresa[empresa] || 0) +
      valor;

    byPeriodo[periodo] =
      (byPeriodo[periodo] || 0) +
      valor;


    if (!periodoMap[periodo]) {

      periodoMap[periodo] = {
        periodo: periodo,
        total: 0,
        empresas: {}
      };

    }

    periodoMap[periodo].total += valor;

    periodoMap[periodo].empresas[empresa] =
      (
        periodoMap[periodo]
          .empresas[empresa] || 0
      ) + valor;

  });


  var empresas = Object.keys(
    empresasMap
  ).sort();


  var periodos = Object.keys(
    periodoMap
  ).sort(function(a, b) {

    var ka =
      vektorArEmailPeriodoKey_(a);

    var kb =
      vektorArEmailPeriodoKey_(b);

    if (ka < kb) return -1;
    if (ka > kb) return 1;

    return 0;
  });


  var rowsEmpresa =
    Object.keys(byEmpresa)
      .map(function(k) {

        return {
          empresa: k,
          valor: byEmpresa[k]
        };

      })
      .sort(function(a, b) {

        return b.valor - a.valor;

      });


  var rowsPeriodo =
    Object.keys(byPeriodo)
      .map(function(k) {

        return {
          periodo: k,
          valor: byPeriodo[k]
        };

      })
      .sort(function(a, b) {

        var ka =
          vektorArEmailPeriodoKey_(
            a.periodo
          );

        var kb =
          vektorArEmailPeriodoKey_(
            b.periodo
          );

        if (ka < kb) return -1;
        if (ka > kb) return 1;

        return 0;
      });


  var totalDocs =
    Number(cards.total_docs);

  if (!isFinite(totalDocs)) {
    totalDocs = somaDocs;
  }


  var totalValor =
    Number(cards.total_valor);

  if (!isFinite(totalValor)) {
    totalValor = somaValor;
  }


  return {

    cards: cards,

    rows: rows,

    rowsEmpresa: rowsEmpresa,

    rowsPeriodo: rowsPeriodo,

    periodoMap: periodoMap,

    empresas: empresas,

    periodos: periodos,

    totalDocs: totalDocs,

    totalValor: totalValor,

    generatedAt:
      data.generatedAt || ""

  };
}


// -----------------------------------------------------
// Barras HTML
// -----------------------------------------------------

function vektorArEmailBuildBars_(
  rows,
  labelKey
) {

  rows = Array.isArray(rows)
    ? rows
    : [];

  if (!rows.length) {

    return (
      '<div style="' +
        'font-size:13px;' +
        'color:#64748b;' +
      '">' +
        'Sem dados.' +
      '</div>'
    );

  }


  var max = 0;

  rows.forEach(function(r) {

    var v = Number(
      r.valor || 0
    );

    if (v > max) {
      max = v;
    }

  });


  if (max <= 0) {
    max = 1;
  }


  return rows.map(function(r) {

    var label =
      vektorArEmailEscapeHtml_(
        r[labelKey] || "—"
      );

    var valor = Number(
      r.valor || 0
    );

    var pct = Math.max(
      2,
      Math.round(
        (valor / max) * 100
      )
    );


    return (

      '<div style="' +
        'margin-bottom:16px;' +
      '">' +

        '<table role="presentation" ' +
          'width="100%" ' +
          'cellpadding="0" ' +
          'cellspacing="0">' +

          '<tr>' +

            '<td style="' +
              'font-family:Arial,sans-serif;' +
              'font-size:13px;' +
              'font-weight:700;' +
              'color:#0f172a;' +
            '">' +
              label +
            '</td>' +

            '<td align="right" style="' +
              'font-family:Arial,sans-serif;' +
              'font-size:13px;' +
              'font-weight:800;' +
              'color:#0f2d5c;' +
            '">' +
              vektorArEmailFmtBrl_(
                valor
              ) +
            '</td>' +

          '</tr>' +

        '</table>' +


        '<div style="' +
          'height:13px;' +
          'margin-top:6px;' +
          'background:#e2e8f0;' +
          'border-radius:999px;' +
          'overflow:hidden;' +
        '">' +

          '<div style="' +
            'height:13px;' +
            'width:' + pct + '%;' +
            'background:#005E27;' +
            'border-radius:999px;' +
          '"></div>' +

        '</div>' +

      '</div>'

    );

  }).join("");
}


// -----------------------------------------------------
// Cores das empresas
// -----------------------------------------------------

function vektorArEmailEmpresaColor_(
  empresa,
  idx
) {

  var nome = String(
    empresa || ""
  ).toUpperCase();

  if (nome === "SBF") {
    return "#0f2d5c";
  }

  if (nome === "FISIA") {
    return "#84cc16";
  }

  var palette = [
    "#2563eb",
    "#9333ea",
    "#f59e0b",
    "#ef4444",
    "#14b8a6",
    "#8b5cf6"
  ];

  return palette[
    idx % palette.length
  ];
}

function vektorArEmailBuildComboChart_(model) {

  if (!model || !Array.isArray(model.periodos) || !model.periodos.length) {
    throw new Error("Não há períodos disponíveis para gerar o gráfico.");
  }

  if (!Array.isArray(model.empresas) || !model.empresas.length) {
    throw new Error("Não há empresas disponíveis para gerar o gráfico.");
  }

  var width = 1200;
  var height = 500;

  var margin = {
    top: 92,
    right: 105,
    bottom: 72,
    left: 92
  };

  var chartX = margin.left;
  var chartY = margin.top;
  var chartW = width - margin.left - margin.right;
  var chartH = height - margin.top - margin.bottom;

  function esc_(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function fmtShortBrl_(n) {
    n = Number(n || 0);
    if (!isFinite(n)) n = 0;

    if (Math.abs(n) >= 1000) {
      var k = (n / 1000).toFixed(1).replace(".", ",");
      return "R$ " + k + "k";
    }

    return vektorArEmailFmtBrl_(n);
  }

  function fmtPct_(n) {
    n = Number(n || 0);
    if (!isFinite(n)) n = 0;
    return n.toFixed(2).replace(".", ",") + "%";
  }

  function niceCeil_(max) {
    max = Number(max || 0);
    if (!isFinite(max) || max <= 0) return 10;

    var exp = Math.pow(10, Math.floor(Math.log(max) / Math.LN10));
    var f = max / exp;

    var nice;
    if (f <= 1) nice = 1;
    else if (f <= 2) nice = 2;
    else if (f <= 5) nice = 5;
    else nice = 10;

    return nice * exp;
  }

  function nicePctMax_(maxAbs) {
    maxAbs = Number(maxAbs || 0);
    if (!isFinite(maxAbs) || maxAbs <= 0) return 10;

    if (maxAbs <= 5) return 5;
    if (maxAbs <= 10) return 10;
    if (maxAbs <= 15) return 15;
    if (maxAbs <= 20) return 20;
    if (maxAbs <= 25) return 25;
    if (maxAbs <= 30) return 30;
    if (maxAbs <= 40) return 40;
    if (maxAbs <= 50) return 50;

    return Math.ceil(maxAbs / 10) * 10;
  }

  function yFromValor_(valor, maxValor) {
    var p = maxValor > 0 ? (valor / maxValor) : 0;
    return chartY + chartH - (p * chartH);
  }

  function yFromPct_(pct, pctMax) {
    var top = pctMax;
    var bottom = -pctMax;
    var ratio = (top - pct) / (top - bottom);
    return chartY + (ratio * chartH);
  }

  var empresas = model.empresas.slice();
  var periodos = model.periodos.slice();

  var data = [];
  var maxBarValue = 0;
  var maxAbsPct = 0;

  periodos.forEach(function(periodo, idx) {
    var pObj = model.periodoMap[periodo] || { empresas: {}, total: 0 };
    var vals = {};
    var total = Number(pObj.total || 0);
    if (!isFinite(total)) total = 0;

    empresas.forEach(function(emp) {
      var v = Number((pObj.empresas || {})[emp] || 0);
      if (!isFinite(v)) v = 0;
      vals[emp] = v;
      if (v > maxBarValue) maxBarValue = v;
    });

    var pct = null;

    if (idx > 0) {
      var prevPeriodo = periodos[idx - 1];
      var prevObj = model.periodoMap[prevPeriodo] || { total: 0 };
      var prevTotal = Number(prevObj.total || 0);

      if (isFinite(prevTotal) && prevTotal > 0) {
        pct = ((total - prevTotal) / prevTotal) * 100;
        if (Math.abs(pct) > maxAbsPct) {
          maxAbsPct = Math.abs(pct);
        }
      }
    }

    data.push({
      periodo: periodo,
      total: total,
      vals: vals,
      pct: pct
    });
  });

  var maxValorEixo = niceCeil_(maxBarValue * 1.08);
  var pctAxisMax = nicePctMax_(maxAbsPct || 10);

  var slotW = chartW / data.length;
  var groupW = Math.min(slotW * 0.62, 140);
  var barGap = 6;
  var barW = (groupW - (barGap * (empresas.length - 1))) / empresas.length;

  if (barW < 16) barW = 16;

  var svg = [];

  svg.push(
    '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="' + height + '" viewBox="0 0 ' + width + ' ' + height + '">'
  );

  svg.push(
    '<rect x="0" y="0" width="' + width + '" height="' + height + '" fill="#ffffff"></rect>'
  );

  // Título
  svg.push(
    '<text x="24" y="34" font-family="Arial" font-size="17" font-weight="800" fill="#0f172a">Valor por período / empresa + variação mensal (%)</text>'
  );

  svg.push(
    '<text x="24" y="59" font-family="Arial" font-size="12" fill="#64748b">Barras verticais por empresa no eixo X por período, com linha de variação mensal do valor consolidado.</text>'
  );

  // Legenda
  var legendX = chartX;
  var legendY = 78;

  empresas.forEach(function(emp, idx) {
    var color = vektorArEmailEmpresaColor_(emp, idx);
    var blockX = legendX + (idx * 110);

    svg.push(
      '<rect x="' + blockX + '" y="' + (legendY - 11) + '" width="16" height="16" fill="' + color + '"></rect>'
    );

    svg.push(
      '<text x="' + (blockX + 22) + '" y="' + (legendY + 2) + '" font-family="Arial" font-size="12" font-weight="700" fill="#0f172a">' + esc_(emp) + '</text>'
    );
  });

  // Grid valor
  var ticksValor = 5;

  for (var i = 0; i <= ticksValor; i++) {
    var v = (maxValorEixo / ticksValor) * i;
    var y = yFromValor_(v, maxValorEixo);

    svg.push(
      '<line x1="' + chartX + '" y1="' + y.toFixed(2) + '" x2="' + (chartX + chartW) + '" y2="' + y.toFixed(2) + '" stroke="#e2e8f0" stroke-width="1"></line>'
    );

    svg.push(
      '<text x="' + (chartX - 10) + '" y="' + (y + 4).toFixed(2) + '" text-anchor="end" font-family="Arial" font-size="11" fill="#64748b">' + esc_(fmtShortBrl_(v)) + '</text>'
    );
  }

  // Eixo Y esquerdo
  svg.push(
    '<text x="38" y="' + (chartY + chartH / 2) + '" transform="rotate(-90 38 ' + (chartY + chartH / 2) + ')" font-family="Arial" font-size="12" font-weight="700" fill="#334155">Valor (R$)</text>'
  );

  // Eixo Y direito percentual
  var pctTicks = [pctAxisMax, pctAxisMax / 2, 0, -pctAxisMax / 2, -pctAxisMax];

  pctTicks.forEach(function(pct) {
    var y = yFromPct_(pct, pctAxisMax);

    svg.push(
      '<text x="' + (chartX + chartW + 12) + '" y="' + (y + 4).toFixed(2) + '" font-family="Arial" font-size="11" font-weight="700" fill="#166534">' + esc_(fmtPct_(pct)) + '</text>'
    );
  });

  // Eixos
  svg.push(
    '<line x1="' + chartX + '" y1="' + chartY + '" x2="' + chartX + '" y2="' + (chartY + chartH) + '" stroke="#94a3b8" stroke-width="1.2"></line>'
  );

  svg.push(
    '<line x1="' + chartX + '" y1="' + (chartY + chartH) + '" x2="' + (chartX + chartW) + '" y2="' + (chartY + chartH) + '" stroke="#94a3b8" stroke-width="1.2"></line>'
  );

  var linePoints = [];

  // Barras + labels + x-axis
  data.forEach(function(item, idx) {
    var slotX = chartX + (slotW * idx);
    var groupX = slotX + ((slotW - groupW) / 2);

    empresas.forEach(function(emp, eIdx) {
      var valor = Number(item.vals[emp] || 0);
      var barH = maxValorEixo > 0 ? (valor / maxValorEixo) * chartH : 0;
      var x = groupX + (eIdx * (barW + barGap));
      var y = chartY + chartH - barH;
      var color = vektorArEmailEmpresaColor_(emp, eIdx);

      svg.push(
        '<rect x="' + x.toFixed(2) + '" y="' + y.toFixed(2) + '" width="' + barW.toFixed(2) + '" height="' + Math.max(0, barH).toFixed(2) + '" rx="4" ry="4" fill="' + color + '"></rect>'
      );

      svg.push(
        '<text x="' + (x + barW / 2).toFixed(2) + '" y="' + Math.max(chartY - 4, y - 8).toFixed(2) + '" text-anchor="middle" font-family="Arial" font-size="11" font-weight="800" fill="#0f172a">' + esc_(fmtShortBrl_(valor)) + '</text>'
      );
    });

    var centerX = slotX + (slotW / 2);

    svg.push(
      '<text x="' + centerX.toFixed(2) + '" y="' + (chartY + chartH + 18) + '" text-anchor="middle" font-family="Arial" font-size="11" font-weight="800" fill="#334155">' + esc_(item.periodo) + '</text>'
    );

    if (item.pct !== null && isFinite(item.pct)) {
      linePoints.push({
        x: centerX,
        y: yFromPct_(item.pct, pctAxisMax),
        pct: item.pct
      });
    }
  });

  // Linha de variação
  if (linePoints.length) {
    svg.push(
      '<polyline fill="none" stroke="#16a34a" stroke-width="3" points="' +
      linePoints.map(function(pt) {
        return pt.x.toFixed(2) + ',' + pt.y.toFixed(2);
      }).join(' ') +
      '"></polyline>'
    );

    linePoints.forEach(function(pt) {
      var pctTxt = fmtPct_(pt.pct);
      var boxW = Math.max(54, pctTxt.length * 7 + 16);
      var boxH = 22;
      var boxX = pt.x - (boxW / 2);
      var boxY = Math.max(chartY + 4, pt.y - 34);

      svg.push(
        '<circle cx="' + pt.x.toFixed(2) + '" cy="' + pt.y.toFixed(2) + '" r="5.5" fill="#16a34a" stroke="#ffffff" stroke-width="2"></circle>'
      );

      svg.push(
        '<rect x="' + boxX.toFixed(2) + '" y="' + boxY.toFixed(2) + '" width="' + boxW.toFixed(2) + '" height="' + boxH + '" rx="6" ry="6" fill="#ecfdf5" stroke="#16a34a" stroke-width="1.2"></rect>'
      );

      svg.push(
        '<text x="' + pt.x.toFixed(2) + '" y="' + (boxY + 15).toFixed(2) + '" text-anchor="middle" font-family="Arial" font-size="11" font-weight="900" fill="#14532d">' + esc_(pctTxt) + '</text>'
      );
    });
  }

  svg.push('</svg>');

  return Utilities.newBlob(
    svg.join(""),
    "image/svg+xml",
    "indicadores_prosegur.svg"
  );
}

// -----------------------------------------------------
// Corpo completo do e-mail
// -----------------------------------------------------

function vektorArEmailBuildHtml_(
  model
) {

  var rowsHtml = "";


  model.rows.forEach(
    function(r, index) {

      var bg =
        index % 2 === 0
          ? "#ffffff"
          : "#f8fafc";


      rowsHtml +=

        '<tr style="' +
          'background:' + bg + ';' +
        '">' +

          '<td style="' +
            'padding:10px;' +
            'border-bottom:1px solid #e2e8f0;' +
            'font-family:Arial,sans-serif;' +
            'font-size:12px;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailEscapeHtml_(
              r.periodo || ""
            ) +
          '</td>' +

          '<td style="' +
            'padding:10px;' +
            'border-bottom:1px solid #e2e8f0;' +
            'font-family:Arial,sans-serif;' +
            'font-size:12px;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailEscapeHtml_(
              r.empresa || ""
            ) +
          '</td>' +

          '<td align="center" style="' +
            'padding:10px;' +
            'border-bottom:1px solid #e2e8f0;' +
            'font-family:Arial,sans-serif;' +
            'font-size:12px;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailFmtInt_(
              r.docs || 0
            ) +
          '</td>' +

          '<td align="right" style="' +
            'padding:10px;' +
            'border-bottom:1px solid #e2e8f0;' +
            'font-family:Arial,sans-serif;' +
            'font-size:12px;' +
            'font-weight:700;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailFmtBrl_(
              r.valor || 0
            ) +
          '</td>' +

        '</tr>';

    }
  );


  var html = "";


  html +=
    '<div style="' +
      'margin:0;' +
      'padding:24px;' +
      'background:#f1f5f9;' +
      'font-family:Arial,sans-serif;' +
      'color:#0f172a;' +
    '">';


  html +=
    '<div style="' +
      'max-width:1200px;' +
      'margin:0 auto;' +
      'background:#ffffff;' +
      'border:1px solid #e2e8f0;' +
      'border-radius:18px;' +
      'overflow:hidden;' +
    '">';


  // Header
  html +=
    '<div style="' +
      'padding:24px;' +
      'background:#061a3a;' +
      'color:#ffffff;' +
    '">' +

      '<div style="' +
        'font-size:22px;' +
        'font-weight:800;' +
      '">' +
        'Indicadores Prosegur' +
      '</div>' +

      '<div style="' +
        'margin-top:6px;' +
        'font-size:13px;' +
        'color:#cbd5e1;' +
      '">' +
        'Visão analítica consolidada • Base completa' +
      '</div>' +

    '</div>';

    // =====================================================
// TEXTO EXPLICATIVO DO E-MAIL
// =====================================================

html +=
  '<div style="' +
    'margin:22px 22px 0 22px;' +
    'padding:18px 20px;' +
    'background:#f8fafc;' +
    'border-radius:10px;' +
    'font-family:Arial,sans-serif;' +
    'font-size:14px;' +
    'line-height:1.6;' +
    'color:#334155;' +
  '">' +

    '<div style="' +
      'font-size:15px;' +
      'font-weight:800;' +
      'color:#0f172a;' +
      'margin-bottom:8px;' +
    '">' +
      'Sobre este relatório' +
    '</div>' +

    'Este e-mail é enviado mensalmente para acompanhamento dos valores ' +
    'processados pela Prosegur, apresentando a visão consolidada da base completa. ' +
    'O relatório reúne os principais indicadores, valores por empresa e período, ' +
    'detalhamento mensal e evolução dos valores ao longo do tempo.' +

  '</div>';

  // Cards
  html +=
    '<div style="padding:22px;">' +

      '<table role="presentation" ' +
        'width="100%" ' +
        'cellpadding="0" ' +
        'cellspacing="8">' +

        '<tr>' +


          '<td width="33%" valign="top" style="' +
            'padding:18px;' +
            'border:2px double #0f2d5c;' +
            'border-radius:14px;' +
          '">' +

            '<div style="' +
            'font-size:11px;' +
            'font-weight:800;' +
            'color:#64748b;' +
          '">' +
            'DOCS' +
          '</div>' +

          '<div style="' +
            'display:inline-block;' +
            'margin-top:7px;' +
            'padding:3px 8px;' +
            'background:#ecfdf5;' +
            'border-radius:999px;' +
            'font-size:10px;' +
            'font-weight:800;' +
            'color:#166534;' +
          '">' +
            'ACUMULADO (DESDE 04/26)' +
          '</div>' +

          '<div style="' +
            'margin-top:8px;' +
            'font-size:28px;' +
            'font-weight:800;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailFmtInt_(
              model.totalDocs
            ) +
'</div>' +

          '</td>' +


          '<td width="33%" valign="top" style="' +
            'padding:18px;' +
            'border:2px double #0f2d5c;' +
            'border-radius:14px;' +
          '">' +

            '<div style="' +
            'font-size:11px;' +
            'font-weight:800;' +
            'color:#64748b;' +
          '">' +
            'VALOR TOTAL' +
          '</div>' +

          '<div style="' +
            'display:inline-block;' +
            'margin-top:7px;' +
            'padding:3px 8px;' +
            'background:#ecfdf5;' +
            'border-radius:999px;' +
            'font-size:10px;' +
            'font-weight:800;' +
            'color:#166534;' +
          '">' +
            'ACUMULADO (DESDE 04/26)' +
          '</div>' +

          '<div style="' +
            'margin-top:8px;' +
            'font-size:28px;' +
            'font-weight:800;' +
            'color:#0f172a;' +
          '">' +
            vektorArEmailFmtBrl_(
              model.totalValor
            ) +
          '</div>' +

          '</td>' +


          '<td width="33%" valign="top" style="' +
            'padding:18px;' +
            'border:2px double #0f2d5c;' +
            'border-radius:14px;' +
          '">' +

            '<div style="' +
              'font-size:11px;' +
              'font-weight:800;' +
              'color:#64748b;' +
            '">' +
              'GERADO EM' +
            '</div>' +

            '<div style="' +
              'margin-top:10px;' +
              'font-size:17px;' +
              'font-weight:800;' +
              'color:#0f172a;' +
            '">' +
              vektorArEmailEscapeHtml_(
                vektorArEmailFmtDateTime_(
                  model.generatedAt
                )
              ) +
            '</div>' +

          '</td>' +


        '</tr>' +

      '</table>';


  // Valor por empresa / período
  html +=

    '<table role="presentation" ' +
      'width="100%" ' +
      'cellpadding="0" ' +
      'cellspacing="10" ' +
      'style="margin-top:18px;">' +

      '<tr>' +

        '<td width="50%" valign="top" style="' +
          'padding:18px;' +
          'border:1px solid #e2e8f0;' +
          'border-radius:14px;' +
        '">' +

          '<div style="' +
            'font-size:16px;' +
            'font-weight:800;' +
            'margin-bottom:18px;' +
          '">' +
            'Valor por empresa' +
          '</div>' +

          vektorArEmailBuildBars_(
            model.rowsEmpresa,
            "empresa"
          ) +

        '</td>' +


        '<td width="50%" valign="top" style="' +
          'padding:18px;' +
          'border:1px solid #e2e8f0;' +
          'border-radius:14px;' +
        '">' +

          '<div style="' +
            'font-size:16px;' +
            'font-weight:800;' +
            'margin-bottom:18px;' +
          '">' +
            'Valor por período' +
          '</div>' +

          vektorArEmailBuildBars_(
            model.rowsPeriodo,
            "periodo"
          ) +

        '</td>' +

      '</tr>' +

    '</table>';


  // Tabela
  html +=

    '<div style="' +
      'margin-top:22px;' +
      'padding:18px;' +
      'border:1px solid #e2e8f0;' +
      'border-radius:14px;' +
    '">' +

      '<div style="' +
        'font-size:16px;' +
        'font-weight:800;' +
        'margin-bottom:14px;' +
      '">' +
        'Detalhe por período / empresa' +
      '</div>' +

      '<table width="100%" ' +
        'cellpadding="0" ' +
        'cellspacing="0" ' +
        'style="' +
          'border-collapse:collapse;' +
          'border:1px solid #e2e8f0;' +
        '">' +

        '<thead>' +

          '<tr style="' +
            'background:#061a3a;' +
            'color:#ffffff;' +
          '">' +

            '<th style="padding:10px;font-size:12px;">Período</th>' +

            '<th style="padding:10px;font-size:12px;">Empresa</th>' +

            '<th style="padding:10px;font-size:12px;">Docs</th>' +

            '<th style="padding:10px;font-size:12px;">Valor</th>' +

          '</tr>' +

        '</thead>' +

        '<tbody>' +
          rowsHtml +
        '</tbody>' +

      '</table>' +

    '</div>';


  // Gráfico
  html +=

    '<div style="' +
      'margin-top:22px;' +
      'padding:18px;' +
      'border:1px solid #e2e8f0;' +
      'border-radius:14px;' +
    '">' +

      '<div style="' +
        'font-size:16px;' +
        'font-weight:800;' +
      '">' +
        'Valor por período / empresa + variação mensal (%)' +
      '</div>' +

      '<div style="' +
        'margin-top:5px;' +
        'font-size:13px;' +
        'color:#64748b;' +
      '">' +
        'Barras verticais por empresa no eixo X por período, ' +
        'com linha de variação mensal do valor consolidado.' +
      '</div>' +

      '<div style="' +
        'margin-top:18px;' +
        'text-align:center;' +
      '">' +

        '<img src="cid:prosegurGrafico" ' +
          'alt="Indicadores Prosegur" ' +
          'style="' +
            'display:block;' +
            'width:100%;' +
            'max-width:1150px;' +
            'height:auto;' +
            'margin:0 auto;' +
          '">' +

      '</div>' +

    '</div>';


  html +=
      '</div>' +
    '</div>' +
  '</div>';


  return html;
}


// -----------------------------------------------------
// Envio principal
// -----------------------------------------------------

function vektorArEnviarRelatorioProsegurEmail_(
  opts
) {

  opts = opts || {};

  var isTeste =
    opts.teste === true;


  var data =
    vektorArEmailGetFullAnalytics_();


  if (
    !data ||
    !Array.isArray(data.rows) ||
    !data.rows.length
  ) {

    throw new Error(
      "A base completa da Prosegur está vazia."
    );

  }


  var model =
    vektorArEmailBuildModel_(
      data
    );


  var grafico =
    vektorArEmailBuildComboChart_(
      model
    );


  var html =
    vektorArEmailBuildHtml_(
      model
    );


  var destinatarios =
    VEKTOR_AR_PROSEGUR_EMAIL_CFG
      .DESTINATARIOS
      .filter(Boolean);


  if (!destinatarios.length) {

    throw new Error(
      "Nenhum destinatário configurado."
    );

  }


  var assunto =
    VEKTOR_AR_PROSEGUR_EMAIL_CFG
      .ASSUNTO;


  if (isTeste) {

    assunto =
      "[TESTE] " +
      assunto;

  }


  var opcoes = {

    from: "usuario05@empresa.exemplo",

    name: "Vektor",

    htmlBody: html,

    inlineImages: {
      prosegurGrafico: grafico
    }

  };


  GmailApp.sendEmail(

    destinatarios.join(","),

    assunto,

    "Relatório de Indicadores Prosegur - Vektor",

    opcoes

  );


  return {

    ok: true,

    teste: isTeste,

    destinatarios:
      destinatarios,

    assunto:
      assunto,

    rows:
      model.rows.length,

    totalDocs:
      model.totalDocs,

    totalValor:
      model.totalValor

  };
}


// -----------------------------------------------------
// TESTE MANUAL
// -----------------------------------------------------

function vektorArTestarEmailProsegurIndicadores() {

  return vektorArEnviarRelatorioProsegurEmail_({
    teste: false
  });

}


// -----------------------------------------------------
// PRODUÇÃO - executada pelo trigger
// -----------------------------------------------------

function vektorArEnviarRelatorioProsegurMensal() {

  var cfg =
    VEKTOR_AR_PROSEGUR_EMAIL_CFG;

  var tz =
    cfg.TIMEZONE ||
    "America/Sao_Paulo";


  var now =
    new Date();


  var dia =
    Number(
      Utilities.formatDate(
        now,
        tz,
        "d"
      )
    );


  // Segurança adicional.
  if (
    dia !==
    Number(cfg.DIA_ENVIO)
  ) {

    return {
      ok: true,
      sent: false,
      motivo:
        "Hoje não é o dia configurado."
    };

  }


  var mesKey =
    Utilities.formatDate(
      now,
      tz,
      "yyyy-MM"
    );


  var props =
    PropertiesService
      .getScriptProperties();


  var ultimo =
    props.getProperty(
      cfg.PROP_ULTIMO_ENVIO
    ) || "";


  // Impede duplicação no mesmo mês.
  if (ultimo === mesKey) {

    return {
      ok: true,
      sent: false,
      motivo:
        "Relatório já enviado neste mês."
    };

  }


  var res =
    vektorArEnviarRelatorioProsegurEmail_({
      teste: false
    });


  if (
    res &&
    res.ok
  ) {

    props.setProperty(
      cfg.PROP_ULTIMO_ENVIO,
      mesKey
    );

  }


  return res;
}


// -----------------------------------------------------
// INSTALA TRIGGER MENSAL
// -----------------------------------------------------

function vektorArInstalarTriggerRelatorioProsegur() {

  var handler =
    "vektorArEnviarRelatorioProsegurMensal";


  // Remove gatilhos antigos da mesma função.
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


  var cfg =
    VEKTOR_AR_PROSEGUR_EMAIL_CFG;


  var trigger =
    ScriptApp
      .newTrigger(handler)
      .timeBased()
      .onMonthDay(
        Number(cfg.DIA_ENVIO)
      )
      .atHour(
        Number(cfg.HORA_ENVIO)
      )
      .inTimezone(
        cfg.TIMEZONE
      )
      .create();


  return {

    ok: true,

    triggerId:
      trigger.getUniqueId(),

    dia:
      cfg.DIA_ENVIO,

    hora:
      cfg.HORA_ENVIO,

    timezone:
      cfg.TIMEZONE

  };
}


// -----------------------------------------------------
// REMOVE TRIGGER
// -----------------------------------------------------

function vektorArRemoverTriggerRelatorioProsegur() {

  var handler =
    "vektorArEnviarRelatorioProsegurMensal";


  var removidos = 0;


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

        removidos++;

      }

    });


  return {

    ok: true,
    removidos: removidos

  };
}

/* =========================
   HELPERS INTERNOS AR
   ========================= */

function vektorArCountEmailsElegiveisProsegur_() {
  var query =
    'in:inbox from:' + VEKTOR_AR_PROSEGUR_CFG.REMETENTE_EMAIL +
    ' newer_than:' + VEKTOR_AR_PROSEGUR_CFG.JANELA_DIAS_BUSCA + 'd';

  var threads = GmailApp.search(query, 0, 500);
  var total = 0;

  for (var i = 0; i < threads.length; i++) {
    var msgs = threads[i].getMessages();

    for (var j = 0; j < msgs.length; j++) {
      var msg = msgs[j];
      if (!msg || !msg.isInInbox()) continue;

      var from = String(msg.getFrom() || "");
      var fromUpper = from.toUpperCase();
      var diaMes = msg.getDate().getDate();

      var contemEmailProsegur =
        fromUpper.indexOf(String(VEKTOR_AR_PROSEGUR_CFG.REMETENTE_EMAIL || "").toUpperCase()) !== -1;

      var contemAliasPermitido =
        fromUpper.indexOf(String(VEKTOR_AR_PROSEGUR_CFG.ALIAS_PERMITIDO || "").toUpperCase()) !== -1;

      var contemAliasBloqueado =
        fromUpper.indexOf(String(VEKTOR_AR_PROSEGUR_CFG.ALIAS_BLOQUEADO || "").toUpperCase()) !== -1;

      if (contemAliasBloqueado) continue;

      if (
        contemEmailProsegur &&
        contemAliasPermitido &&
        diaMes >= Number(VEKTOR_AR_PROSEGUR_CFG.DIA_INICIAL || 0) &&
        diaMes <= Number(VEKTOR_AR_PROSEGUR_CFG.DIA_FINAL || 0)
      ) {
        total++;
      }
    }
  }

  return total;
}

function vektorArCountEmailsPendentesMarcador_() {
  var query = 'label:"' + VEKTOR_AR_PROSEGUR_CFG.NOME_SUBMARCADOR + '" is:unread';
  var threads = GmailApp.search(query, 0, 500);
  var total = 0;

  for (var i = 0; i < threads.length; i++) {
    var msgs = threads[i].getMessages();
    for (var j = 0; j < msgs.length; j++) {
      if (msgs[j] && msgs[j].isUnread()) total++;
    }
  }

  return total;
}

function vektorArGetDriveStatsProsegur_() {
  var pastaDestino = DriveApp.getFolderById(VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_DRIVE);
  var pastaProcessadosRaiz = DriveApp.getFolderById(VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_PROCESSADOS_RAIZ);

  var totalDestino = 0;
  var itDest = pastaDestino.getFiles();
  while (itDest.hasNext()) {
    itDest.next();
    totalDestino++;
  }

  var periodoAtual = Utilities.formatDate(new Date(), Session.getScriptTimeZone() || "America/Sao_Paulo", "MM-yyyy");
  var totalProcessadosMes = 0;

  var itPastas = pastaProcessadosRaiz.getFoldersByName(periodoAtual);
  if (itPastas.hasNext()) {
    var pastaMes = itPastas.next();
    var itFilesMes = pastaMes.getFiles();
    while (itFilesMes.hasNext()) {
      itFilesMes.next();
      totalProcessadosMes++;
    }
  }

  return {
    totalDestino: totalDestino,
    totalProcessadosMes: totalProcessadosMes
  };
}

function vektorArJobPropKey_(jobId) {
  return VEKTOR_AR_JOB_PREFIX + String(jobId || "").trim();
}

function vektorArSaveJobSnapshot_(snapshot) {
  if (!snapshot || !snapshot.jobId) throw new Error("Snapshot inválido.");

  var props = PropertiesService.getScriptProperties();
  props.setProperty(vektorArJobPropKey_(snapshot.jobId), JSON.stringify(snapshot));
}

function vektorArGetJobSnapshot_(jobId) {
  var props = PropertiesService.getScriptProperties();
  var raw = props.getProperty(vektorArJobPropKey_(jobId));
  if (!raw) return null;

  try {
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function vektorArPushJobDetail_(snapshot, label) {
  snapshot.details = Array.isArray(snapshot.details) ? snapshot.details : [];
  snapshot.details.push({
    at: new Date().toISOString(),
    label: String(label || "")
  });

  if (snapshot.details.length > 50) {
    snapshot.details = snapshot.details.slice(snapshot.details.length - 50);
  }
}

function vektorArSetLastJobId_(jobId) {
  PropertiesService.getScriptProperties().setProperty("VEKTOR_AR_LAST_JOB_ID", String(jobId || ""));
}

function vektorArGetLastJobSnapshot_() {
  var props = PropertiesService.getScriptProperties();
  var jobId = props.getProperty("VEKTOR_AR_LAST_JOB_ID") || "";
  if (!jobId) return null;
  return vektorArGetJobSnapshot_(jobId);
}

function vektorArFindRunningJob_() {
  var last = vektorArGetLastJobSnapshot_();
  if (!last || !last.jobId) return null;
  if (String(last.status || "") === "RUNNING" || String(last.status || "") === "QUEUED") {
    return last;
  }
  return null;
}

function testeBibliotecaProsegur() {
  Logger.log("Maker_PDF.libRotularEmailsProsegur => " + typeof Maker_PDF.libRotularEmailsProsegur);
  Logger.log("Maker_PDF.libSalvarAnexosProsegur => " + typeof Maker_PDF.libSalvarAnexosProsegur);
  Logger.log("Maker_PDF.libSalvarRelatorioAuditoriaProsegur => " + typeof Maker_PDF.libSalvarRelatorioAuditoriaProsegur);
}

var RPA_FOLDER_ID = PropertiesService.getScriptProperties().getProperty("RPA_FOLDER_ID") || "";

function vektorRpaBridgeTick() {
  vektorRpaBridgeWriteQueue_();
  vektorRpaBridgeApplyStatusUpdate_();
}

function vektorRpaBridgeWriteQueue_() {
  var result = vektorRpaApiGetNextPendingClara_();
  vektorRpaBridgeWriteJsonFile_("rpa_queue.json", result);
}

function vektorRpaBridgeApplyStatusUpdate_() {
  var file = vektorRpaBridgeGetFile_("rpa_status_update.json");
  if (!file) return;

  var raw = file.getBlob().getDataAsString("UTF-8");
  if (!raw) return;

  var payload = JSON.parse(raw);
  if (!payload || !payload.rowNumber || !payload.status) return;

  vektorRpaApiUpdateClara_(payload);

  vektorRpaBridgeWriteJsonFile_("rpa_status_update.json", {
    ok: true,
    updatedAt: new Date().toISOString(),
    applied: true
  });
}

function vektorRpaBridgeWriteJsonFile_(name, obj) {
  var folder = DriveApp.getFolderById(RPA_FOLDER_ID);
  var content = JSON.stringify(obj, null, 2);
  var file = vektorRpaBridgeGetFile_(name);

  if (file) {
    file.setContent(content);
  } else {
    folder.createFile(name, content, MimeType.PLAIN_TEXT);
  }
}

function vektorRpaBridgeGetFile_(name) {
  var folder = DriveApp.getFolderById(RPA_FOLDER_ID);
  var files = folder.getFilesByName(name);
  return files.hasNext() ? files.next() : null;
}

function testePainelProsegurV2() {
  var resultado = vektorAr2GetProsegurDashboard();
  console.log(JSON.stringify(resultado, null, 2));
}