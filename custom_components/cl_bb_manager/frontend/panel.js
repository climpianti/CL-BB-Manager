class ClBbManagerPanel extends HTMLElement {
 constructor(){super();this.attachShadow({mode:"open"});this.loaded=false;this.tab="dashboard";this.data=null;this.error="";this.pin="";this.qr=null;this.selectedGate=null;this.relays=null;this.busy=false;this.requestId=0;this.userId=null;this.connection=null;this.generation=0;this.operationId=0;}
 set hass(h){
  const userId=h?.user?.id||null, connection=h?.connection;
  if(this.userId!==userId || (this.connection && this.connection!==connection)){
   this.loaded=false;this.data=null;this.pin="";this.qr=null;this.relays=null;this.tab="dashboard";this.requestId++;this.generation++;this.operationId++;this.busy=false;
  }
  this.userId=userId;this.connection=connection;this._hass=h;
  if(!this.loaded && typeof h?.callWS==="function"){this.loaded=true;this.load();}
 }
 api(type,body={}){return this._hass.callWS({type:"cl_bb_manager/"+type,...body});}
 async load(){const requestId=++this.requestId;try{const data=await this.api("list");if(requestId!==this.requestId)return;this.data=data;this.error="";if(data.role!=="admin" && ["varchi","impostazioni"].includes(this.tab))this.tab="dashboard";}catch(e){if(requestId!==this.requestId)return;this.data=null;this.pin="";this.qr=null;this.error=this.describeError(e);}this.render();}
 async act(type,body={},pin=false){if(this.busy)return;const generation=this.generation,operationId=++this.operationId;this.busy=true;try{const result=await this.api(type,body);if(generation!==this.generation)return;this.pin=pin?result.pin_once:"";this.qr=null;await this.load();}catch(e){if(generation===this.generation)this.error=this.describeError(e);}finally{if(operationId===this.operationId && generation===this.generation){this.busy=false;this.render();}}}
 describeError(e){if(typeof e==="string")return e;const candidate=e?.message||e?.error?.message||e?.description||e?.error?.description;return typeof candidate==="string"&&candidate.trim()?candidate:"Operazione non riuscita. Verifica i dati inseriti e riprova.";}
 showValidation(form,message){let note=form.querySelector("[data-cl-validation]");if(!note){note=this.node("div","","notice");note.setAttribute("data-cl-validation","true");note.setAttribute("role","alert");form.prepend(note);}note.textContent=message;}
 node(type,text="",cls=""){const n=document.createElement(type);n.textContent=text;n.className=cls;return n;}
 button(text,action){const b=this.node("button",text);b.type="button";b.disabled=this.busy;b.addEventListener("click",action);return b;}
 field(form,label,name,type="text",value=""){const wrap=this.node("label",label),input=this.node("input");input.name=name;input.type=type;input.value=value;input.required=true;wrap.append(input);form.append(wrap);return input;}
 select(form,label,name,options,selected){const wrap=this.node("label",label),s=this.node("select");s.name=name;for(const [value,text] of options){const o=this.node("option",text);o.value=value;o.selected=value===selected;s.append(o);}wrap.append(s);form.append(wrap);return s;}
 card(title,cls=""){const card=this.node("section","","card "+cls);card.append(this.node("h2",title));return card;}
 go(tab){this.tab=tab;this.pin="";this.qr=null;this.render();}
 armed(gate){return gate.physical_enabled && this.data.hardware_control==="enabled";}
 render(){
  const root=this.shadowRoot;root.replaceChildren();const style=this.node("style");style.textContent="@import url('/cl_bb_manager_static/bluetech-glass.css?v=0.6.0-beta.1');";root.append(style);
  const page=this.node("main","","page"),hero=this.node("header","","hero");root.append(page);
  const brand=this.node("div","","hero-brand"),logo=this.node("img");logo.src="/cl_bb_manager_static/cl-impianti-logo.svg?v=0.6.0-beta.1";logo.alt="CL Impianti";logo.className="brand-logo";brand.append(logo);
  const word=this.node("span","","brand-word");word.append(this.node("strong","CL B&B MANAGER"),this.node("small","Gestione struttura e accessi"));brand.append(word);
  hero.append(brand,this.node("h1",this.data?.structure||"CL B&B Manager"),this.node("p","Prenotazioni, codici personali e accessi alla struttura","subtitle"));page.append(hero);
  if(this.error){const note=this.node("div",this.error,"notice");note.setAttribute("role","alert");page.append(note);}
  if(!this.data){page.append(this.button("Riprova accesso",()=>this.load()));return;}
  if(this.pin){const note=this.node("div","Codice di accesso generato · visibile una sola volta: "+this.pin+" ","notice");note.append(this.button("Copia codice",()=>navigator.clipboard?.writeText(this.pin)));page.append(note);}
  const nav=this.node("nav","","nav");
  for(const [id,label] of [["dashboard","Panoramica"],["prenotazioni","Prenotazioni"],["accessi","QR delle porte"],["registro","Registro accessi"],["varchi","Varchi"],["impostazioni","Impostazioni"]]){
   if(this.data.role!=="admin" && ["varchi","impostazioni"].includes(id))continue;
   const b=this.button(label,()=>this.go(id));if(this.tab===id)b.classList.add("active");nav.append(b);
  }
  nav.append(this.button("Aggiorna",()=>this.load()));page.append(nav);
  const grid=this.node("div","","grid");page.append(grid);
  if(this.tab==="dashboard")this.dashboard(grid);
  if(this.tab==="prenotazioni")this.bookings(grid);
  if(this.tab==="accessi")this.accesses(grid);
  if(this.tab==="registro")this.events(grid);
  if(this.data.role==="admin" && this.tab==="varchi")this.gates(grid);
  if(this.data.role==="admin" && this.tab==="impostazioni")this.settings(grid);
  page.append(this.node("p","CL Impianti · Gestione accessi della struttura","footer-note"));
 }
 dashboard(grid){
  const all=this.data.gates||[],bookings=this.data.bookings||[],metrics=this.node("div","","metrics");
  for(const [label,value] of [["Porte attive",all.filter(g=>this.armed(g)).length],["Prenotazioni valide",bookings.filter(b=>!b.revoked&&new Date(b.end)>new Date()).length],["Varchi configurati",all.length]]){
   const box=this.node("div","","metric");box.append(this.node("strong",String(value)),this.node("span",label));metrics.append(box);
  }grid.append(metrics);
  const welcome=this.card("Gestisci la struttura");welcome.append(this.node("p","Crea una prenotazione, scegli le porte autorizzate e consegna il codice personale all'ospite. I QR delle porte restano validi: è il codice a seguire le date del soggiorno."));
  welcome.append(this.button("Nuova prenotazione",()=>this.go("prenotazioni")),this.button("QR delle porte",()=>this.go("accessi")));grid.append(welcome);
  const doors=this.card("Stato delle porte");for(const gate of all)doors.append(this.node("p",gate.name+" · "+(this.armed(gate)?"Accesso attivo":gate.physical_qr_prepared?"Inattivo":"Da configurare")));if(!all.length)doors.append(this.node("p","Aggiungi il primo varco da Impostazioni dell'integrazione o dalla sezione Varchi."));grid.append(doors);
 }
 bookings(grid){
  const card=this.card("Nuova prenotazione"),form=this.node("form");this.field(form,"Camera / Unità","room");const guest=this.field(form,"Intestatario prenotazione (facoltativo)","guest_name");guest.required=false;guest.maxLength=80;
  this.field(form,"Check-in","start","datetime-local");this.field(form,"Check-out","end","datetime-local");const choices=this.node("div");choices.append(this.node("strong","Varchi autorizzati"));
  for(const gate of this.data.gates.filter(g=>g.enabled && g.physical_qr_prepared)){
   const label=this.node("label",gate.name+(this.armed(gate)?"":" · attualmente inattivo")),cb=this.node("input");cb.type="checkbox";cb.value=gate.id;label.append(cb);choices.append(label);
  }form.append(choices);const submit=this.node("button","Crea prenotazione e codice");submit.type="submit";submit.disabled=this.busy;form.append(submit);
  form.onsubmit=e=>{e.preventDefault();const data=new FormData(form),start=new Date(data.get("start")),end=new Date(data.get("end"));const gate_ids=[...choices.querySelectorAll("input:checked")].map(x=>x.value);
   if(!Number.isFinite(+start)||!Number.isFinite(+end)||end<=start){this.showValidation(form,"Il check-out deve essere successivo al check-in.");return;}
   if(end<=new Date()){this.showValidation(form,"Il check-out non può essere nel passato.");return;}
   if(!gate_ids.length){this.showValidation(form,"Seleziona almeno un varco autorizzato per questa prenotazione.");return;}
   this.act("add_booking",{room:data.get("room"),guest_name:String(data.get("guest_name")||"").trim(),start:start.toISOString(),end:end.toISOString(),gate_ids},true);
  };card.append(form);grid.append(card);
  const list=this.card("Prenotazioni");for(const booking of [...this.data.bookings].reverse()){
   const row=this.node("div","","item");row.append(this.node("strong",booking.room),this.node("p",booking.guest_name||"","small"),this.node("p",new Date(booking.start).toLocaleString("it-IT")+" → "+new Date(booking.end).toLocaleString("it-IT"),"small"));
   const effective=booking.physical_gate_ids||[];row.append(this.node("p",booking.revoked?"Revocata":"Porte autorizzate: "+this.data.gates.filter(g=>effective.includes(g.id)).map(g=>g.name).join(", "),"small"));
   if(!booking.revoked)row.append(this.button("Revoca codice",()=>{if(confirm("Revocare il codice di questa prenotazione?"))this.act("revoke_booking",{booking_id:booking.id});}));list.append(row);
  }grid.append(list);
 }
 accesses(grid){
  const card=this.card("QR permanente della porta"),gates=this.data.gates.filter(g=>g.physical_qr_prepared);
  card.append(this.node("p","Stampa il QR e applicalo accanto alla porta. Ogni ospite usa il proprio codice, valido soltanto per le date e le porte autorizzate."));
  if(!gates.length){card.append(this.node("p","Nessun QR predisposto. L'amministratore deve configurare i varchi."));grid.append(card);return;}
  const form=this.node("form"),select=this.select(form,"Porta","gate_id",gates.map(g=>[g.id,g.name]),this.selectedGate||gates[0].id);
  select.addEventListener("change",()=>{this.selectedGate=select.value;this.qr=null;this.render();});form.addEventListener("submit",e=>e.preventDefault());card.append(form);
  const gate=gates.find(g=>g.id===(this.selectedGate||select.value))||gates[0];card.append(this.node("p",this.armed(gate)?"Porta abilitata":"Porta inattiva · il QR non consente aperture","notice"));
  card.append(this.button("Mostra / scarica QR",async()=>{const generation=this.generation;try{const qr=await this.api("physical_qr",{gate_id:gate.id});if(generation!==this.generation)return;this.qr=qr;this.error="";}catch(e){if(generation!==this.generation)return;this.error=this.describeError(e);}this.render();}));grid.append(card);
  if(this.qr?.gate_id===gate.id){const preview=this.card(gate.name,"qr-print"),img=this.node("img");img.width=260;img.height=260;img.alt="QR di accesso a "+gate.name;const src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(this.qr.svg);img.src=src;preview.append(img);const dl=this.node("a","Scarica QR SVG");dl.href=src;dl.download="CL-BB-QR-"+gate.id+".svg";preview.append(dl);grid.append(preview);}
 }
 gates(grid){
  const list=this.card("Varchi della struttura");for(const gate of this.data.gates){
   const row=this.node("div","","item");row.append(this.node("strong",gate.name),this.node("p",(gate.kind==="shared"?"Accesso comune":"Accesso privato")+" · "+(this.armed(gate)?"Attivo":"Inattivo"),"small"));
   if(gate.pulse_seconds)row.append(this.node("p","Impulso: "+gate.pulse_seconds+" s","small"));
   row.append(this.button("Modifica nome / tipo",()=>this.edit(gate,grid)));
   if(gate.physical_qr_prepared){row.append(this.button("QR della porta",()=>{this.selectedGate=gate.id;this.go("accessi");}));row.append(this.button(this.armed(gate)?"Disattiva accesso":"Abilita accesso",()=>{
    if(this.armed(gate)){if(confirm("Disattivare gli accessi con codice a "+gate.name+"? Il QR viene conservato."))this.act("disarm_physical_gate",{gate_id:gate.id,confirm:true});}
    else if(confirm("Confermi di aver verificato il collegamento elettrico e la durata dell'impulso per "+gate.name+"? L'abilitazione consente agli ospiti autorizzati di aprire la porta."))this.act("arm_physical_gate",{gate_id:gate.id,confirm:true,confirm_wiring:true});
   }));}
   row.append(this.button(gate.physical_qr_prepared?"Revoca e sostituisci QR":"Prepara nuovo QR",()=>{if(confirm("Creare un nuovo QR per "+gate.name+"? Il precedente non funzionerà più e il varco resterà inattivo fino alla nuova abilitazione."))this.act("prepare_physical_qr",{gate_id:gate.id,confirm:true});}));
   row.append(this.button("Elimina varco",()=>{if(confirm("Eliminare "+gate.name+" dal gestionale? Le prenotazioni valide possono impedirne la rimozione."))this.act("remove_gate",{gate_id:gate.id});}));list.append(row);
  }grid.append(list);
  const setup=this.card("Aggiungi varco Shelly");setup.append(this.node("p","Seleziona un relè Shelly 1 Mini Gen3 già aggiunto a Home Assistant. La procedura imposta il profilo ad impulso, verifica le impostazioni e prepara il QR. Non invia comandi di apertura."));
  setup.append(this.button("Cerca dispositivi",async()=>{const generation=this.generation;try{const result=await this.api("shelly_relays");if(generation!==this.generation)return;this.relays=result.relays;this.error="";}catch(e){if(generation!==this.generation)return;this.error=this.describeError(e);}this.render();}));
  if(this.relays?.length){const form=this.node("form");this.field(form,"Nome varco","name");this.select(form,"Shelly / uscita","entity_id",this.relays.map(r=>[r.entity_id,r.name+" · "+r.model]),this.relays[0].entity_id);const duration=this.field(form,"Durata impulso (secondi)","pulse_seconds","number",2);duration.min=.5;duration.max=5;duration.step=.5;this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],"private");const save=this.node("button","Configura e prepara QR");save.type="submit";save.disabled=this.busy;form.append(save);form.onsubmit=e=>{e.preventDefault();if(!form.reportValidity())return;if(!confirm("Applicare al relè selezionato il profilo apriporta? Avvio spento, accensione automatica disabilitata e spegnimento automatico dopo l'impulso. Il varco resterà inattivo."))return;const values=Object.fromEntries(new FormData(form));this.act("add_shelly_gate",{...values,pulse_seconds:Number(values.pulse_seconds),confirm:true});};setup.append(form);}
  else if(this.relays)setup.append(this.node("p","Nessun dispositivo compatibile pronto. Aggiungi lo Shelly in Home Assistant, controlla che sia online e con uscita OFF, poi ripeti la ricerca.","notice"));grid.append(setup);
  const emergency=this.card("Blocco accessi");emergency.append(this.node("p","Il blocco di emergenza revoca tutti i QR e i relativi permessi. I QR stampati dovranno essere sostituiti."),this.button("Blocca e revoca tutti i QR",()=>{if(confirm("Revocare tutti i QR e tutti i permessi fisici della struttura?"))this.act("emergency_disable_physical",{confirm:true});}));grid.append(emergency);
 }
 edit(gate,grid){const card=this.card("Modifica "+gate.name),form=this.node("form");this.field(form,"Nome","name","text",gate.name);this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],gate.kind);const submit=this.node("button","Salva modifiche");submit.type="submit";form.append(submit);form.onsubmit=e=>{e.preventDefault();this.act("update_gate",{...Object.fromEntries(new FormData(form)),gate_id:gate.id,entity_id:gate.entity_id,action:gate.action,enabled:gate.enabled});};card.append(form);grid.prepend(card);}
 settings(grid){
  const addresses=this.card("Accesso degli ospiti");addresses.append(this.node("p",this.data.public_origin||"Indirizzo HTTPS non configurato"),this.node("p",this.data.public_access_enabled?"Accesso HTTPS abilitato":"Accesso HTTPS disabilitato"));addresses.append(this.node("p","L'indirizzo viene letto dalle impostazioni di rete di Home Assistant. Le autorizzazioni degli operatori e l'accesso HTTPS si modificano nelle opzioni dell'integrazione.","small"));grid.append(addresses);
  const roles=this.card("Permessi utenti");roles.append(this.node("p","Gli amministratori configurano dispositivi e operatori. Gli operatori abilitati gestiscono prenotazioni, codici personali, QR e registro accessi. Gli altri account non hanno accesso al gestionale."));grid.append(roles);
 }
 events(grid){
  const history=this.card("Registro accessi");for(const entry of [...(this.data.access_history||[])].reverse()){const row=this.node("div","","item");row.append(this.node("strong",entry.gate_name||"Porta"),this.node("p",(entry.guest_name||entry.room||"Ospite")+" · "+new Date(entry.at).toLocaleString("it-IT"),"small"),this.node("p",entry.result==="authorized"?"Comando autorizzato":"Accesso negato","small"));history.append(row);}grid.append(history);
  if(this.data.role!=="admin")return;const admin=this.card("Registro amministrativo");for(const event of [...(this.data.events||[])].reverse()){const row=this.node("div","","item");row.append(this.node("strong",({booking_added:"Prenotazione creata",booking_revoked:"Codice revocato",gate_updated:"Varco modificato",gate_removed:"Varco rimosso",shelly_gate_configured:"Shelly configurato",physical_gate_armed_permanent:"Accesso porta abilitato",physical_gate_disarmed:"Accesso porta disabilitato",physical_command_sent:"Comando di apertura inviato",physical_denied:"Accesso negato",physical_emergency_disabled:"Blocco di emergenza",physical_qr_prepared_dormant:"QR della porta predisposto"})[event.event]||"Operazione registrata"),this.node("p",new Date(event.at).toLocaleString("it-IT"),"small"));admin.append(row);}grid.append(admin);
 }
}
if(!customElements.get("cl-bb-manager-panel"))customElements.define("cl-bb-manager-panel",ClBbManagerPanel);
