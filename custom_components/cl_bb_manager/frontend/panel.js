class ClBbManagerPanel extends HTMLElement {
 constructor(){super();this.attachShadow({mode:"open"});this.loaded=false;this.tab="dashboard";this.data=null;this.error="";this.pin="";this.testResult=null;this.testBusy=false;this.demoQR=null;this.permanentQR=null;this.demoTargetGateId=null;this.qrMode="https";}
 set hass(h){this._hass=h;if(!this.loaded){this.loaded=true;this.load();}}
 api(type,body={}){return this._hass.callWS({type:"cl_bb_manager/"+type,...body});}
 async load(){try{this.data=await this.api("list");this.error="";}catch(e){this.error=this.describeError(e);}this.render();}
 async act(type,body={},pin=false){try{const r=await this.api(type,body);this.pin=pin?r.pin_once:"";this.data=pin?r.data:r;this.error="";}catch(e){this.error=this.describeError(e);}this.render();}
 describeError(e){if(typeof e==="string")return e;const candidate=e?.message||e?.error?.message||e?.description||e?.error?.description;return typeof candidate==="string"&&candidate.trim()?candidate:"Operazione non riuscita. Verifica i dati inseriti e riprova.";}
 showValidation(form,message){let note=form.querySelector("[data-cl-validation]");if(!note){note=this.node("div","","notice");note.setAttribute("data-cl-validation","true");note.setAttribute("role","alert");form.prepend(note);}note.textContent=message;}
 node(t,text="",cls=""){const n=document.createElement(t);n.textContent=text;n.className=cls;return n;}
 button(t,cb){const b=this.node("button",t);b.type="button";b.addEventListener("click",cb);return b;}
 field(form,label,name,type="text",value=""){const wrap=this.node("label",label);const inp=this.node("input");inp.name=name;inp.type=type;inp.value=value;inp.required=true;wrap.append(inp);form.append(wrap);return inp;}
 select(form,label,name,options,selected){const wrap=this.node("label",label);const s=this.node("select");s.name=name;for(const [v,t] of options){const o=this.node("option",t);o.value=v;o.selected=v===selected;s.append(o);}wrap.append(s);form.append(wrap);}
 card(title){const a=this.node("section","","card");a.append(this.node("h2",title));return a;}
 render(){const root=this.shadowRoot;root.replaceChildren();const style=this.node("style");
 style.textContent="@import url('/cl_bb_manager_static/bluetech-glass.css?v=0.5.0-alpha.11');";root.append(style);
 const page=this.node("main","","page");root.append(page);const hero=this.node("header","","hero");
 const brand=this.node("div","","hero-brand");
 const logo=this.node("img");logo.src="/cl_bb_manager_static/cl-impianti-logo.svg?v=0.5.0-alpha.11";logo.alt="CL Impianti";logo.className="brand-logo";logo.decoding="async";brand.append(logo);
 const brandText=this.node("span","","brand-word");
 brandText.append(this.node("strong","CL CONTROL"),this.node("small","Hospitality · Access Manager"));
 brand.append(brandText);
 hero.append(brand,this.node("h1",this.data?.structure||"CL B&B Manager"),this.node("p","Gestione prenotazioni, varchi e autorizzazioni","subtitle"));
 const context=this.node("div","","context");
 context.append(this.node("span","Gestione accessi","tag safe"),this.node("span","Ambiente pilota · solo varchi virtuali","tag"));
 hero.append(context);page.append(hero);
 if(this.error)page.append(this.node("div",this.error,"notice"));
 if(this.pin){const box=this.node("div","Codice di accesso generato · visibile una sola volta: "+this.pin+" ","notice");box.append(this.button("Copia codice",()=>navigator.clipboard?.writeText(this.pin)));page.append(box);}
 if(!this.data)return;const nav=this.node("nav","","nav");for(const [id,label] of [["dashboard","Panoramica"],["prenotazioni","Prenotazioni"],["accessi","Accessi"],["varchi","Varchi"],["registro","Registro"],["impostazioni","Impostazioni"]]){
   if(this.data.role!=="admin" && ["varchi","impostazioni"].includes(id))continue;
   const b=this.button(label,()=>{this.tab=id;this.pin="";this.render();});
   if(this.tab===id)b.classList.add("active");
   nav.append(b);
 }page.append(nav);
 const grid=this.node("div","","grid");page.append(grid);
 if(this.tab==="dashboard")this.dashboard(grid);if(this.tab==="varchi")this.gates(grid);if(this.tab==="prenotazioni")this.bookings(grid);if(this.tab==="registro")this.events(grid);if(this.tab==="accessi")this.testAccess(grid);if(this.tab==="impostazioni")this.settings(grid);
 page.append(this.node("p","Versione pilota · QR temporanei e soli varchi virtuali. Non utilizzare con porte fisiche.","footer-note"));
 }

 dashboard(grid){
   const metrics=this.node("div","","metrics");
   const all=this.data.gates||[],bookings=this.data.bookings||[];
   for(const [label,value] of [["Varchi abilitati",all.filter(g=>g.enabled).length],["Prenotazioni non revocate",bookings.filter(b=>!b.revoked&&new Date(b.end)>new Date()).length],["Varchi configurati",all.length]]){
     const metric=this.node("div","","metric");
     metric.append(this.node("strong",String(value)),this.node("span",label));
     metrics.append(metric);
   }
   grid.append(metrics);
   const welcome=this.card("Benvenuto in CL Control Hospitality");
   welcome.append(this.node("p",this.data.role==="admin"
     ?"Gestisci varchi e permessi, crea i codici di accesso e genera i QR temporanei."
     :"Crea prenotazioni con codici temporanei e genera QR dalla sezione Accessi."));
   const actions=this.node("div","","dashboard-actions");
   actions.append(this.button("Gestisci accessi",()=>{this.tab="accessi";this.render();}));
   actions.append(this.button("Nuova prenotazione",()=>{this.tab="prenotazioni";this.render();}));
   welcome.append(actions);
   grid.append(welcome);
   const status=this.card("Stato dei servizi");
   status.append(this.node("p","QR HTTPS temporanei: "+(this.data.public_pilot==="enabled"?"Abilitati":"Disabilitati")));
   status.append(this.node("p","QR fisso HTTPS virtuale: "+(this.data.permanent_pilot==="enabled"?"Abilitato (pilota)":"Disabilitato")));
   status.append(this.node("p","I comandi agiscono soltanto su varchi virtuali in questa versione.","small"));
   grid.append(status);
 }
 settings(grid){
   const addresses=this.card("Indirizzi di accesso");
   const external=this._hass?.config?.external_url||"";
   const internal=this._hass?.config?.internal_url||"";
   addresses.append(this.node("p","Indirizzo esterno Home Assistant","small"),this.node("p",external||"Non configurato"));
   addresses.append(this.node("p","Indirizzo interno Home Assistant","small"),this.node("p",internal||"Non configurato · opzionale"));
   addresses.append(this.node("p","Gli indirizzi si modificano in Home Assistant → Impostazioni → Sistema → Rete.","small"));
   grid.append(addresses);
   const security=this.card("Sicurezza e modalità di accesso");
   security.append(this.node("p","QR HTTPS temporanei: "+(this.data.public_pilot==="enabled"?"Abilitati":"Disabilitati")));
   security.append(this.node("p","QR fisso HTTPS virtuale: "+(this.data.permanent_pilot==="enabled"?"Abilitato (pilota)":"Disabilitato")));
   security.append(this.node("p","Serrature e attuatori fisici: non collegati"));
   security.append(this.node("p","I QR temporanei durano 10 minuti e, dopo un comando riuscito, non sono riutilizzabili. In questa versione funzionano esclusivamente con gli script virtuali consentiti.","small"));
   grid.append(security);
 }

 gates(grid){const list=this.card("Varchi della struttura");list.append(this.node("p","Gestisci qui i varchi e i relativi script. Per creare un QR vai nella sezione Accessi.","notice"));for(const gate of this.data.gates){const line=this.node("div","","item");line.append(this.node("strong",gate.name),this.node("p",(gate.kind==="shared"?"Accesso comune":"Accesso privato")+" · "+(gate.enabled?"Attivo":"Disattivato"),"small"));if(gate.hardware_candidate){line.append(this.node("p","Shelly predisposto: "+gate.hardware_candidate.entity_id+" · in attesa della revisione sicurezza. Il QR continua ad aprire solo il varco virtuale.","notice"));}line.append(this.button("Modifica",()=>this.edit(gate,grid)));line.append(this.button("QR di accesso",()=>{this.demoTargetGateId=gate.id;this.demoQR=null;this.qrMode="https";this.tab="accessi";this.render();}));line.append(this.button(gate.enabled?"Disattiva":"Attiva",()=>this.act("update_gate",{gate_id:gate.id,name:gate.name,entity_id:gate.entity_id,action:gate.action,kind:gate.kind,enabled:!gate.enabled})));line.append(this.button("Elimina",()=>{if(confirm("Eliminare "+gate.name+"?"))this.act("remove_gate",{gate_id:gate.id});}));list.append(line);}grid.append(list);
 const card=this.card("Nuovo varco");const form=this.node("form");this.field(form,"Nome varco","name");this.field(form,"Entità HA","entity_id");this.select(form,"Azione","action",[["script.turn_on","Script"],["button.press","Pulsante"],["lock.unlock","Serratura"]],"script.turn_on");this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],"private");const send=this.node("button","Salva varco inattivo");send.type="submit";form.append(send);form.onsubmit=e=>{e.preventDefault();this.act("add_gate",Object.fromEntries(new FormData(form)));};card.append(form);grid.append(card);}
 edit(gate,grid){const card=this.card("Modifica "+gate.name);const form=this.node("form");this.field(form,"Nome","name","text",gate.name);this.field(form,"Entità","entity_id","text",gate.entity_id);this.select(form,"Azione","action",[["script.turn_on","Script"],["button.press","Pulsante"],["lock.unlock","Serratura"]],gate.action);this.select(form,"Tipo","kind",[["private","Privato"],["shared","Comune"]],gate.kind);const submit=this.node("button","Salva modifiche");submit.type="submit";form.append(submit);form.onsubmit=e=>{e.preventDefault();this.act("update_gate",{...Object.fromEntries(new FormData(form)),gate_id:gate.id,enabled:gate.enabled});};card.append(form);grid.prepend(card);}
 bookings(grid){const card=this.card("Nuova prenotazione");const form=this.node("form");this.field(form,"Camera / Unità","room");const guest=this.field(form,"Intestatario prenotazione (facoltativo)","guest_name");guest.required=false;guest.maxLength=80;this.field(form,"Check-in","start","datetime-local");this.field(form,"Check-out","end","datetime-local");const choices=this.node("div");choices.append(this.node("strong","Varchi autorizzati"));for(const gate of this.data.gates.filter(g=>g.enabled)){const label=this.node("label",gate.name);const cb=this.node("input");cb.type="checkbox";cb.value=gate.id;label.append(cb);choices.append(label);}form.append(choices);const submit=this.node("button","Crea prenotazione e codice");submit.type="submit";form.append(submit);form.onsubmit=e=>{e.preventDefault();const data=new FormData(form);const a=new Date(data.get("start"));const b=new Date(data.get("end"));const gate_ids=[...choices.querySelectorAll("input:checked")].map(x=>x.value);if(!Number.isFinite(+a)||!Number.isFinite(+b)){this.showValidation(form,"Controlla le date del check-in e del check-out.");return;}if(b<=a){this.showValidation(form,"Il check-out deve essere successivo al check-in.");return;}if(b<=new Date()){this.showValidation(form,"Il check-out non può essere nel passato.");return;}if(!gate_ids.length){this.showValidation(form,"Seleziona almeno un varco autorizzato per questa prenotazione (per esempio Camera 1).");return;}this.act("add_booking",{room:data.get("room"),guest_name:String(data.get("guest_name")||"").trim(),start:a.toISOString(),end:b.toISOString(),gate_ids},true);};card.append(form);grid.append(card);
 const list=this.card("Prenotazioni");for(const booking of [...this.data.bookings].reverse()){const row=this.node("div","","item");row.append(this.node("strong",booking.room),this.node("p",new Date(booking.start).toLocaleString("it-IT")+" → "+new Date(booking.end).toLocaleString("it-IT"),"small"),this.node("p",booking.revoked?"Revocata":"Autorizzata per le date indicate","small"));if(!booking.revoked)row.append(this.button("Revoca",()=>{if(confirm("Revocare il PIN?"))this.act("revoke_booking",{booking_id:booking.id});}));list.append(row);}grid.append(list);}

 testAccess(grid){
   const card=this.card("Controllo autorizzazioni");
   card.append(this.node("p","Controlla i permessi dei codici e genera QR di accesso temporanei. In questa versione i comandi sono limitati ai varchi virtuali.","small"));
   const demoScripts=new Set([
     "script.cl_bb_demo_apri_cancello","script.cl_bb_demo_apri_portone",
     "script.cl_bb_demo_apri_camera_1","script.cl_bb_demo_apri_camera_2",
     "script.cl_bb_demo_apri_camera_3"
   ]);
   const gates=this.data.gates.filter(g=>g.demo_allowed===true);
   if(!gates.length){
     card.append(this.node("p","Nessun varco di accesso abilitato.","notice"));
     grid.append(card);return;
   }
   if(this.data.role==="admin"){
   const form=this.node("form");
   this.select(form,"Varco da verificare","gate_id",gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const pinInput=this.field(form,"Codice di accesso · 8 cifre","pin","password");
   pinInput.autocomplete="off";pinInput.inputMode="numeric";pinInput.pattern="[0-9]{8}";pinInput.maxLength=8;
   const buttons=this.node("div","","nav");
   const verify=this.button("Controlla codice",()=>run(false));
   const simulate=this.button("Verifica e invia comando",()=>run(true));
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
           ?"Codice valido: comando inviato al varco virtuale selezionato."
           :"Codice valido: autorizzazione confermata, nessun comando inviato."};
       }else{
         this.testResult={kind:"denied",message:"Accesso negato. Codice non valido, scaduto o senza autorizzazione per questo varco."};
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
   card.append(this.node("p","I tentativi sono limitati e registrati; il codice non viene memorizzato nel browser. Nessun attuatore fisico viene comandato.","small"));
   }else{
     card.append(this.node("p","Puoi generare QR temporanei. La simulazione dei comandi sui varchi resta riservata agli amministratori.","small"));
   }
   grid.append(card);
   const modeCard=this.card("Connessione");
   modeCard.append(this.node("p","Per accedere da Internet viene utilizzato l'URL esterno configurato in Home Assistant. Seleziona la rete locale solo per accessi dalla stessa Wi-Fi.","small"));
   const modes=this.node("div","","connection-modes");
   const internet=this.button("Accesso da Internet",()=>{this.qrMode="https";this.render();});
   internet.setAttribute("aria-pressed",String(this.qrMode==="https"));
   const local=this.button("Rete locale / Wi-Fi",()=>{this.qrMode="lan";this.render();});
   local.setAttribute("aria-pressed",String(this.qrMode==="lan"));
   modes.append(internet,local);
   modeCard.append(modes);
   grid.append(modeCard);
   const publicCard=this.card("QR temporaneo · HTTPS · 10 minuti");
   const externalUrl=this._hass?.config?.external_url||"";
   publicCard.append(this.node("p",externalUrl
     ?"Indirizzo pubblico: "+externalUrl
     :"Indirizzo pubblico non configurato. Impostalo in Home Assistant → Impostazioni → Sistema → Rete.",
     externalUrl?"small":"notice"));
   publicCard.append(this.node("p",
     "I QR usano l'indirizzo esterno Home Assistant. Abilita l'opzione " +
     "«Accesso temporaneo HTTPS» dalle opzioni dell'integrazione, usando il dominio HTTPS " +
     "autorizzato. Validi 10 minuti e monouso dopo l'utilizzo.",
     "small"));
   const publicForm=this.node("form");
   this.select(publicForm,"Varco virtuale","gate_id",
     gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const makePublic=this.node("button","Genera QR temporaneo (10 minuti)");
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
         gate:gates.find(g=>g.id===values.get("gate_id"))?.name||"Varco"
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
     img.alt="QR di accesso per "+this.publicQR.gate;
     preview.append(img);
     preview.append(this.node("p","NON STAMPARE: questo QR scade dopo 10 minuti ed è monouso. Per un QR da applicare alla porta usa il riquadro QR permanente qui sopra.","small"));
     const link=this.node("a","Apri pagina di accesso");
     link.href=this.publicQR.url;
     link.target="_blank";
     link.rel="noreferrer noopener";
     preview.append(link);
     publicCard.append(preview);
   }

    if(this.qrMode==="https" && this.data.role==="admin"){
      const fixed=this.card("QR permanente stampabile · varchi virtuali");
      fixed.append(this.node("p","Il QR resta uguale per ogni porta, anche cambiando gli ospiti. Ogni accesso richiede un PIN valido, e l'amministratore può revocare il QR stampato. Non utilizzare su porte fisiche.","small"));
      if(this.data.permanent_pilot!=="enabled"){
        fixed.append(this.node("p","Per creare il QR da stampare, vai in Home Assistant → Impostazioni → Dispositivi e servizi → CL B&B Manager → Configura → Accesso HTTPS e operatori e attiva «QR permanente solo varchi virtuali». Poi torna qui. Richiede dominio HTTPS.","notice"));
      }else{
        const form=this.node("form");
        this.select(form,"Varco per QR fisso","gate_id",gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
        const submit=this.node("button","Genera / mostra QR fisso");submit.type="submit";form.append(submit);
        form.onsubmit=async event=>{
          event.preventDefault();if(this.testBusy||!form.reportValidity())return;
          this.testBusy=true;submit.disabled=true;
          try{
            const gate_id=String(new FormData(form).get("gate_id"));
            const result=await this.api("permanent_pilot_qr",{gate_id});
            this.permanentQR={...result,gate_id,gate:gates.find(g=>g.id===gate_id)?.name||"Varco"};
            this.error="";
          }catch(err){this.permanentQR=null;this.error=this.describeError(err);}
          finally{this.testBusy=false;this.render();}
        };
        fixed.append(form);
        if(this.permanentQR){
          const preview=this.node("div");
          const img=this.node("img");img.width=260;img.height=260;img.alt="QR permanente virtuale per "+this.permanentQR.gate;
          const svgData="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(this.permanentQR.svg);
          img.src=svgData;preview.append(img);
          preview.append(this.node("p","QR stabile · stampabile · valido finché non viene revocato. Solo collaudo virtuale.","small"));
          const download=this.node("a","Scarica QR SVG da stampare");
          download.href=svgData;download.download="CL-BB-QR-"+this.permanentQR.gate_id+".svg";preview.append(download);
          const link=this.node("a","Apri pagina di accesso");
          link.href=this.permanentQR.url;link.target="_blank";link.rel="noreferrer noopener";preview.append(link);
          preview.append(this.button("Revoca QR e genera un nuovo codice",async()=>{
            if(!confirm("ATTENZIONE: il QR stampato non funzionerà più. Dovrai sostituirlo sulla porta. Procedere?"))return;
            try{
              await this.api("rotate_permanent_qr",{gate_id:this.permanentQR.gate_id,confirm:true});
              this.permanentQR=null;this.error="Vecchio QR revocato. Genera, stampa e applica il nuovo QR.";
              await this.load();
            }catch(err){this.error=this.describeError(err);this.render();}
          }));
          fixed.append(preview);
        }
      }
      grid.append(fixed);
    }

   // The printable QR is the primary choice. Show the temporary demo beneath it.
   if(this.qrMode==="https")grid.append(publicCard);
   const qrCard=this.card("QR di accesso · rete locale");
   qrCard.append(this.node(
     "p",
     "Il QR temporaneo dura 10 minuti e richiede un codice di accesso. " +
     "Usa questo indirizzo soltanto quando il telefono è collegato alla stessa rete Wi-Fi. " +
     "L'accesso permanente non è ancora disponibile.",
     "small"
   ));
   const qrForm=this.node("form");
   this.select(qrForm,"Varco virtuale","gate_id",gates.map(g=>[g.id,g.name]),this.demoTargetGateId||gates[0].id);
   const address=this.field(qrForm,"URL interno Home Assistant","base_url","url",this._hass?.config?.internal_url||"");
   address.placeholder="http://192.168.1.100:8123";
   const create=this.node("button","Genera QR locale");
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
         gate:gates.find(g=>g.id===values.get("gate_id"))?.name||"Varco"
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
       img.alt="QR temporaneo per "+this.demoQR.gate;
       preview.append(img);
       preview.append(this.node("p","Apri il QR su un dispositivo collegato alla stessa rete locale.","small"));
       const link=this.node("a","Apri pagina di accesso");
       link.href=this.demoQR.url;
       link.target="_blank";
       link.rel="noreferrer noopener";
       preview.append(link);
       qrCard.append(preview);
     }else{
       this.demoQR=null;
       qrCard.append(this.node("p","QR scaduto. Generane uno nuovo.","notice"));
     }
   }
   if(this.qrMode==="lan")grid.append(qrCard);
   const info=this.card("Informazioni di servizio");
   info.append(this.node("p","QR permanente HTTPS: "+(this.data.permanent_pilot==="enabled"?"abilitato (solo demo virtuale)":"disabilitato"),"small"),
               this.node("p","Collegamenti autorizzati: soltanto script virtuali","small"),
               this.node("p","Comandi verso serrature fisiche: disattivati","small"));
   grid.append(info);
 }
 events(grid){
   const history=this.card("Registro accessi");
   history.append(this.node("p","Ultimi 90 giorni · l'identità visualizzata è quella associata alla prenotazione, non una verifica della persona che ha digitato il codice.","small"));
   const access=this.data.access_history||[];
   if(!access.length)history.append(this.node("p","Nessun utilizzo di codici registrato.","small"));
   for(const entry of [...access].reverse()){
     const row=this.node("div","","item");
     const granted=entry.result==="authorized";
     row.append(this.node("strong",granted?"Codice autorizzato":"Codice rifiutato"));
     const when=entry.at?new Date(entry.at).toLocaleString("it-IT"):"Data non disponibile";
     const gate=entry.gate_name||"Varco";
     const mode=({https:"HTTPS",lan:"Rete locale",legacy:"Collaudo"})[entry.source]||"Sconosciuto";
     row.append(this.node("p",when+" · "+gate+" · "+mode,"small"));
     if(granted){
       const reference=entry.guest_name||entry.room||"Prenotazione non nominativa";
       row.append(this.node("p","Codice associato a: "+reference+(entry.room&&entry.guest_name?" · "+entry.room:""),"small"));
     }else{
       row.append(this.node("p","Codice non associato ad alcuna prenotazione verificata.","small"));
     }
     history.append(row);
   }
   grid.append(history);
   if(this.data.role!=="admin")return;
   const card=this.card("Registro modifiche");
   for(const event of [...this.data.events].reverse()){
     const row=this.node("div","","item");
     row.append(this.node("strong",({
       gate_added:"Varco creato",gate_updated:"Varco aggiornato",gate_removed:"Varco eliminato",
       booking_added:"Prenotazione creata",booking_revoked:"Codice revocato",
       public_pilot_open:"Accesso autorizzato",public_pilot_denied:"Accesso rifiutato",
       demo_pin_denied:"Codice rifiutato",demo_pin_opened:"Comando virtuale eseguito",
       demo_qr_open:"QR locale utilizzato",guest_denied:"Accesso rifiutato"
     })[event.event]||event.event),
     this.node("p",new Date(event.at).toLocaleString("it-IT")+" · "+event.details,"small"));
     card.append(row);
   }
   grid.append(card);
 }
}
if (!customElements.get("cl-bb-manager-panel")) { customElements.define("cl-bb-manager-panel",ClBbManagerPanel); }
