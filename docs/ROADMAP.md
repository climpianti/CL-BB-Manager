> Documento storico delle release precedenti. Per installazione e stato attuali vedere [README](../README.md) e [PRODUCT-READINESS](PRODUCT-READINESS.md).

# Roadmap CL B&B Manager

## 0.1 e 0.2 — completato
- [x] Config flow e pannello administrator Home Assistant
- [x] Varchi dinamici, gestione prenotazioni, PIN protetti
- [x] Registro eventi amministrativi e test unitari base
- [x] Collegamento ai cinque script virtuali della demo

## 0.3 alpha — QR / accesso demo (codice pubblicato)
- [x] QR permanente per varco, scaricabile come SVG da un amministratore
- [x] Pagina ospiti con modulo PIN e autorizzazione backend
- [x] Allowlist rigida di soli cinque script di apertura simulata
- [x] Rate limit in memoria, verifica Origin e scadenza, revoca
- [x] Accesso pubblico inattivo per impostazione predefinita
- [ ] Convalida CI dopo commit 0.3
- [ ] Distribuzione della 0.3 sulla demo Home Assistant
- [ ] Test end-to-end in ambiente isolato, incluso PIN errato/scaduto e altre camere
- [ ] Gestione avanzata anti-abuso, proxy HTTPS e dispositivi mobili

## Beta / produzione
- [ ] Impostazioni sicure per abilitare il portale ospiti dopo collaudo
- [ ] Ruoli separati installatore/manager e audit avanzato
- [ ] GDPR, backup, recupero, sicurezza e prove su hardware reale
- [ ] Tastierini opzionali, notifiche e calendari

## 0.3.1-alpha.1 — hardening e collaudo interno
- [x] Limiti ai tentativi persistenti per struttura e varco
- [x] Controllo delle prenotazioni attive con numero massimo di candidate
- [x] Verifica PIN via WebSocket riservato all'amministratore, con apertura esclusivamente virtuale opzionale
- [x] Test unitari delle autorizzazioni e dei limiti
- [ ] Collaudo sul server demo dopo caricamento e riavvio
- [ ] Audit HTTPS/reverse proxy e portale ospiti pubblico (disattivato)

## 0.3.2-alpha.1 — collaudo grafico nel pannello installatore
- [x] Nuova scheda 'Collaudo accessi' nel pannello Home Assistant
- [x] Selezione soltanto fra i cinque varchi virtuali abilitati
- [x] Verifica PIN senza azionamento e prova con impulso virtuale esplicitamente confermato
- [x] Esito leggibile, nessun PIN salvato nel frontend o nel registro
- [ ] Verifica del rendering su desktop/mobile e prova locale PIN valido/errato/revocato
- [ ] Portale ospiti pubblico ancora disattivato

## 0.4.0-alpha.1 — collaudo QR locale e temporaneo
- [x] Generazione QR temporaneo da amministratore, valido 10 minuti, senza account HA per lo smartphone
- [x] Pagina locale con form PIN, verifica stanza/orario/revoca e apertura limitata ai cinque script virtuali
- [x] URL vincolato a indirizzi LAN o `*.local`, verifica Host e Origin
- [x] Tentativi conteggiati e persistiti prima del controllo PIN
- [x] Test unitari policy locale e simulazione HTTP isolata
- [ ] Installazione e verifica dell'endpoint demo nell'istanza Home Assistant reale
- [ ] Collaudo da smartphone sulla stessa rete LAN, con PIN valido/non valido
- [ ] Audit del reverse proxy e revisione indipendente per il portale permanente


## Stato di riferimento — 2026-11-09
- Release di riferimento: 0.5.0-alpha.6; le sezioni storiche sopra non rappresentano lo stato corrente di ogni funzionalità.
- [x] Protezione delle modifiche ai varchi via WebSocket (PR #10): blocco in presenza di prenotazioni attive/future, disabilitazione e invalidazione delle sessioni QR in caso di rimappatura.
- [ ] Collaudo end-to-end su installazione reale e smartphone: PIN valido, errato, scaduto, revocato; nessuna apertura fisica.
- [ ] Revisione di sicurezza indipendente prima di abilitare accessi fisici o portale pubblico permanente.

## Obiettivo di prodotto — integrazione HACS riutilizzabile
Architettura **local-first**: ogni installazione Home Assistant conserva localmente dati, segreti e audit. Nessun servizio cloud obbligatorio. B&B Covone è un ambiente di collaudo, non un requisito del prodotto.

### Milestone A — solidità dell'alpha
- [ ] Test di autorizzazione WebSocket/HTTP, isolamento tra utenti e regressioni per modifiche ai varchi.
- [ ] Migrazione dati con versionamento, backup/ripristino documentati e test di aggiornamento.
- [ ] Verifica delle entità HA ammesse e procedure fail-closed in caso di errori o riavvii.
- [ ] Documentazione operativa aggiornata e matrice dei test su HA supportati.

### Milestone B — modello multi-struttura
- [ ] Definire identificativi stabili per struttura, unità/camera, varco, prenotazione e utente.
- [ ] Specificare isolamento dei dati, delle autorizzazioni e dell'audit per struttura; nessuna fuga incrociata.
- [ ] Progettare migrazione retrocompatibile delle prenotazioni attuali a una struttura predefinita, con backup e rollback.
- [ ] Prove su due strutture indipendenti, compresi conflitti di nomi e orari.

### Milestone C — portale ospiti e sicurezza
- [ ] Threat model per QR/PIN, proxy HTTPS, replay, enumerazione, rate limiting e revoca.
- [ ] Portale mobile accessibile, senza credenziali HA, con autorizzazioni temporanee e test reali.
- [ ] Consenso/trasparenza, minimizzazione, conservazione e cancellazione dei dati personali.
- [ ] Accesso a dispositivi fisici solo dopo revisione indipendente e attivazione esplicita.

### Milestone D — distribuzione beta HACS
- [ ] Installazione/configurazione senza riferimenti hardcoded alla struttura di prova.
- [ ] Traduzioni, diagnostica senza segreti, manuale installatore e troubleshooting.
- [ ] CI su versioni HA/Python supportate, release versionate e test di upgrade/downgrade.
- [ ] Beta controllata presso più B&B, raccolta bug e criteri di rilascio pubblico.

### Criteri di rilascio
Nessuna funzionalità di apertura fisica abilitata di default; nessun merge senza CI verde; migrazioni con backup e test; test di isolamento multi-struttura e revisione di sicurezza prima della beta pubblica.

