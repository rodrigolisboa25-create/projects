/******************************************************
 * VEKTOR | NUMERÁRIO V2
 * ASSISTENTE NUMERÁRIO | GATEWAY CLOUDFLARE
 *
 * SEM PROPRIEDADES DO SCRIPT
 *
 * Fluxo:
 * HTML
 *   ↓
 * Apps Script
 *   ↓
 * Cloudflare Worker
 *   ↓
 * D1
 *
 * O n8n processa posteriormente a mensagem.
 ******************************************************/


/* =====================================================
   CONFIGURAÇÃO FIXA
   ===================================================== */

var VEKTOR_TP_WORKER_URL =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_TP_WORKER_URL") || "";


var VEKTOR_TP_WORKER_KEY =
  "TP_2026_PxgdKUe1XOD_YjWNJOFx8Kbhkey02Ys1cXlUakzsf9FWjISecDuSLngbdp_F1L8L";


/* =====================================================
   HTTP | WORKER
   ===================================================== */

function vektorTpWorkerFetchJson_(
  url,
  options
) {

  options =
    options || {};


  options.muteHttpExceptions =
    true;


  options.followRedirects =
    true;


  var response;


  try {

    response =
      UrlFetchApp.fetch(
        url,
        options
      );

  } catch (error) {

    throw new Error(
      "Não foi possível conectar ao Assistente Numerário. " +
      (
        error &&
        error.message
          ? error.message
          : String(error)
      )
    );

  }


  var statusCode =
    Number(
      response.getResponseCode()
    );


  var responseText =
    response.getContentText(
      "UTF-8"
    );


  var result;


  try {

    result =
      JSON.parse(
        responseText || "{}"
      );

  } catch (_) {

    console.error(
      "Assistente Numerário | JSON inválido | HTTP " +
      statusCode +
      " | " +
      responseText
    );


    throw new Error(
      "O Assistente Numerário retornou uma resposta inválida."
    );

  }


  if (
    statusCode < 200 ||
    statusCode >= 300
  ) {

    console.error(
      "Assistente Numerário | HTTP " +
      statusCode +
      " | " +
      responseText
    );


    var detalhe =
      result &&
      (
        result.error ||
        result.message
      )
        ? String(
            result.error ||
            result.message
          )
        : "";


    throw new Error(
      detalhe
        ? (
            "Assistente Numerário: " +
            detalhe
          )
        : (
            "O Assistente Numerário não conseguiu processar a solicitação."
          )
    );

  }


  return result || {};

}


/* =====================================================
   ENVIAR MENSAGEM
   =====================================================
   Mantemos o nome antigo porque o HTML atual
   já chama esta função.
   ===================================================== */

function vektorNumerarioAgentQueueRequestV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioAgentQueueRequestV2"
  );


  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  /* ===================================================
     USUÁRIO REAL DO VEKTOR
     =================================================== */

  var ctx =
    vektorGetUserRole_() || {};


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
      .trim();


  if (!userEmail) {

    throw new Error(
      "Não foi possível identificar o usuário do Vektor."
    );

  }


  /* ===================================================
     EMPRESA
     =================================================== */

  var empresa =
    String(
      req.empresa || ""
    )
      .trim()
      .toUpperCase();


  if (
    empresa !== "CENTAURO" &&
    empresa !== "FISIA"
  ) {

    throw new Error(
      "Empresa inválida."
    );

  }


  /* ===================================================
     MENSAGEM
     =================================================== */

  var message =
    String(
      req.message ||
      req.mensagem ||
      ""
    ).trim();


  if (!message) {

    throw new Error(
      "Digite uma mensagem."
    );

  }


  if (
    message.length > 5000
  ) {

    throw new Error(
      "A mensagem ultrapassa 5000 caracteres."
    );

  }


  /* ===================================================
     IDENTIFICADORES
     =================================================== */

  var requestId =
    String(
      req.requestId || ""
    ).trim();


  if (!requestId) {

    requestId =
      Utilities.getUuid();

  }


  var sessionId =
    String(
      req.sessionId || ""
    ).trim();


  if (!sessionId) {

    sessionId =
      Utilities.getUuid();

  }


  /* ===================================================
     PAYLOAD
     =================================================== */

  var payload = {

    requestId:
      requestId,

    sessionId:
      sessionId,

    message:
      message,

    empresa:
      empresa,

    userEmail:
      userEmail,

    userRole:
      userRole,

    source:
      "VEKTOR_NUMERARIO",

    view:
      "DISPAROS"

  };


  /* ===================================================
     ENVIO AO WORKER
     =================================================== */

  var result =
    vektorTpWorkerFetchJson_(
      VEKTOR_TP_WORKER_URL +
      "/api/numerario/message",
      {

        method:
          "post",

        contentType:
          "application/json; charset=utf-8",

        headers: {

          "x-vektor-agent-key":
            VEKTOR_TP_WORKER_KEY

        },

        payload:
          JSON.stringify(
            payload
          )

      }
    );


  if (
    !result ||
    result.ok !== true
  ) {

    throw new Error(
      "Não foi possível enviar a solicitação ao Assistente Numerário."
    );

  }


  /* ===================================================
     GUARDAR SESSION ID TEMPORARIAMENTE
     ===================================================
     O HTML atual consulta pelo requestId.

     Guardamos a sessionId temporariamente para
     conseguir localizar a resposta depois.
     =================================================== */

  try {

    CacheService
      .getUserCache()
      .put(
        "TP_SESSION_" +
        requestId,

        String(
          result.sessionId ||
          sessionId
        ),

        1200
      );

  } catch (_) {}


  return {

    ok:
      true,

    id:
      String(
        result.id || ""
      ),

    requestId:
      String(
        result.requestId ||
        requestId
      ),

    sessionId:
      String(
        result.sessionId ||
        sessionId
      ),

    status:
      String(
        result.status ||
        "PENDENTE"
      ),

    duplicate:
      result.duplicate === true

  };

}


