/**
 * Vektor AR / Prosegur - executor V2 resiliente a timeout.
 *
 * Crie um novo arquivo .gs no MESMO projeto Apps Script e cole este arquivo.
 * Ele reutiliza VEKTOR_AR_PROSEGUR_CFG, VEKTOR_AR_MODULE_KEY e
 * vektorAssertModuleAllowed_ já existentes no projeto.
 */

var VEKTOR_AR2_JOB_PREFIX = "VEKTOR_AR2_JOB_";
var VEKTOR_AR2_LAST_JOB_KEY = "VEKTOR_AR2_LAST_JOB_ID";
var VEKTOR_AR2_STALE_MINUTES = 8;
var VEKTOR_AR2_BATCH_THREADS = 5;
var VEKTOR_AR2_BATCH_MAX_MS = 210000;
var VEKTOR_AR2_MANIFEST_LIMIT = 1000;
var VEKTOR_AR2_DRIVE_CACHE_KEY = "VEKTOR_AR2_DRIVE_STATS";

function vektorAr2GetProsegurDashboard() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);
  var errors = [];
  var resumo = {
    emailsElegiveisInbox: 0,
    emailsPendentesMarcador: 0,
    arquivosNaPastaDestino: 0,
    arquivosNaPastaProcessadosMes: 0,
    ultimaExecucao: "",
    ultimoStatus: ""
  };

  try {
    resumo.emailsElegiveisInbox = vektorAr2CountEligibleInbox_();
  } catch (e1) {
    errors.push("Gmail/inbox: " + vektorAr2Error_(e1));
  }

  try {
    resumo.emailsPendentesMarcador = vektorAr2CountPendingLabel_();
  } catch (e2) {
    errors.push("Gmail/marcador: " + vektorAr2Error_(e2));
  }

  try {
    var drive = vektorAr2GetDriveStatsCached_(false);
    resumo.arquivosNaPastaDestino = drive.totalDestino;
    resumo.arquivosNaPastaProcessadosMes = drive.totalProcessadosMes;
  } catch (e3) {
    errors.push("Drive: " + vektorAr2Error_(e3));
  }

  var last = vektorAr2GetLastJob_();
  if (last) {
    last = vektorAr2ExpireStaleJob_(last);
    resumo.ultimaExecucao = last.startedAt || "";
    resumo.ultimoStatus = last.status || "";
  }

  return {
    ok: true,
    partial: errors.length > 0,
    errors: errors,
    modulo: VEKTOR_AR_MODULE_KEY,
    email: ctx.email,
    role: ctx.role,
    resumo: resumo,
    ultimoJob: last || null
  };
}

function vektorAr2StartProsegurJob() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    var active = vektorAr2GetLastJob_();
    if (active) active = vektorAr2ExpireStaleJob_(active);

    if (active && (active.status === "RUNNING" || active.status === "QUEUED")) {
      return {
        ok: true,
        alreadyRunning: true,
        jobId: active.jobId,
        status: active.status,
        startedAt: active.startedAt,
        startedAtIso: active.startedAtIso
      };
    }

    var now = new Date();
    var tz = Session.getScriptTimeZone() || "America/Sao_Paulo";
    var snapshot = {
      jobId: Utilities.getUuid(),
      modulo: VEKTOR_AR_MODULE_KEY,
      status: "QUEUED",
      stageKey: "labeling",
      stageLabel: "Execução preparada para processamento em lotes.",
      progressPct: 4,
      startedAt: Utilities.formatDate(now, tz, "yyyy-MM-dd HH:mm:ss"),
      startedAtIso: now.toISOString(),
      lastHeartbeatAtIso: now.toISOString(),
      finishedAt: "",
      finishedAtIso: "",
      userEmail: String(ctx.email || "").trim().toLowerCase(),
      userRole: String(ctx.role || "").trim(),
      details: [{ at: now.toISOString(), label: "Execução preparada." }],
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

    vektorAr2SaveJob_(snapshot);
    PropertiesService.getScriptProperties()
      .setProperty(VEKTOR_AR2_LAST_JOB_KEY, snapshot.jobId);

    return {
      ok: true,
      alreadyRunning: false,
      jobId: snapshot.jobId,
      status: snapshot.status,
      startedAt: snapshot.startedAt,
      startedAtIso: snapshot.startedAtIso
    };
  } finally {
    lock.releaseLock();
  }
}

