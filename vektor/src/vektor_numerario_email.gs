/******************************************************
 * VEKTOR | NUMERÁRIO V2
 *
 * Disparos operacionais
 * Base de lojas compartilhada com POS
 * Configurações
 * Relatórios
 * Persistência em JSON no Google Drive
 ******************************************************/

var VEKTOR_NUM_V2_MODULE_KEY = "AR";
var VEKTOR_NUM_V2_SCHEMA_VERSION = 3;


/* =====================================================
   STORAGE
   ===================================================== */

var VEKTOR_NUM_V2_STORAGE_FOLDER_ID =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_V2_STORAGE_FOLDER_ID") || "";

var VEKTOR_NUM_V2_STORAGE_FOLDER_PROP =
  "VEKTOR_NUMERARIO_V2_STORAGE_FOLDER_ID";


var VEKTOR_NUM_V2_FILE_NAMES = {

  CENTAURO:
    "vektor_numerario_centauro.json",

  FISIA:
    "vektor_numerario_fisia.json",

  CONFIG:
    "vektor_numerario_config.json",

  DISPAROS:
    "vektor_numerario_disparos.json"
};

/*
 * =====================================================
 * RECOVERY / PROTEÇÃO DE PERSISTÊNCIA
 * =====================================================
 *
 * Mantém snapshots locais antes de qualquer
 * alteração nos JSONs oficiais do Numerário.
 */
var VEKTOR_NUM_V2_RECOVERY_FOLDER_NAME =
  "_RECOVERY";

var VEKTOR_NUM_V2_RECOVERY_KEEP =
  20;


/* =====================================================
   E-MAIL
   ===================================================== */

var VEKTOR_NUM_V2_EMAIL_FROM =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_V2_EMAIL_FROM") || "";

var VEKTOR_NUM_V2_EMAIL_NAME =
  "Vektor - Grupo SBF";

var VEKTOR_NUM_V2_EMAIL_CC =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_V2_EMAIL_CC") || "";

/* =====================================================
   TESTE TEMPORÁRIO DE E-MAIL
   ===================================================== */

var VEKTOR_NUM_V2_TEST_EMAIL =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_V2_TEST_EMAIL") || "";


var VEKTOR_NUM_V2_TEST_STORES = {

  CENTAURO:
    "0012",

  FISIA:
    "2029"

};

/* =====================================================
   EXCLUSÃO ADMINISTRATIVA DE LINHAS
   ===================================================== */

var VEKTOR_NUM_V2_DELETE_ALLOWED_EMAIL =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_V2_DELETE_ALLOWED_EMAIL") || "";


/* =====================================================
   STATUS
   ===================================================== */

var VEKTOR_NUM_V2_STATUS_OPTIONS = [

  {
    value: "OK",
    color: "#16c96f",
    text: "#052e16"
  },

  {
    value: "PENDENTE",
    color: "#ef2b20",
    text: "#ffffff"
  },

  {
    value: "TRATATIVA - LOJA",
    color: "#efa1a5",
    text: "#111827"
  },

  {
    value: "TRATATIVA - FIN",
    color: "#5ed2df",
    text: "#111827"
  },

  {
    value: "PERDA",
    color: "#fff832",
    text: "#111827"
  }

];


/* =====================================================
   CABEÇALHOS
   ===================================================== */

var VEKTOR_NUM_V2_HEADERS = {

  CENTAURO: [
    "CÓDIGO ENVIO EMAIL_ASSUNTO",
    "Status",
    "DATA COBRANÇA",
    "DATA FINAL (TRATATIVA)",
    "LOJA",
    "DATA DEPÓSITO",
    "Mov. Inicial",
    "Mov. Final",
    "VALOR PREVISTO",
    "VALOR DEPOSITADO",
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

  FISIA: [
    "CÓDIGO ÚNICO_ASSUNTO",
    "STATUS",
    "DATA COBRANÇA",
    "DATA FINAL (TRATATIVA)",
    "LOJA",
    "DATA DEPÓSITO",
    "Mov. Inicial",
    "Mov. Final",
    "VALOR PREVISTO",
    "VALOR DEPOSITADO",
    "DIFERENÇA",
    "OBSERVAÇÃO",
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)",
    "E-mail Loja",
    "TIPO",
    "MÊS PENDÊNCIA",
    "QTD DIAS TRATATIVA",
    "STATUS ENVIO"
  ]
};


var VEKTOR_NUM_V2_MANUAL_COLUMNS = {

  CENTAURO: {
    "Status": true,
    "LOJA": true,
    "DATA DEPÓSITO": true,
    "Mov. Inicial": true,
    "Mov. Final": true,
    "VALOR PREVISTO": true,
    "VALOR DEPOSITADO": true,
    "INFORMAÇÕES": true,
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)": true
  },

  FISIA: {
    "STATUS": true,
    "LOJA": true,
    "DATA DEPÓSITO": true,
    "Mov. Inicial": true,
    "Mov. Final": true,
    "VALOR PREVISTO": true,
    "VALOR DEPOSITADO": true,
    "OBSERVAÇÃO": true,
    "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)": true
  }
};


/* =====================================================
   CONFIG
   ===================================================== */

var VEKTOR_NUM_V2_DEFAULT_CONFIG = {

  emailFrom:
    VEKTOR_NUM_V2_EMAIL_FROM,

  emailName:
    VEKTOR_NUM_V2_EMAIL_NAME,

  emailCc:
    VEKTOR_NUM_V2_EMAIL_CC,

  replyTo:
    VEKTOR_NUM_V2_EMAIL_CC,

  maxSendPerRun:
    100,

  backupEnabled:
    false,

  backupFrequency:
    "DAILY",

  backupStartDate:
    "",

  backupTime:
    "23:00"
};


/* =====================================================
   HELPERS BÁSICOS
   ===================================================== */

function vektorNumV2NormEmpresa_(empresa) {

  empresa =
    String(
      empresa || ""
    )
      .trim()
      .toUpperCase();

  return empresa === "FISIA"
    ? "FISIA"
    : "CENTAURO";
}


function vektorNumV2EmpresaPos_(empresa) {

  return (
    vektorNumV2NormEmpresa_(
      empresa
    ) === "FISIA"
  )
    ? "NIKE"
    : "CENTAURO";
}


function vektorNumV2Store4_(value) {

  var digits =
    String(
      value || ""
    )
      .replace(
        /\D/g,
        ""
      );

  if (!digits) {
    return "";
  }

  return String(
    Number(
      digits
    )
  ).padStart(
    4,
    "0"
  );
}

function vektorNumV2IsTestStore_(
  empresa,
  loja
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var loja4 =
    vektorNumV2Store4_(
      loja
    );


  return (
    loja4 &&
    loja4 ===
      VEKTOR_NUM_V2_TEST_STORES[
        empresa
      ]
  );
}


function vektorNumV2ResolveRecipients_(
  empresa,
  loja,
  store
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var loja4 =
    vektorNumV2Store4_(
      loja
    );


  /*
   * TESTE TEMPORÁRIO
   */
  if (
    vektorNumV2IsTestStore_(
      empresa,
      loja4
    )
  ) {

    return VEKTOR_NUM_V2_TEST_EMAIL;
  }


  /*
   * Produção normal.
   */
  store =
    store || {};


  return vektorNumV2NormalizeEmails_(
    store.EMAILS
  );
}

function vektorNumV2Now_() {

  return Utilities
    .formatDate(
      new Date(),
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo",
      "yyyy-MM-dd HH:mm:ss"
    );
}


function vektorNumV2TodayBr_() {

  return Utilities
    .formatDate(
      new Date(),
      Session.getScriptTimeZone() ||
      "America/Sao_Paulo",
      "dd/MM/yyyy"
    );
}


function vektorNumV2Escape_(
  value
) {

  return String(
    value == null
      ? ""
      : value
  )
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


function vektorNumV2ParseMoney_(
  value
) {

  if (
    typeof value ===
    "number"
  ) {

    return isFinite(value)
      ? value
      : 0;
  }

  var text =
    String(
      value || ""
    )
      .trim();

  if (!text) {
    return 0;
  }

  text =
    text
      .replace(
        /R\$/gi,
        ""
      )
      .replace(
        /\s/g,
        ""
      );


  if (
    text.indexOf(",") >= 0
  ) {

    text =
      text
        .replace(
          /\./g,
          ""
        )
        .replace(
          ",",
          "."
        );
  }


  var number =
    Number(
      text
    );


  return isFinite(number)
    ? number
    : 0;
}


function vektorNumV2FmtMoney_(
  value
) {

  var number =
    Number(
      value || 0
    );

  if (!isFinite(number)) {
    number = 0;
  }


  var negative =
    number < 0;


  number =
    Math.abs(
      number
    );


  var parts =
    number
      .toFixed(2)
      .split(".");


  parts[0] =
    parts[0].replace(
      /\B(?=(\d{3})+(?!\d))/g,
      "."
    );


  return (
    (negative ? "-" : "") +
    "R$ " +
    parts[0] +
    "," +
    parts[1]
  );
}


function vektorNumV2NormalizeEmails_(
  value
) {

  var seen = {};


  String(
    value || ""
  )
    .replace(
      /;/g,
      ","
    )
    .split(",")
    .map(function(email) {

      return String(
        email || ""
      )
        .trim()
        .toLowerCase();

    })
    .filter(function(email) {

      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        .test(
          email
        );

    })
    .forEach(function(email) {

      seen[email] =
        true;

    });


  return Object
    .keys(
      seen
    )
    .join(",");
}




/* =====================================================
   REGRAS OPERACIONAIS / MIGRAÇÃO
   ===================================================== */

function vektorNumV2RequiredInputsComplete_(row) {
  row = row || {};

  return !!(
    vektorNumV2Store4_(row.LOJA) &&
    String(row["VALOR PREVISTO"] == null ? "" : row["VALOR PREVISTO"]).trim() !== "" &&
    String(row["VALOR DEPOSITADO"] == null ? "" : row["VALOR DEPOSITADO"]).trim() !== ""
  );
}


function vektorNumV2MigrateRow_(empresa, row) {
  empresa = vektorNumV2NormEmpresa_(empresa);
  row = row || {};

  // Migração da versão anterior: DATA REFERÊNCIA -> DATA DEPÓSITO.
  if (
    String(row["DATA DEPÓSITO"] == null ? "" : row["DATA DEPÓSITO"]).trim() === "" &&
    String(row["DATA REFERÊNCIA"] == null ? "" : row["DATA REFERÊNCIA"]).trim() !== ""
  ) {
    row["DATA DEPÓSITO"] = row["DATA REFERÊNCIA"];
  }

  if (row["Mov. Inicial"] === undefined || row["Mov. Inicial"] === null) {
    row["Mov. Inicial"] = "";
  }

  if (row["Mov. Final"] === undefined || row["Mov. Final"] === null) {
    row["Mov. Final"] = "";
  }

  // A chave antiga deixa de fazer parte da estrutura operacional.
  try { delete row["DATA REFERÊNCIA"]; } catch (_) {}

  return row;
}


/* =====================================================
   DATA
   ===================================================== */

function vektorNumV2DateIso_(
  value
) {

  if (!value) {
    return "";
  }


  if (
    value instanceof Date &&
    !isNaN(
      value.getTime()
    )
  ) {

    return Utilities
      .formatDate(
        value,
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
        "yyyy-MM-dd"
      );
  }


  var text =
    String(
      value || ""
    ).trim();


  var iso =
    text.match(
      /^(\d{4})-(\d{2})-(\d{2})$/
    );


  if (iso) {

    return (
      iso[1] +
      "-" +
      iso[2] +
      "-" +
      iso[3]
    );
  }


  var br =
    text.match(
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


  return "";
}


function vektorNumV2DateBr_(
  value
) {

  var iso =
    vektorNumV2DateIso_(
      value
    );


  if (!iso) {
    return "";
  }


  var parts =
    iso.split("-");


  return (
    parts[2] +
    "/" +
    parts[1] +
    "/" +
    parts[0]
  );
}


function vektorNumV2DateCode_(
  value
) {

  var iso =
    vektorNumV2DateIso_(
      value
    );


  if (!iso) {

    iso =
      Utilities.formatDate(
        new Date(),
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
        "yyyy-MM-dd"
      );
  }


  var p =
    iso.split("-");


  return (
    p[2] +
    p[1] +
    p[0].slice(-2)
  );
}


function vektorNumV2MonthText_(
  value
) {

  var iso =
    vektorNumV2DateIso_(
      value
    );


  if (!iso) {
    return "";
  }


  var p =
    iso.split("-");


  return (
    p[1] +
    "/" +
    p[0]
  );
}


function vektorNumV2BusinessDays_(
  startValue,
  endValue
) {

  var startIso =
    vektorNumV2DateIso_(
      startValue
    );


  if (!startIso) {
    return "";
  }


  var endIso =
    vektorNumV2DateIso_(
      endValue
    );


  if (!endIso) {

    endIso =
      Utilities.formatDate(
        new Date(),
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
        "yyyy-MM-dd"
      );
  }


  var startParts =
    startIso.split("-");


  var endParts =
    endIso.split("-");


  var start =
    new Date(
      Number(startParts[0]),
      Number(startParts[1]) - 1,
      Number(startParts[2])
    );


  var end =
    new Date(
      Number(endParts[0]),
      Number(endParts[1]) - 1,
      Number(endParts[2])
    );


  if (
    end <
    start
  ) {

    return 0;
  }


  var total = 0;


  var current =
    new Date(
      start.getTime()
    );


  current.setDate(
    current.getDate() + 1
  );


  while (
    current <= end
  ) {

    var day =
      current.getDay();


    if (
      day !== 0 &&
      day !== 6
    ) {

      total++;
    }


    current.setDate(
      current.getDate() + 1
    );
  }


  return total;
}


/* =====================================================
   STORAGE
   ===================================================== */

function vektorNumV2GetStorageFolder_() {

  var folderId =
    String(
      VEKTOR_NUM_V2_STORAGE_FOLDER_ID ||
      ""
    ).trim();


  if (!folderId) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: " +
      "o ID da pasta oficial de armazenamento não está configurado. " +
      "Nenhuma nova pasta será criada."
    );
  }


  try {

    var folder =
      DriveApp.getFolderById(
        folderId
      );


    return folder;


  } catch (error) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: " +
      "não foi possível acessar a pasta oficial de armazenamento. " +
      "ID: " +
      folderId +
      ". Nenhuma nova pasta foi criada. Detalhe: " +
      (
        error &&
        error.message
          ? error.message
          : String(error)
      )
    );
  }
}

