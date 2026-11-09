import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import {parseHTML} from "linkedom";

const source=readFileSync("custom_components/cl_bb_manager/frontend/panel.js","utf8");
const manifest=JSON.parse(readFileSync("custom_components/cl_bb_manager/manifest.json","utf8"));
const gate={id:"door-a",name:"Entrance",kind:"shared",enabled:true,physical_enabled:true,physical_qr_prepared:true,entity_id:"switch.entrance",action:"switch.turn_on",pulse_seconds:2};
const snapshot=(role="admin")=>({structure:"Customer property",role,gates:[{...gate}],bookings:[],events:[],access_history:[],hardware_control:"enabled",public_origin:"https://hotel.example.org",public_access_enabled:true});
const settle=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};

function setup(response=snapshot(),overrides={}){
 const {window,document}=parseHTML("<!doctype html><html><body></body></html>");
 let Panel;
 const calls=[];
 const context={HTMLElement:window.HTMLElement,document,customElements:{get:name=>window.customElements.get(name),define(name,ctor){Panel=ctor;window.customElements.define(name,ctor);}},
  navigator:{clipboard:{writeText:async()=>{}}},confirm:()=>true,Date,console,...overrides};
 context.FormData=class{constructor(form){this.values=[...form.querySelectorAll("input,select")].filter(n=>n.name).map(n=>[n.name,n.value]);}get(name){return this.values.find(([key])=>key===name)?.[1];}[Symbol.iterator](){return this.values[Symbol.iterator]();}};
 runInNewContext(source,context);
 const panel=document.createElement("cl-bb-manager-panel");document.body.append(panel);
 const hass={user:{id:"current-user"},connection:{},callWS:async request=>{calls.push(request);if(request.type==="cl_bb_manager/list")return typeof response==="function"?response(request):response;if(request.type==="cl_bb_manager/shelly_relays")return {relays:[{entity_id:"switch.new_door",name:"New door",model:"Shelly 1 Mini Gen3"}]};if(request.type==="cl_bb_manager/physical_qr")return {gate_id:"door-a",name:"Entrance",svg:"<svg/>"};return snapshot();}};
 return {panel,hass,calls,document,Panel,context};
}
function button(panel,text){return [...panel.shadowRoot.querySelectorAll("button")].find(n=>n.textContent===text);}


test("Renders the real DOM with customer branding and no retired modes",async()=>{
 const {panel,hass}=setup();panel.hass=hass;await settle();
 for(const tab of ["dashboard","prenotazioni","accessi","registro","varchi","impostazioni"]){panel.go(tab);const text=panel.shadowRoot.querySelector("main").textContent;assert.doesNotMatch(text,/demo|pilota|virtual[ei]|qr temporane[oi]|non stampare/i);}
 assert.equal(panel.shadowRoot.querySelector("img.brand-logo").getAttribute("alt"),"CL Impianti");
 assert.ok(panel.shadowRoot.querySelector("img.brand-logo").src.endsWith("?v="+manifest.version));
});

test("Selected operators see bookings, permanent QR and history, not setup",async()=>{
 const {panel,hass}=setup(snapshot("operator"));panel.hass=hass;await settle();
 assert.ok(button(panel,"Prenotazioni"));assert.ok(button(panel,"QR delle porte"));assert.ok(button(panel,"Registro accessi"));
 assert.equal(button(panel,"Varchi"),undefined);assert.equal(button(panel,"Impostazioni"),undefined);
 panel.go("varchi");assert.doesNotMatch(panel.shadowRoot.querySelector("main").textContent,/Aggiungi varco Shelly|Configura e prepara QR/);
 assert.ok(!source.includes("this._hass.user.is_admin"));
});

test("Permission failure can be retried after the operator is enabled",async()=>{
 let allowed=false;
 const {panel,hass}=setup(()=>{if(!allowed)throw {code:"unauthorized",message:"Utente non autorizzato."};return snapshot("operator");});
 panel.hass=hass;await settle();assert.match(panel.shadowRoot.querySelector("main").textContent,/Utente non autorizzato/);
 assert.equal(panel.data,null);allowed=true;button(panel,"Riprova accesso").click();await settle();
 assert.equal(panel.data.role,"operator");assert.ok(button(panel,"Prenotazioni"));
});

