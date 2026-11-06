# CL B&B Manager

**Versione 0.3.0-alpha.1 — prova QR per i cinque script virtuali della demo.**

Integrazione Home Assistant per strutture ricettive: varchi dinamici, prenotazioni con PIN temporanei, QR permanenti per varco e registro attività.

## Funzionalità disponibili

- Pannello amministratore Home Assistant con sezioni **Varchi**, **Prenotazioni**, **Registro**.
- Varchi aggiungibili, modificabili, abilitabili e disabilitabili (fino a 200 nell'alpha).
- Prenotazioni a validità temporale, associazione esplicita dei varchi, revoca e PIN di 8 cifre salvato come hash salato.
- Pulsante **Scarica QR** su ogni varco: richiede la base HTTPS pubblica della struttura e scarica un SVG stampabile senza credenziali Home Assistant.
- Codice di portale ospiti con controllo PIN e autorizzazioni lato server, limite rudimentale dei tentativi e apertura esclusivamente di cinque script virtuali demo.
- **Il portale pubblico è disabilitato in modo predefinito, e in questa alpha non ha un controllo UI per attivarlo.** Pertanto i QR scaricabili non aprono ancora porte: sono destinati alla revisione grafica e tecnica.

## Installazione su demo

Copia `custom_components/cl_bb_manager/` nella cartella Home Assistant `/config/custom_components/cl_bb_manager/`, poi verifica la configurazione e riavvia Home Assistant. Il manifest installa `segno==1.6.6` per generare i QR. In Impostazioni → Dispositivi e servizi, aggiungi l'integrazione come **CL B&B Manager**. Se già configurata, non creare duplicati.

Gli script virtuali demo sono:
`script.cl_bb_demo_apri_cancello`, `script.cl_bb_demo_apri_portone`, `script.cl_bb_demo_apri_camera_1`, `script.cl_bb_demo_apri_camera_2`, `script.cl_bb_demo_apri_camera_3`.

**NON collegare gli script demo a dispositivi fisici**. La limitazione ai soli ID demo non è una certificazione della sicurezza.

## Verifiche mancanti

- Test E2E con portale attivato in ambiente isolato, protezione contro brute force persistente, rate limit reverse proxy e test su Safari/Chrome mobili.
- Protezione CSRF e integrazione con il reverse proxy in diverse configurazioni, verifica delle autorizzazioni in concorrenza.
- Valutazione GDPR e ruoli manager/installatore meno privilegiati.
- Test con serrature fisiche e gestione guasti: vietati finché non sarà completata una revisione indipendente.

Il repository è privato. Vedere [Roadmap](docs/ROADMAP.md) e [Sicurezza](docs/SECURITY.md).