function vektorNumV2BlankData_(
  key
) {

  var header =
    VEKTOR_NUM_V2_HEADERS[key] ||
    [];


  return {

    version:
      VEKTOR_NUM_V2_SCHEMA_VERSION,

    header:
      header.slice(),

    rows: [],

    meta: {
      createdAt:
        vektorNumV2Now_()
    }

  };
}


function vektorNumV2BlankDispatches_() {

  return {

    version:
      VEKTOR_NUM_V2_SCHEMA_VERSION,

    rows: [],

    meta: {
      createdAt:
        vektorNumV2Now_()
    }

  };
}


function vektorNumV2FindFile_(
  key
) {

  var name =
    VEKTOR_NUM_V2_FILE_NAMES[
      key
    ];


  if (!name) {

    throw new Error(
      "Arquivo Numerário inválido: " +
      key
    );
  }


  var folder =
    vektorNumV2GetStorageFolder_();


  var files =
    folder.getFilesByName(
      name
    );


  return files.hasNext()
    ? files.next()
    : null;
}


function vektorNumV2EnsureFile_(
  key
) {

  var name =
    VEKTOR_NUM_V2_FILE_NAMES[
      key
    ];


  if (!name) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: " +
      "chave de arquivo inválida: " +
      key
    );
  }


  var file =
    vektorNumV2FindFile_(
      key
    );


  if (!file) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: " +
      "o arquivo obrigatório '" +
      name +
      "' não foi encontrado na storage oficial. " +
      "Nenhum arquivo vazio foi criado."
    );
  }


  return file;
}

function vektorNumV2ValidateJsonText_(
  key,
  text
) {

  text =
    String(
      text == null
        ? ""
        : text
    );


  if (
    !text.trim()
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: o arquivo '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "' está vazio."
    );
  }


  var obj;


  try {

    obj =
      JSON.parse(
        text
      );

  } catch (error) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: o arquivo '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "' contém JSON inválido. Detalhe: " +
      (
        error &&
        error.message
          ? error.message
          : String(error)
      )
    );
  }


  if (
    !obj ||
    typeof obj !==
      "object" ||
    Array.isArray(obj)
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: estrutura inválida no arquivo '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "'."
    );
  }


  if (
    (
      key === "CENTAURO" ||
      key === "FISIA" ||
      key === "DISPAROS"
    ) &&
    !Array.isArray(
      obj.rows
    )
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: o arquivo '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "' não possui uma estrutura válida de linhas."
    );
  }


  if (
    (
      key === "CENTAURO" ||
      key === "FISIA"
    ) &&
    !Array.isArray(
      obj.header
    )
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: o arquivo '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "' não possui cabeçalho válido."
    );
  }


  return obj;
}

function vektorNumV2RecoveryFolder_() {

  var storage =
    vektorNumV2GetStorageFolder_();


  var folders =
    storage.getFoldersByName(
      VEKTOR_NUM_V2_RECOVERY_FOLDER_NAME
    );


  if (
    folders.hasNext()
  ) {

    return folders.next();
  }


  return storage.createFolder(
    VEKTOR_NUM_V2_RECOVERY_FOLDER_NAME
  );
}

function vektorNumV2CreateRecoverySnapshot_(
  key,
  text
) {

  /*
   * Antes de criar o snapshot,
   * confirma que o conteúdo atual
   * realmente é válido.
   */
  vektorNumV2ValidateJsonText_(
    key,
    text
  );


  var folder =
    vektorNumV2RecoveryFolder_();


  var stamp =
    Utilities.formatDate(
      new Date(),
      Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
      "yyyyMMdd_HHmmss_SSS"
    );


  var name =
    "RECOVERY_" +
    key +
    "_" +
    stamp +
    "_" +
    Utilities
      .getUuid()
      .slice(
        0,
        8
      ) +
    ".json";


  var snapshot =
    folder.createFile(
      name,
      text,
      MimeType.PLAIN_TEXT
    );


  /*
   * Relê o snapshot recém-criado
   * e valida novamente.
   */
  var check =
    snapshot
      .getBlob()
      .getDataAsString(
        "UTF-8"
      );


  vektorNumV2ValidateJsonText_(
    key,
    check
  );


  /*
   * O snapshot precisa ser exatamente
   * igual ao conteúdo original.
   */
  if (
    check !==
    text
  ) {

    snapshot.setTrashed(
      true
    );


    throw new Error(
      "Não foi possível confirmar o snapshot de segurança de " +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "."
    );
  }


  return snapshot;
}

function vektorNumV2LatestRecovery_(
  key
) {

  var folder =
    vektorNumV2RecoveryFolder_();


  var prefix =
    "RECOVERY_" +
    key +
    "_";


  var files =
    folder.getFiles();


  var candidates =
    [];


  while (
    files.hasNext()
  ) {

    var file =
      files.next();


    if (
      String(
        file.getName() ||
        ""
      ).indexOf(
        prefix
      ) === 0
    ) {

      candidates.push(
        file
      );
    }
  }


  /*
   * Mais recente primeiro.
   */
  candidates.sort(
    function(a, b) {

      return (
        b.getDateCreated().getTime() -
        a.getDateCreated().getTime()
      );
    }
  );


  /*
   * Procura o primeiro snapshot
   * que realmente seja válido.
   */
  for (
    var i = 0;
    i < candidates.length;
    i++
  ) {

    try {

      var text =
        candidates[i]
          .getBlob()
          .getDataAsString(
            "UTF-8"
          );


      var obj =
        vektorNumV2ValidateJsonText_(
          key,
          text
        );


      return {

        file:
          candidates[i],

        text:
          text,

        obj:
          obj

      };

    } catch (_) {

      /*
       * Snapshot inválido:
       * ignora e tenta o anterior.
       */
    }
  }


  return null;
}

function vektorNumV2RestoreLatestRecovery_(
  key
) {

  /*
   * IMPORTANTE:
   * esta função será chamada somente
   * enquanto o ScriptLock estiver ativo.
   */

  var recovery =
    vektorNumV2LatestRecovery_(
      key
    );


  if (
    !recovery
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: não existe snapshot válido de recuperação para '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "'."
    );
  }


  /*
   * Valida mais uma vez o snapshot
   * antes de tocar no arquivo oficial.
   */
  vektorNumV2ValidateJsonText_(
    key,
    recovery.text
  );


  var file =
    vektorNumV2EnsureFile_(
      key
    );


  /*
   * Restaura o conteúdo do último
   * snapshot válido.
   */
  file.setContent(
    recovery.text
  );


  /*
   * Confirma no próprio Drive que
   * a restauração realmente aconteceu.
   */
  var confirmedText =
    "";


  for (
    var attempt = 0;
    attempt < 3;
    attempt++
  ) {

    if (
      attempt > 0
    ) {

      Utilities.sleep(
        250
      );
    }


    confirmedText =
      file
        .getBlob()
        .getDataAsString(
          "UTF-8"
        );


    if (
      confirmedText ===
      recovery.text
    ) {

      break;
    }
  }


  /*
   * Não basta existir conteúdo.
   * Precisa continuar sendo JSON válido.
   */
  vektorNumV2ValidateJsonText_(
    key,
    confirmedText
  );


  if (
    confirmedText !==
    recovery.text
  ) {

    throw new Error(
      "ERRO CRÍTICO NUMERÁRIO: o Drive não confirmou corretamente a restauração de '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "'."
    );
  }


  return {

    ok:
      true,

    key:
      key,

    snapshot:
      recovery.file.getName(),

    obj:
      recovery.obj

  };
}

function vektorNumV2PruneRecovery_(
  key
) {

  var folder =
    vektorNumV2RecoveryFolder_();


  var prefix =
    "RECOVERY_" +
    key +
    "_";


  var files =
    folder.getFiles();


  var candidates =
    [];


  while (
    files.hasNext()
  ) {

    var file =
      files.next();


    if (
      String(
        file.getName() ||
        ""
      ).indexOf(
        prefix
      ) === 0
    ) {

      candidates.push(
        file
      );
    }
  }


  /*
   * Mais recentes primeiro.
   */
  candidates.sort(
    function(a, b) {

      return (
        b.getDateCreated().getTime() -
        a.getDateCreated().getTime()
      );
    }
  );


  /*
   * Mantém somente os 20 snapshots
   * mais recentes de cada arquivo.
   */
  for (
    var i =
      VEKTOR_NUM_V2_RECOVERY_KEEP;

    i <
      candidates.length;

    i++
  ) {

    try {

      candidates[i]
        .setTrashed(
          true
        );

    } catch (_) {

      /*
       * Se não conseguir limpar um snapshot
       * antigo, não interrompe o Numerário.
       */
    }
  }
}

function vektorNumerarioSeedRecoveryV2() {

  var lock =
    LockService
      .getScriptLock();

  lock.waitLock(
    30000
  );


  try {

    var keys = [
      "CENTAURO",
      "FISIA"
    ];


    var created =
      [];


    keys.forEach(
      function(key) {

        var file =
          vektorNumV2EnsureFile_(
            key
          );


        var text =
          file
            .getBlob()
            .getDataAsString(
              "UTF-8"
            );


        /*
         * Só cria o snapshot se o arquivo
         * oficial estiver realmente válido.
         */
        vektorNumV2ValidateJsonText_(
          key,
          text
        );


        var snapshot =
          vektorNumV2CreateRecoverySnapshot_(
            key,
            text
          );


        created.push({
          key:
            key,

          snapshot:
            snapshot.getName()
        });

      }
    );


    return {

      ok:
        true,

      created:
        created
    };


  } finally {

    lock.releaseLock();

  }
}

function vektorNumV2ReadJson_(
  key
) {

  var file =
    vektorNumV2EnsureFile_(
      key
    );


  var lastError =
    null;

  for (
    var attempt = 0;
    attempt < 3;
    attempt++
  ) {

    if (
      attempt > 0
    ) {

      Utilities.sleep(
        250
      );
    }


    try {

      var text =
        file
          .getBlob()
          .getDataAsString(
            "UTF-8"
          );

      return vektorNumV2ValidateJsonText_(
        key,
        text
      );


    } catch (error) {

      lastError =
        error;

    }
  }

  throw new Error(
    "ERRO CRÍTICO NUMERÁRIO: não foi possível ler '" +
    VEKTOR_NUM_V2_FILE_NAMES[key] +
    "' corretamente após 3 tentativas. " +
    "Nenhuma alteração foi realizada. Detalhe: " +
    (
      lastError &&
      lastError.message
        ? lastError.message
        : String(
            lastError || ""
          )
    )
  );
}

function vektorNumV2WriteJson_(
  key,
  obj
) {

  var file =
    vektorNumV2EnsureFile_(
      key
    );


  /*
   * =====================================================
   * 1. PREPARA E VALIDA O NOVO CONTEÚDO
   * =====================================================
   */

  var newText =
    JSON.stringify(
      obj,
      null,
      2
    );


  /*
   * Jamais permite gravar vazio,
   * JSON quebrado ou estrutura inválida.
   */
  vektorNumV2ValidateJsonText_(
    key,
    newText
  );


  /*
   * =====================================================
   * 2. LÊ E VALIDA O ARQUIVO ATUAL
   * =====================================================
   */

  var previousText =
    file
      .getBlob()
      .getDataAsString(
        "UTF-8"
      );


  /*
   * Se o arquivo atual já estiver corrompido,
   * NÃO sobrescreve nada.
   */
  vektorNumV2ValidateJsonText_(
    key,
    previousText
  );


  /*
   * =====================================================
   * 3. CRIA SNAPSHOT ANTES DE ALTERAR O OFICIAL
   * =====================================================
   */

  var snapshot =
    vektorNumV2CreateRecoverySnapshot_(
      key,
      previousText
    );


  /*
   * =====================================================
   * 4. TENTA GRAVAR O NOVO CONTEÚDO
   * =====================================================
   */

  try {

    file.setContent(
      newText
    );


    /*
     * =====================================================
     * 5. RELÊ O ARQUIVO APÓS A GRAVAÇÃO
     * =====================================================
     *
     * Faz algumas tentativas para evitar considerar
     * uma pequena demora do Drive como falha.
     */

    var confirmedText =
      "";


    for (
      var attempt = 0;
      attempt < 3;
      attempt++
    ) {

      if (
        attempt > 0
      ) {

        Utilities.sleep(
          250
        );
      }


      confirmedText =
        file
          .getBlob()
          .getDataAsString(
            "UTF-8"
          );


      if (
        confirmedText ===
        newText
      ) {

        break;
      }
    }


    /*
     * Confirma que continua sendo JSON válido.
     */
    vektorNumV2ValidateJsonText_(
      key,
      confirmedText
    );


    /*
     * O conteúdo precisa ser exatamente
     * o mesmo que tentamos gravar.
     */
    if (
      confirmedText !==
      newText
    ) {

      throw new Error(
        "O conteúdo gravado no Drive não corresponde ao conteúdo esperado."
      );
    }


    /*
     * Gravação confirmada.
     * Agora pode limpar snapshots antigos.
     */
    vektorNumV2PruneRecovery_(
      key
    );


    return true;

  } catch (error) {

    /*
     * =====================================================
     * 6. ROLLBACK AUTOMÁTICO
     * =====================================================
     *
     * Qualquer problema na gravação faz o sistema
     * tentar devolver imediatamente o conteúdo anterior.
     */

    try {

      file.setContent(
        previousText
      );


      var rollbackText =
        file
          .getBlob()
          .getDataAsString(
            "UTF-8"
          );


      vektorNumV2ValidateJsonText_(
        key,
        rollbackText
      );


      if (
        rollbackText !==
        previousText
      ) {

        throw new Error(
          "O conteúdo restaurado não corresponde ao original."
        );
      }

    } catch (rollbackError) {

      throw new Error(
        "ERRO CRÍTICO NUMERÁRIO: falha ao gravar '" +
        VEKTOR_NUM_V2_FILE_NAMES[key] +
        "' e também falha ao restaurar o conteúdo anterior. " +
        "Snapshot preservado: " +
        snapshot.getName() +
        ". Erro original: " +
        (
          error &&
          error.message
            ? error.message
            : String(error)
        ) +
        ". Erro no rollback: " +
        (
          rollbackError &&
          rollbackError.message
            ? rollbackError.message
            : String(rollbackError)
        )
      );
    }


    throw new Error(
      "Gravação cancelada por segurança em '" +
      VEKTOR_NUM_V2_FILE_NAMES[key] +
      "'. O conteúdo anterior foi restaurado automaticamente. " +
      "Snapshot: " +
      snapshot.getName() +
      ". Motivo: " +
      (
        error &&
        error.message
          ? error.message
          : String(error)
      )
    );
  }
}


