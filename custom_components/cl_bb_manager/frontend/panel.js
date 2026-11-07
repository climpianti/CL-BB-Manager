class ClBbManagerPanel extends HTMLElement {
 constructor(){super();this.attachShadow({mode:"open"});this.loaded=false;this.tab="varchi";this.data=null;this.error="";this.pin="";this.testResult=null;this.testBusy=false;this.demoQR=null;this.demoTargetGateId=null;this.qrMode="https";}
 set hass(h){this._hass=h;if(!this.loaded){this.loaded=true;this.load();}}
 api(type,body={}){return this._hass.callWS({type:"cl_bb_manager/"+type,...body});}
 async load(){try{this.data=await this.api("list");this.error="";}catch(e){this.error=this.describeError(e);}this.render();}
 async act(type,body={},pin=false){try{const r=await this.api(type,body);this.pin=pin?r.pin_once:"";this.data=pin?r.data:r;this.error="";}catch(e){this.error=this.describeError(e);}this.render();}
 describeError(e){if(typeof e==="string")return e;const candidate=e?.message||e?.error?.message||e?.description||e?.error?.description;return typeof candidate==="string"&&candidate.trim()?candidate:"Operazione non riuscita. Verifica i dati inseriti e riprova.";}
 showValidation(form,message){let note=form.querySelector("[data-cl-validation]");if(!note){note=this.node("div","","notice");note.setAttribute("data-cl-validation","true");note.setAttribute("role","alert");form.prepend(note);}note.textContent=message;}
 async qr(gate){const base=prompt("URL pubblico HTTPS della struttura (es. https://accesso.esempio.it):");if(!base)return;try{const data=await this.api("qr",{gate_id:gate.id,base_url:base});const blob=new Blob([data.svg],{type:"image/svg+xml"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="qr-"+gate.name.toLowerCase().replace(/[^a-z0-9]+/g,"-")+".svg";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);this.error="QR generato. Portale ospiti attualmente disabilitato: non stamparlo per i clienti.";}catch(e){this.error=this.describeError(e);}this.render();}
 node(t,text="",cls=""){const n=document.createElement(t);n.textContent=text;n.className=cls;return n;}
 button(t,cb){const b=this.node("button",t);b.type="button";b.addEventListener("click",cb);return b;}
 field(form,label,name,type="text",value=""){const wrap=this.node("label",label);const inp=this.node("input");inp.name=name;inp.type=type;inp.value=value;inp.required=true;wrap.append(inp);form.append(wrap);return inp;}
 select(form,label,name,options,selected){const wrap=this.node("label",label);const s=this.node("select");s.name=name;for(const [v,t] of options){const o=this.node("option",t);o.value=v;o.selected=v===selected;s.append(o);}wrap.append(s);form.append(wrap);}
 card(title){const a=this.node("section","","card");a.append(this.node("h2",title));return a;}
 render(){const root=this.shadowRoot;root.replaceChildren();const style=this.node("style");
 style.textContent=":host{display:block;background:#eff4fa;color:#18314f;min-height:100%;font:14px system-ui}.page{max-width:1200px;margin:auto;padding:22px}h1{font-size:28px}h2{font-size:19px;margin-top:0}.nav{display:flex;gap:10px;overflow:auto;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:16px}.card{background:#fff;border:1px solid #dce6f2;border-radius:18px;padding:22px}button{background:#19509b;color:white;border:0;border-radius:10px;padding:11px;margin:4px;cursor:pointer}label{display:grid;gap:7px;margin:12px 0}input,select{padding:10px;border:1px solid #bbcddd;border-radius:9px;font:inherit}.item{padding:13px 0;border-bottom:1px solid #edf1f6}.small{color:#617e9f;font-size:12px;overflow-wrap:anywhere}.notice{background:#fff1e0;padding:14px;border-radius:10px;margin:10px 0}";root.append(style);
 const page=this.node("main","","page");root.append(page);page.append(this.node("div","CL IMPIANTI / HOSPITALITY","small"),this.node("h1","CL B&B Manager"),this.node("p",this.data?.structure||"Caricamento..."));
 if(this.error)page.append(this.node("div",this.error,"notice"));
 if(this.pin){const box=this.node("div","PIN generato (mostrato una volta sola): "+this.pin+" ","notice");box.append(this.button("Copia PIN",()=>navigator.clipboard?.writeText(this.pin)));page.append(box);}
 if(!this.data)return;const nav=this.node("nav","","nav");for(const [id,label] of [["varchi","Varchi"],["prenotazioni","Prenotazioni"],["registro","Registro"],["collaudo","Collaudo accessi"]])nav.append(this.button(label,()=>{this.tab=id;this.pin="";this.render();}));page.append(nav);
 const grid=this.node("div","","grid");page.append(grid);
 if(this.tab==="varchi")this.gates(grid);if(this.tab==="prenotazioni")this.bookings(grid);if(this.tab==="registro")this.events(grid);if(this.tab==="collaudo")this.testAccess(grid);
 page.append(this.node("p","ALPHA 0.5.0 — QR LAN e HTTPS temporanei; portale /guest/ permanente disattivato.","small"));
 }
 gates(grid){const list=this.card("Gestione varchi");list.append(this.node("p","I QR permanenti sono disattivati. Usa «QR di prova» per HTTPS (predefinito) oppure LAN opzionale.","notice"));for(const gate of this.data.gates){const line=this.node("div","","item");line.append(this.node("strong",gate.name),this.node("p",gate.entity_id+" · "+gate.kind+" · "+(gate.enabled?"Abilitato":"Disabilitato"),"small"));line.append(this.button("Modifica",()=>this.edit(gate,grid)));line.append(this.button("QR di prova",()=>{this.demoTargetGateId=gate.id;this.demoQR=null;this.qrMode="https";this.tab="collaudo";this.render();}));line.append(this.button(gate.enabled?"Disabilita":"Abilita",()=>this.act("update_gate",{gate_id:gate.id,name:gate.name,entity_id:gate.entity_id,action:gate.action,kind:gate.kind,enabled:!gate.enabled})));line.append(this.button("Elimina",()=>{if(confirm("Eliminare "+gate.name+"?"))this.act("remove_gate",{gate_id:gate.id});}));list.append(line);}grid.append(list);
 const card=this.card("Aggiungi varco");const form=this.node("form");this.field(form,"Nome varco","name");this.field(form,"Entità HA","entity_id");this.select(form,"Azione","action",[["script.turn_on","Script"],["button.press","Pulsante"],["lock.unlock","Serratura"]],"script.turn_on");this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],"private");const send=this.node("button","Salva varco disabilitato");send.type="submit";form.append(send);form.onsubmit=e=>{e.preventDefault();this.act("add_gate",Object.fromEntries(new FormData(form)));};card.append(form);grid.append(card);}
 edit(gate,grid){const card=this.card("Modifica "+gate.name);const form=this.node("form");this.field(form,"Nome","name","text",gate.name);this.field(form,"Entità","entity_id","text",gate.entity_id);this.select(form,"Azione","action",[["script.turn_on","Script"],["button.press","Pulsante"],["lock.unlock","Serratura"]],gate.action);this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],gate.kind);const submit=this.node("button","Salva modifiche");submit.type="submit";form.append(submit);form.onsubmit=e=>{e.preventDefault();this.act("update_gate",{...Object.fromEntries(new FormData(form)),gate_id:gate.id,enabled:gate.enabled});};card.append(form);grid.prepend(card);}
 bookings(grid){const card=this.card("Nuova prenotazione");const form=this.node("form");this.field(form,"Camera","room");this.field(form,"Check-in","start","datetime-local");this.field(form,"Check-out","end","datetime-local");const choices=this.node("div");choices.append(this.node("strong","Varchi autorizzati"));for(const gate of this.data.gates.filter(g=>g.enabled)){const label=this.node("label",gate.name);const cb=this.node("input");cb.type="checkbox";cb.value=gate.id;label.append(cb);choices.append(label);}form.append(choices);const submit=this.node("button","Genera prenotazione e PIN");submit.type="submit";form.append(submit);form.onsubmit=e=>{e.preventDefault();const data=new FormData(form);const a=new Date(data.get("start"));const b=new Date(data.get("end"));const gate_ids=[...choices.querySelectorAll("input:checked")].map(x=>x.value);if(!Number.isFinite(+a)||!Number.isFinite(+b)){this.showValidation(form,"Controlla le date del check-in e del check-out.");return;}if(b<=a){this.showValidation(form,"Il check-out deve essere successivo al check-in.");return;}if(b<=new Date()){this.showValidation(form,"Il check-out non può essere nel passato.");return;}if(!gate_ids.length){this.showValidation(form,"Seleziona almeno un varco autorizzato per questa prenotazione (per esempio Camera 1).");return;}this.act("add_booking",{room:data.get("room"),start:a.toISOString(),end:b.toISOString(),gate_ids},true);};card.append(form);grid.append(card);
 const list=this.card("Prenotazioni");for(const booking of [...this.data.bookings].reverse()){const row=this.node("div","","item");row.append(this.node("strong",booking.room),this.node("p",new Date(booking.start).toLocaleString("it-IT")+" → "+new Date(booking.end).toLocaleString("it-IT"),"small"),this.node("p",booking.revoked?"Revocata":"Non revocata","small"));if(!booking.revoked)row.append(this.button("Revoca",()=>{if(confirm("Revocare il PIN?"))this.act("revoke_booking",{booking_id:booking.id});}));list.append(row);}grid.append(list);}

 testAccess(grid){
   const card=this.card("Collaudo accessi · solo demo");
   card.append(this.node("p","Verifica autorizzazioni e PIN direttamente dall'area installatore. Nessun collegamento al portale ospiti pubblico.","small"));
   const demoScripts=new Set([
     "script.cl_bb_demo_apri_cancello","script.cl_bb_demo_apri_portone",
     "script.cl_bb_demo_apri_camera_1","script.cl_bb_demo_apri_camera_2",
     "script.cl_bb_demo_apri_camera_3"
   ]);
   const gates=this.data.gates.filter(g=>g.enabled && g.action==="script.turn_on" && demoScripts.has(g.entity_id));
   if(!gates.length){
     card.append(this.node("p","Nessun varco virtuale demo abilitato.","notice"));
     grid.append(card);return;
   }
   const form=this.node("form");
   this.select(form,"Varco da verificare","gate_id",gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const pinInput=this.field(form,"PIN temporaneo di 8 cifre","pin","password");
   pinInput.autocomplete="off";pinInput.inputMode="numeric";pinInput.pattern="[0-9]{8}";pinInput.maxLength=8;
   const buttons=this.node("div","","nav");
   const verify=this.button("Verifica PIN",()=>run(false));
   const simulate=this.button("Verifica e simula apertura",()=>run(true));
   buttons.append(verify,simulate);
   form.append(buttons);
   form.addEventListener("submit",event=>{event.preventDefault();run(false);});
   const run=async simulateOpen=>{
     if(this.testBusy || !form.reportValidity())return;
     const gate_id=form.querySelector('select[name="gate_id"]').value;
     const pin=pinInput.value;
     pinInput.value="";
     if(simulateOpen && !confirm("Simulare un impulso di 2 secondi sul solo varco virtuale selezionato?"))return;
     this.testBusy=true;
     verify.disabled=true;simulate.disabled=true;
     this.testResult=null;
     try {
       const result=await this.api("demo_check_pin",{gate_id,pin,simulate_open:simulateOpen});
       if(result.allowed){
         this.testResult={kind:"success",message:result.opened
           ?"PIN valido: comando inviato al varco virtuale selezionato."
           :"PIN valido: autorizzazione confermata, nessuna apertura eseguita."};
       }else{
         this.testResult={kind:"denied",message:"Accesso negato. PIN errato, scaduto, revocato o non valido per questo varco."};
       }
     }catch(err){
       this.testResult={kind:"error",message:"Verifica non riuscita: "+this.describeError(err).slice(0,180)};
     }finally{
       this.testBusy=false;this.render();
     }
   };
   card.append(form);
   if(this.testResult){
     const outcome=this.node("div",this.testResult.message,"notice");
     outcome.setAttribute("role","status");
     outcome.setAttribute("aria-live","polite");
     outcome.style.background=this.testResult.kind==="success"?"#e4f7eb":"#fff1e0";
     card.append(outcome);
   }
   card.append(this.node("p","I tentativi sono limitati e registrati. Il PIN non viene salvato nel browser e non compare nel registro. Usa soltanto i cinque script di prova.","small"));
   grid.append(card);
   const modeCard=this.card("Modalità QR");
   modeCard.append(this.node("p","Predefinito: indirizzo esterno HTTPS configurato in Home Assistant. LAN solo per prove su Wi-Fi.","small"));
   modeCard.append(this.button("HTTPS esterno",()=>{this.qrMode="https";this.render();}));
   modeCard.append(this.button("LAN / Wi-Fi locale",()=>{this.qrMode="lan";this.render();}));
   grid.append(modeCard);
   const publicCard=this.card("QR HTTPS esterno · 10 minuti / un utilizzo");
   const externalUrl=this._hass?.config?.external_url||"";
   publicCard.append(this.node("p",externalUrl
     ?"Indirizzo esterno Home Assistant (automatico): "+externalUrl
     :"Nessun URL esterno configurato. Impostalo in Home Assistant → Impostazioni → Sistema → Rete.",
     externalUrl?"small":"notice"));
   publicCard.append(this.node("p",
     "Solo tre varchi virtuali per il collaudo esterno. Abilita prima l'opzione " +
     "«Collaudo HTTPS» dall'integrazione Home Assistant con il dominio HTTPS " +
     "autorizzato. Nessun QR permanente viene abilitato.",
     "small"));
   const publicForm=this.node("form");
   this.select(publicForm,"Varco virtuale","gate_id",
     gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const makePublic=this.node("button","Genera QR HTTPS di prova");
   makePublic.type="submit";
   publicForm.append(makePublic);
   publicForm.onsubmit=async event=>{
     event.preventDefault();
     if(!publicForm.reportValidity() || this.testBusy)return;
     this.testBusy=true;
     makePublic.disabled=true;
     this.error="";
     try{
       const values=new FormData(publicForm);
       const result=await this.api("public_pilot_qr",{
         gate_id:String(values.get("gate_id"))
       });
       this.publicQR={
         ...result,
         expires:Date.now()+result.expires_seconds*1000,
         gate:gates.find(g=>g.id===values.get("gate_id"))?.name||"Varco demo"
       };
     }catch(err){
       this.publicQR=null;
       this.error=this.describeError(err);
     }finally{
       this.testBusy=false;
       this.render();
     }
   };
   publicCard.append(publicForm);
   if(this.publicQR && Date.now()<this.publicQR.expires){
     const preview=this.node("div");
     const img=this.node("img");
     img.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(this.publicQR.svg);
     img.width=220;
     img.height=220;
     img.alt="QR HTTPS temporaneo per "+this.publicQR.gate;
     preview.append(img);
     preview.append(this.node("p","Usa una sola volta, entro 10 minuti. Non condividere il QR pubblicamente.","small"));
     const link=this.node("a","Apri la prova HTTPS");
     link.href=this.publicQR.url;
     link.target="_blank";
     link.rel="noreferrer noopener";
     preview.append(link);
     publicCard.append(preview);
   }
   if(this.qrMode==="https")grid.append(publicCard);
   const qrCard=this.card("QR LAN / Wi-Fi locale · 10 minuti");
   qrCard.append(this.node(
     "p",
     "Questo QR usa il percorso /demo/, dura 10 minuti e richiede il PIN. " +
     "Inserisci l’indirizzo IP LAN di Home Assistant (192.168.x.x:8123), non il dominio Cloudflare. " +
     "I QR con /guest/ restituiscono 404 finché il portale permanente è disattivato.",
     "small"
   ));
   const qrForm=this.node("form");
   this.select(qrForm,"Varco virtuale","gate_id",gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const address=this.field(qrForm,"URL interno Home Assistant","base_url","url",this._hass?.config?.internal_url||"");
   address.placeholder="http://192.168.1.100:8123";
   const create=this.node("button","Genera QR demo");
   create.type="submit";
   qrForm.append(create);
   qrForm.onsubmit=async event=>{
     event.preventDefault();
     if(!qrForm.reportValidity() || this.testBusy)return;
     this.testBusy=true;
     create.disabled=true;
     this.error="";
     try{
       const values=new FormData(qrForm);
       const result=await this.api("demo_qr",{
         gate_id:String(values.get("gate_id")),
         base_url:String(values.get("base_url"))
       });
       this.demoQR={
         ...result,
         expires:Date.now()+result.expires_seconds*1000,
         gate:gates.find(g=>g.id===values.get("gate_id"))?.name||"Varco demo"
       };
     }catch(err){
       this.demoQR=null;
       this.error=this.describeError(err);
     }finally{
       this.testBusy=false;
       this.render();
     }
   };
   qrCard.append(qrForm);
   if(this.demoQR){
     if(Date.now()<this.demoQR.expires){
       const preview=this.node("div");
       const img=this.node("img");
       img.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(this.demoQR.svg);
       img.width=220;
       img.height=220;
       img.alt="QR di collaudo temporaneo per "+this.demoQR.gate;
       preview.append(img);
       preview.append(this.node("p","Scansiona il QR con lo smartphone connesso alla stessa rete locale.","small"));
       const link=this.node("a","Apri il collegamento di prova");
       link.href=this.demoQR.url;
       link.target="_blank";
       link.rel="noreferrer noopener";
       preview.append(link);
       qrCard.append(preview);
     }else{
       this.demoQR=null;
       qrCard.append(this.node("p","QR scaduto: genera una nuova sessione.","notice"));
     }
   }
   if(this.qrMode==="lan")grid.append(qrCard);
   const info=this.card("Stato di sicurezza");
   info.append(this.node("p","Portale QR ospiti: disattivato","small"),
               this.node("p","Target consentiti: cinque script virtuali demo","small"),
               this.node("p","Attivazione comandi reali: non prevista in questa versione","small"));
   grid.append(info);
 }
 events(grid){const card=this.card("Registro modifiche");for(const event of [...this.data.events].reverse()){const row=this.node("div","","item");row.append(this.node("strong",event.event),this.node("p",new Date(event.at).toLocaleString("it-IT")+" · "+event.details,"small"));card.append(row);}grid.append(card);}
}
if (!customElements.get("cl-bb-manager-panel")) { customElements.define("cl-bb-manager-panel",ClBbManagerPanel); }
