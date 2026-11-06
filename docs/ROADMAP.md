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
