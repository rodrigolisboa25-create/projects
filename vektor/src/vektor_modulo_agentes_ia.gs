var VEKTOR_AI_AGENTS_MODULE_KEY = "AGENTES_IA";
var VEKTOR_AI_AGENTS_TITLE = "Agentes de IA";

function vektorGetAiAgentsCatalogo() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_AI_AGENTS_MODULE_KEY);

  var email = String((ctx && ctx.email) || "").trim().toLowerCase();

  var pacoteAcesso = "";
  if (/@gruposbf\.com\.br$/.test(email)) {
    pacoteAcesso = "grupo_acesso_ia_exemplo";
  } else if (/@centauro\.com\.br$/.test(email)) {
    pacoteAcesso = "g_a_plataforma_ia_centauro";
  }

  return {
    ok: true,
    modulo: VEKTOR_AI_AGENTS_MODULE_KEY,
    title: VEKTOR_AI_AGENTS_TITLE,
    email: email,
    portalAcesso: "https://myaccess.microsoft.com/@centaurotech.onmicrosoft.com#/access-packages",
    pacoteAcesso: pacoteAcesso,
    agentes: [
  {
    id: "vertex_financial_agent",
    nome: "Agente Vektor",
    descricao: "Agente corporativo no Vertex para apoio operacional e analítico quanto às transações do cartão Clara nas lojas.",
    status: "ATIVO",
    abrirEmNovaAba: true,
    url: "https://vertexaisearch.cloud.google.com/configure-agente"
  },
  {
    id: "vertex_smartslip_agent",
    nome: "SmartSlip",
    descricao: "Agente corporativo para apoio às análises e leitura de comprovante de depósitos das lojas via OCR.",
    status: "ATIVO",
    abrirEmNovaAba: true,
    url: "https://vertexaisearch.cloud.google.com/configure-agente"
  }
]
  };
}