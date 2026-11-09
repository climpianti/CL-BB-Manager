import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

let Panel;
const source = readFileSync("custom_components/cl_bb_manager/frontend/panel.js", "utf8");
runInNewContext(source, {
  HTMLElement: class {},
  customElements: {
    get(name) { return undefined; },
    define(name, ctor) {
      if (name === "cl-bb-manager-panel") Panel = ctor;
    },
  },
});
assert.ok(Panel, "Il pannello deve registrarsi come custom element");

test("Mostra il messaggio di errore WS invece di [object Object]", () => {
  const error = { code: "invalid_request", message: "Selezionare varchi distinti." };
  assert.equal(Panel.prototype.describeError(error), "Selezionare varchi distinti.");
});

test("Legge anche gli errori incapsulati e fornisce un fallback", () => {
  assert.equal(Panel.prototype.describeError({ error: { message: "Dati non validi" } }), "Dati non validi");
  assert.match(Panel.prototype.describeError({ code: "unknown" }), /Operazione non riuscita/);
});

test("Il form verifica la selezione del varco prima di generare il PIN", () => {
  assert.ok(source.includes("if(!gate_ids.length)"));
  assert.ok(source.includes("Seleziona almeno un varco autorizzato"));
  assert.ok(source.includes("if(b<=a)"));
});

test("I varchi non propongono QR permanenti disattivati", () => {
  assert.ok(source.includes("QR di accesso"));
  assert.ok(!source.includes('this.button("Scarica QR"'));
  assert.ok(source.includes('this.tab="accessi"'));
  assert.ok(source.includes('this.demoTargetGateId=gate.id'));
  assert.ok(source.includes("L\u0027accesso permanente non è ancora disponibile."));
});


test("L'URL esterno HA è la modalità QR predefinita e la LAN è opzionale", () => {
  assert.ok(source.includes('this.qrMode="https"'));
  assert.ok(source.includes('this._hass?.config?.external_url'));
  assert.ok(source.includes('this._hass?.config?.internal_url'));
  assert.ok(source.includes('if(this.qrMode==="https")grid.append(publicCard)'));
  assert.ok(source.indexOf('grid.append(fixed)') < source.indexOf('grid.append(publicCard)'));
  assert.ok(source.includes('QR temporaneo · HTTPS · 10 minuti'));
  assert.ok(source.includes('NON STAMPARE: questo QR scade dopo 10 minuti'));
  assert.ok(source.includes('Genera / mostra QR fisso'));
  assert.ok(source.includes('if(this.qrMode==="lan")grid.append(qrCard)'));
  assert.ok(source.includes('this.api("public_pilot_qr"'));
  assert.ok(source.includes('this.api("demo_qr"'));
});


test("CL Control BlueTech Glass conserva navigazione e stati di collaudo", () => {
  assert.ok(source.includes("bluetech-glass.css"));
  assert.ok(source.includes('"dashboard","Panoramica"'));
  assert.ok(source.includes('"accessi","Accessi"'));
  assert.ok(source.includes('"impostazioni","Impostazioni"'));
  assert.ok(source.includes('"Genera QR temporaneo (10 minuti)"'));
  assert.ok(source.includes('Ambiente pilota · solo varchi virtuali'));
  assert.ok(!source.includes('this.button("Scarica QR"'));
});


test("BlueTech Glass usa i colori ufficiali CL Control e layout responsive", () => {
  const css=readFileSync("custom_components/cl_bb_manager/frontend/bluetech-glass.css","utf8");
  assert.ok(css.includes("#061324"));
  assert.ok(css.includes("#19baff"));
  assert.ok(css.includes("#32e394"));
  assert.ok(css.includes("backdrop-filter:blur"));
  assert.ok(css.includes("@media(max-width:740px)"));
  assert.ok(css.includes(":focus-visible"));
});


test("Logo CL Impianti ufficiale integrato in pannello e pagina accessi", () => {
  const css=readFileSync("custom_components/cl_bb_manager/frontend/bluetech-glass.css","utf8");
  const logo=readFileSync("custom_components/cl_bb_manager/frontend/cl-impianti-logo.svg","utf8");
  assert.ok(source.includes('logo.alt="CL Impianti"'));
  const manifest=JSON.parse(readFileSync("custom_components/cl_bb_manager/manifest.json","utf8"));
  assert.ok(source.includes(`/cl_bb_manager_static/cl-impianti-logo.svg?v=${manifest.version}`));
  assert.ok(css.includes(".brand-logo{"));
  assert.ok(!css.includes(".brand-mark{"));
  assert.ok(logo.includes('viewBox="355 90 840 750"'));
  assert.ok(logo.includes('data:image/png;base64,'));
});

test("Operatori vedono solo prenotazioni e accessi, non configurazione varchi", () => {
  assert.ok(source.includes('this.data.role!=="admin"'));
  assert.ok(source.includes('["varchi","impostazioni"].includes(id)'));
  assert.ok(source.includes('if(this.data.role==="admin"){'));
  assert.ok(source.includes('g.demo_allowed===true'));
  assert.ok(source.includes('this.api("public_pilot_qr"'));
  assert.ok(source.includes('this.api("demo_qr"'));
});

test("L'interfaccia non usa l'account locale per decidere i diritti", () => {
  assert.ok(!source.includes('this._hass.user.is_admin'));
  assert.ok(!source.includes('this._hass?.user?.is_admin'));
  assert.ok(source.includes('this.data.role'));
});

test("Operatori consultano il registro accessi e non la configurazione tecnica", () => {
  assert.ok(source.includes('const history=this.card("Registro accessi")'));
  assert.ok(source.includes('this.data.access_history||[]'));
  assert.ok(source.includes('if(this.data.role!=="admin")return;'));
  assert.ok(source.includes('entry.guest_name||entry.room'));
  assert.ok(source.includes('Intestatario prenotazione (facoltativo)'));
  assert.ok(source.includes('guest_name:String(data.get("guest_name")||"").trim()'));
});


test("LAN e Internet hanno contenitore responsive e selezione leggibile",()=>{
  const css=readFileSync("custom_components/cl_bb_manager/frontend/bluetech-glass.css","utf8");
  assert.ok(source.includes('this.node("div","","connection-modes")'));
  assert.ok(source.includes('internet.setAttribute("aria-pressed"'));
  assert.ok(source.includes('local.setAttribute("aria-pressed"'));
  assert.ok(css.includes(".connection-modes{display:grid"));
  assert.ok(css.includes("grid-template-columns:minmax(0,1fr);gap:14px"));
});
