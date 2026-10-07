// =========================================================================
// GOOGLE APPS SCRIPT: ROTULAR, SALVAR E AUDITAR PDFS DA PROSEGUR
// =========================================================================
// VERSÃO INTEGRAL COM AUDITORIA (335+ LINHAS PRESERVADAS)
// =========================================================================

var CFG_PROSEGUR = {
  ID_PASTA_DRIVE: "CONFIGURE_ID_PASTA_DRIVE",
  NOME_SUBMARCADOR: "CONTAS A RECEBER/Prosegur",
  REMETENTE_EMAIL: "usuario01@empresa.exemplo",
  ALIAS_PERMITIDO: "PROSEGUR CASH",
  ALIAS_BLOQUEADO: "SEGURPRO VIGILANCIA",
  DIA_INICIAL: 5,
  DIA_FINAL: 15,
  ARQUIVAR_APOS_ROTULAR: true,   // true = tira da caixa de entrada; false = mantém na Inbox
  LOTE_THREADS: 100,
  JANELA_DIAS_BUSCA: 90          // reduz o escopo da busca para não varrer a caixa inteira
};


// -------------------------------------------------------------------------
// FUNÇÃO PRINCIPAL
// Rode esta função manualmente ou por trigger.
// Ela primeiro rotula/arquiva os e-mails elegíveis e depois salva os PDFs.
// -------------------------------------------------------------------------
function processarProsegur() {
  // Inicializa objeto de auditoria (Agente IA)
  var logsAuditoria = {
    data_geracao: new Date().toISOString(),
    total_threads_lote: 0,
    total_emails_vistos: 0,
    total_arquivos_salvos: 0,
    total_arquivos_ignorados: 0,
    detalhes: []
  };

  try {
    rotularEmailsProsegurNaInbox_(logsAuditoria);
    salvarAnexosProsegur(logsAuditoria);
    salvarRelatorioAuditoria_(logsAuditoria);
  } catch (e) {
    Logger.log("Erro no processamento principal: " + e.message);
  }
}


// -------------------------------------------------------------------------
// ETAPA 1: localizar e-mails da Prosegur na Inbox e mover para o submarcador
// Regras:
// - remetente deve conter usuario01@empresa.exemplo
// - deve estar entre os dias 05 e 15 do mês (pela data do e-mail)
// - se o "From" contiver SEGURPRO VIGILANCIA, NÃO processa
// - opcionalmente arquiva após rotular
// -------------------------------------------------------------------------
function rotularEmailsProsegurNaInbox_(logs) {
  var label = GmailApp.getUserLabelByName(CFG_PROSEGUR.NOME_SUBMARCADOR);
  if (!label) {
    throw new Error("Marcador não encontrado: " + CFG_PROSEGUR.NOME_SUBMARCADOR);
  }

  var inicio = 0;
  var lote = CFG_PROSEGUR.LOTE_THREADS;

  while (true) {
    var query =
      'in:inbox from:' + CFG_PROSEGUR.REMETENTE_EMAIL +
      ' newer_than:' + CFG_PROSEGUR.JANELA_DIAS_BUSCA + 'd';

    var threads = GmailApp.search(query, inicio, lote);
    Logger.log("Lote Inbox | início: " + inicio + " | threads encontradas: " + threads.length);

    if (!threads.length) {
      break;
    }

    if (logs) logs.total_threads_lote += threads.length;

    for (var i = 0; i < threads.length; i++) {
      var thread = threads[i];
      var mensagens = thread.getMessages();

      var deveRotularThread = false;
      var bloquearThread = false;

      for (var j = 0; j < mensagens.length; j++) {
        var msg = mensagens[j];

        if (!msg.isInInbox()) continue;

        var from = String(msg.getFrom() || "");
        var fromUpper = from.toUpperCase();
        var diaMes = msg.getDate().getDate();

        var contemEmailProsegur =
          fromUpper.indexOf(CFG_PROSEGUR.REMETENTE_EMAIL.toUpperCase()) !== -1;

        var contemAliasPermitido =
          fromUpper.indexOf(CFG_PROSEGUR.ALIAS_PERMITIDO.toUpperCase()) !== -1;

        var contemAliasBloqueado =
          fromUpper.indexOf(CFG_PROSEGUR.ALIAS_BLOQUEADO.toUpperCase()) !== -1;

        if (contemAliasBloqueado) {
          bloquearThread = true;
          Logger.log("Thread bloqueada por alias proibido: " + from);
          break;
        }

        if (
          contemEmailProsegur &&
          contemAliasPermitido &&
          diaMes >= CFG_PROSEGUR.DIA_INICIAL &&
          diaMes <= CFG_PROSEGUR.DIA_FINAL
        ) {
          deveRotularThread = true;
        }
      }

      if (bloquearThread || !deveRotularThread) {
        continue;
      }

      if (!threadTemMarcador_(thread, CFG_PROSEGUR.NOME_SUBMARCADOR)) {
        label.addToThread(thread);
        Logger.log("Marcador aplicado à thread: " + thread.getFirstMessageSubject());
      } else {
        Logger.log("Thread já estava com o marcador: " + thread.getFirstMessageSubject());
      }

      if (CFG_PROSEGUR.ARQUIVAR_APOS_ROTULAR && thread.isInInbox()) {
        thread.moveToArchive();
        Logger.log("Thread arquivada.");
      }
    }

    inicio += lote;
  }
}