/** Processa um único lote; o navegador chama novamente enquanto for RUNNING. */
function vektorAr2RunProsegurBatch(jobId) {
  vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);
  jobId = String(jobId || "").trim();
  if (!jobId) return { ok: false, error: "JobId não informado." };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) {
    return vektorAr2GetJob_(jobId) || { ok: false, error: "Outro lote está em execução." };
  }

  try {
    var snapshot = vektorAr2GetJob_(jobId);
    if (!snapshot) return { ok: false, error: "Job V2 não encontrado." };
    snapshot = vektorAr2ExpireStaleJob_(snapshot);

    if (snapshot.status === "DONE" || snapshot.status === "ERROR") return snapshot;

    snapshot.status = "RUNNING";
    vektorAr2Heartbeat_(snapshot);

    if (snapshot.stageKey === "labeling") {
      snapshot.stageLabel = "Etapa 1/3 • Localizando e rotulando e-mails elegíveis...";
      snapshot.progressPct = 22;
      vektorAr2PushDetail_(snapshot, snapshot.stageLabel);
      vektorAr2SaveJob_(snapshot);

      var labeled = vektorAr2LabelEligibleBatch_();
      vektorAr2Heartbeat_(snapshot);

      if (labeled.hasMore) {
        snapshot.stageLabel = "Etapa 1/3 • " + labeled.labeled + " thread(s) rotulada(s) neste lote.";
        snapshot.progressPct = 30;
      } else {
        snapshot.stageKey = "saving";
        snapshot.stageLabel = "Etapa 2/3 • E-mails preparados; iniciando anexos em lotes.";
        snapshot.progressPct = 40;
      }

      vektorAr2SaveJob_(snapshot);
      return snapshot;
    }

    if (snapshot.stageKey === "saving") {
      snapshot.stageLabel = "Etapa 2/3 • Salvando anexos PDF no Drive...";
      snapshot.progressPct = Math.max(45, Number(snapshot.progressPct || 0));
      vektorAr2SaveJob_(snapshot);

      var batch = vektorAr2SavePendingBatch_(snapshot);
      snapshot.metrics.totalEmailsVistos += batch.emails;
      snapshot.metrics.totalArquivosSalvos += batch.saved;
      snapshot.metrics.totalArquivosIgnorados += batch.ignored;
      snapshot.metrics.totalThreadsLote += batch.threads;
      vektorAr2Heartbeat_(snapshot);

      var pending = vektorAr2CountPendingLabel_();
      snapshot.metrics.emailsPendentesMarcador = pending;

      if (pending > 0) {
        var done = Number(snapshot.metrics.totalEmailsVistos || 0);
        snapshot.progressPct = Math.min(88, 45 + Math.round((done / (done + pending)) * 43));
        snapshot.stageLabel = "Etapa 2/3 • Lote concluído; restam " + pending + " e-mail(s).";
        vektorAr2PushDetail_(snapshot, snapshot.stageLabel);
        vektorAr2SaveJob_(snapshot);
        return snapshot;
      }

      snapshot.stageKey = "audit";
      snapshot.stageLabel = "Etapa 3/3 • Consolidando auditoria final...";
      snapshot.progressPct = 94;
      vektorAr2PushDetail_(snapshot, snapshot.stageLabel);
      vektorAr2SaveJob_(snapshot);
      return snapshot;
    }

    if (snapshot.stageKey === "audit") {
      CacheService.getScriptCache().remove(VEKTOR_AR2_DRIVE_CACHE_KEY);
      try {
        var stats = vektorAr2GetDriveStatsCached_(true);
        snapshot.metrics.arquivosNaPastaDestino = stats.totalDestino;
        snapshot.metrics.arquivosNaPastaProcessadosMes = stats.totalProcessadosMes;
      } catch (_) {}

      snapshot.status = "DONE";
      snapshot.stageKey = "done";
      snapshot.stageLabel = "Processamento concluído sem duplicar arquivos.";
      snapshot.progressPct = 100;
      var end = new Date();
      var tzEnd = Session.getScriptTimeZone() || "America/Sao_Paulo";
      snapshot.finishedAt = Utilities.formatDate(end, tzEnd, "yyyy-MM-dd HH:mm:ss");
      snapshot.finishedAtIso = end.toISOString();
      snapshot.lastHeartbeatAtIso = end.toISOString();
      vektorAr2PushDetail_(snapshot, snapshot.stageLabel);
      vektorAr2SaveJob_(snapshot);
      return snapshot;
    }

    throw new Error("Etapa desconhecida: " + snapshot.stageKey);
  } catch (e) {
    var errorText = vektorAr2Error_(e);
    var failed = vektorAr2GetJob_(jobId) || { jobId: jobId, metrics: {}, details: [] };
    failed.status = "ERROR";
    failed.stageKey = "error";
    failed.stageLabel = errorText;
    failed.progressPct = Math.min(96, Number(failed.progressPct || 0));
    var endErr = new Date();
    failed.finishedAtIso = endErr.toISOString();
    failed.lastHeartbeatAtIso = endErr.toISOString();
    vektorAr2PushDetail_(failed, "Erro: " + errorText);
    vektorAr2SaveJob_(failed);
    return failed;
  } finally {
    lock.releaseLock();
  }
}