/* =====================================================
   LINHAS
   ===================================================== */

function vektorNumV2NewRow_(
  empresa
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var obj = {};


  VEKTOR_NUM_V2_HEADERS[
    empresa
  ].forEach(function(header) {

    obj[header] =
      "";

  });


  obj.__id =
    Utilities.getUuid();


  obj.__createdAt =
    vektorNumV2Now_();


  obj.__updatedAt =
    obj.__createdAt;


  obj.__sent =
    false;


  return obj;
}


function vektorNumV2IsBlankRow_(
  empresa,
  row
) {
  empresa = vektorNumV2NormEmpresa_(empresa);
  row = row || {};

  var fields = empresa === "FISIA"
    ? [
        "DATA COBRANÇA",
        "LOJA",
        "DATA DEPÓSITO",
        "Mov. Inicial",
        "Mov. Final",
        "VALOR PREVISTO",
        "VALOR DEPOSITADO",
        "OBSERVAÇÃO",
        "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)"
      ]
    : [
        "DATA COBRANÇA",
        "LOJA",
        "DATA DEPÓSITO",
        "Mov. Inicial",
        "Mov. Final",
        "VALOR PREVISTO",
        "VALOR DEPOSITADO",
        "INFORMAÇÕES",
        "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)"
      ];

  return fields.every(function(field) {
    return String(row[field] == null ? "" : row[field]).trim() === "";
  });
}

function vektorNumV2EnsureDraft_(
  empresa,
  data
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  data =
    data || {};


  data.header =
    VEKTOR_NUM_V2_HEADERS[
      empresa
    ].slice();


  data.rows =
    Array.isArray(
      data.rows
    )
      ? data.rows
      : [];


  var filled = [];

  var batchDrafts = [];

  var normalDraft =
    null;


  data.rows.forEach(
    function(row) {

      var isBlank =
        vektorNumV2IsBlankRow_(
          empresa,
          row
        );


      /*
       * Linha preenchida:
       * comportamento normal.
       */
      if (!isBlank) {

        /*
         * Se ela nasceu do lote e já recebeu
         * dados, deixa de ser um batch draft.
         */
        if (
          row.__batchDraft ===
          true
        ) {

          delete row.__batchDraft;
        }


        filled.push(
          row
        );

        return;
      }


      /*
       * Linhas vazias criadas pelo botão
       * "Inserir em lote" são preservadas.
       */
      if (
        row.__batchDraft ===
        true
      ) {

        batchDrafts.push(
          row
        );

        return;
      }


      /*
       * Fora do lote continua existindo
       * somente um rascunho automático.
       */
      if (!normalDraft) {

        normalDraft =
          row;
      }
    }
  );


  if (!normalDraft) {

    normalDraft =
      vektorNumV2NewRow_(
        empresa
      );
  }


  data.rows =
    filled
      .concat(
        batchDrafts
      )
      .concat([
        normalDraft
      ]);


  return data;
}

/* =====================================================
   BASE DE LOJAS COMPARTILHADA COM POS
   ===================================================== */

function vektorNumV2GetPosStores_() {

  if (
    typeof vektorPosReadData_ !==
    "function"
  ) {

    throw new Error(
      "A função vektorPosReadData_ não foi encontrada. O Numerário depende da Base de Lojas do POS."
    );
  }


  var data =
    vektorPosReadData_(
      "LOJAS"
    );


  return Array.isArray(
    data.rows
  )
    ? data.rows
    : [];
}


function vektorNumV2GetStores_(
  empresa
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var empresaPos =
    vektorNumV2EmpresaPos_(
      empresa
    );


  return vektorNumV2GetPosStores_()
    .filter(
      function(row) {

        var rowEmpresa =
          String(
            row.EMPRESA || ""
          )
            .trim()
            .toUpperCase();


        if (
          rowEmpresa !==
          empresaPos
        ) {

          return false;
        }


        var ativo =
          String(
            row.ATIVO || "SIM"
          )
            .trim()
            .toUpperCase();


        return !(
          ativo === "NÃO" ||
          ativo === "NAO" ||
          ativo === "N" ||
          ativo === "FALSE"
        );
      }
    )
    .map(
      function(row) {

        return {

          LOJA:
            vektorNumV2Store4_(
              row.LOJA
            ),

          EMAILS:
            String(
              row.EMAILS || ""
            ),

          NOMINAL:
            String(
              row.NOMINAL || ""
            ),

          RENAME:
            String(
              row.RENAME || ""
            ),

          TIPO:
            String(
              row.TIPO || ""
            ),

          COD_LOJA_NOVA:
            String(
              row.COD_LOJA_NOVA || ""
            ),

          BU:
            String(
              row.BU || ""
            ),

          SHOPPING:
            String(
              row.SHOPPING || ""
            ),

          NOME_LOJA:
            String(
              row.NOME_LOJA || ""
            ),

          TIME:
            String(
              row.TIME || ""
            ),

          EMAIL_REGIONAL:
            String(
              row.EMAIL_REGIONAL || ""
            ),

          EMAIL_GERENTE_GRUPO:
            String(
              row.EMAIL_GERENTE_GRUPO || ""
            ),

          EMAIL_SUP_AUTO:
            String(
              row.EMAIL_SUP_AUTO || ""
            ),

          EMAIL_SUP_VENDAS:
            String(
              row.EMAIL_SUP_VENDAS || ""
            ),

          ATIVO:
            String(
              row.ATIVO || "SIM"
            )
        };

      }
    )
    .sort(
      function(a, b) {

        return Number(
          a.LOJA
        ) -
        Number(
          b.LOJA
        );
      }
    );
}


function vektorNumV2StoreMap_() {

  var map = {};


  ["CENTAURO", "FISIA"]
    .forEach(
      function(empresa) {

        vektorNumV2GetStores_(
          empresa
        )
          .forEach(
            function(store) {

              map[
                empresa +
                "|" +
                store.LOJA
              ] =
                store;

            }
          );

      }
    );


  return map;
}


/* =====================================================
   ASSUNTO
   ===================================================== */

function vektorNumV2BuildSubject_(
  empresa,
  row,
  store
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  row =
    row || {};


  store =
    store || {};


  var loja4 =
    vektorNumV2Store4_(
      row.LOJA
    );


  if (!loja4) {
    return "";
  }


  var loja =
    String(
      Number(
        loja4
      )
    );


  var dateCode =
    vektorNumV2DateCode_(
      row["DATA COBRANÇA"]
    );


  if (
    empresa === "FISIA"
  ) {

    var rename =
      String(
        store.RENAME ||
        ""
      ).trim();


    if (!rename) {

      rename =
        "NV" +
        loja4;
    }


    return (
      "FS" +
      loja +
      dateCode +
      " - CONTROLE NUMERÁRIO FÍSIA " +
      rename
    );
  }


  return (
    "#" +
    loja +
    dateCode +
    " - DIVERGÊNCIA DE VALORES CE" +
    loja4
  );
}


/* =====================================================
   CAMPOS DERIVADOS
   ===================================================== */

function vektorNumV2ApplyDerived_(
  empresa,
  row,
  storeMap,
  previousStatus
) {
  empresa = vektorNumV2NormEmpresa_(empresa);
  row = vektorNumV2MigrateRow_(empresa, row || {});
  storeMap = storeMap || {};

  var statusHeader = empresa === "FISIA" ? "STATUS" : "Status";
  var status = String(row[statusHeader] || "").trim().toUpperCase();

  var loja4 = vektorNumV2Store4_(row.LOJA);
  if (loja4) {
    row.LOJA = loja4;
  }

  /*
   * Mantém o comportamento atual do Status operacional:
   * uma linha preenchida começa como PENDENTE quando ainda não tem status.
   */
  if (!vektorNumV2IsBlankRow_(empresa, row) && !status) {
    status = "PENDENTE";
    row[statusHeader] = status;
  }

  /*
   * DATA COBRANÇA agora é automática e bloqueada na interface.
   * Ela nasce com a data atual assim que Loja + Valor Previsto +
   * Valor Depositado estiverem preenchidos.
   */
  var requiredComplete = vektorNumV2RequiredInputsComplete_(row);

  if (row.__sent !== true) {
    if (requiredComplete && !String(row["DATA COBRANÇA"] || "").trim()) {
      row["DATA COBRANÇA"] = vektorNumV2TodayBr_();
    } else if (!requiredComplete) {
      row["DATA COBRANÇA"] = "";
    }
  }

  if (row["DATA COBRANÇA"]) {
    row["DATA COBRANÇA"] =
      vektorNumV2DateBr_(row["DATA COBRANÇA"]) || row["DATA COBRANÇA"];
  }

  if (row["DATA DEPÓSITO"]) {
    row["DATA DEPÓSITO"] =
      vektorNumV2DateBr_(row["DATA DEPÓSITO"]) || row["DATA DEPÓSITO"];
  }

  if (
  row["Mov. Inicial"]
) {

  row["Mov. Inicial"] =
    vektorNumV2DateBr_(
      row["Mov. Inicial"]
    ) ||
    row["Mov. Inicial"];
}


if (
  row["Mov. Final"]
) {

  row["Mov. Final"] =
    vektorNumV2DateBr_(
      row["Mov. Final"]
    ) ||
    row["Mov. Final"];
}

  var previsto = vektorNumV2ParseMoney_(row["VALOR PREVISTO"]);
  var depositado = vektorNumV2ParseMoney_(row["VALOR DEPOSITADO"]);

  if (
    String(row["VALOR PREVISTO"] || "").trim() ||
    String(row["VALOR DEPOSITADO"] || "").trim()
  ) {
    row.DIFERENÇA = (previsto - depositado).toFixed(2);
  } else {
    row.DIFERENÇA = "";
  }

  var store = loja4
    ? storeMap[empresa + "|" + loja4]
    : null;

  if (empresa === "CENTAURO") {
    row["E-mail Gerente Grupo"] = store ? String(store.EMAIL_GERENTE_GRUPO || "") : "";
    row["E-mail Sup Auto"] = store ? String(store.EMAIL_SUP_AUTO || "") : "";
    row["E-mail Sup Vendas"] = store ? String(store.EMAIL_SUP_VENDAS || "") : "";
    row["E-mail Regional"] = store ? String(store.EMAIL_REGIONAL || "") : "";
    row["Enviar Para"] = store ? vektorNumV2NormalizeEmails_(store.EMAILS) : "";
    row.Time = store ? String(store.TIME || "") : "";
  } else {
    row["E-mail Loja"] = store ? vektorNumV2NormalizeEmails_(store.EMAILS) : "";
    row.TIPO = store ? String(store.TIPO || "") : "";
  }

  var subject = vektorNumV2BuildSubject_(empresa, row, store);

  if (empresa === "FISIA") {
    row["CÓDIGO ÚNICO_ASSUNTO"] = subject;
  } else {
    row["CÓDIGO ENVIO EMAIL_ASSUNTO"] = subject;
  }

  row["MÊS PENDÊNCIA"] = vektorNumV2MonthText_(row["DATA COBRANÇA"]);

  previousStatus = String(previousStatus || "").trim().toUpperCase();

  var closed = status === "OK" || status === "PERDA";
  var previouslyClosed = previousStatus === "OK" || previousStatus === "PERDA";

  if (closed && !row["DATA FINAL (TRATATIVA)"]) {
    row["DATA FINAL (TRATATIVA)"] = vektorNumV2TodayBr_();
  }

  if (!closed && previouslyClosed) {
    row["DATA FINAL (TRATATIVA)"] = "";
  }

  row["QTD DIAS TRATATIVA"] = vektorNumV2BusinessDays_(
    row["DATA COBRANÇA"],
    row["DATA FINAL (TRATATIVA)"]
  );

  if (row.__sent === true) {
    row["STATUS ENVIO"] = "ENVIADO";
  } else if (String(row.__emailStatus || "").toUpperCase() === "ERRO") {
    row["STATUS ENVIO"] = "ERRO";
  } else {
    row["STATUS ENVIO"] = "";
  }

  return row;
}