// -------------------------------------------------------------------------
// ETAPA 2: salvar os PDFs das threads já marcadas no Drive
// - evita duplicidade pelo nome original do arquivo PDF
// - marca a mensagem como lida quando salvou ou quando já existia
// -------------------------------------------------------------------------
function salvarAnexosProsegur(logs) {
  var lock = LockService.getScriptLock();
  lock.waitLock(60000); // 60 segundos de espera pelo lock

  try {
    var pastaDestino = DriveApp.getFolderById(CFG_PROSEGUR.ID_PASTA_DRIVE);
    var label = GmailApp.getUserLabelByName(CFG_PROSEGUR.NOME_SUBMARCADOR);

    if (!label) {
      throw new Error("Marcador não encontrado: " + CFG_PROSEGUR.NOME_SUBMARCADOR);
    }

    Logger.log("Pasta encontrada: " + pastaDestino.getName());

    // INDEXA O QUE JÁ EXISTE NA PASTA
    var arquivosExistentes = {};
    var files = pastaDestino.getFiles();

    while (files.hasNext()) {
      var f = files.next();
      var nome = (f.getName() || "").trim();
      if (!nome) continue;

      var chave = normalizarNomeCanonico_(nome);
      arquivosExistentes[chave] = true;
    }

    var inicio = 0;
    var lote = CFG_PROSEGUR.LOTE_THREADS;

    while (true) {
      var conversas = label.getThreads(inicio, lote);
      Logger.log("Lote do marcador | início: " + inicio + " | conversas: " + conversas.length);

      if (!conversas.length) {
        break;
      }

      for (var i = 0; i < conversas.length; i++) {
        var mensagens = conversas[i].getMessages();
        if (logs) logs.total_emails_vistos += mensagens.length;

        for (var j = 0; j < mensagens.length; j++) {
          var msg = mensagens[j];

          var auditInfo = {
            assunto: msg.getSubject(),
            data: msg.getDate().toISOString(),
            arquivos: [],
            status: "OK"
          };

          // trava: não processa novamente mensagens já lidas
          if (!msg.isUnread()) {
            Logger.log("Mensagem já lida, ignorada: " + msg.getSubject());
            if (logs) {
              auditInfo.status = "SKIPPED_ALREADY_READ";
              logs.detalhes.push(auditInfo);
            }
            continue;
          }

          var anexos = msg.getAttachments();
          var processouAlgo = false;

          Logger.log("-----");
          Logger.log("Assunto: " + msg.getSubject());
          Logger.log("Remetente: " + msg.getFrom());
          Logger.log("Qtd anexos: " + anexos.length);

          for (var k = 0; k < anexos.length; k++) {
            try {
              var anexo = anexos[k];
              var nomeArquivoOriginal = (anexo.getName() || "").trim();

              if (!nomeArquivoOriginal) {
                Logger.log("Ignorado: anexo sem nome.");
                continue;
              }

              if (!nomeArquivoOriginal.toLowerCase().endsWith(".pdf")) {
                Logger.log("Ignorado (não é PDF): " + nomeArquivoOriginal);
                continue;
              }

              var chaveCanonica = normalizarNomeCanonico_(nomeArquivoOriginal);

              if (arquivosExistentes[chaveCanonica]) {
                Logger.log("Arquivo já existe, ignorado: " + nomeArquivoOriginal);
                if (logs) {
                  auditInfo.arquivos.push({ nome: nomeArquivoOriginal, status: "DUPLICITY" });
                  logs.total_arquivos_ignorados++;
                }
                processouAlgo = true;
                continue;
              }

              var blobPdf = Utilities.newBlob(
                anexo.getBytes(),
                "application/pdf",
                nomeArquivoOriginal
              );

              pastaDestino.createFile(blobPdf);
              arquivosExistentes[chaveCanonica] = true;

              Logger.log("PDF salvo: " + nomeArquivoOriginal);
              if (logs) {
                auditInfo.arquivos.push({ nome: nomeArquivoOriginal, status: "DOWNLOADED" });
                logs.total_arquivos_salvos++;
              }
              processouAlgo = true;

            } catch (erroAnexo) {
              Logger.log("Erro ao salvar anexo: " + erroAnexo);
            }
          }

          if (processouAlgo && msg.isUnread()) {
            msg.markRead();
            Logger.log("Mensagem marcada como lida.");
          }

          if (logs) logs.detalhes.push(auditInfo);
        }
      }

      inicio += lote;
    }

    Logger.log("Processo finalizado.");

  } catch (erroGeral) {
    Logger.log("Ocorreu um erro: " + erroGeral.toString());
    throw erroGeral;
  } finally {
    lock.releaseLock();
  }
}