function vektorAr2GetProsegurJobStatus(jobId) {
  vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);
  try {
    var snapshot = vektorAr2GetJob_(String(jobId || "").trim());
    if (!snapshot) throw new Error("Job V2 não encontrado.");
    snapshot = vektorAr2ExpireStaleJob_(snapshot);
    return { ok: true, job: snapshot };
  } catch (e) {
    return { ok: false, error: vektorAr2Error_(e) };
  }
}

function vektorAr2LabelEligibleBatch_() {
  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var label = GmailApp.getUserLabelByName(cfg.NOME_SUBMARCADOR) ||
    GmailApp.createLabel(cfg.NOME_SUBMARCADOR);
  var query = 'in:inbox from:' + cfg.REMETENTE_EMAIL +
    ' newer_than:' + Number(cfg.JANELA_DIAS_BUSCA || 90) + 'd' +
    ' -label:"' + cfg.NOME_SUBMARCADOR + '"';
  var threads = GmailApp.search(query, 0, 25);
  var labeled = 0;

  for (var i = 0; i < threads.length; i++) {
    var messages = threads[i].getMessages();
    var eligible = false;
    for (var j = 0; j < messages.length; j++) {
      if (vektorAr2IsAllowedMessage_(messages[j], true)) {
        eligible = true;
        break;
      }
    }
    if (eligible) {
      threads[i].addLabel(label);
      labeled++;
    }
  }

  return { labeled: labeled, hasMore: threads.length >= 25 && labeled > 0 };
}

