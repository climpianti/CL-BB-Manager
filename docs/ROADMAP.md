# Roadmap CL B&B Manager

## 0.1.0-alpha.1 — base iniziale
- [x] Integrazione con config flow Home Assistant
- [x] Modello di varchi dinamici e PIN temporanei
- [x] Persistenza locale e test unitari di base

## 0.2.0-alpha.1 — prima UI gestionale (codice pubblicato)
- [x] Pannello amministratore responsive nel menu laterale
- [x] API WebSocket con controllo amministratore
- [x] Creazione, modifica, abilitazione, disabilitazione ed eliminazione varchi
- [x] Prenotazioni, generazione PIN mostrato una sola volta e revoca
- [x] Registro degli eventi amministrativi
- [x] Workflow CI per sintassi e test di modello
- [ ] Conferma esecuzione dei test CI
- [ ] Installazione e collaudo funzionale su HA demo 2026.10.4
- [ ] Test grafici su desktop e mobile

## 0.3 — prova QR e controllo varchi virtuali
- [ ] Endpoint QR pubblico separato dai privilegi di Home Assistant
- [ ] Generazione QR permanente, rotazione e stampa
- [ ] Validazione PIN e autorizzazioni solo lato server
- [ ] Rate limit persistente, protezioni contro abuso e revisione di sicurezza
- [ ] Invio comando soltanto allo script virtuale autorizzato
- [ ] Test end-to-end: check-in, scadenza, revoca, camera non autorizzata

## Beta / produzione
- [ ] Ruoli installatore e gestore con autorizzazioni minime
- [ ] GDPR, conservazione, cancellazione, backup e ripristino
- [ ] Calendario, pulizie, clima, integrazioni calendari delle prenotazioni
- [ ] Test di carico, concorrenza, fail-closed e hardware reale
- [ ] Eventuale supporto a tastierini fisici
