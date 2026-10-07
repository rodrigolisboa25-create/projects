/**
 * AR | Automação Prosegur via Gmail API avançada.
 *
 * Adicione este arquivo ao MESMO projeto Apps Script do Vektor.
 * Em Serviços (+), adicione "Gmail API" v1.
 *
 * Este código não usa GmailApp.
 */

var VEKTOR_AR_API_JOB_PREFIX = "VEKTOR_AR_API_JOB_";
var VEKTOR_AR_API_LAST_JOB_KEY = "VEKTOR_AR_API_LAST_JOB_ID";
var VEKTOR_AR_API_STALE_MINUTES = 8;
var VEKTOR_AR_API_BATCH_MESSAGES = 5;
var VEKTOR_AR_API_BATCH_MAX_MS = 210000;
var VEKTOR_AR_API_MANIFEST_LIMIT = 1000;
var VEKTOR_AR_API_CACHE_KEY = "VEKTOR_AR_API_DASHBOARD";
var VEKTOR_AR_API_VERSION = "2026-09-10.5";

function vektorArApiGetProsegurDashboard() {
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
    var gmailCounts = vektorArApiGetGmailCountsCached_(false);
    resumo.emailsElegiveisInbox = gmailCounts.eligible;
    resumo.emailsPendentesMarcador = gmailCounts.pending;
  } catch (e1) {
    errors.push("Gmail API: " + vektorArApiError_(e1));
  }

  try {
    var drive = vektorArApiGetDriveStatsCached_(false);
    resumo.arquivosNaPastaDestino = drive.totalDestino;
    resumo.arquivosNaPastaProcessadosMes = drive.totalProcessadosMes;
  } catch (e2) {
    errors.push("Drive: " + vektorArApiError_(e2));
  }

  var last = vektorArApiGetLastJob_();

  if (last) {
    last = vektorArApiExpireStaleJob_(last);
    resumo.ultimaExecucao = last.startedAt || "";
    resumo.ultimoStatus = last.status || "";
  }

  return {
    ok: true,
    partial: errors.length > 0,
    errors: errors,
    backendVersion: VEKTOR_AR_API_VERSION,
    modulo: VEKTOR_AR_MODULE_KEY,
    email: ctx.email,
    role: ctx.role,
    resumo: resumo,
    ultimoJob: last || null
  };
}