/* =====================================================
   CONFIG
   ===================================================== */

function vektorNumV2GetConfig_() {

  var obj =
    vektorNumV2ReadJson_(
      "CONFIG"
    );


  var saved =
    obj &&
    obj.config
      ? obj.config
      : {};


  var out = {};


  Object.keys(
    VEKTOR_NUM_V2_DEFAULT_CONFIG
  )
    .forEach(
      function(key) {

        out[key] =
          saved[key] !== undefined &&
          saved[key] !== ""
            ? saved[key]
            : VEKTOR_NUM_V2_DEFAULT_CONFIG[
                key
              ];

      }
    );


  out.maxSendPerRun =
    Math.max(
      1,
      Math.min(
        Number(
          out.maxSendPerRun ||
          100
        ),
        100
      )
    );


  return out;
}


/* =====================================================
   DADOS OPERACIONAIS
   ===================================================== */

function vektorNumV2ReadCompany_(
  empresa,
  lockJaAdquirido
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var lock =
    null;


  if (
    lockJaAdquirido !== true
  ) {

    lock =
      LockService
        .getScriptLock();


    lock.waitLock(
      30000
    );
  }


  try {

    var data;


    /*
     * =====================================================
     * LEITURA PROTEGIDA + RECUPERAÇÃO AUTOMÁTICA
     * =====================================================
     *
     * A leitura normal já faz 3 tentativas.
     *
     * Se as 3 falharem, tentamos restaurar
     * o último snapshot válido do _RECOVERY.
     */
    try {

      data =
        vektorNumV2ReadJson_(
          empresa
        );

    } catch (readError) {

      var recovery =
        vektorNumV2RestoreLatestRecovery_(
          empresa
        );


      /*
       * Depois da restauração,
       * lê novamente o arquivo oficial.
       */
      data =
        vektorNumV2ReadJson_(
          empresa
        );


      /*
       * Registra no log do Apps Script
       * que houve recuperação automática.
       */
      console.warn(
        "NUMERÁRIO RECUPERADO AUTOMATICAMENTE: " +
        empresa +
        " | Snapshot: " +
        recovery.snapshot +
        " | Erro original: " +
        (
          readError &&
          readError.message
            ? readError.message
            : String(
                readError
              )
        )
      );
    }


    /*
     * Guarda o estado original para não
     * fazer gravações desnecessárias.
     */
    var before =
      JSON.stringify(
        data
      );


    data.version =
      VEKTOR_NUM_V2_SCHEMA_VERSION;


    data.header =
      VEKTOR_NUM_V2_HEADERS[
        empresa
      ].slice();


    data.rows =
      Array.isArray(
        data.rows
      )
        ? data.rows
        : [];


    var storeMap =
      vektorNumV2StoreMap_();


    data.rows.forEach(
      function(row) {

        vektorNumV2ApplyDerived_(
          empresa,
          row,
          storeMap,
          row[
            empresa === "FISIA"
              ? "STATUS"
              : "Status"
          ]
        );

      }
    );


    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    /*
     * Só grava se as normalizações
     * realmente alteraram alguma coisa.
     */
    var after =
      JSON.stringify(
        data
      );


    if (
      before !==
      after
    ) {

      vektorNumV2WriteJson_(
        empresa,
        data
      );
    }


    return data;


  } finally {

    if (
      lock
    ) {

      lock.releaseLock();

    }
  }
}


/* =====================================================
   SETUP
   ===================================================== */

function vektorNumerarioV2Setup() {

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  vektorNumV2EnsureFile_(
    "CENTAURO"
  );

  vektorNumV2EnsureFile_(
    "FISIA"
  );

  vektorNumV2EnsureFile_(
    "CONFIG"
  );

  vektorNumV2EnsureFile_(
    "DISPAROS"
  );


  vektorNumV2ReadCompany_(
    "CENTAURO"
  );

  vektorNumV2ReadCompany_(
    "FISIA"
  );


  return {

    ok: true,

    folderId:
      vektorNumV2GetStorageFolder_()
        .getId(),

    message:
      "Storage Numerário V2 validado com sucesso."
  };
}


/* =====================================================
   BOOTSTRAP COMPLETO
   ===================================================== */

function vektorNumerarioGetBootstrapDataV2() {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioGetBootstrapDataV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  /*
   * Garante storage antes de devolver qualquer coisa.
   */
  vektorNumV2EnsureFile_(
    "CENTAURO"
  );

  vektorNumV2EnsureFile_(
    "FISIA"
  );

  vektorNumV2EnsureFile_(
    "CONFIG"
  );

  vektorNumV2EnsureFile_(
    "DISPAROS"
  );


  var ctx =
    vektorGetUserRole_();


  /*
   * IMPORTANTE:
   * tudo é carregado antes da página
   * avisar ao Vektor que ficou pronta.
   */
  var storesCentauro =
    vektorNumV2GetStores_(
      "CENTAURO"
    );


  var storesFisia =
    vektorNumV2GetStores_(
      "FISIA"
    );


  var dataCentauro =
    vektorNumV2ReadCompany_(
      "CENTAURO"
    );


  var dataFisia =
    vektorNumV2ReadCompany_(
      "FISIA"
    );


  var config =
    vektorNumV2GetConfig_();


  var reportsCentauro =
    vektorNumV2BuildReports_(
      "CENTAURO"
    );


  var reportsFisia =
    vektorNumV2BuildReports_(
      "FISIA"
    );


  var backupStatus =
    vektorNumV2BackupGetStatus_();


  return {

    ok: true,

    user: {

      email:
        String(
          ctx.email || ""
        )
          .trim()
          .toLowerCase(),

      role:
        String(
          ctx.role || ""
        ),

      isAdmin:
        String(
          ctx.role || ""
        )
          .trim()
          .toLowerCase() ===
        "administrador"
    },


    headers:
      VEKTOR_NUM_V2_HEADERS,


    statusOptions:
      VEKTOR_NUM_V2_STATUS_OPTIONS,


    stores: {

      CENTAURO:
        storesCentauro,

      FISIA:
        storesFisia
    },


    rows: {

      CENTAURO:
        dataCentauro.rows,

      FISIA:
        dataFisia.rows
    },


    config:
      config,


    backupStatus:
      backupStatus,


    reports: {

      CENTAURO:
        reportsCentauro,

      FISIA:
        reportsFisia
    }

  };
}


/* =====================================================
   GET ROWS
   ===================================================== */

function vektorNumerarioGetRowsV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioGetRowsV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  var data =
    vektorNumV2ReadCompany_(
      empresa
    );


  return {

    ok: true,

    empresa:
      empresa,

    header:
      data.header,

    rows:
      data.rows

  };
}


/* =====================================================
   SAVE ROWS
   ===================================================== */

function vektorNumerarioSaveRowsV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioSaveRowsV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  var incoming =
    Array.isArray(
      req.rows
    )
      ? req.rows
      : [];


  if (!incoming.length) {

    return vektorNumerarioGetRowsV2({
      empresa:
        empresa
    });
  }


  var ctx =
    vektorGetUserRole_();


  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    var byId = {};


    data.rows.forEach(
      function(row, index) {

        byId[
          String(
            row.__id || ""
          )
        ] =
          index;

      }
    );


    var storeMap =
      vektorNumV2StoreMap_();


    var statusHeader =
      empresa === "FISIA"
        ? "STATUS"
        : "Status";


    incoming.forEach(
      function(input) {

        var id =
          String(
            input.__id || ""
          ).trim();


        if (
          !id ||
          byId[id] === undefined
        ) {

          return;
        }


        var target =
          data.rows[
            byId[id]
          ];


        /*
         * Linha já enviada:
         * somente Status pode ser alterado.
         */
        var sent =
          target.__sent === true;


        var previousStatus =
          String(
            target[
              statusHeader
            ] || ""
          );


        VEKTOR_NUM_V2_HEADERS[
          empresa
        ]
          .forEach(
            function(header) {

              if (
                !VEKTOR_NUM_V2_MANUAL_COLUMNS[
                  empresa
                ][header]
              ) {

                return;
              }


              if (
                sent &&
                header !==
                statusHeader
              ) {

                return;
              }


              if (
                input[header] !==
                undefined
              ) {

                target[header] =
                  input[header] == null
                    ? ""
                    : String(
                        input[header]
                      );
              }
            }
          );


        vektorNumV2ApplyDerived_(
          empresa,
          target,
          storeMap,
          previousStatus
        );


        if (
          !vektorNumV2IsBlankRow_(
            empresa,
            target
          )
        ) {

          delete target.__batchDraft;
          delete target.__batchCreatedAt;
        }


        target.__updatedAt =
          vektorNumV2Now_();


        target.__updatedBy =
          String(
            ctx.email || ""
          )
            .trim()
            .toLowerCase();
      }
    );


    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    return {

      ok: true,

      empresa:
        empresa,

      header:
        data.header,

      rows:
        data.rows,

      reports:
        vektorNumV2BuildReports_(
          empresa
        )
    };


  } finally {

    lock.releaseLock();

  }
}


/* =====================================================
   ADD ROW
   ===================================================== */

function vektorNumerarioAddRowV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioAddRowV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  /*
   * Protege toda a operação contra
   * duas gravações simultâneas.
   */
  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    /*
     * O true informa que esta função
     * já possui o ScriptLock.
     */
    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    /*
     * Se já existe rascunho,
     * ele é reutilizado.
     */
    var draft =
      null;


    data.rows.forEach(
      function(row) {

        if (
          !draft &&
          vektorNumV2IsBlankRow_(
            empresa,
            row
          )
        ) {

          draft =
            row;
        }
      }
    );


    if (!draft) {

      draft =
        vektorNumV2NewRow_(
          empresa
        );


      data.rows.push(
        draft
      );
    }


    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    return {

      ok: true,

      empresa:
        empresa,

      rows:
        data.rows,

      draftId:
        draft.__id
    };


  } finally {

    /*
     * Libera o lock mesmo se ocorrer erro.
     */
    lock.releaseLock();

  }
}

/* =====================================================
   ADD ROWS BATCH
   ===================================================== */

function vektorNumerarioAddRowsBatchV2(
  req
) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioAddRowsBatchV2"
  );


  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  var quantidade =
    Math.floor(
      Number(
        req.quantidade ||
        0
      )
    );


  if (
    !isFinite(
      quantidade
    ) ||
    quantidade < 1
  ) {

    throw new Error(
      "Informe uma quantidade válida de linhas."
    );
  }


  if (
    quantidade > 50
  ) {

    throw new Error(
      "É permitido inserir no máximo 50 linhas por vez."
    );
  }


  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    var createdIds = [];


    for (
      var i = 0;
      i < quantidade;
      i++
    ) {

      var row =
        vektorNumV2NewRow_(
          empresa
        );


      row.__batchDraft =
        true;


      row.__batchCreatedAt =
        vektorNumV2Now_();


      data.rows.push(
        row
      );


      createdIds.push(
        row.__id
      );
    }


    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    return {

      ok: true,

      empresa:
        empresa,

      quantidade:
        quantidade,

      createdIds:
        createdIds,

      rows:
        data.rows
    };


  } finally {

    lock.releaseLock();
  }
}

/* =====================================================
   DELETE
   ===================================================== */

