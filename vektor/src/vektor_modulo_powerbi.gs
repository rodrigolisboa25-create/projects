var VEKTOR_POWER_BI_MODULE_KEY = "POWER_BI";
var VEKTOR_POWER_BI_TITLE = "Business Intelligence Hub";

var VEKTOR_POWER_BI_EMBED_URL =
  PropertiesService.getScriptProperties().getProperty("VEKTOR_POWER_BI_EMBED_URL") || "";

function vektorGetPowerBiEmbedData() {
  var ctx = vektorAssertModuleAllowed_(VEKTOR_POWER_BI_MODULE_KEY);

  return {
    ok: true,
    modulo: VEKTOR_POWER_BI_MODULE_KEY,
    title: VEKTOR_POWER_BI_TITLE,
    embedUrl: VEKTOR_POWER_BI_EMBED_URL,
    email: ctx.email,
    role: ctx.role
  };
}