function vektorArApiStartProsegurJob() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);
  var lock = LockService.getScriptLock();

  lock.waitLock(30000);

  try {
    vektorArApiAssertService_();

    var active = vektorArApiGetLastJob_();

    if (active) {
      active = vektorArApiExpireStaleJob_(active);
    }

    if (
      active &&
      (active.status === "RUNNING" || active.status === "QUEUED")
    ) {
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
    var tz =
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo";

    var snapshot = {
      jobId: Utilities.getUuid(),
      modulo: VEKTOR_AR_MODULE_KEY,
      status: "QUEUED",
      stageKey: "labeling",
      stageLabel: "Execução preparada pela Gmail API.",
      progressPct: 4,
      startedAt: Utilities.formatDate(
        now,
        tz,
        "yyyy-MM-dd HH:mm:ss"
      ),
      startedAtIso: now.toISOString(),
      lastHeartbeatAtIso: now.toISOString(),
      finishedAt: "",
      finishedAtIso: "",
      userEmail: String(ctx.email || "")
        .trim()
        .toLowerCase(),
      userRole: String(ctx.role || "").trim(),
      details: [
        {
          at: now.toISOString(),
          label: "Execução preparada pela Gmail API."
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

    vektorArApiSaveJob_(snapshot);

    PropertiesService
      .getScriptProperties()
      .setProperty(
        VEKTOR_AR_API_LAST_JOB_KEY,
        snapshot.jobId
      );

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

function vektorArApiRunProsegurBatch(jobId) {
  vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  jobId = String(jobId || "").trim();

  if (!jobId) {
    return {
      ok: false,
      error: "JobId não informado."
    };
  }

  var lock = LockService.getScriptLock();

  if (!lock.tryLock(5000)) {
    return (
      vektorArApiGetJob_(jobId) || {
        ok: false,
        error: "Outro lote está em execução."
      }
    );
  }

  try {
    vektorArApiAssertService_();

    var snapshot = vektorArApiGetJob_(jobId);

    if (!snapshot) {
      return {
        ok: false,
        error: "Job Gmail API não encontrado."
      };
    }

    snapshot = vektorArApiExpireStaleJob_(snapshot);

    if (
      snapshot.status === "DONE" ||
      snapshot.status === "ERROR"
    ) {
      return snapshot;
    }

    snapshot.status = "RUNNING";
    vektorArApiHeartbeat_(snapshot);

    if (snapshot.stageKey === "labeling") {
      snapshot.stageLabel =
        "Etapa 1/3 • Localizando e rotulando e-mails pela Gmail API...";
      snapshot.progressPct = 20;

      vektorArApiPushDetail_(
        snapshot,
        snapshot.stageLabel
      );

      vektorArApiSaveJob_(snapshot);

      var labeled =
        vektorArApiLabelEligibleBatch_();

      vektorArApiHeartbeat_(snapshot);

      if (labeled.hasMore) {
        snapshot.stageLabel =
          "Etapa 1/3 • " +
          labeled.labeled +
          " e-mail(s) rotulado(s) neste lote.";

        snapshot.progressPct = 30;
      } else {
        snapshot.stageKey = "saving";
        snapshot.stageLabel =
          "Etapa 2/3 • Fila preparada; iniciando anexos em lotes.";
        snapshot.progressPct = 40;
      }

      vektorArApiSaveJob_(snapshot);
      return snapshot;
    }

    if (snapshot.stageKey === "saving") {
      snapshot.stageLabel =
        "Etapa 2/3 • Salvando PDFs pela Gmail API...";

      snapshot.progressPct = Math.max(
        45,
        Number(snapshot.progressPct || 0)
      );

      vektorArApiSaveJob_(snapshot);

      var batch =
        vektorArApiSavePendingBatch_(snapshot);

      snapshot.metrics.totalEmailsVistos +=
        batch.emails;

      snapshot.metrics.totalArquivosSalvos +=
        batch.saved;

      snapshot.metrics.totalArquivosIgnorados +=
        batch.ignored;

      snapshot.metrics.totalThreadsLote +=
        batch.threads;

      vektorArApiHeartbeat_(snapshot);

      CacheService
        .getScriptCache()
        .remove(VEKTOR_AR_API_CACHE_KEY);

      var pending =
        vektorArApiCountPending_();

      snapshot.metrics.emailsPendentesMarcador =
        pending;

      if (pending > 0) {
        var done = Number(
          snapshot.metrics.totalEmailsVistos || 0
        );

        snapshot.progressPct = Math.min(
          88,
          45 +
            Math.round(
              (done / (done + pending)) * 43
            )
        );

        snapshot.stageLabel =
          "Etapa 2/3 • Lote concluído; restam " +
          pending +
          " e-mail(s).";

        vektorArApiPushDetail_(
          snapshot,
          snapshot.stageLabel
        );

        vektorArApiSaveJob_(snapshot);
        return snapshot;
      }

      snapshot.stageKey = "audit";
      snapshot.stageLabel =
        "Etapa 3/3 • Consolidando auditoria final...";
      snapshot.progressPct = 94;

      vektorArApiPushDetail_(
        snapshot,
        snapshot.stageLabel
      );

      vektorArApiSaveJob_(snapshot);
      return snapshot;
    }

    if (snapshot.stageKey === "audit") {
      try {
        var stats =
          vektorArApiGetDriveStatsCached_(true);

        snapshot.metrics.arquivosNaPastaDestino =
          stats.totalDestino;

        snapshot.metrics.arquivosNaPastaProcessadosMes =
          stats.totalProcessadosMes;
      } catch (_) {}

      snapshot.status = "DONE";
      snapshot.stageKey = "done";
      snapshot.stageLabel =
        "Processamento concluído pela Gmail API, sem duplicar arquivos.";
      snapshot.progressPct = 100;

      var end = new Date();

      var tzEnd =
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo";

      snapshot.finishedAt =
        Utilities.formatDate(
          end,
          tzEnd,
          "yyyy-MM-dd HH:mm:ss"
        );

      snapshot.finishedAtIso =
        end.toISOString();

      snapshot.lastHeartbeatAtIso =
        end.toISOString();

      vektorArApiPushDetail_(
        snapshot,
        snapshot.stageLabel
      );

      vektorArApiSaveJob_(snapshot);
      return snapshot;
    }

    throw new Error(
      "Etapa desconhecida: " +
        snapshot.stageKey
    );
  } catch (e) {
    var errorText =
      vektorArApiError_(e);

    var failed =
      vektorArApiGetJob_(jobId) || {
        jobId: jobId,
        metrics: {},
        details: []
      };

    failed.status = "ERROR";
    failed.stageKey = "error";
    failed.stageLabel = errorText;

    failed.progressPct = Math.min(
      96,
      Number(failed.progressPct || 0)
    );

    failed.finishedAtIso =
      new Date().toISOString();

    failed.lastHeartbeatAtIso =
      failed.finishedAtIso;

    vektorArApiPushDetail_(
      failed,
      "Erro: " + errorText
    );

    vektorArApiSaveJob_(failed);

    return failed;
  } finally {
    lock.releaseLock();
  }
}

function vektorArApiGetProsegurJobStatus(jobId) {
  vektorAssertModuleAllowed_(VEKTOR_AR_MODULE_KEY);

  try {
    var snapshot =
      vektorArApiGetJob_(
        String(jobId || "").trim()
      );

    if (!snapshot) {
      throw new Error(
        "Job Gmail API não encontrado."
      );
    }

    snapshot =
      vektorArApiExpireStaleJob_(snapshot);

    return {
      ok: true,
      job: snapshot
    };
  } catch (e) {
    return {
      ok: false,
      error: vektorArApiError_(e)
    };
  }
}

function vektorArApiLabelEligibleBatch_() {
  var cfg = VEKTOR_AR_PROSEGUR_CFG;

  var labelId =
    vektorArApiGetOrCreateLabelId_(
      cfg.NOME_SUBMARCADOR
    );

  var query =
    vektorArApiEligibleQuery_(true);

  var refs =
    vektorArApiListMessages_(query, 500);

  var labeled = 0;

  for (
    var i = 0;
    i < refs.length && labeled < 25;
    i++
  ) {
    var message =
      Gmail.Users.Messages.get(
        "me",
        refs[i].id,
        {
          format: "metadata",
          metadataHeaders: [
            "From",
            "Subject",
            "Date"
          ]
        }
      );

    if (!vektorArApiIsAllowedMessage_(message)) {
      continue;
    }

    vektorArApiModifyMessageLabels_(
      message.id,
      [labelId],
      []
    );

    labeled++;
  }

  CacheService
    .getScriptCache()
    .remove(VEKTOR_AR_API_CACHE_KEY);

  return {
    labeled: labeled,
    hasMore: labeled >= 25
  };
}

function vektorArApiSavePendingBatch_(snapshot) {
  var started = Date.now();

  var query =
    vektorArApiPendingQuery_();

  var refs =
    vektorArApiListMessages_(query, 100);

  var folder =
    DriveApp.getFolderById(
      VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_DRIVE
    );

  var result = {
    threads: 0,
    emails: 0,
    saved: 0,
    ignored: 0
  };

  var seenThreads = {};

  for (var i = 0; i < refs.length; i++) {
    if (
      result.emails >=
      VEKTOR_AR_API_BATCH_MESSAGES
    ) {
      break;
    }

    if (
      Date.now() - started >
      VEKTOR_AR_API_BATCH_MAX_MS
    ) {
      break;
    }

    var message =
      Gmail.Users.Messages.get(
        "me",
        refs[i].id,
        {
          format: "full"
        }
      );

    if (!vektorArApiIsAllowedMessage_(message)) {
      continue;
    }

    var subject =
      vektorArApiHeader_(
        message,
        "Subject"
      );

    var date =
      new Date(
        Number(message.internalDate || 0)
      );

    var row = {
      job_id: snapshot.jobId,
      message_id: message.id,
      data: isNaN(date.getTime())
        ? ""
        : date.toISOString(),
      assunto: subject,
      status: "OK",
      arquivos: []
    };

    var parts = [];

    vektorArApiCollectPdfParts_(
      message.payload || {},
      parts
    );

    for (
      var j = 0;
      j < parts.length;
      j++
    ) {
      var attachmentInfo =
        vektorArApiGetAttachmentBlob_(
          message.id,
          parts[j]
        );

      var saved;

      try {
        saved =
          vektorArApiSaveAttachmentOnce_(
            folder,
            attachmentInfo.blob,
            attachmentInfo.sha1,
            attachmentInfo.size,
            message.id,
            j
          );
      } catch (saveError) {
        throw new Error(
          "Drive/PDF [mensagem " +
            message.id +
            ", anexo " +
            String(parts[j].filename || j + 1) +
            "]: " +
            vektorArApiError_(saveError)
        );
      }

      row.arquivos.push({
        nome: saved.name,
        status: saved.created
          ? "DOWNLOADED"
          : "DUPLICITY"
      });

      if (saved.created) {
        result.saved++;
      } else {
        result.ignored++;
      }
    }

    if (!parts.length) {
      row.status = "SKIPPED_NO_PDF";
      result.ignored++;
    }

    // Primeiro atualiza a auditoria.
    try {
      vektorArApiUpsertAuditRows_([row]);
    } catch (auditError) {
      throw new Error(
        "Drive/auditoria [mensagem " +
          message.id +
          "]: " +
          vektorArApiError_(auditError)
      );
    }

    // Somente depois retira a mensagem da fila.
    try {
      vektorArApiModifyMessageLabels_(
        message.id,
        [],
        ["UNREAD", "INBOX"]
      );
    } catch (finalizeError) {
      throw new Error(
        "Gmail/finalização [mensagem " +
          message.id +
          "]: " +
          vektorArApiError_(finalizeError)
      );
    }

    result.emails++;

    if (
      message.threadId &&
      !seenThreads[message.threadId]
    ) {
      seenThreads[message.threadId] = true;
      result.threads++;
    }

    vektorArApiHeartbeat_(snapshot);
    vektorArApiSaveJob_(snapshot);
  }

  return result;
}

function vektorArApiGetAttachmentBlob_(
  messageId,
  part
) {
  var body = part.body || {};

  /*
   * Para anexos externos, usa a Gmail REST API.
   * Isso evita a conversão automática do campo
   * "bytes" feita pelo serviço avançado.
   */
  var data = body.attachmentId
    ? vektorArApiFetchAttachmentBase64Url_(
        messageId,
        body.attachmentId
      )
    : body.data;

  if (!data) {
    throw new Error(
      "Anexo sem conteúdo: " +
        String(part.filename || "PDF")
    );
  }

  var filename =
    String(
      part.filename ||
      "anexo.pdf"
    );

  var mime =
    String(
      part.mimeType ||
      "application/pdf"
    );

  var bytes =
    vektorArApiAttachmentBytes_(
      data,
      filename
    );

  var digest;

  try {
    digest =
      Utilities.computeDigest(
        Utilities.DigestAlgorithm.SHA_1,
        bytes
      );
  } catch (errorDigest) {
    throw new Error(
      "Falha ao calcular o hash do anexo " +
        filename +
        " (" +
        bytes.length +
        " bytes): " +
        errorDigest.message
    );
  }

  var sha1 = digest
    .map(function (value) {
      var n =
        value < 0
          ? value + 256
          : value;

      return (
        "0" +
        n.toString(16)
      ).slice(-2);
    })
    .join("");

  var blob;

  try {
    blob =
      Utilities.newBlob(
        bytes,
        mime,
        filename
      );
  } catch (errorBlob) {
    throw new Error(
      "Falha ao criar o PDF " +
        filename +
        " (" +
        bytes.length +
        " bytes): " +
        errorBlob.message
    );
  }

  return {
    blob: blob,
    sha1: sha1,
    size: bytes.length
  };
}

function vektorArApiAttachmentBytes_(
  data,
  filename
) {
  /*
   * O serviço avançado pode devolver
   * o campo bytes já como Byte[].
   */
  if (Array.isArray(data)) {
    return vektorArApiNormalizeBytes_(
      data,
      filename
    );
  }

  if (
    data &&
    typeof data.getBytes === "function"
  ) {
    return vektorArApiNormalizeBytes_(
      data.getBytes(),
      filename
    );
  }

  var encoded =
    String(data || "")
      .replace(/\s+/g, "");

  if (!encoded) {
    throw new Error(
      "Anexo sem conteúdo: " +
        filename
    );
  }

  /*
   * Converte Base64URL para Base64 padrão
   * e recompõe o padding.
   */
  encoded = encoded
    .replace(/-/g, "+")
    .replace(/_/g, "/");

  while (
    encoded.length % 4 !== 0
  ) {
    encoded += "=";
  }

  try {
    return Utilities.base64Decode(
      encoded
    );
  } catch (error) {
    throw new Error(
      "Não foi possível decodificar o anexo " +
        filename +
        ": " +
        error.message
    );
  }
}

function vektorArApiFetchAttachmentBase64Url_(
  messageId,
  attachmentId
) {
  var url =
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/" +
    encodeURIComponent(
      String(messageId || "")
    ) +
    "/attachments/" +
    encodeURIComponent(
      String(attachmentId || "")
    );

  var response =
    UrlFetchApp.fetch(
      url,
      {
        method: "get",
        headers: {
          Authorization:
            "Bearer " +
            ScriptApp.getOAuthToken()
        },
        muteHttpExceptions: true
      }
    );

  var status =
    response.getResponseCode();

  var text =
    response.getContentText();

  if (
    status < 200 ||
    status >= 300
  ) {
    throw new Error(
      "Gmail API HTTP " +
        status +
        " ao baixar anexo: " +
        text.substring(0, 500)
    );
  }

  var payload;

  try {
    payload = JSON.parse(text);
  } catch (errorJson) {
    throw new Error(
      "Resposta inválida da Gmail API ao baixar anexo: " +
        errorJson.message
    );
  }

  var encoded =
    String(
      (payload && payload.data) ||
      ""
    );

  if (!encoded) {
    throw new Error(
      "Gmail API retornou anexo sem conteúdo."
    );
  }

  return encoded;
}

function vektorArApiModifyMessageLabels_(
  messageId,
  addLabelIds,
  removeLabelIds
) {
  var id = String(messageId || "").trim();
  if (!id) {
    throw new Error("Gmail/finalização: messageId vazio.");
  }

  var payload = {};
  if (Array.isArray(addLabelIds) && addLabelIds.length) {
    payload.addLabelIds = addLabelIds;
  }
  if (Array.isArray(removeLabelIds) && removeLabelIds.length) {
    payload.removeLabelIds = removeLabelIds;
  }

  var url =
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/" +
    encodeURIComponent(id) +
    "/modify";

  var response = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + ScriptApp.getOAuthToken()
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  var status = response.getResponseCode();
  var text = response.getContentText();
  if (status < 200 || status >= 300) {
    throw new Error(
      "Gmail/finalização HTTP " + status + ": " + text.substring(0, 500)
    );
  }

  return text ? JSON.parse(text) : {};
}

function vektorArApiNormalizeBytes_(
  values,
  filename
) {
  var output =
    new Array(values.length);

  for (
    var i = 0;
    i < values.length;
    i++
  ) {
    var value =
      Number(values[i]);

    if (
      !isFinite(value) ||
      Math.floor(value) !== value
    ) {
      throw new Error(
        "Byte inválido no anexo " +
          filename +
          " (posição " +
          i +
          ")."
      );
    }

    /*
     * Converte byte sem sinal 0..255
     * para Byte assinado -128..127.
     */
    if (
      value >= 128 &&
      value <= 255
    ) {
      value -= 256;
    }

    if (
      value < -128 ||
      value > 127
    ) {
      throw new Error(
        "Byte fora da faixa no anexo " +
          filename +
          " (posição " +
          i +
          ")."
      );
    }

    output[i] = value;
  }

  return output;
}

function vektorArApiCollectPdfParts_(
  part,
  output
) {
  if (!part) {
    return;
  }

  var filename =
    String(part.filename || "");

  var mime =
    String(part.mimeType || "")
      .toLowerCase();

  if (
    filename &&
    (
      /\.pdf$/i.test(filename) ||
      mime === "application/pdf"
    )
  ) {
    output.push(part);
  }

  var children =
    Array.isArray(part.parts)
      ? part.parts
      : [];

  children.forEach(
    function (child) {
      vektorArApiCollectPdfParts_(
        child,
        output
      );
    }
  );
}

function vektorArApiSaveAttachmentOnce_(
  folder,
  blob,
  sha1,
  size,
  messageId,
  attachmentIndex
) {
  var originalName =
    String(
      blob.getName() ||
      "anexo.pdf"
    );

  var token =
    "VEKTOR_AR_SHA1=" + sha1;

  var sameName =
    folder.getFilesByName(
      originalName
    );

  while (sameName.hasNext()) {
    var existing =
      sameName.next();

    var description = "";

    try {
      description =
        String(
          existing.getDescription() ||
          ""
        );
    } catch (_) {}

    if (
      description.indexOf(token) !== -1 ||
      Number(existing.getSize() || 0) ===
        Number(size || 0)
    ) {
      return {
        created: false,
        name: existing.getName(),
        id: existing.getId(),
        sha1: sha1
      };
    }
  }

  var targetName = originalName;

  if (
    folder
      .getFilesByName(originalName)
      .hasNext()
  ) {
    var dot =
      originalName.lastIndexOf(".");

    var base =
      dot > 0
        ? originalName.substring(0, dot)
        : originalName;

    var ext =
      dot > 0
        ? originalName.substring(dot)
        : "";

    targetName =
      base +
      "__" +
      sha1.substring(0, 10) +
      ext;
  }

  /*
   * Cria o arquivo diretamente com o nome definitivo. A versão anterior
   * criava um temporário e chamava setName/setDescription em seguida; essas
   * mutações são desnecessárias e podem falhar em unidades compartilhadas.
   */
  try {
    blob.setName(targetName);
    blob.setContentType("application/pdf");
  } catch (prepareError) {
    throw new Error(
      "não foi possível preparar " +
        targetName +
        ": " +
        vektorArApiError_(prepareError)
    );
  }

  var file;

  try {
    file = folder.createFile(blob);
  } catch (createError) {
    throw new Error(
      "não foi possível criar " +
        targetName +
        ": " +
        vektorArApiError_(createError)
    );
  }

  /* A descrição reforça a deduplicação, mas não é requisito. */
  try {
    file.setDescription(
      token +
        "\nVEKTOR_AR_MESSAGE=" +
        messageId +
        "\nVEKTOR_AR_ATTACHMENT=" +
        attachmentIndex
    );
  } catch (_) {}

  return {
    created: true,
    name: targetName,
    id: file.getId(),
    sha1: sha1
  };
}

function vektorArApiGetGmailCountsCached_(
  force
) {
  var cache =
    CacheService.getScriptCache();

  if (!force) {
    var cached =
      cache.get(
        VEKTOR_AR_API_CACHE_KEY
      );

    if (cached) {
      return JSON.parse(cached);
    }
  }

  vektorArApiAssertService_();

  var result = {
    eligible:
      vektorArApiCountAllowed_(
        vektorArApiEligibleQuery_(false)
      ),
    pending:
      vektorArApiCountPending_(),
    cachedAt:
      new Date().toISOString()
  };

  cache.put(
    VEKTOR_AR_API_CACHE_KEY,
    JSON.stringify(result),
    120
  );

  return result;
}

function vektorArApiCountPending_() {
  return vektorArApiCountAllowed_(
    vektorArApiPendingQuery_()
  );
}

function vektorArApiCountAllowed_(query) {
  var refs =
    vektorArApiListMessages_(
      query,
      500
    );

  var total = 0;

  for (
    var i = 0;
    i < refs.length;
    i++
  ) {
    var message =
      Gmail.Users.Messages.get(
        "me",
        refs[i].id,
        {
          format: "metadata",
          metadataHeaders: [
            "From",
            "Date"
          ]
        }
      );

    if (
      vektorArApiIsAllowedMessage_(
        message
      )
    ) {
      total++;
    }
  }

  return total;
}

function vektorArApiListMessages_(
  query,
  maximum
) {
  var output = [];
  var pageToken = null;

  maximum = Math.max(
    1,
    Math.min(
      Number(maximum || 500),
      500
    )
  );

  do {
    var args = {
      q: query,
      maxResults: Math.min(
        500,
        maximum - output.length
      )
    };

    if (pageToken) {
      args.pageToken = pageToken;
    }

    var response =
      Gmail.Users.Messages.list(
        "me",
        args
      ) || {};

    var messages =
      Array.isArray(response.messages)
        ? response.messages
        : [];

    output =
      output.concat(messages);

    pageToken =
      response.nextPageToken || null;
  } while (
    pageToken &&
    output.length < maximum
  );

  return output.slice(0, maximum);
}

function vektorArApiEligibleQuery_(
  excludeLabel
) {
  var cfg =
    VEKTOR_AR_PROSEGUR_CFG;

  var now = new Date();

  var tz =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";

  var yyyyMm =
    Utilities.formatDate(
      now,
      tz,
      "yyyy/MM/"
    );

  var startDay =
    (
      "0" +
      Number(cfg.DIA_INICIAL || 5)
    ).slice(-2);

  var endExclusive =
    (
      "0" +
      (
        Number(cfg.DIA_FINAL || 15) +
        1
      )
    ).slice(-2);

  /*
   * Aceita tanto o remetente direto
   * quanto "PROSEGUR CASH via".
   */
  var query =
    "in:inbox {from:" +
    cfg.REMETENTE_EMAIL +
    ' from:"' +
    cfg.ALIAS_PERMITIDO +
    '"}' +
    " after:" +
    yyyyMm +
    startDay +
    " before:" +
    yyyyMm +
    endExclusive;

  if (excludeLabel) {
    query +=
      ' -label:"' +
      cfg.NOME_SUBMARCADOR +
      '"';
  }

  return query;
}

function vektorArApiPendingQuery_() {
  var cfg =
    VEKTOR_AR_PROSEGUR_CFG;

  /*
   * O marcador delimita a fila.
   * A validação do remetente ocorre
   * depois da busca.
   */
  return (
    'label:"' +
    cfg.NOME_SUBMARCADOR +
    '" is:unread'
  );
}

function vektorArApiIsAllowedMessage_(
  message
) {
  var cfg =
    VEKTOR_AR_PROSEGUR_CFG;

  var fromUpper =
    vektorArApiHeader_(
      message,
      "From"
    ).toUpperCase();

  var sender =
    String(
      cfg.REMETENTE_EMAIL || ""
    ).toUpperCase();

  var allowed =
    String(
      cfg.ALIAS_PERMITIDO || ""
    ).toUpperCase();

  var blocked =
    String(
      cfg.ALIAS_BLOQUEADO || ""
    ).toUpperCase();

  if (
    blocked &&
    fromUpper.indexOf(blocked) !== -1
  ) {
    return false;
  }

  var senderOk =
    sender &&
    fromUpper.indexOf(sender) !== -1;

  var aliasOk =
    allowed &&
    fromUpper.indexOf(allowed) !== -1;

  return Boolean(
    senderOk ||
    aliasOk
  );
}

function vektorArApiHeader_(
  message,
  headerName
) {
  var headers =
    message &&
    message.payload &&
    Array.isArray(
      message.payload.headers
    )
      ? message.payload.headers
      : [];

  var wanted =
    String(headerName || "")
      .toLowerCase();

  for (
    var i = 0;
    i < headers.length;
    i++
  ) {
    if (
      String(
        headers[i].name || ""
      ).toLowerCase() === wanted
    ) {
      return String(
        headers[i].value || ""
      );
    }
  }

  return "";
}

function vektorArApiGetOrCreateLabelId_(
  labelName
) {
  var response =
    Gmail.Users.Labels.list("me") ||
    {};

  var labels =
    Array.isArray(response.labels)
      ? response.labels
      : [];

  for (
    var i = 0;
    i < labels.length;
    i++
  ) {
    if (
      String(labels[i].name || "") ===
      String(labelName || "")
    ) {
      return labels[i].id;
    }
  }

  var created =
    Gmail.Users.Labels.create(
      {
        name: labelName,
        labelListVisibility: "labelShow",
        messageListVisibility: "show"
      },
      "me"
    );

  if (!created || !created.id) {
    throw new Error(
      "Não foi possível criar o marcador " +
        labelName +
        "."
    );
  }

  return created.id;
}

function vektorArApiAssertService_() {
  if (
    typeof Gmail === "undefined" ||
    !Gmail.Users ||
    !Gmail.Users.Messages
  ) {
    throw new Error(
      'Serviço avançado "Gmail API" não habilitado. ' +
      "No editor, clique em Serviços (+), " +
      "escolha Gmail API v1 e clique em Adicionar."
    );
  }
}

function vektorArApiUpsertAuditRows_(
  newRows
) {
  if (
    !newRows ||
    !newRows.length
  ) {
    return;
  }

  var folder =
    DriveApp.getFolderById(
      VEKTOR_AR_PROSEGUR_CFG.ID_PASTA_DRIVE
    );

  var files =
    folder.getFilesByName(
      "AUDITORIA_EMAIL.json"
    );

  var file =
    files.hasNext()
      ? files.next()
      : null;

  var manifest = {
    detalhes: []
  };

  if (file) {
    try {
      manifest =
        JSON.parse(
          file
            .getBlob()
            .getDataAsString("UTF-8") ||
            "{}"
        ) || {};
    } catch (_) {
      manifest = {
        detalhes: []
      };
    }
  }

  var rows =
    Array.isArray(manifest.detalhes)
      ? manifest.detalhes
      : [];

  var byMessage = {};

  rows.forEach(
    function (row, idx) {
      if (
        row &&
        row.message_id
      ) {
        byMessage[
          String(row.message_id)
        ] = idx;
      }
    }
  );

  newRows.forEach(
    function (row) {
      var key =
        String(
          (row && row.message_id) ||
          ""
        );

      if (
        key &&
        Object.prototype
          .hasOwnProperty.call(
            byMessage,
            key
          )
      ) {
        rows[byMessage[key]] = row;
      } else {
        rows.push(row);

        if (key) {
          byMessage[key] =
            rows.length - 1;
        }
      }
    }
  );

  if (
    rows.length >
    VEKTOR_AR_API_MANIFEST_LIMIT
  ) {
    rows =
      rows.slice(
        -VEKTOR_AR_API_MANIFEST_LIMIT
      );
  }

  manifest.data_geracao =
    new Date().toISOString();

  manifest.detalhes = rows;

  var content =
    JSON.stringify(
      manifest,
      null,
      2
    );

  if (file) {
    vektorArApiUpdateDriveTextFile_(
      file.getId(),
      content
    );
  } else {
    try {
      folder.createFile(
        "AUDITORIA_EMAIL.json",
        content,
        MimeType.PLAIN_TEXT
      );
    } catch (createAuditError) {
      throw new Error(
        "não foi possível criar AUDITORIA_EMAIL.json: " +
          vektorArApiError_(createAuditError)
      );
    }
  }
}

/**
 * Atualiza o conteúdo do manifesto pela Drive API REST. O parâmetro
 * supportsAllDrives torna a operação compatível com unidade compartilhada e
 * evita o erro genérico de File.setContent observado neste projeto.
 */
function vektorArApiUpdateDriveTextFile_(
  fileId,
  content
) {
  var id = String(fileId || "").trim();

  if (!id) {
    throw new Error(
      "ID de AUDITORIA_EMAIL.json vazio."
    );
  }

  var url =
    "https://www.googleapis.com/upload/drive/v3/files/" +
    encodeURIComponent(id) +
    "?uploadType=media&supportsAllDrives=true";

  var response = UrlFetchApp.fetch(url, {
    method: "patch",
    contentType: "application/json; charset=UTF-8",
    headers: {
      Authorization: "Bearer " + ScriptApp.getOAuthToken()
    },
    payload: String(content || ""),
    muteHttpExceptions: true
  });

  var status = response.getResponseCode();
  var text = response.getContentText();

  if (status < 200 || status >= 300) {
    throw new Error(
      "HTTP " +
        status +
        " ao atualizar AUDITORIA_EMAIL.json: " +
        text.substring(0, 500)
    );
  }
}

function vektorArApiGetDriveStatsCached_(
  force
) {
  var cache =
    CacheService.getScriptCache();

  var key =
    VEKTOR_AR_API_CACHE_KEY +
    "_DRIVE";

  if (!force) {
    var cached = cache.get(key);

    if (cached) {
      return JSON.parse(cached);
    }
  }

  var cfg =
    VEKTOR_AR_PROSEGUR_CFG;

  var destination =
    DriveApp.getFolderById(
      cfg.ID_PASTA_DRIVE
    );

  var processedRoot =
    DriveApp.getFolderById(
      cfg.ID_PASTA_PROCESSADOS_RAIZ
    );

  var totalDestination = 0;

  var files =
    destination.getFiles();

  while (files.hasNext()) {
    files.next();
    totalDestination++;
  }

  var currentPeriod =
    Utilities.formatDate(
      new Date(),
      Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
      "MM-yyyy"
    );

  var totalProcessed = 0;

  var folders =
    processedRoot.getFoldersByName(
      currentPeriod
    );

  if (folders.hasNext()) {
    var monthFiles =
      folders.next().getFiles();

    while (monthFiles.hasNext()) {
      monthFiles.next();
      totalProcessed++;
    }
  }

  var result = {
    totalDestino: totalDestination,
    totalProcessadosMes: totalProcessed
  };

  cache.put(
    key,
    JSON.stringify(result),
    300
  );

  return result;
}

function vektorArApiJobKey_(jobId) {
  return (
    VEKTOR_AR_API_JOB_PREFIX +
    String(jobId || "").trim()
  );
}

function vektorArApiSaveJob_(snapshot) {
  if (
    !snapshot ||
    !snapshot.jobId
  ) {
    throw new Error(
      "Snapshot Gmail API inválido."
    );
  }

  PropertiesService
    .getScriptProperties()
    .setProperty(
      vektorArApiJobKey_(
        snapshot.jobId
      ),
      JSON.stringify(snapshot)
    );
}

function vektorArApiGetJob_(jobId) {
  if (!jobId) {
    return null;
  }

  var raw =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        vektorArApiJobKey_(jobId)
      );

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

function vektorArApiGetLastJob_() {
  var id =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        VEKTOR_AR_API_LAST_JOB_KEY
      ) || "";

  return id
    ? vektorArApiGetJob_(id)
    : null;
}

function vektorArApiHeartbeat_(snapshot) {
  snapshot.lastHeartbeatAtIso =
    new Date().toISOString();
}

function vektorArApiExpireStaleJob_(
  snapshot
) {
  if (
    !snapshot ||
    (
      snapshot.status !== "RUNNING" &&
      snapshot.status !== "QUEUED"
    )
  ) {
    return snapshot;
  }

  var heartbeat =
    new Date(
      snapshot.lastHeartbeatAtIso ||
      snapshot.startedAtIso ||
      ""
    );

  if (isNaN(heartbeat.getTime())) {
    return snapshot;
  }

  if (
    (
      Date.now() -
      heartbeat.getTime()
    ) /
      60000 <=
    VEKTOR_AR_API_STALE_MINUTES
  ) {
    return snapshot;
  }

  snapshot.status = "ERROR";
  snapshot.stageKey = "error";
  snapshot.stageLabel =
    "Execução interrompida; inicie novamente para retomar sem duplicidade.";
  snapshot.finishedAtIso =
    new Date().toISOString();

  vektorArApiPushDetail_(
    snapshot,
    snapshot.stageLabel
  );

  vektorArApiSaveJob_(snapshot);

  return snapshot;
}

function vektorArApiPushDetail_(
  snapshot,
  label
) {
  snapshot.details =
    Array.isArray(snapshot.details)
      ? snapshot.details
      : [];

  snapshot.details.push({
    at: new Date().toISOString(),
    label: String(label || "")
  });

  if (
    snapshot.details.length > 40
  ) {
    snapshot.details =
      snapshot.details.slice(-40);
  }
}

function vektorArApiError_(e) {
  return e && e.message
    ? e.message
    : String(
        e ||
        "Erro desconhecido."
      );
}

function testePainelProsegurGmailApi() {
  console.log(
    JSON.stringify(
      vektorArApiGetProsegurDashboard(),
      null,
      2
    )
  );
}

/**
 * Teste somente leitura:
 * não salva no Drive;
 * não altera marcador;
 * não marca mensagem como lida;
 * não modifica o JSON.
 */
function testarLeituraProsegurGmailApi() {
  var result = {
    ok: false,
    query: "",
    mensagensEncontradas: 0,
    mensagemTestada: "",
    assunto: "",
    anexo: "",
    tamanhoBytes: 0,
    sha1: ""
  };

  try {
    vektorArApiAssertService_();

    result.query =
      vektorArApiPendingQuery_();

    var refs =
      vektorArApiListMessages_(
        result.query,
        20
      );

    result.mensagensEncontradas =
      refs.length;

    for (
      var i = 0;
      i < refs.length;
      i++
    ) {
      var message =
        Gmail.Users.Messages.get(
          "me",
          refs[i].id,
          {
            format: "full"
          }
        );

      if (
        !vektorArApiIsAllowedMessage_(
          message
        )
      ) {
        continue;
      }

      var parts = [];

      vektorArApiCollectPdfParts_(
        message.payload || {},
        parts
      );

      if (!parts.length) {
        continue;
      }

      var attachment =
        vektorArApiGetAttachmentBlob_(
          message.id,
          parts[0]
        );

      result.ok = true;
      result.mensagemTestada =
        message.id;

      result.assunto =
        vektorArApiHeader_(
          message,
          "Subject"
        );

      result.anexo =
        attachment.blob.getName();

      result.tamanhoBytes =
        attachment.size;

;

      result.sha1 =
        attachment.sha1;

      console.log(
        JSON.stringify(
          result,
          null,
          2
        )
      );

      return result;
    }

    result.error =
      "Nenhuma mensagem permitida com PDF foi encontrada para o teste.";
  } catch (error) {
    result.error =
      vektorArApiError_(error);

    result.stack =
      error && error.stack
        ? String(error.stack)
        : "";
  }

  console.log(
    JSON.stringify(
      result,
      null,
      2
    )
  );

  return result;
}