function vektorNumerarioDeleteRowV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioDeleteRowV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  var ctx =
    vektorGetUserRole_();


  var userEmail =
    String(
      ctx.email || ""
    )
      .trim()
      .toLowerCase();


  var userRole =
    String(
      ctx.role || ""
    )
      .trim()
      .toLowerCase();


  /*
   * Rodrigo:
   * pode excluir qualquer linha,
   * inclusive linha já enviada.
   */
  var isDeleteAdmin =
    userEmail ===
    VEKTOR_NUM_V2_DELETE_ALLOWED_EMAIL;


  /*
   * Analista Pro:
   * pode excluir somente linhas
   * que ainda NÃO foram enviadas.
   */
  var isAnalistaPro =
    userRole ===
    "analista pro";


  if (
    !isDeleteAdmin &&
    !isAnalistaPro
  ) {

    throw new Error(
      "Você não possui permissão para excluir linhas do Numerário."
    );
  }


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  /*
   * Aceita:
   *
   * rowId  = exclusão individual
   * rowIds = exclusão múltipla
   */
  var rowIds =
    [];


  if (
    Array.isArray(
      req.rowIds
    )
  ) {

    rowIds =
      req.rowIds
        .map(
          function(id) {

            return String(
              id || ""
            ).trim();

          }
        )
        .filter(
          function(id) {

            return !!id;

          }
        );

  } else {

    var singleRowId =
      String(
        req.rowId || ""
      ).trim();


    if (
      singleRowId
    ) {

      rowIds.push(
        singleRowId
      );
    }
  }


  /*
   * Remove IDs duplicados.
   */
  var uniqueIds =
    [];


  var seenIds =
    {};


  rowIds.forEach(
    function(id) {

      if (
        !seenIds[id]
      ) {

        seenIds[id] =
          true;

        uniqueIds.push(
          id
        );
      }
    }
  );


  rowIds =
    uniqueIds;


  if (
    !rowIds.length
  ) {

    throw new Error(
      "Nenhuma linha foi informada para exclusão."
    );
  }


  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    /*
     * O true indica que o ScriptLock
     * já está adquirido nesta função.
     */
    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    var rowsById =
      {};


    data.rows.forEach(
      function(row) {

        var id =
          String(
            row.__id || ""
          );


        if (
          id
        ) {

          rowsById[id] =
            row;
        }
      }
    );


    /*
     * Antes de excluir qualquer coisa,
     * confirma que todas as linhas existem.
     *
     * Assim a operação é atômica:
     * ou exclui todas ou nenhuma.
     */
    var missingIds =
      rowIds.filter(
        function(id) {

          return !rowsById[id];

        }
      );


    if (
      missingIds.length
    ) {

      throw new Error(
        missingIds.length === 1
          ? "Linha não encontrada."
          : "Uma ou mais linhas selecionadas não foram encontradas."
      );
    }


    /*
     * Para Analista Pro,
     * nenhuma das linhas selecionadas
     * pode ter sido enviada.
     *
     * A validação é feita também no backend
     * para impedir contorno da regra pelo navegador.
     */
    if (
      !isDeleteAdmin
    ) {

      var sentRows =
        rowIds.filter(
          function(id) {

            var row =
              rowsById[id];


            var statusEnvio =
              String(
                row[
                  "STATUS ENVIO"
                ] || ""
              )
                .trim()
                .toUpperCase();


            return (
              row.__sent === true ||
              statusEnvio ===
                "ENVIADO"
            );

          }
        );


      if (
        sentRows.length
      ) {

        throw new Error(
          sentRows.length === 1
            ? "Esta linha já foi enviada e não pode ser excluída pelo perfil Analista Pro."
            : "Existem linhas já enviadas na seleção. O perfil Analista Pro não pode excluir linhas enviadas."
        );
      }
    }


    /*
     * Guarda as linhas antes da remoção
     * para auditoria.
     */
    var removedRows =
      rowIds.map(
        function(id) {

          return rowsById[id];

        }
      );


    var deleteSet =
      {};


    rowIds.forEach(
      function(id) {

        deleteSet[id] =
          true;

      }
    );


    data.rows =
      data.rows.filter(
        function(row) {

          return !deleteSet[
            String(
              row.__id || ""
            )
          ];

        }
      );


    /*
     * Mantém o rascunho vazio
     * utilizado pela tabela.
     */
    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    /*
     * Auditoria.
     */
    data.meta =
      data.meta || {};


    data.meta.lastDeletedAt =
      vektorNumV2Now_();


    data.meta.lastDeletedBy =
      userEmail;


    data.meta.lastDeletedRowId =
      rowIds.length === 1
        ? rowIds[0]
        : rowIds[
            rowIds.length - 1
          ];


    data.meta.lastDeletedRowIds =
      rowIds.slice();


    data.meta.lastDeletedCount =
      rowIds.length;


    data.meta.lastDeletedStore =
      String(
        removedRows[0] &&
        removedRows[0].LOJA ||
        ""
      );


    data.meta.lastDeletedEmailStatus =
      String(
        removedRows[0] &&
        removedRows[0][
          "STATUS ENVIO"
        ] ||
        ""
      );


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    return {

      ok:
        true,

      deleted:
        true,

      empresa:
        empresa,

      rowId:
        rowIds.length === 1
          ? rowIds[0]
          : "",

      rowIds:
        rowIds,

      quantidade:
        rowIds.length,

      loja:
        rowIds.length === 1
          ? String(
              removedRows[0] &&
              removedRows[0].LOJA ||
              ""
            )
          : "",

      statusEnvio:
        rowIds.length === 1
          ? String(
              removedRows[0] &&
              removedRows[0][
                "STATUS ENVIO"
              ] ||
              ""
            )
          : "",

      rows:
        data.rows,

      reports:
        vektorNumV2BuildReports_(
          empresa
        )
    };


  } finally {

    lock.releaseLock();

  }
}


/* =====================================================
   CONFIG SAVE
   ===================================================== */

function vektorNumerarioSaveConfigV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioSaveConfigV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  var ctx =
    vektorGetUserRole_();


  if (
    String(
      ctx.role || ""
    )
      .trim()
      .toLowerCase() !==
    "administrador"
  ) {

    throw new Error(
      "Apenas Administrador pode alterar as configurações."
    );
  }


  req =
    req || {};


  var input =
    req.config || {};


  var config =
    vektorNumV2GetConfig_();

  /*
 * =====================================================
 * BACKUP | PROTEÇÃO CONTRA DESATIVAÇÃO
 * =====================================================
 *
 * Depois que o backup for ativado uma vez,
 * não poderá mais ser desativado.
 */
var backupJaAtivado =
  config.backupEnabled === true;


if (
  backupJaAtivado &&
  input.backupEnabled !== undefined &&
  (
    input.backupEnabled === false ||
    String(
      input.backupEnabled
    ).toLowerCase() === "false"
  )
) {

  throw new Error(
    "O backup automático do Numerário já foi ativado e não pode ser desativado."
  );
}


  [
    "emailFrom",
    "emailName",
    "emailCc",
    "replyTo",
    "maxSendPerRun",
    "backupEnabled",
    "backupFrequency",
    "backupStartDate",
    "backupTime"
  ].forEach(
    function(key) {

      if (
        input[key] !==
        undefined
      ) {

        config[key] =
          input[key];
      }
    }
  );


  config.emailFrom =
    String(
      config.emailFrom ||
      VEKTOR_NUM_V2_EMAIL_FROM
    )
      .trim()
      .toLowerCase();


  config.emailName =
    String(
      config.emailName ||
      VEKTOR_NUM_V2_EMAIL_NAME
    ).trim();


  config.emailCc =
    vektorNumV2NormalizeEmails_(
      config.emailCc
    );


  config.replyTo =
    String(
      config.replyTo ||
      ""
    )
      .trim()
      .toLowerCase();


  config.maxSendPerRun =
    Math.max(
      1,
      Math.min(
        Number(
          config.maxSendPerRun ||
          100
        ),
        100
      )
    );


  config.backupEnabled =
    (
      config.backupEnabled === true ||
      String(
        config.backupEnabled
      ).toLowerCase() ===
      "true"
    );

  if (
  backupJaAtivado
  ) {

    config.backupEnabled =
      true;
  }


  config.backupFrequency =
    String(
      config.backupFrequency ||
      "DAILY"
    )
      .trim()
      .toUpperCase();


  if (
    [
      "DAILY",
      "WEEKLY",
      "MONTHLY"
    ].indexOf(
      config.backupFrequency
    ) < 0
  ) {

    config.backupFrequency =
      "DAILY";
  }


  config.backupStartDate =
    String(
      config.backupStartDate ||
      ""
    ).trim();


  config.backupTime =
    String(
      config.backupTime ||
      "23:00"
    ).trim();


  if (
    config.backupEnabled &&
    !/^\d{4}-\d{2}-\d{2}$/.test(
      config.backupStartDate
    )
  ) {

    throw new Error(
      "Informe uma data inicial válida para o backup."
    );
  }


  if (
    config.backupEnabled &&
    !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(
      config.backupTime
    )
  ) {

    throw new Error(
      "Informe um horário válido para o backup."
    );
  }


  vektorNumV2WriteJson_(
    "CONFIG",
    {

      version:
        VEKTOR_NUM_V2_SCHEMA_VERSION,

      config:
        config,

      updatedAt:
        vektorNumV2Now_(),

      updatedBy:
        String(
          ctx.email || ""
        )
          .trim()
          .toLowerCase()
    }
  );


  var backupStatus =
    vektorNumV2BackupScheduleNext_(
      config
    );


  return {

    ok: true,

    config:
      config,

    backupStatus:
      backupStatus
  };
}


/* =====================================================
   BACKUP NUMERÁRIO V2
   ===================================================== */

var VEKTOR_NUM_V2_BACKUP_FOLDER_NAME =
  "BACKUPS";

var VEKTOR_NUM_V2_BACKUP_STATUS_PROP =
  "VEKTOR_NUMERARIO_BACKUP_STATUS_V2";

var VEKTOR_NUM_V2_BACKUP_HANDLER =
  "vektorNumerarioBackupScheduledV2";


function vektorNumV2BackupStatusRead_() {

  var raw =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        VEKTOR_NUM_V2_BACKUP_STATUS_PROP
      );


  if (!raw) {

    return {
      status: "NEVER",
      lastSuccess: "",
      lastError: "",
      nextBackupAt: "",
      backupRootFolderUrl: ""
    };
  }


  try {

    var obj =
      JSON.parse(
        raw
      );


    return obj &&
      typeof obj ===
        "object"
      ? obj
      : {};


  } catch (_) {

    return {
      status: "ERROR",
      lastSuccess: "",
      lastError:
        "Status interno do backup inválido.",
      nextBackupAt: "",
      backupRootFolderUrl: ""
    };
  }
}


function vektorNumV2BackupStatusWrite_(
  patch
) {

  var current =
    vektorNumV2BackupStatusRead_();


  patch =
    patch || {};


  Object.keys(
    patch
  )
    .forEach(
      function(key) {

        current[key] =
          patch[key];

      }
    );


  PropertiesService
    .getScriptProperties()
    .setProperty(
      VEKTOR_NUM_V2_BACKUP_STATUS_PROP,
      JSON.stringify(
        current
      )
    );


  return current;
}


function vektorNumV2BackupRootFolder_() {

  var storage =
    vektorNumV2GetStorageFolder_();


  var folders =
    storage.getFoldersByName(
      VEKTOR_NUM_V2_BACKUP_FOLDER_NAME
    );


  var folder =
    folders.hasNext()
      ? folders.next()
      : storage.createFolder(
          VEKTOR_NUM_V2_BACKUP_FOLDER_NAME
        );


  return folder;
}


function vektorNumV2BackupRootUrl_(
  folder
) {

  folder =
    folder ||
    vektorNumV2BackupRootFolder_();


  return (
    "https://example.com/configure-recurso" +
    folder.getId()
  );
}


function vektorNumV2BackupSha256_(
  text
) {

  var bytes =
    Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      String(
        text == null
          ? ""
          : text
      ),
      Utilities.Charset.UTF_8
    );


  return bytes
    .map(
      function(value) {

        var b =
          value < 0
            ? value + 256
            : value;


        return (
          "0" +
          b.toString(16)
        ).slice(-2);
      }
    )
    .join("");
}


function vektorNumV2BackupDeleteTriggers_() {

  ScriptApp
    .getProjectTriggers()
    .forEach(
      function(trigger) {

        if (
          trigger.getHandlerFunction() ===
          VEKTOR_NUM_V2_BACKUP_HANDLER
        ) {

          ScriptApp.deleteTrigger(
            trigger
          );
        }
      }
    );
}


function vektorNumV2BackupAddMonths_(
  date,
  months
) {

  var year =
    date.getFullYear();

  var month =
    date.getMonth();

  var day =
    date.getDate();

  var hour =
    date.getHours();

  var minute =
    date.getMinutes();


  var base =
    new Date(
      year,
      month + months,
      1,
      hour,
      minute,
      0,
      0
    );


  var lastDay =
    new Date(
      base.getFullYear(),
      base.getMonth() + 1,
      0
    ).getDate();


  base.setDate(
    Math.min(
      day,
      lastDay
    )
  );


  return base;
}


function vektorNumV2BackupNextDate_(
  config
) {

  config =
    config ||
    vektorNumV2GetConfig_();


  if (
    config.backupEnabled !==
    true
  ) {

    return null;
  }


  var dateText =
    String(
      config.backupStartDate ||
      ""
    ).trim();


  var timeText =
    String(
      config.backupTime ||
      "23:00"
    ).trim();


  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(
      dateText
    )
  ) {

    throw new Error(
      "Data inicial do backup inválida."
    );
  }


  if (
    !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(
      timeText
    )
  ) {

    throw new Error(
      "Horário do backup inválido."
    );
  }


  var d =
    dateText.split("-");

  var t =
    timeText.split(":");


  var candidate =
    new Date(
      Number(d[0]),
      Number(d[1]) - 1,
      Number(d[2]),
      Number(t[0]),
      Number(t[1]),
      0,
      0
    );


  var now =
    new Date();


  var frequency =
    String(
      config.backupFrequency ||
      "DAILY"
    )
      .trim()
      .toUpperCase();


  var guard =
    0;


  while (
    candidate <= now &&
    guard < 5000
  ) {

    if (
      frequency ===
      "WEEKLY"
    ) {

      candidate.setDate(
        candidate.getDate() +
        7
      );


    } else if (
      frequency ===
      "MONTHLY"
    ) {

      candidate =
        vektorNumV2BackupAddMonths_(
          candidate,
          1
        );


    } else {

      candidate.setDate(
        candidate.getDate() +
        1
      );
    }


    guard++;
  }


  if (
    guard >= 5000
  ) {

    throw new Error(
      "Não foi possível calcular a próxima execução do backup."
    );
  }


  return candidate;
}


function vektorNumV2BackupScheduleNext_(
  config
) {

  config =
    config ||
    vektorNumV2GetConfig_();


  vektorNumV2BackupDeleteTriggers_();


  if (
    config.backupEnabled !==
    true
  ) {

    return vektorNumV2BackupStatusWrite_({
      nextBackupAt: ""
    });
  }


  var next =
    vektorNumV2BackupNextDate_(
      config
    );


  ScriptApp
    .newTrigger(
      VEKTOR_NUM_V2_BACKUP_HANDLER
    )
    .timeBased()
    .at(
      next
    )
    .create();


  return vektorNumV2BackupStatusWrite_({

    nextBackupAt:
      Utilities.formatDate(
        next,
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
        "yyyy-MM-dd HH:mm:ss"
      )

  });
}


