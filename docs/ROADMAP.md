# Roadmap CL B&B Manager

## Alpha 0.1: struttura dati

- Integrazione Home Assistant con configurazione iniziale dalla UI
- Modello varchi dinamico senza hardcode dei cinque varchi demo
- Modello prenotazioni con PIN protetto e scadenza
- Test unitari del modello

## Alpha 0.2: gestione operativa

- Pannello installatore per aggiungere, modificare, abilitare e disabilitare varchi
- Configurazione delle entità HA con scelta di comando autorizzato
- Dashboard prenotazioni e generazione PIN visibile una sola volta
- Audit dei comandi, revoca, database protetto

## Alpha 0.3: accesso ospiti

- QR permanente per varco e pagina ospiti mobile-first
- Endpoint pubblico isolato da HA e protetto da rate-limit, anti-bruteforce e controlli server
- Test end-to-end sui cinque varchi virtuali già presenti in HA

## Beta: sicurezza e operatività

- Concorrenza e controlli per attacchi, GDPR, backup, recupero, test hardware
- Supporto tastierini fisici in futuro
