# CL B&B Manager

**Versione 0.4.0-alpha.1 — dimostrazione QR temporanea su rete LAN. Non per strutture in produzione.**

Integrazione custom per Home Assistant, progettata da CL Impianti per la gestione di varchi, camere e prenotazioni nei B&B.

## Funzioni oggi presenti

- **Pannello amministrativo** in Home Assistant, sezioni *Varchi*, *Prenotazioni*, *Registro* e *Collaudo accessi*.
- **Varchi dinamici**: aggiungi, configura, modifica e disabilita varchi comuni o privati; fino a 200 in questa alpha.
- **Prenotazioni con PIN** numerico di 8 cifre: check-in, check-out, elenco di varchi autorizzati, revoca immediata e PIN salvato soltanto come hash salato.
- **QR permanenti scaricabili** da un amministratore, ma la loro destinazione pubblica è ancora *spenta*. Non usarli sugli accessi di clienti reali.
- **QR di prova temporaneo (10 minuti)**, generato dall'amministratore per uno dei cinque varchi **virtuali** della demo e utilizzabile da smartphone collegato alla **stessa rete LAN** di Home Assistant, senza account HA.
- **Portale di prova** con PIN di prenotazione, controllo su permessi, data, revoca, limiti di tentativi persistenti, registro delle azioni e comando esclusivamente virtuale.

## Collaudo da smartphone sulla rete locale

1. Collegati a Home Assistant con un account amministratore e apri **CL B&B Manager → Prenotazioni**. Crea una prenotazione di prova valida per l'ora corrente, con **Camera 1** tra i varchi autorizzati. Copia il PIN mostrato una sola volta.
2. Apri **Collaudo accessi → QR temporaneo per smartphone** e seleziona **Camera 1**.
3. Inserisci l'**indirizzo LAN di Home Assistant**, per esempio `http://192.168.1.100:8123` (sostituiscilo con quello reale) oppure un nome `*.local` risolto sulla rete.
4. Genera il QR e scansionalo entro **10 minuti** da uno smartphone collegato alla **stessa LAN/Wi-Fi**.
5. Inserisci il PIN corretto: il server controlla la prenotazione e simula l'apertura di Camera 1 mediante lo script virtuale `script.cl_bb_demo_apri_camera_1`.
6. Verifica che PIN errati, scaduti, revocati o destinati ad altre camere siano rifiutati. Revoca la prenotazione di prova al termine.

**Non utilizzare il nome di dominio Cloudflare, tunnel pubblici o indirizzi Internet per il QR demo.** Sono ammessi esclusivamente indirizzi RFC1918 o `*.local`. Il collegamento QR temporaneo e i dati di sessione scompaiono al riavvio di Home Assistant. I PIN restano validi solo finché la prenotazione lo consente.

Gli script virtuali previsti sono `script.cl_bb_demo_apri_cancello`, `script.cl_bb_demo_apri_portone`, `script.cl_bb_demo_apri_camera_1`, `script.cl_bb_demo_apri_camera_2` e `script.cl_bb_demo_apri_camera_3`, ciascuno collegato esclusivamente a un `input_boolean` dimostrativo.

## Installazione

Copia `custom_components/cl_bb_manager/` in `/config/custom_components/cl_bb_manager/`, verifica la configurazione e riavvia Home Assistant. Configura l'integrazione da **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL B&B Manager**. Non creare una seconda istanza se è già configurata.

## Limiti importanti

- **Il portale QR pubblico permanente è disattivato.** La nuova pagina QR temporanea è un ambiente di collaudo, non un sistema di accesso per clienti.
- Non è consentito l'uso con serrature o attuatori fisici; non collegare gli script virtuali a comandi hardware.
- La verifica dell'interfaccia su smartphone e il test completo sul server reale sono richiesti prima di considerare completata la fase alpha.
- Per un prodotto commerciale restano da implementare protezione del proxy HTTPS, sessioni ospiti di produzione, ruoli gestore/installatore, GDPR, backup, audit e fail-safe.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
node --test tests/test_panel.mjs
node --check custom_components/cl_bb_manager/frontend/panel.js
```

La pipeline GitHub Actions ripete i controlli a ogni push.

Repository privato, licenza non ancora definita. Consulta [Roadmap](docs/ROADMAP.md) e [Sicurezza](docs/SECURITY.md).