function vektorNumV2BackupGetStatus_() {

  var status =
    vektorNumV2BackupStatusRead_();


  try {

    var root =
      vektorNumV2BackupRootFolder_();


    status.backupRootFolderUrl =
      vektorNumV2BackupRootUrl_(
        root
      );


  } catch (error) {

    status.backupRootFolderUrl =
      "";

    if (
      !status.lastError
    ) {

      status.lastError =
        error &&
        error.message
          ? error.message
          : String(error);
    }
  }


  status.ok =
    true;


  return status;
}


function vektorNumV2BackupExecute_() {

  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  var backupFolder =
    null;


  try {

    var root =
      vektorNumV2BackupRootFolder_();


    var now =
      new Date();


    var stamp =
      Utilities.formatDate(
        now,
        Session.getScriptTimeZone() ||
        "America/Sao_Paulo",
        "yyyyMMdd_HHmmss"
      );


    backupFolder =
      root.createFolder(
        "backup_" +
        stamp
      );


    vektorNumV2BackupStatusWrite_({

      status:
        "RUNNING",

      lastError:
        "",

      backupRootFolderUrl:
        vektorNumV2BackupRootUrl_(
          root
        )

    });


    var keys = [
      "CENTAURO",
      "FISIA",
      "CONFIG",
      "DISPAROS"
    ];


    var manifest = {

      createdAt:
        vektorNumV2Now_(),

      storageFolderId:
        VEKTOR_NUM_V2_STORAGE_FOLDER_ID,

      files:
        []

    };


    var confirmed =
      0;


    keys.forEach(
      function(key) {

        var source =
          vektorNumV2EnsureFile_(
            key
          );


        var name =
          VEKTOR_NUM_V2_FILE_NAMES[
            key
          ];


        var content =
          source
            .getBlob()
            .getDataAsString(
              "UTF-8"
            );

            /*
        * Antes de aceitar o arquivo como origem do backup,
        * confirma que ele contém um JSON realmente válido.
        *
        * Se estiver vazio ou corrompido,
        * o backup para imediatamente e NÃO cria uma
        * falsa cópia de segurança.
        */
        vektorNumV2ValidateJsonText_(
          key,
          content
        );


        var originalHash =
          vektorNumV2BackupSha256_(
            content
          );


        var copy =
          backupFolder.createFile(
            name,
            content,
            MimeType.PLAIN_TEXT
          );


        var copiedContent =
          copy
            .getBlob()
            .getDataAsString(
              "UTF-8"
            );


        var copiedHash =
          vektorNumV2BackupSha256_(
            copiedContent
          );


        if (
          originalHash !==
          copiedHash
        ) {

          throw new Error(
            "Falha de integridade no backup de " +
            name +
            "."
          );
        }


        confirmed++;


        manifest.files.push({

          key:
            key,

          name:
            name,

          sourceFileId:
            source.getId(),

          backupFileId:
            copy.getId(),

          sha256:
            originalHash

        });
      }
    );


    backupFolder.createFile(
      "BACKUP_MANIFEST.json",
      JSON.stringify(
        manifest,
        null,
        2
      ),
      MimeType.PLAIN_TEXT
    );


    var successAt =
      vektorNumV2Now_();


    var status =
      vektorNumV2BackupStatusWrite_({

        status:
          "SUCCESS",

        lastSuccess:
          successAt,

        lastError:
          "",

        lastBackupFolderId:
          backupFolder.getId(),

        lastBackupFolderUrl:
          (
            "https://example.com/configure-recurso" +
            backupFolder.getId()
          ),

        backupRootFolderUrl:
          vektorNumV2BackupRootUrl_(
            root
          )

      });


    return {

      status:
        "SUCCESS",

      confirmedFiles:
        confirmed,

      folderId:
        backupFolder.getId(),

      folderUrl:
        status.lastBackupFolderUrl,

      createdAt:
        successAt
    };


  } catch (error) {

    vektorNumV2BackupStatusWrite_({

      status:
        "ERROR",

      lastError:
        error &&
        error.message
          ? error.message
          : String(error)

    });


    throw error;


  } finally {

    lock.releaseLock();
  }
}


function vektorNumerarioBackupGetStatusV2() {

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  return vektorNumV2BackupGetStatus_();
}


function vektorNumerarioBackupRunNowV2() {

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  var ctx =
    vektorGetUserRole_();


  if (
    String(
      ctx.role || ""
    )
      .trim()
      .toLowerCase() !==
    "administrador"
  ) {

    throw new Error(
      "Apenas Administrador pode executar o backup manual."
    );
  }


  var backup =
    vektorNumV2BackupExecute_();


  var config =
    vektorNumV2GetConfig_();


  if (
    config.backupEnabled ===
    true
  ) {

    vektorNumV2BackupScheduleNext_(
      config
    );
  }


  return {

    ok: true,

    backup:
      backup,

    status:
      vektorNumV2BackupGetStatus_()
  };
}


function vektorNumerarioBackupScheduledV2() {

  var config =
    vektorNumV2GetConfig_();


  if (
    config.backupEnabled !==
    true
  ) {

    vektorNumV2BackupDeleteTriggers_();

    return;
  }


  try {

    vektorNumV2BackupExecute_();


  } finally {

    vektorNumV2BackupScheduleNext_(
      config
    );
  }
}


/* =====================================================
   EMAIL BODY
   ===================================================== */

function vektorNumV2BuildEmailHtml_(
  empresa,
  loja4,
  rows,
  store,
  subject
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  rows =
    Array.isArray(
      rows
    )
      ? rows
      : [];


  loja4 =
    vektorNumV2Store4_(
      loja4
    );


  /*
   * Identificação da loja na saudação.
   *
   * CENTAURO:
   * CE0012
   *
   * FISIA:
   * 2029
   */
  var lojaSaudacao =
    empresa === "FISIA"
      ? loja4
      : "CE" + loja4;


  /*
   * Saudação conforme horário do envio.
   */
  var tz =
    Session.getScriptTimeZone() ||
    "America/Sao_Paulo";


  var hora =
    Number(
      Utilities.formatDate(
        new Date(),
        tz,
        "H"
      )
    );


  var saudacaoHorario =
    hora < 12
      ? "bom dia"
      : (
          hora < 18
            ? "boa tarde"
            : "boa noite"
        );


  /*
   * Helpers da tabela.
   */
  function th_(label) {

    return (
      '<th style="' +
        'padding:8px 10px;' +
        'border:1px solid #cbd5e1;' +
        'background:#005E27;' +
        'color:#ffffff;' +
        'font-family:Arial,sans-serif;' +
        'font-size:12px;' +
        'font-weight:700;' +
        'text-align:center;' +
        'white-space:nowrap;' +
      '">' +
        vektorNumV2Escape_(
          label
        ) +
      '</th>'
    );
  }


  function td_(
    value,
    extraStyle
  ) {

    return (
      '<td style="' +
        'padding:8px 10px;' +
        'border:1px solid #cbd5e1;' +
        'background:#ffffff;' +
        'color:#111827;' +
        'font-family:Arial,sans-serif;' +
        'font-size:12px;' +
        'vertical-align:middle;' +
        (
          extraStyle ||
          ""
        ) +
      '">' +

        vektorNumV2Escape_(
          value == null
            ? ""
            : value
        ) +

      '</td>'
    );
  }

  /*
 * Informações complementares das linhas
 * agrupadas para esta loja.
 *
 * Remove vazios e evita repetir o mesmo
 * texto caso apareça em mais de uma linha.
 */
var informacoesComplementares = [];

var complementaresMap = {};


rows.forEach(
  function(row) {

    var texto =
      String(
        row[
          "INFORMAÇÕES COMPLEMENTARES (SERÁ ENVIADA NO CORPO DO E-MAIL)"
        ] || ""
      ).trim();


    if (!texto) {
      return;
    }


    var key =
      texto.toLowerCase();


    if (
      complementaresMap[
        key
      ]
    ) {
      return;
    }


    complementaresMap[
      key
    ] = true;


    informacoesComplementares.push(
      texto
    );
  }
);

  var html = "";


  /*
   * Corpo normal do e-mail.
   *
   * Sem banner.
   * Sem cards.
   * Sem box externo.
   */
  html +=
    '<div style="' +
      'font-family:Arial,sans-serif;' +
      'font-size:14px;' +
      'line-height:1.55;' +
      'color:#111827;' +
    '">';


  /*
   * Saudação.
   */
  html +=
    '<p style="' +
      'margin:0 0 16px 0;' +
    '">' +

      'Olá ' +

      '<strong>' +
        vektorNumV2Escape_(
          lojaSaudacao
        ) +
      '</strong>' +

      ', ' +

      saudacaoHorario +

      '!' +

    '</p>';


  /*
   * Texto introdutório.
   */
  html +=
  '<p style="' +
    'margin:0 0 20px 0;' +
  '">' +

    'Em nossa análise da Conciliação de Vendas em dinheiro, ' +
    'referente ao período indicado na tabela abaixo, identificamos ' +
    'as seguintes faltas entre o ' +

    '<strong>Valor do movimento</strong>' +

    ' e o ' +

    '<strong>Valor efetivamente depositado</strong>' +

    '.' +


    (
      informacoesComplementares.length
        ? (
            ' ' +

            informacoesComplementares
              .map(
                function(texto) {

                  return vektorNumV2Escape_(
                    texto
                  )
                  .replace(
                    /\r?\n/g,
                    '<br>'
                  );
                }
              )
              .join(
                '<br>'
              )
          )
        : ''
    ) +

  '</p>';


  /*
   * TABELA
   *
   * Os nomes abaixo são os mesmos
   * apresentados na tela do Numerário.
   */
  html +=
    '<table style="' +
      'width:100%;' +
      'border-collapse:collapse;' +
      'border-spacing:0;' +
      'margin:0 0 24px 0;' +
      'font-family:Arial,sans-serif;' +
    '">';


  html +=
    '<thead>' +

      '<tr>' +

        th_(
          'LOJA'
        ) +

        th_(
          'DATA DEPÓSITO'
        ) +

        th_(
          'MOV. INICIAL'
        ) +

        th_(
          'MOV. FINAL'
        ) +

        th_(
          'VALOR PREVISTO'
        ) +

        th_(
          'VALOR DEPOSITADO'
        ) +

        th_(
          'DIFERENÇA'
        ) +

      '</tr>' +

    '</thead>';


  html +=
    '<tbody>';


  rows.forEach(
    function(row) {

      html +=
        '<tr>' +

          td_(
            loja4,
            'text-align:center;'
          ) +

          td_(
            row[
              "DATA DEPÓSITO"
            ] ||
            "",
            'text-align:center;'
          ) +

          td_(
            row[
              "Mov. Inicial"
            ] ||
            "",
            'text-align:center;'
          ) +

          td_(
            row[
              "Mov. Final"
            ] ||
            "",
            'text-align:center;'
          ) +

          td_(
            vektorNumV2FmtMoney_(
              vektorNumV2ParseMoney_(
                row[
                  "VALOR PREVISTO"
                ]
              )
            ),
            'text-align:right;'
          ) +

          td_(
            vektorNumV2FmtMoney_(
              vektorNumV2ParseMoney_(
                row[
                  "VALOR DEPOSITADO"
                ]
              )
            ),
            'text-align:right;'
          ) +

          td_(
            vektorNumV2FmtMoney_(
              vektorNumV2ParseMoney_(
                row.DIFERENÇA
              )
            ),
            'text-align:right;font-weight:700;'
          ) +

        '</tr>';
    }
  );


  html +=
      '</tbody>' +
    '</table>';


  /*
   * Orientações.
   */
  html +=
    '<p style="' +
      'margin:0 0 18px 0;' +
    '">' +

      'Para que possamos resolver essas diferenças de forma ágil, ' +
      'solicitamos sua colaboração com as seguintes ações, conforme o caso:' +

    '</p>';


  /*
   * Item 1.
   */
  html +=
    '<p style="' +
      'margin:0 0 20px 0;' +
    '">' +

      '<strong>' +
        '1. Se a Falta Não Corresponde ao Registro Interno (Livro de Caixa)' +
      '</strong>' +

      '<br><br>' +

      'Caso os valores de falta identificados não condizem com o que está ' +
      'registrado em seu Livro de Caixa ou Fechamento Operacional:' +

      '<br><br>' +

      '<strong>- Ação Requerida:</strong> ' +

      'Solicitamos o envio imediato da Cópia do Fechamento X ' +
      '(ou Relatório de Caixa) completo do(s) dia(s) apontados ' +
      'para nossa verificação cruzada.' +

    '</p>';


  /*
   * Item 2.
   */
  html +=
    '<p style="' +
      'margin:0 0 20px 0;' +
    '">' +

      '<strong>' +
        '2. Se a Falta Corresponde a Movimentações de Caixa' +
      '</strong>' +

      '<br><br>' +

      'Caso os valores de falta correspondam a sangrias, retiradas, ' +
      'repasses ou reembolsos específicos realizados:' +

      '<br><br>' +

      '<strong>- Ação Requerida:</strong> ' +

      'Solicitamos que nos enviem os números de identificação/documento ' +
      '(protocolo ou comprovante) dessas respectivas movimentações aqui.' +

    '</p>';


  /*
   * Prazo.
   */
  html +=
    '<p style="' +
      'margin:0 0 24px 0;' +
    '">' +

      'Aguardamos o retorno com as informações ou documentos solicitados ' +
      'em um prazo máximo de 3 dias úteis.' +

    '</p>';


  /*
   * Assinatura.
   */
  html +=
    '<p style="' +
      'margin:0;' +
      'font-weight:700;' +
    '">' +

      'Contas a Receber - Grupo SBF' +

    '</p>';


  html +=
    '</div>';


  return html;
}



/* =====================================================
   DISPAROS LOG
   ===================================================== */