function vektorAr2SavePendingBatch_(snapshot) {
  var started = Date.now();
  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var folder = DriveApp.getFolderById(cfg.ID_PASTA_DRIVE);
  var query = 'label:"' + cfg.NOME_SUBMARCADOR + '" is:unread';
  var threads = GmailApp.search(query, 0, VEKTOR_AR2_BATCH_THREADS);
  var result = { threads: 0, emails: 0, saved: 0, ignored: 0 };

  for (var i = 0; i < threads.length; i++) {
    if (Date.now() - started > VEKTOR_AR2_BATCH_MAX_MS) break;
    var thread = threads[i];
    var messages = thread.getMessages();
    var touched = false;

    for (var j = 0; j < messages.length; j++) {
      if (Date.now() - started > VEKTOR_AR2_BATCH_MAX_MS) break;
      var message = messages[j];
      if (!message.isUnread()) continue;

      var allowed = vektorAr2IsAllowedMessage_(message, false);
      var fromUpper = String(message.getFrom() || "").toUpperCase();
      var blocked = fromUpper.indexOf(String(cfg.ALIAS_BLOQUEADO || "").toUpperCase()) !== -1;
      if (!allowed && !blocked) continue;

      touched = true;
      result.emails++;
      var row = {
        message_id: message.getId(),
        data: message.getDate().toISOString(),
        assunto: String(message.getSubject() || ""),
        status: blocked ? "SKIPPED_BLOCKED_ALIAS" : "OK",
        arquivos: []
      };

      if (blocked) {
        result.ignored++;
      } else {
        var attachments = message.getAttachments({
          includeInlineImages: false,
          includeAttachments: true
        });
        var pdfCount = 0;

        for (var k = 0; k < attachments.length; k++) {
          var attachment = attachments[k];
          var name = String(attachment.getName() || "anexo.pdf");
          var mime = String(attachment.getContentType() || "").toLowerCase();
          if (!/\.pdf$/i.test(name) && mime !== "application/pdf") continue;
          pdfCount++;

          var saved = vektorAr2SaveAttachmentOnce_(folder, attachment, message.getId(), k);
          row.arquivos.push({ nome: saved.name, status: saved.created ? "DOWNLOADED" : "DUPLICITY" });
          if (saved.created) result.saved++;
          else result.ignored++;
        }

        if (!pdfCount) {
          row.status = "SKIPPED_NO_PDF";
          result.ignored++;
        }
      }

      vektorAr2UpsertAuditRows_([row]);
      message.markRead();
      vektorAr2Heartbeat_(snapshot);
      vektorAr2SaveJob_(snapshot);
    }

    if (touched) result.threads++;

    var refreshed = GmailApp.getThreadById(thread.getId());
    if (refreshed) {
      var freshMessages = refreshed.getMessages();
      var anyUnread = freshMessages.some(function (m) { return m.isUnread(); });
      if (!anyUnread && refreshed.isInInbox()) refreshed.moveToArchive();
    }
  }

  CacheService.getScriptCache().remove(VEKTOR_AR2_DRIVE_CACHE_KEY);
  return result;
}

function vektorAr2SaveAttachmentOnce_(folder, attachment, messageId, attachmentIndex) {
  var originalName = String(attachment.getName() || "anexo.pdf");
  var size = Number(attachment.getSize() || 0);
  var sha1 = String(attachment.getHash() || "");
  var token = "VEKTOR_AR_SHA1=" + sha1;
  var sameName = folder.getFilesByName(originalName);

  while (sameName.hasNext()) {
    var existing = sameName.next();
    var description = "";
    try { description = String(existing.getDescription() || ""); } catch (_) {}
    if (description.indexOf(token) !== -1 || Number(existing.getSize() || 0) === size) {
      return { created: false, name: existing.getName(), id: existing.getId(), sha1: sha1 };
    }
  }

  var tempName = ".vektor_tmp_" + sha1 + "_" + originalName;
  var tempFiles = folder.getFilesByName(tempName);
  if (tempFiles.hasNext()) {
    var recovered = tempFiles.next();
    recovered.setDescription(token + "\nVEKTOR_AR_MESSAGE=" + messageId + "\nVEKTOR_AR_ATTACHMENT=" + attachmentIndex);
    recovered.setName(originalName);
    return { created: false, name: recovered.getName(), id: recovered.getId(), sha1: sha1 };
  }

  var targetName = originalName;
  if (folder.getFilesByName(originalName).hasNext()) {
    var dot = originalName.lastIndexOf(".");
    var base = dot > 0 ? originalName.substring(0, dot) : originalName;
    var ext = dot > 0 ? originalName.substring(dot) : "";
    targetName = base + "__" + sha1.substring(0, 10) + ext;
  }

  var blob = attachment.copyBlob().setName(tempName);
  var file = folder.createFile(blob);
  file.setDescription(token + "\nVEKTOR_AR_MESSAGE=" + messageId + "\nVEKTOR_AR_ATTACHMENT=" + attachmentIndex);
  file.setName(targetName);
  return { created: true, name: targetName, id: file.getId(), sha1: sha1 };
}