/**
 * NOVO: SALVA O MANIFESTO DE AUDITORIA NA PASTA DO DRIVE
 */
function salvarRelatorioAuditoria_(logs) {
  if (!logs) return;
  var pasta = DriveApp.getFolderById(CFG_PROSEGUR.ID_PASTA_DRIVE);
  var nomeArquivo = "AUDITORIA_EMAIL.json";

  // Limpa manifesto anterior
  var files = pasta.getFilesByName(nomeArquivo);
  while (files.hasNext()) { files.next().setTrashed(true); }

  pasta.createFile(nomeArquivo, JSON.stringify(logs, null, 2));
  Logger.log("Manifesto de Auditoria gerado: AUDITORIA_EMAIL.json");
}


// -------------------------------------------------------------------------
// NORMALIZA O NOME DO ARQUIVO PARA COMPARAÇÃO DE DUPLICIDADE
// -------------------------------------------------------------------------
function normalizarNomeCanonico_(nome) {
  return String(nome || "").toLowerCase().trim();
}


// -------------------------------------------------------------------------
// HELPER: verifica se a thread já possui o marcador
// -------------------------------------------------------------------------
function threadTemMarcador_(thread, nomeMarcador) {
  var labels = thread.getLabels();
  for (var i = 0; i < labels.length; i++) {
    if (labels[i].getName() === nomeMarcador) {
      return true;
    }
  }
  return false;
}


// -------------------------------------------------------------------------
// LISTA TODOS OS TRIGGERS DO PROJETO
// Use para verificar se há duplicidade
// -------------------------------------------------------------------------
function listarTriggersDoProjeto() {
  var triggers = ScriptApp.getProjectTriggers();

  if (!triggers.length) {
    Logger.log("Nenhum trigger encontrado.");
    return;
  }

  for (var i = 0; i < triggers.length; i++) {
    var t = triggers[i];
    Logger.log(
      "Trigger #" + (i + 1) +
      " | Função: " + t.getHandlerFunction() +
      " | Tipo: " + t.getEventType() +
      " | Origem: " + t.getTriggerSource() +
      " | ID único: " + t.getUniqueId()
    );
  }
}


// -------------------------------------------------------------------------
// CRIEI UM GATILHO PARA RODAR AUTOMATICAMENTE A CADA 15 MINUTOS
// Só cria se ainda não existir trigger para processarProsegur
// -------------------------------------------------------------------------
function criarTriggerProcessarProsegur() {
  var triggers = ScriptApp.getProjectTriggers();

  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === "processarProsegur") {
      Logger.log("Já existe trigger para processarProsegur. Nenhum novo trigger foi criado.");
      return;
    }
  }

  ScriptApp.newTrigger("processarProsegur")
    .timeBased()
    .everyMinutes(15)
    .create();

  Logger.log("Trigger criado para processarProsegur.");
}


// -------------------------------------------------------------------------
// REMOVE TRIGGERS ANTIGOS RELACIONADOS À ROTINA DA PROSEGUR
// -------------------------------------------------------------------------
function removerTriggersProcessarProsegur() {
  var triggers = ScriptApp.getProjectTriggers();

  for (var i = 0; i < triggers.length; i++) {
    var fn = triggers[i].getHandlerFunction();

    if (fn === "processarProsegur" || fn === "salvarAnexosProsegur") {
      ScriptApp.deleteTrigger(triggers[i]);
      Logger.log("Trigger removido da função: " + fn);
    }
  }
}
