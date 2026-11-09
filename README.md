# CL B&B Manager

**Versione 0.5.0-alpha.8 — QR fisso stampabile HTTPS con PIN, soltanto per varchi virtuali, attivabile esplicitamente. Non per accessi reali in produzione.**

Integrazione custom per Home Assistant, progettata da CL Impianti per la gestione di varchi, camere e prenotazioni nei B&B.

## Funzioni oggi presenti

La versione alpha.7 consolida la migrazione dell’archivio alla versione 3 e l’isolamento dei dati per struttura. L’impianto pilota usa ancora **una sola struttura per istanza Home Assistant**: la gestione simultanea di più B&B nello stesso archivio e il portale permanente restano funzionalità future.

- **Pannello amministrativo** in Home Assistant con *Panoramica*, *Prenotazioni*, *Accessi*, *Varchi*, *Registro* e *Impostazioni*.
- **Varchi dinamici**: aggiungi, configura, modifica e disabilita varchi comuni o privati; fino a 200 in questa alpha.
- **Prenotazioni con PIN** numerico di 8 cifre: check-in, check-out, elenco di varchi autorizzati, revoca immediata e PIN salvato soltanto come hash salato.
- **QR permanenti /guest/** non attivi. Nel pannello Varchi si accede ora alla generazione di un **QR prova (LAN)** temporaneo; non consegnare QR agli ospiti reali.
- **QR di prova temporaneo (10 minuti)**, generato dall'amministratore per uno dei cinque varchi **virtuali** della demo e utilizzabile da smartphone collegato alla **stessa rete LAN** di Home Assistant, senza account HA.
- **Portale di prova** con PIN di prenotazione, controllo su permessi, data, revoca, limiti di tentativi persistenti, registro delle azioni e comando esclusivamente virtuale.
- **QR HTTPS temporaneo (opzionale)**: richiede un'attivazione amministrativa esplicita e un dominio HTTPS fissato nelle opzioni; token valido 10 minuti, monouso dopo l'apertura, solo script virtuali. Vedere [piano di collaudo HTTPS](docs/PUBLIC-HTTPS-PILOT.md).

## Collaudo da smartphone sulla rete locale

1. Collegati a Home Assistant con un account amministratore e apri **CL B&B Manager → Prenotazioni**. Crea una prenotazione di prova valida per l'ora corrente, con **Camera 1** tra i varchi autorizzati. Copia il PIN mostrato una sola volta.
2. Apri **Collaudo accessi → QR temporaneo per smartphone** e seleziona **Camera 1**.
3. Inserisci l'**indirizzo LAN di Home Assistant**, per esempio `http://192.168.1.100:8123` (sostituiscilo con quello reale) oppure un nome `*.local` risolto sulla rete.
4. Genera il QR e scansionalo entro **10 minuti** da uno smartphone collegato alla **stessa LAN/Wi-Fi**.
5. Inserisci il PIN corretto: il server controlla la prenotazione e simula l'apertura di Camera 1 mediante lo script virtuale `script.cl_bb_demo_apri_camera_1`.
6. Verifica che PIN errati, scaduti, revocati o destinati ad altre camere siano rifiutati. Revoca la prenotazione di prova al termine.

**Non utilizzare il nome di dominio Cloudflare, tunnel pubblici o indirizzi Internet per il QR demo.** Sono ammessi esclusivamente indirizzi RFC1918 o `*.local`. Il collegamento QR temporaneo e i dati di sessione scompaiono al riavvio di Home Assistant. I PIN restano validi solo finché la prenotazione lo consente.

Gli script virtuali previsti sono `script.cl_bb_demo_apri_cancello`, `script.cl_bb_demo_apri_portone`, `script.cl_bb_demo_apri_camera_1`, `script.cl_bb_demo_apri_camera_2` e `script.cl_bb_demo_apri_camera_3`, ciascuno collegato esclusivamente a un `input_boolean` dimostrativo.

## Installazione tramite Home Assistant Marketplace / HACS (pilot)

1. Aggiungi il repository GitHub pubblico `climpianti/CL-BB-Manager` come **repository personalizzato** di categoria **Integrazione** nel Marketplace/HACS. Il repository deve essere pubblico, oppure l'account GitHub connesso a HACS deve essere autorizzato a leggere il repository privato.
2. Cerca **CL B&B Manager** tra le integrazioni personalizzate e installa la revisione pubblicata più recente e verifica il numero versione nel `manifest.json`. Verifica la versione nell'apposito `manifest.json` prima di usare il componente.
3. Prima di installare su un'istanza con altri sistemi attivi, salva e verifica un backup completo Home Assistant. Per attivare il componente occorre un riavvio di Home Assistant.
4. In Home Assistant apri **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL B&B Manager** e crea un'unica istanza; non duplicare una configurazione già presente.
5. Per il collaudo usa soltanto script `script.cl_bb_demo_apri_*` verificati, collegati esclusivamente a helper `input_boolean` virtuali. Non collegare attuatori fisici.

Il Marketplace di Home Assistant 2026.11 può richiedere prima l'accettazione dell'avviso iniziale e la connessione dell'account GitHub. Per il piano Covone vedere [PILOT-COVONE.md](docs/PILOT-COVONE.md) sul [branch pilota](https://github.com/climpianti/CL-BB-Manager/tree/pilot/bb-covone-alpha4). In assenza di un rilascio stabile, la selezione della versione può corrispondere al branch principale; verificare sempre `manifest.json`.

**Alternativa manuale:** copia `custom_components/cl_bb_manager/` in `/config/custom_components/cl_bb_manager/`, valida la configurazione, riavvia e aggiungi l'integrazione dall'interfaccia.

**Pubblicare questo repository su GitHub non attiva il portale permanente**: il percorso `/guest/` resta disattivato e il QR `/demo/` è utilizzabile solo sulla LAN. La nuova pagina `/public-demo/` è inattiva fino all'attivazione esplicita delle opzioni HTTPS da parte dell'amministratore.

## Collaudo HTTPS temporaneo (opzionale)

In **Impostazioni → Dispositivi e servizi → CL B&B Manager → Configura**, l'amministratore può attivare il test HTTPS e inserire il nome di dominio esatto (solo HTTPS). Nel pannello **Collaudo accessi** è possibile generare un QR esterno, temporaneo e monouso, per un solo varco virtuale. L'accesso richiede un PIN di prenotazione valido; l'endpoint permanente `/guest/` resta spento. La disattivazione nelle opzioni invalida immediatamente le sessioni. Non usare questa modalità per serrature reali.

## Limiti importanti

- **Il portale QR pubblico permanente è disattivato.** I QR temporanei LAN/HTTPS sono ambienti di collaudo con soli script virtuali, non un sistema di accesso per clienti.
- Non è consentito l'uso con serrature o attuatori fisici; non collegare gli script virtuali a comandi hardware.
- La verifica dell'interfaccia su smartphone e il test completo sul server reale sono richiesti prima di considerare completata la fase alpha.
- Per un prodotto commerciale restano da implementare protezione del proxy HTTPS, sessioni ospiti di produzione, ruoli gestore/installatore, GDPR, backup, audit e fail-safe.

## Interfaccia CL Control · BlueTech Glass

Il pannello amministrativo e la pagina PIN/QR temporanea utilizzano il design system **CL Control Blue Tech Premium**, adattato in stile glassmorphism (blu notte `#061324`, ciano `#19baff`, verde `#32e394`), con card traslucide, interazioni accessibili e layout responsive.

La navigazione del pannello comprende **Panoramica, Prenotazioni, Accessi, Varchi, Registro e Impostazioni**. Il collegamento HTTPS usa l'URL esterno configurato in Home Assistant; il QR locale rimane opzionale. La pagina ospite visualizza un form PIN più chiaro e messaggi di esito semplificati.

**Nota di sicurezza:** le diciture orientate al cliente non trasformano questa release alpha in un sistema di apertura fisica. Sono consentite soltanto simulazioni tramite script virtuali. Il portale permanente `/guest/` continua a restituire 404. I PIN e i QR temporanei non devono essere condivisi pubblicamente.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
node --test tests/test_panel.mjs
node --check custom_components/cl_bb_manager/frontend/panel.js
```

La pipeline GitHub Actions ripete i controlli a ogni push.

Repository pubblico per collaudo; licenza non ancora definita. Consulta [Roadmap](docs/ROADMAP.md) e [Sicurezza](docs/SECURITY.md).

## Impostazioni e varchi (0.5.0-alpha.6)

Da **Home Assistant → Impostazioni → Dispositivi e servizi → CL B&B Manager → Configura** si apre un menu con:

- **Accesso HTTPS e operatori**: mostra i nomi degli operatori già salvati, preseleziona i relativi account Home Assistant quando riapri la pagina e permette di aggiornarne l'elenco (massimo 20 utenti non amministratori attivi). Gli amministratori hanno già accesso senza selezione. Gli operatori non possono modificare le configurazioni dei varchi.
- **Gestione varchi → Aggiungi varco**: seleziona un'entità Home Assistant esistente (script/button/lock), indica l'azione coerente e il tipo. Il nuovo varco è sempre creato **disattivato**, per verifica e successiva abilitazione dal pannello amministrativo.
- **Gestione varchi → Elimina varco**: seleziona un varco esistente e conferma in una seconda schermata. Il server impedisce la rimozione finché sono associate prenotazioni non revocate e non scadute. Il comando elimina solo la mappatura nel gestionale; **non elimina le entità Home Assistant né comanda dispositivi**.

Le modifiche sono applicate alla configurazione dell'integrazione e allo storage gestito da HA; non modificano PIN o token in chiaro. La modalità di accesso pubblico permanente resta disattivata e l'apertura è consentita solo ai cinque script virtuali approvati nel pilot.

## Scelta automatica dell'indirizzo QR

Nel pannello **Collaudo accessi** il percorso **HTTPS esterno** è predefinito e usa automaticamente l'URL esterno configurato in **Home Assistant → Impostazioni → Sistema → Rete**. Il backend valida l'URL HTTPS di HA e genera link solo per il portale temporaneo `/public-demo/`, se il collaudo pubblico è stato esplicitamente abilitato nelle opzioni dell'integrazione. La modalità **LAN / Wi-Fi locale** resta selezionabile per i test locali e legge, se presente, l'URL interno configurato in Home Assistant; altrimenti l'indirizzo LAN può essere inserito manualmente. Le due modalità non sono intercambiabili e il percorso permanente `/guest/` resta disabilitato.


**Branding CL Control:** il logo in testata e sulla pagina QR/PIN è il logo originale CL Impianti già usato in CL Control, distribuito come risorsa statica locale del componente. La versione BlueTech Glass mantiene colori e funzione di collaudo virtuale.


## Stato collaudo e percorso beta

Consulta [Checklist pre-beta](docs/BETA-READINESS.md) prima di distribuire questa versione. L’aggiornamento HACS si applica al riavvio Home Assistant. La scansione QR su smartphone e il flusso completo PIN valido → autorizzazione → impulso virtuale richiedono ancora una prova end-to-end in ambiente di test; non dichiararli verificati sulla base dei soli test unitari o di un impulso virtuale avviato manualmente.


## QR permanente stampabile · pilota virtuale (alpha.8)

Nelle **opzioni dell'integrazione** attiva esplicitamente **QR permanente solo varchi virtuali**, con un dominio HTTPS pubblico valido. Nella scheda **Accessi → Connessione → Accesso da Internet**, l'amministratore seleziona il varco, genera/visualizza il QR fisso, e scarica l'SVG da stampare. Il QR contiene il token persistente del varco, **non contiene il PIN** e resta uguale tra prenotazioni, riavvii e rigenerazioni. Ogni richiesta richiede una sessione web temporanea, il PIN valido e una prenotazione che autorizzi quel varco nel periodo selezionato.

**Revoca QR:** con **Revoca QR e genera un nuovo codice** un amministratore può invalidare il QR stampato; sarà necessario sostituirlo sulla porta. Cambiare la mappatura del varco invalida automaticamente il QR precedente. Disabilitare il pilot rende il percorso non disponibile. I QR permanenti non sono monouso, ma i moduli web di verifica lo sono. Non utilizzare questa funzione su serrature o attuatori fisici: il server accetta soltanto i cinque script dimostrativi. Il portale legacy `/guest/` resta inattivo.

**Stato:** implementazione virtuale sperimentale. Richiede test CI, collaudo HTTPS/reverse proxy da smartphone e revisione indipendente prima dell'esposizione a ospiti reali.