function vektorAr2UpsertAuditRows_(newRows) {
  if (!newRows || !newRows.length) return;
  var folder = DriveApp.getFolderById(VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_DRIVE);
  var files = folder.getFilesByName("AUDITORIA_EMAIL.json");
  var file = files.hasNext() ? files.next() : null;
  var manifest = { detalhes: [] };

  if (file) {
    try {
      manifest = JSON.parse(file.getBlob().getDataAsString("UTF-8") || "{}") || {};
    } catch (_) {
      manifest = { detalhes: [] };
    }
  }

  var rows = Array.isArray(manifest.detalhes) ? manifest.detalhes : [];
  var byMessage = {};
  rows.forEach(function (row, idx) {
    if (row && row.message_id) byMessage[String(row.message_id)] = idx;
  });

  newRows.forEach(function (row) {
    var key = String((row && row.message_id) || "");
    if (key && Object.prototype.hasOwnProperty.call(byMessage, key)) {
      rows[byMessage[key]] = row;
    } else {
      rows.push(row);
      if (key) byMessage[key] = rows.length - 1;
    }
  });

  if (rows.length > VEKTOR_AR2_MANIFEST_LIMIT) {
    rows = rows.slice(rows.length - VEKTOR_AR2_MANIFEST_LIMIT);
  }

  manifest.data_geracao = new Date().toISOString();
  manifest.detalhes = rows;
  var content = JSON.stringify(manifest, null, 2);
  if (file) file.setContent(content);
  else folder.createFile("AUDITORIA_EMAIL.json", content, MimeType.PLAIN_TEXT);
}

function vektorAr2IsAllowedMessage_(message, enforceDayWindow) {
  if (!message) return false;
  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var fromUpper = String(message.getFrom() || "").toUpperCase();
  var sender = String(cfg.REMETENTE_EMAIL || "").toUpperCase();
  var allowedAlias = String(cfg.ALIAS_PERMITIDO || "").toUpperCase();
  var blockedAlias = String(cfg.ALIAS_BLOQUEADO || "").toUpperCase();

  if (fromUpper.indexOf(sender) === -1) return false;
  if (blockedAlias && fromUpper.indexOf(blockedAlias) !== -1) return false;
  if (allowedAlias && fromUpper.indexOf(allowedAlias) === -1) return false;

  if (enforceDayWindow) {
    var day = message.getDate().getDate();
    if (day < Number(cfg.DIA_INICIAL || 1) || day > Number(cfg.DIA_FINAL || 31)) return false;
  }
  return true;
}

function vektorAr2CountEligibleInbox_() {
  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var query = 'in:inbox from:' + cfg.REMETENTE_EMAIL +
    ' newer_than:' + Number(cfg.JANELA_DIAS_BUSCA || 90) + 'd';
  var threads = GmailApp.search(query, 0, 200);
  var matrix = threads.length ? GmailApp.getMessagesForThreads(threads) : [];
  var total = 0;

  matrix.forEach(function (messages) {
    messages.forEach(function (message) {
      if (message.isInInbox() && vektorAr2IsAllowedMessage_(message, true)) total++;
    });
  });
  return total;
}

function vektorAr2CountPendingLabel_() {
  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var query = 'label:"' + cfg.NOME_SUBMARCADOR + '" is:unread';
  var threads = GmailApp.search(query, 0, 200);
  var matrix = threads.length ? GmailApp.getMessagesForThreads(threads) : [];
  var total = 0;

  matrix.forEach(function (messages) {
    messages.forEach(function (message) {
      var fromUpper = String(message.getFrom() || "").toUpperCase();
      var blocked = fromUpper.indexOf(String(cfg.ALIAS_BLOQUEADO || "").toUpperCase()) !== -1;
      if (message.isUnread() && (vektorAr2IsAllowedMessage_(message, false) || blocked)) total++;
    });
  });
  return total;
}

