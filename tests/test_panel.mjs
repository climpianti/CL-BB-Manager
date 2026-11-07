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
  assert.ok(source.includes('this.tab="collaudo"'));
  assert.ok(source.includes('this.demoTargetGateId=gate.id'));
  assert.ok(source.includes("L\u0027accesso permanente non è ancora disponibile."));
});


test("L'URL esterno HA è la modalità QR predefinita e la LAN è opzionale", () => {
  assert.ok(source.includes('this.qrMode="https"'));
  assert.ok(source.includes('this._hass?.config?.external_url'));
  assert.ok(source.includes('this._hass?.config?.internal_url'));
  assert.ok(source.includes('if(this.qrMode==="https")grid.append(publicCard)'));
  assert.ok(source.includes('if(this.qrMode==="lan")grid.append(qrCard)'));
  assert.ok(source.includes('this.api("public_pilot_qr"'));
  assert.ok(source.includes('this.api("demo_qr"'));
});


test("CL Control BlueTech Glass conserva navigazione e stati di collaudo", () => {
  assert.ok(source.includes("bluetech-glass.css"));
  assert.ok(source.includes('"dashboard","Panoramica"'));
  assert.ok(source.includes('"accessi","Accessi"'));
  assert.ok(source.includes('"impostazioni","Impostazioni"'));
  assert.ok(source.includes('"Genera QR di accesso"'));
  assert.ok(source.includes('Ambiente pilota · solo varchi virtuali'));
  assert.ok(!source.includes('this.button("Scarica QR"'));
});