test("Switching accounts clears codes and ignores an older response",async()=>{
 let release;const pending=new Promise(resolve=>release=resolve);
 const {panel,hass}=setup(()=>pending);panel.hass=hass;await settle();panel.pin="private-code";
 panel.hass={user:{id:"other-user"},connection:{},callWS:async()=>snapshot("operator")};await settle();
 assert.equal(panel.pin,"");assert.equal(panel.data.role,"operator");
 release(snapshot("admin"));await settle();assert.equal(panel.data.role,"operator");assert.equal(button(panel,"Varchi"),undefined);
});

test("Permanent QR display reads existing credentials and does not rotate",async()=>{
 const {panel,hass,calls}=setup(snapshot("operator"));panel.hass=hass;await settle();panel.go("accessi");
 button(panel,"Mostra / scarica QR").click();await settle();
 assert.ok(calls.some(r=>r.type==="cl_bb_manager/physical_qr"));
 assert.ok(!calls.some(r=>/prepare|rotate|demo|arm|open/.test(r.type)));
 assert.equal(panel.shadowRoot.querySelector("a[download]").download,"CL-BB-QR-door-a.svg");
});

test("Setup offers actual devices and sends one explicit configuration request",async()=>{
 const {panel,hass,calls}=setup();panel.hass=hass;await settle();panel.go("varchi");button(panel,"Cerca dispositivi").click();await settle();
 const form=panel.shadowRoot.querySelector('input[name="pulse_seconds"]').closest("form");
 form.reportValidity=()=>true;form.querySelector('input[name="name"]').value="New entrance";
 form.dispatchEvent(new panel.ownerDocument.defaultView.Event("submit",{cancelable:true}));await settle();
 const request=calls.find(r=>r.type==="cl_bb_manager/add_shelly_gate");
 assert.ok(request);assert.equal(request.confirm,true);assert.equal(request.pulse_seconds,2);
 assert.equal(request.entity_id,"switch.new_door");assert.ok(!calls.some(r=>/script|arm_physical|open/.test(r.type)));
});

test("Declining setup confirmation performs no configuration",async()=>{
 const {panel,hass,calls}=setup(snapshot(),{confirm:()=>false});panel.hass=hass;await settle();panel.go("varchi");button(panel,"Cerca dispositivi").click();await settle();
 const form=panel.shadowRoot.querySelector('input[name="pulse_seconds"]').closest("form");form.reportValidity=()=>true;
 form.dispatchEvent(new panel.ownerDocument.defaultView.Event("submit",{cancelable:true}));await settle();
 assert.ok(!calls.some(r=>r.type==="cl_bb_manager/add_shelly_gate"));
});

test("Booking form rejects empty gate selection before requesting a PIN",async()=>{
 const {panel,hass,calls}=setup(snapshot("operator"));panel.hass=hass;await settle();panel.go("prenotazioni");
 const form=panel.shadowRoot.querySelector("form");form.querySelector('[name="room"]').value="Room";
 form.querySelector('[name="start"]').value="2099-01-01T12:00";form.querySelector('[name="end"]').value="2099-01-02T12:00";
 form.dispatchEvent(new panel.ownerDocument.defaultView.Event("submit",{cancelable:true}));await settle();
 assert.match(form.textContent,/Seleziona almeno un varco/);assert.ok(!calls.some(r=>r.type==="cl_bb_manager/add_booking"));
});

test("Names are rendered as text and never injected as HTML",async()=>{
 const data=snapshot();data.structure='<img src=x onerror="alert(1)">';data.gates[0].name='<script>alert(1)</script>';
 const {panel,hass}=setup(data);panel.hass=hass;await settle();
 assert.equal(panel.shadowRoot.querySelector("script"),null);assert.equal(panel.shadowRoot.querySelector("img[onerror]"),null);
 assert.ok(panel.shadowRoot.querySelector("main").textContent.includes(data.structure));
});

test("BlueTech Glass stylesheet retains responsive layout and keyboard focus",()=>{
 const css=readFileSync("custom_components/cl_bb_manager/frontend/bluetech-glass.css","utf8");
 for(const required of ["#061324","#19baff","#32e394","backdrop-filter:blur","@media(max-width:740px)",":focus-visible"])assert.ok(css.includes(required));
});

test("Error messages support both WS envelopes and a readable fallback",()=>{
 const {Panel}=setup();assert.equal(Panel.prototype.describeError({error:{message:"Invalid request"}}),"Invalid request");
 assert.match(Panel.prototype.describeError({code:"unknown"}),/Operazione non riuscita/);
});