function vektorAr2GetDriveStatsCached_(force) {
  var cache = CacheService.getScriptCache();
  if (!force) {
    var cached = cache.get(VEKTOR_AR2_DRIVE_CACHE_KEY);
    if (cached) return JSON.parse(cached);
  }

  var cfg = VEKTOR_AR_PROSEGUR_CFG;
  var destination = DriveApp.getFolderById(cfg.ID_PASTA_DRIVE);
  var processedRoot = DriveApp.getFolderById(cfg.ID_PASTA_PROCESSADOS_RAIZ);
  var totalDestination = 0;
  var files = destination.getFiles();
  while (files.hasNext()) { files.next(); totalDestination++; }

  var currentPeriod = Utilities.formatDate(
    new Date(), Session.getScriptTimeZone() || "America/Sao_Paulo", "MM-yyyy"
  );
  var totalProcessed = 0;
  var folders = processedRoot.getFoldersByName(currentPeriod);
  if (folders.hasNext()) {
    var monthFiles = folders.next().getFiles();
    while (monthFiles.hasNext()) { monthFiles.next(); totalProcessed++; }
  }

  var result = {
    totalDestino: totalDestination,
    totalProcessadosMes: totalProcessed,
    cachedAt: new Date().toISOString()
  };
  cache.put(VEKTOR_AR2_DRIVE_CACHE_KEY, JSON.stringify(result), 300);
  return result;
}

function vektorAr2JobKey_(jobId) {
  return VEKTOR_AR2_JOB_PREFIX + String(jobId || "").trim();
}

function vektorAr2SaveJob_(snapshot) {
  if (!snapshot || !snapshot.jobId) throw new Error("Snapshot V2 inválido.");
  PropertiesService.getScriptProperties()
    .setProperty(vektorAr2JobKey_(snapshot.jobId), JSON.stringify(snapshot));
}

function vektorAr2GetJob_(jobId) {
  if (!jobId) return null;
  var raw = PropertiesService.getScriptProperties().getProperty(vektorAr2JobKey_(jobId));
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (_) { return null; }
}

function vektorAr2GetLastJob_() {
  var id = PropertiesService.getScriptProperties().getProperty(VEKTOR_AR2_LAST_JOB_KEY) || "";
  return id ? vektorAr2GetJob_(id) : null;
}

function vektorAr2Heartbeat_(snapshot) {
  snapshot.lastHeartbeatAtIso = new Date().toISOString();
}

function vektorAr2ExpireStaleJob_(snapshot) {
  if (!snapshot || (snapshot.status !== "RUNNING" && snapshot.status !== "QUEUED")) return snapshot;
  var heartbeat = new Date(snapshot.lastHeartbeatAtIso || snapshot.startedAtIso || "");
  if (isNaN(heartbeat.getTime())) return snapshot;
  var ageMinutes = (Date.now() - heartbeat.getTime()) / 60000;
  if (ageMinutes <= VEKTOR_AR2_STALE_MINUTES) return snapshot;

  snapshot.status = "ERROR";
  snapshot.stageKey = "error";
  snapshot.stageLabel = "Execução anterior interrompida pelo limite de tempo; pode ser retomada com segurança em um novo job.";
  snapshot.finishedAtIso = new Date().toISOString();
  vektorAr2PushDetail_(snapshot, snapshot.stageLabel);
  vektorAr2SaveJob_(snapshot);
  return snapshot;
}

function vektorAr2PushDetail_(snapshot, label) {
  snapshot.details = Array.isArray(snapshot.details) ? snapshot.details : [];
  snapshot.details.push({ at: new Date().toISOString(), label: String(label || "") });
  if (snapshot.details.length > 40) snapshot.details = snapshot.details.slice(-40);
}

function vektorAr2Error_(e) {
  return e && e.message ? e.message : String(e || "Erro desconhecido.");
}