function vektorNumV2ReadDispatches_() {

  var data =
    vektorNumV2ReadJson_(
      "DISPAROS"
    );


  data.rows =
    Array.isArray(
      data.rows
    )
      ? data.rows
      : [];


  return data;
}


function vektorNumV2AppendDispatch_(
  data,
  payload
) {

  data =
    data || {
      rows: []
    };


  data.rows =
    Array.isArray(
      data.rows
    )
      ? data.rows
      : [];


  payload =
    payload || {};


  data.rows.push({

    ID_DISPARO:
      Utilities.getUuid(),

    DATA_ENVIO:
      vektorNumV2Now_(),

    USUARIO:
      String(
        payload.usuario || ""
      ),

    EMPRESA:
      String(
        payload.empresa || ""
      ),

    LOJA:
      String(
        payload.loja || ""
      ),

    ASSUNTO:
      String(
        payload.assunto || ""
      ),

    DESTINATARIOS:
      String(
        payload.destinatarios || ""
      ),

    CC:
      String(
        payload.cc || ""
      ),

    ROW_IDS:
      Array.isArray(
        payload.rowIds
      )
        ? payload.rowIds.join(",")
        : "",

    QTD_LINHAS:
      Number(
        payload.qtdLinhas || 0
      ),

    VALOR_DIVERGENCIA:
      Number(
        payload.valorDivergencia || 0
      ),

    STATUS:
      String(
        payload.status || ""
      ),

    ERRO:
      String(
        payload.erro || ""
      )

  });


  return data;
}

/* =====================================================
   GMAIL API | ENVIO NUMERÁRIO
   ===================================================== */

function vektorNumV2MimeEncodeSubject_(
  value
) {

  value =
    String(
      value || ""
    );


  return (
    "=?UTF-8?B?" +
    Utilities.base64Encode(
      value,
      Utilities.Charset.UTF_8
    ) +
    "?="
  );
}


function vektorNumV2HtmlToPlainText_(
  html
) {

  return String(
    html || ""
  )
    .replace(
      /<br\s*\/?>/gi,
      "\n"
    )
    .replace(
      /<\/p>/gi,
      "\n\n"
    )
    .replace(
      /<[^>]+>/g,
      ""
    )
    .replace(
      /&nbsp;/gi,
      " "
    )
    .replace(
      /&amp;/gi,
      "&"
    )
    .replace(
      /&lt;/gi,
      "<"
    )
    .replace(
      /&gt;/gi,
      ">"
    )
    .replace(
      /&#039;/gi,
      "'"
    )
    .replace(
      /&quot;/gi,
      '"'
    )
    .trim();
}


function vektorNumV2EnviarEmailGmailApi_(
  params
) {

  params =
    params || {};


  var to =
    String(
      params.to || ""
    ).trim();


  var cc =
    String(
      params.cc || ""
    ).trim();


  var replyTo =
    String(
      params.replyTo || ""
    ).trim();


  var from =
    String(
      params.from ||
      VEKTOR_NUM_V2_EMAIL_FROM ||
      ""
    ).trim();


  var fromName =
    String(
      params.fromName ||
      VEKTOR_NUM_V2_EMAIL_NAME ||
      ""
    ).trim();


  var subject =
    String(
      params.subject || ""
    );


  var htmlBody =
    String(
      params.htmlBody || ""
    );


  if (!to) {

    throw new Error(
      "Destinatário não informado para o Gmail API."
    );
  }


  if (!subject) {

    throw new Error(
      "Assunto não informado para o Gmail API."
    );
  }


  var plainBody =
    vektorNumV2HtmlToPlainText_(
      htmlBody
    );


  var boundary =
    "vektor_numerario_" +
    Utilities
      .getUuid()
      .replace(
        /-/g,
        ""
      );


  var headers = [];


  /*
   * FROM
   */
  if (from) {

    headers.push(
      "From: " +
      fromName +
      " <" +
      from +
      ">"
    );
  }


  /*
   * TO
   */
  headers.push(
    "To: " +
    to
  );


  /*
   * CC
   */
  if (cc) {

    headers.push(
      "Cc: " +
      cc
    );
  }


  /*
   * REPLY-TO
   */
  if (replyTo) {

    headers.push(
      "Reply-To: " +
      replyTo
    );
  }


  /*
   * ASSUNTO UTF-8
   */
  headers.push(
    "Subject: " +
    vektorNumV2MimeEncodeSubject_(
      subject
    )
  );


  headers.push(
    "MIME-Version: 1.0"
  );


  headers.push(
    'Content-Type: multipart/alternative; boundary="' +
    boundary +
    '"'
  );


  /*
   * MIME
   */
  var mime = [

    headers.join(
      "\r\n"
    ),

    "",

    "--" +
    boundary,

    "Content-Type: text/plain; charset=UTF-8",

    "Content-Transfer-Encoding: base64",

    "",

    Utilities.base64Encode(
      plainBody,
      Utilities.Charset.UTF_8
    ),

    "",

    "--" +
    boundary,

    "Content-Type: text/html; charset=UTF-8",

    "Content-Transfer-Encoding: base64",

    "",

    Utilities.base64Encode(
      htmlBody,
      Utilities.Charset.UTF_8
    ),

    "",

    "--" +
    boundary +
    "--",

    ""

  ].join(
    "\r\n"
  );


  var raw =
    Utilities
      .base64EncodeWebSafe(
        mime,
        Utilities.Charset.UTF_8
      )
      .replace(
        /=+$/g,
        ""
      );


  /*
   * ENVIO PELA GMAIL API AVANÇADA
   */
  var result =
    Gmail.Users.Messages.send(
      {
        raw:
          raw
      },
      "me"
    );


  if (
    !result ||
    !result.id
  ) {

    throw new Error(
      "A Gmail API não retornou o ID da mensagem enviada."
    );
  }


  return {

    ok:
      true,

    messageId:
      String(
        result.id || ""
      ),

    threadId:
      String(
        result.threadId || ""
      )
  };
}


/* =====================================================
   SEND
   ===================================================== */

function vektorNumerarioSendSelectedV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioSendSelectedV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  var rowIds =
    Array.isArray(
      req.rowIds
    )
      ? req.rowIds.map(
          function(id) {
            return String(
              id || ""
            );
          }
        )
      : [];


  if (!rowIds.length) {

    throw new Error(
      "Selecione pelo menos uma linha para envio."
    );
  }


  var config =
    vektorNumV2GetConfig_();


  if (
    rowIds.length >
    Number(
      config.maxSendPerRun ||
      100
    )
  ) {

    throw new Error(
      "Limite de " +
      config.maxSendPerRun +
      " linha(s) por execução."
    );
  }


  var ctx =
    vektorGetUserRole_();


  var lock =
    LockService
      .getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    var storeMap =
      vektorNumV2StoreMap_();


    var selectedMap = {};


    rowIds.forEach(
      function(id) {
        selectedMap[id] =
          true;
      }
    );


    var groups = {};


    data.rows.forEach(
      function(row) {

        var id =
          String(
            row.__id || ""
          );


        if (
          !selectedMap[id]
        ) {
          return;
        }


        if (
          vektorNumV2IsBlankRow_(
            empresa,
            row
          )
        ) {

          return;
        }


        if (
          row.__sent === true
        ) {

          throw new Error(
            "A linha da loja " +
            row.LOJA +
            " já foi enviada."
          );
        }


        var loja4 =
          vektorNumV2Store4_(
            row.LOJA
          );


        if (!loja4) {

          throw new Error(
            "Existe linha selecionada sem loja informada."
          );
        }


        if (
          !vektorNumV2RequiredInputsComplete_(row) ||
          !String(row["DATA COBRANÇA"] || "").trim()
        ) {

          throw new Error(
            "A linha da loja " +
            loja4 +
            " não possui todos os campos obrigatórios: Loja, Valor Previsto e Valor Depositado."
          );
        }


        var store =
          storeMap[
            empresa +
            "|" +
            loja4
          ];


        if (!store) {

          throw new Error(
            "Loja " +
            loja4 +
            " não encontrada na Base de Lojas."
          );
        }


        var to =
          vektorNumV2ResolveRecipients_(
            empresa,
            loja4,
            store
          );


        if (!to) {

          throw new Error(
            "Loja " +
            loja4 +
            " não possui destinatário válido."
          );
        }


        if (!groups[loja4]) {

          groups[loja4] = {

            loja4:
              loja4,

            store:
              store,

            to:
              to,

            isTest:
              vektorNumV2IsTestStore_(
                empresa,
                loja4
              ),

            rows: []
          };
        }


        groups[loja4]
          .rows
          .push(
            row
          );
      }
    );


    var groupKeys =
      Object.keys(
        groups
      );


    if (!groupKeys.length) {

      throw new Error(
        "Nenhuma linha válida selecionada."
      );
    }


    var dispatches =
      vektorNumV2ReadDispatches_();


    var sentGroups = 0;

    var errors = 0;

    var details = [];


    groupKeys.forEach(
      function(loja4) {

        var group =
          groups[
            loja4
          ];


        var subject =
          vektorNumV2BuildSubject_(
            empresa,
            group.rows[0],
            group.store
          );


        var htmlBody =
          vektorNumV2BuildEmailHtml_(
            empresa,
            loja4,
            group.rows,
            group.store,
            subject
          );


        var totalDifference = 0;


        group.rows.forEach(
          function(row) {

            totalDifference +=
              Math.abs(
                vektorNumV2ParseMoney_(
                  row.DIFERENÇA
                )
              );

          }
        );


        try {

          var cc =
            group.isTest
              ? ""
              : vektorNumV2NormalizeEmails_(
                  config.emailCc
                );


          var gmailApiResult =
            vektorNumV2EnviarEmailGmailApi_(
              {

                to:
                  group.to,

                cc:
                  cc,

                replyTo:
                  config.replyTo,

                from:
                  String(
                    config.emailFrom ||
                    VEKTOR_NUM_V2_EMAIL_FROM
                  ),

                fromName:
                  String(
                    config.emailName ||
                    VEKTOR_NUM_V2_EMAIL_NAME
                  ),

                subject:
                  subject,

                htmlBody:
                  htmlBody
              }
            );


          group.rows.forEach(
            function(row) {

              row.__sent =
                true;

              row.__sentAt =
                vektorNumV2Now_();

              row.__sentBy =
                String(
                  ctx.email || ""
                )
                  .trim()
                  .toLowerCase();

              row.__emailStatus =
                "ENVIADO";

              row["STATUS ENVIO"] =
                "ENVIADO";

              delete row.__emailError;
            }
          );


          vektorNumV2AppendDispatch_(
            dispatches,
            {

              usuario:
                ctx.email,

              empresa:
                empresa,

              loja:
                loja4,

              assunto:
                subject,

              destinatarios:
                group.to,

              cc:
                cc,

              rowIds:
                group.rows.map(
                  function(row) {
                    return row.__id;
                  }
                ),

              qtdLinhas:
                group.rows.length,

              valorDivergencia:
                totalDifference,

              status:
                "ENVIADO"
            }
          );


          sentGroups++;


          details.push({

            loja:
              loja4,

            status:
              "ENVIADO",

            assunto:
              subject
          });


        } catch (error) {

          var message =
            error &&
            error.message
              ? error.message
              : String(
                  error
                );


          group.rows.forEach(
            function(row) {

              row.__emailStatus =
                "ERRO";

              row.__emailError =
                message;

              row["STATUS ENVIO"] =
                "ERRO";

            }
          );


          vektorNumV2AppendDispatch_(
            dispatches,
            {

              usuario:
                ctx.email,

              empresa:
                empresa,

              loja:
                loja4,

              assunto:
                subject,

              destinatarios:
                group.to,

              cc:
                config.emailCc,

              rowIds:
                group.rows.map(
                  function(row) {
                    return row.__id;
                  }
                ),

              qtdLinhas:
                group.rows.length,

              valorDivergencia:
                totalDifference,

              status:
                "ERRO",

              erro:
                message
            }
          );


          errors++;


          details.push({

            loja:
              loja4,

            status:
              "ERRO",

            error:
              message
          });
        }
      }
    );


    data =
      vektorNumV2EnsureDraft_(
        empresa,
        data
      );


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    vektorNumV2WriteJson_(
      "DISPAROS",
      dispatches
    );


    return {

      ok: true,

      empresa:
        empresa,

      enviados:
        sentGroups,

      erros:
        errors,

      details:
        details,

      rows:
        data.rows,

      reports:
        vektorNumV2BuildReports_(
          empresa
        )
    };


  } finally {

    lock.releaseLock();

  }
}


/* =====================================================
   REPORTS
   ===================================================== */