/* =====================================================
   CONSULTAR RESPOSTA
   =====================================================
   Mantemos o nome atual porque o HTML
   já chama esta função.
   ===================================================== */

function vektorNumerarioAgentPollResponseV2(req) {

  vektorAssertFunctionAllowed_(
    "vektorNumerarioAgentPollResponseV2"
  );


  vektorAssertModuleAllowed_(
    VEKTOR_NUM_V2_MODULE_KEY
  );


  req =
    req || {};


  var requestId =
    String(
      req.requestId || ""
    ).trim();


  if (!requestId) {

    throw new Error(
      "RequestId não informado."
    );

  }


  /* ===================================================
     SESSION ID
     =================================================== */

  var sessionId =
    String(
      req.sessionId || ""
    ).trim();


  if (!sessionId) {

    try {

      sessionId =
        String(
          CacheService
            .getUserCache()
            .get(
              "TP_SESSION_" +
              requestId
            ) ||
          ""
        ).trim();

    } catch (_) {

      sessionId =
        "";

    }

  }


  if (!sessionId) {

    throw new Error(
      "SessionId não encontrada para esta solicitação."
    );

  }


  /* ===================================================
     CONSULTAR WORKER
     =================================================== */

  var url =
    VEKTOR_TP_WORKER_URL +
    "/api/numerario/result" +
    "?request_id=" +
    encodeURIComponent(
      requestId
    ) +
    "&session_id=" +
    encodeURIComponent(
      sessionId
    );


  var result =
    vektorTpWorkerFetchJson_(
      url,
      {

        method:
          "get",

        headers: {

          "x-vektor-agent-key":
            VEKTOR_TP_WORKER_KEY

        }

      }
    );


  /* ===================================================
     ERRO DE PROCESSAMENTO
     =================================================== */

  if (
    result &&
    result.pronto === true &&
    String(
      result.status || ""
    ).toUpperCase() === "ERRO"
  ) {

    throw new Error(
      String(
        result.error ||
        "Não foi possível processar a solicitação."
      )
    );

  }


  /* ===================================================
     AINDA NÃO RESPONDIDO
     =================================================== */

  if (
    !result ||
    result.pronto !== true
  ) {

    return {

      ok:
        true,

      ready:
        false,

      requestId:
        requestId,

      sessionId:
        sessionId,

      status:
        String(
          (
            result &&
            result.status
          ) ||
          "PENDENTE"
        )

    };

  }


  /* ===================================================
     RESPOSTA PRONTA
     =================================================== */

  var response =
    result.response;


  if (
    !response ||
    typeof response !== "object"
  ) {

    throw new Error(
      "A resposta do Assistente Numerário não foi encontrada."
    );

  }


  if (
    String(
      response.requestId || ""
    ) !== requestId
  ) {

    throw new Error(
      "O requestId da resposta não corresponde à solicitação."
    );

  }


  return {

    ok:
      true,

    ready:
      true,

    requestId:
      requestId,

    sessionId:
      sessionId,

    status:
      "COMPLETED",

    response:
      response

  };

}


/* =====================================================
   TESTE | ENVIAR
   ===================================================== */

function TESTE_AssistenteNumerario_Worker_Send() {

  var result =
    vektorNumerarioAgentQueueRequestV2({

      requestId:
        "TESTE-GAS-WORKER-001",

      sessionId:
        "TESTE-GAS-SESSAO-001",

      empresa:
        "CENTAURO",

      message:
        "Inclua uma pendência da loja 218 com valor previsto de 10000."

    });


  Logger.log(
    JSON.stringify(
      result,
      null,
      2
    )
  );

}


/* =====================================================
   TESTE | CONSULTAR
   ===================================================== */

function TESTE_AssistenteNumerario_Worker_Poll() {

  var result =
    vektorNumerarioAgentPollResponseV2({

      requestId:
        "TESTE-GAS-WORKER-001",

      sessionId:
        "TESTE-GAS-SESSAO-001"

    });


  Logger.log(
    JSON.stringify(
      result,
      null,
      2
    )
  );

}

function TESTE_N8N_DIRETO() {

  var url =
    "https://servico-interno.exemplo/configure";

  var payload = {
    requestId: "TESTE-" + new Date().getTime(),
    sessionId: "TESTE-CONEXAO-N8N",
    message: "Teste de conectividade. Não cadastrar nenhuma pendência.",
    empresa: "CENTAURO",
    userEmail: Session.getActiveUser().getEmail(),
    userRole: "TESTE",
    source: "VEKTOR_NUMERARIO",
    view: "DISPAROS"
  };

  var response = UrlFetchApp.fetch(
    url,
    {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
      followRedirects: true
    }
  );

  Logger.log(
    "STATUS: " +
    response.getResponseCode()
  );

  Logger.log(
    "RESPOSTA: " +
    response.getContentText()
  );
}