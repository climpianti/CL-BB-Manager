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
