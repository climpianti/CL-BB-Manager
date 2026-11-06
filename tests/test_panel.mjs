import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

let Panel;
const source = readFileSync("custom_components/cl_bb_manager/frontend/panel.js", "utf8");
runInNewContext(source, {
  HTMLElement: class {},
  customElements: {
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