function vektorNumV2BuildReports_(
  empresa
) {

  empresa =
    vektorNumV2NormEmpresa_(
      empresa
    );


  var operational =
    vektorNumV2ReadJson_(
      empresa
    );


  var rows =
    Array.isArray(
      operational.rows
    )
      ? operational.rows
      : [];


  var dispatches =
    vektorNumV2ReadDispatches_();


  var logs =
    dispatches.rows
      .filter(
        function(row) {

          return String(
            row.EMPRESA || ""
          )
            .trim()
            .toUpperCase() ===
          empresa;

        }
      );


  var filled =
    rows.filter(
      function(row) {

        return !vektorNumV2IsBlankRow_(
          empresa,
          row
        );

      }
    );


  var statusHeader =
    empresa === "FISIA"
      ? "STATUS"
      : "Status";


  var pendentes = 0;

  var naoEnviados = 0;

  var statusMap = {};

  /*
 * MÉDIA DE DIAS DE TRATATIVA
 * agrupada por mês + loja.
 *
 * Fonte:
 * QTD DIAS TRATATIVA
 */
var treatmentMap = {};


  filled.forEach(
    function(row) {

      var status =
        String(
          row[statusHeader] ||
          "SEM STATUS"
        )
          .trim()
          .toUpperCase() ||
        "SEM STATUS";


      statusMap[status] =
        (
          statusMap[
            status
          ] ||
          0
        ) +
        1;


      if (
        status === "PENDENTE"
      ) {

        pendentes++;
      }


      if (
        row.__sent !== true
      ) {

        naoEnviados++;
      }
      /*
 * Gráfico de média de dias de tratativa.
 *
 * O valor utilizado é EXATAMENTE o existente
 * na coluna QTD DIAS TRATATIVA.
 */
var lojaTratativa =
  vektorNumV2Store4_(
    row.LOJA
  );


var periodoTratativa =
  String(
    row["MÊS PENDÊNCIA"] ||
    vektorNumV2MonthText_(
      row["DATA COBRANÇA"]
    ) ||
    ""
  ).trim();


var diasRaw =
  row[
    "QTD DIAS TRATATIVA"
  ];


/*
 * É importante testar vazio antes de Number(),
 * porque Number("") seria 0.
 */
var diasText =
  String(
    diasRaw == null
      ? ""
      : diasRaw
  ).trim();


if (
  lojaTratativa &&
  periodoTratativa &&
  diasText !== ""
) {

  var diasTratativa =
    Number(
      diasText
        .replace(
          ",",
          "."
        )
    );


  if (
    isFinite(
      diasTratativa
    ) &&
    diasTratativa >= 0
  ) {

    var treatmentKey =
      periodoTratativa +
      "|" +
      lojaTratativa;


    if (
      !treatmentMap[
        treatmentKey
      ]
    ) {

      treatmentMap[
        treatmentKey
      ] = {

        periodo:
          periodoTratativa,

        loja:
          lojaTratativa,

        somaDias:
          0,

        qtd:
          0
      };
    }


    treatmentMap[
      treatmentKey
    ].somaDias +=
      diasTratativa;


    treatmentMap[
      treatmentKey
    ].qtd++;
  }
}
    }
  );


  var sentLogs =
    logs.filter(
      function(row) {

        return String(
          row.STATUS || ""
        )
          .trim()
          .toUpperCase() ===
        "ENVIADO";

      }
    );


  var errorLogs =
    logs.filter(
      function(row) {

        return String(
          row.STATUS || ""
        )
          .trim()
          .toUpperCase() ===
        "ERRO";

      }
    );


  var stores = {};

  var totalValue = 0;

  var totalLines = 0;

  var months = {};

  var storeRanking = {};


  sentLogs.forEach(
    function(row) {

      var loja =
        vektorNumV2Store4_(
          row.LOJA
        );


      if (loja) {

        stores[
          loja
        ] =
          true;


        storeRanking[
          loja
        ] =
          (
            storeRanking[
              loja
            ] ||
            0
          ) +
          Number(
            row.QTD_LINHAS ||
            0
          );
      }


      totalValue +=
        Number(
          row.VALOR_DIVERGENCIA ||
          0
        );


      totalLines +=
        Number(
          row.QTD_LINHAS ||
          0
        );


      var date =
        String(
          row.DATA_ENVIO || ""
        );


      var month =
        date.length >= 7
          ? date.slice(
              0,
              7
            )
          : "N/D";


      if (!months[month]) {

        months[month] = {
          periodo:
            month,

          disparos: 0,

          valor: 0
        };
      }


      months[month].disparos++;

      months[month].valor +=
        Number(
          row.VALOR_DIVERGENCIA ||
          0
        );
    }
  );


  var byStatus =
    Object.keys(
      statusMap
    )
      .map(
        function(status) {

          return {
            status:
              status,

            qtd:
              statusMap[
                status
              ]
          };

        }
      )
      .sort(
        function(a, b) {

          return b.qtd -
            a.qtd;

        }
      );


  var byMonth =
    Object.keys(
      months
    )
      .sort()
      .map(
        function(key) {

          return months[
            key
          ];

        }
      );


  var topStores =
    Object.keys(
      storeRanking
    )
      .map(
        function(loja) {

          return {
            loja:
              loja,

            qtd:
              storeRanking[
                loja
              ]
          };

        }
      )
      .sort(
        function(a, b) {

          return b.qtd -
            a.qtd;

        }
      )
      .slice(
        0,
        10
      );

      /*
 * Média de dias de tratativa
 * por loja e por período mensal.
 */
var treatmentByStoreMonth =
  Object.keys(
    treatmentMap
  )
    .map(
      function(key) {

        var item =
          treatmentMap[
            key
          ];


        var media =
          item.qtd > 0
            ? (
                item.somaDias /
                item.qtd
              )
            : 0;


        return {

          periodo:
            item.periodo,

          loja:
            item.loja,

          mediaDias:
            Number(
              media.toFixed(
                2
              )
            ),

          qtd:
            item.qtd
        };
      }
    )
    .sort(
      function(a, b) {

        /*
         * Ordenação cronológica:
         * MM/YYYY -> YYYYMM
         */
        function periodKey_(
          periodo
        ) {

          var p =
            String(
              periodo || ""
            ).split("/");


          if (
            p.length !== 2
          ) {
            return 0;
          }


          return (
            Number(
              p[1]
            ) *
            100
          ) +
          Number(
            p[0]
          );
        }


        var pa =
          periodKey_(
            a.periodo
          );


        var pb =
          periodKey_(
            b.periodo
          );


        if (
          pa !== pb
        ) {

          return pa - pb;
        }


        return (
          Number(
            a.loja
          ) -
          Number(
            b.loja
          )
        );
      }
    );

  var history =
    logs
      .slice()
      .reverse()
      .slice(
        0,
        200
      );


  return {

  cards: {

    disparos:
      sentLogs.length,

    lojas:
      Object.keys(
        stores
      ).length,

    linhas:
      totalLines,

    valor:
      totalValue,

    pendentes:
      pendentes,

    naoEnviados:
      naoEnviados,

    erros:
      errorLogs.length
  },

  byStatus:
    byStatus,

  byMonth:
    byMonth,

  topStores:
    topStores,

  treatmentByStoreMonth:
    treatmentByStoreMonth,

  history:
    history
};
}


function vektorNumerarioGetReportsV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioGetReportsV2"
  );

  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      req.empresa
    );


  return {

    ok: true,

    empresa:
      empresa,

    reports:
      vektorNumV2BuildReports_(
        empresa
      )
  };
}

/* =====================================================
   RESPOSTAS DE E-MAIL | APLICAR STATUS AUTOMÁTICO
   ===================================================== */

var VEKTOR_NUM_EMAIL_REPLY_QUEUE_FOLDER_ID =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_NUM_EMAIL_REPLY_QUEUE_FOLDER_ID") || "";


function vektorNumerarioProcessEmailReplyQueueV2() {

  var folder =
    DriveApp.getFolderById(
      VEKTOR_NUM_EMAIL_REPLY_QUEUE_FOLDER_ID
    );


  var files =
    folder.getFiles();


  var processados = 0;
  var ignorados = 0;
  var erros = 0;


  while (files.hasNext()) {

    var file =
      files.next();


    var fileName =
      String(
        file.getName() || ""
      );


    /*
     * Somente arquivos criados pelo
     * workflow de monitoramento.
     */
    if (
      !/^email_reply_.+\.json$/i.test(
        fileName
      )
    ) {

      continue;
    }


    var payload;


    try {

      payload =
        JSON.parse(
          file
            .getBlob()
            .getDataAsString(
              "UTF-8"
            ) ||
          "{}"
        );

    } catch (error) {

      erros++;

      continue;
    }


    /*
     * Arquivo já tratado.
     */
    if (
      String(
        payload.status || ""
      )
        .trim()
        .toUpperCase() !==
      "PENDING"
    ) {

      ignorados++;

      continue;
    }


    /*
     * Segurança.
     */
    if (
      String(
        payload.type || ""
      ).toUpperCase() !==
        "NUMERARIO_EMAIL_REPLY" ||
      String(
        payload.action || ""
      ).toUpperCase() !==
        "APPLY_EMAIL_REPLY"
    ) {

      payload.status =
        "IGNORED";

      payload.processedAt =
        new Date().toISOString();

      payload.error =
        "Tipo ou ação inválidos.";


      file.setContent(
        JSON.stringify(
          payload,
          null,
          2
        )
      );


      ignorados++;

      continue;
    }


    try {

      var result =
        vektorNumV2ApplyEmailReply_(
          payload
        );


      payload.status =
        "PROCESSED";

      payload.processedAt =
        new Date().toISOString();

      payload.updatedRows =
        Number(
          result.updatedRows || 0
        );


      file.setContent(
        JSON.stringify(
          payload,
          null,
          2
        )
      );


      processados++;

    } catch (error) {

      payload.status =
        "ERROR";

      payload.processedAt =
        new Date().toISOString();

      payload.error =
        error &&
        error.message
          ? error.message
          : String(error);


      file.setContent(
        JSON.stringify(
          payload,
          null,
          2
        )
      );


      erros++;
    }

  }


  return {

    ok:
      true,

    processados:
      processados,

    ignorados:
      ignorados,

    erros:
      erros

  };

}


/* =====================================================
   APLICAR UMA RESPOSTA NA BASE OPERACIONAL
   ===================================================== */

function vektorNumV2ApplyEmailReply_(
  payload
) {

  payload =
    payload || {};


  var empresa =
    vektorNumV2NormEmpresa_(
      payload.empresa
    );


  var chaveAssunto =
    String(
      payload.chaveAssunto || ""
    )
      .trim()
      .toUpperCase();


  if (!chaveAssunto) {

    throw new Error(
      "chaveAssunto não informada."
    );
  }


  var statusSugerido =
    String(
      payload.statusSugerido || ""
    )
      .trim()
      .toUpperCase();


  var statusPermitidos = {

    "TRATATIVA - LOJA":
      true,

    "TRATATIVA - FIN":
      true

  };


  var alterarStatus =
    statusPermitidos[
      statusSugerido
    ] === true;


  var lock =
    LockService.getScriptLock();


  lock.waitLock(
    30000
  );


  try {

    var data =
      vektorNumV2ReadCompany_(
        empresa,
        true
      );


    var subjectHeader =
      empresa === "FISIA"
        ? "CÓDIGO ÚNICO_ASSUNTO"
        : "CÓDIGO ENVIO EMAIL_ASSUNTO";


    var statusHeader =
      empresa === "FISIA"
        ? "STATUS"
        : "Status";


    var storeMap =
      vektorNumV2StoreMap_();


    var updatedRows =
      0;


    data.rows.forEach(
      function(row) {

        var assunto =
          String(
            row[
              subjectHeader
            ] || ""
          )
            .trim()
            .toUpperCase();


        if (
          assunto.indexOf(
            chaveAssunto
          ) !== 0
        ) {

          return;
        }


        var previousStatus =
          String(
            row[
              statusHeader
            ] || ""
          )
            .trim()
            .toUpperCase();


        if (
          alterarStatus &&
          previousStatus !==
            statusSugerido
        ) {

          row[
            statusHeader
          ] =
            statusSugerido;


          vektorNumV2ApplyDerived_(
            empresa,
            row,
            storeMap,
            previousStatus
          );
        }


        var agora =
          vektorNumV2Now_();


        row.__lastEmailReplyAt =
          String(
            payload.receivedAt ||
            agora
          );


        row.__lastEmailReplyFrom =
          String(
            payload.from || ""
          );


        row.__lastEmailReplyCategory =
          String(
            payload.categoria || ""
          );


        row.__lastEmailReplySummary =
          String(
            payload.resumo || ""
          );


        row.__lastEmailReplyMessageId =
          String(
            payload.messageId || ""
          );


        row.__lastEmailReplyThreadId =
          String(
            payload.gmailThreadId || ""
          );


        row.__lastEmailReplyConfidence =
          Number(
            payload.confianca || 0
          );


        row.__lastStatusChangedAt =
          agora;


        row.__lastStatusChangedBy =
          "AGENTE_EMAIL";


        row.__updatedAt =
          agora;


        row.__updatedBy =
          "AGENTE_EMAIL";


        row.__lastChangeSource =
          "IA - n8n";


        row.__lastChangeAt =
          agora;


        row.__lastChangeBy =
          String(
            payload.from || ""
          );


        row.__lastChangeAction =
          alterarStatus
            ? "RESPOSTA DE E-MAIL"
            : "RESPOSTA REGISTRADA";


        row.__lastChangeDetail =
          alterarStatus
            ? (
                "Status alterado de " +
                previousStatus +
                " para " +
                statusSugerido
              )
            : (
                "Resposta recebida sem alteração automática de Status."
              );


        row.__changeLog =
          Array.isArray(
            row.__changeLog
          )
            ? row.__changeLog
            : [];


        row.__changeLog.push({

          at:
            agora,

          source:
            "IA - n8n",

          action:
            row.__lastChangeAction,

          actor:
            String(
              payload.from || ""
            ),

          detail:
            row.__lastChangeDetail

        });


        updatedRows++;

      }
    );


    if (
      updatedRows === 0
    ) {

      throw new Error(
        "Nenhuma linha encontrada para a chave " +
        chaveAssunto +
        " em " +
        empresa +
        "."
      );
    }


    vektorNumV2WriteJson_(
      empresa,
      data
    );


    return {

      ok:
        true,

      empresa:
        empresa,

      chaveAssunto:
        chaveAssunto,

      status:
        alterarStatus
          ? statusSugerido
          : "",

      updatedRows:
        updatedRows

    };


  } finally {

    lock.releaseLock();

  }

}

