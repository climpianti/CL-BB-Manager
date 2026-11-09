# CL B&B Manager

Integrazione Home Assistant di CL Impianti per gestire prenotazioni, codici personali e QR permanenti delle porte. Un amministratore configura la struttura e i varchi; gli operatori espressamente abilitati gestiscono gli ospiti senza diventare amministratori di Home Assistant.

**Versione in revisione: 0.6.0-beta.1.** L'interfaccia usa il flusso operativo del gestionale. Questa revisione introduce il driver Shelly nativo: prima della distribuzione ai clienti resta necessario il collaudo del driver su hardware e su un'installazione Home Assistant reale pulita. La suite automatica usa dispositivi simulati e non certifica il cablaggio dell'impianto.

## Installazione su un nuovo Home Assistant

1. Collega lo Shelly alla rete e aggiungilo tramite l'integrazione **Shelly ufficiale** di Home Assistant. Il modello supportato da questa revisione è **Shelly 1 Mini Gen3**. Verifica che sia online, con uscita OFF e cablaggio adatto alla serratura.
2. Installa questo repository come integrazione personalizzata in HACS, oppure copia `custom_components/cl_bb_manager` nella cartella `custom_components` di HA. È richiesto Home Assistant 2026.10 o successivo; riavvia Home Assistant.
3. Da **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL B&B Manager**, assegna il nome alla struttura. È supportata una struttura per istanza HA.
4. Configura una volta l'indirizzo HTTPS esterno in **Impostazioni → Sistema → Rete**. Nelle opzioni di CL B&B Manager verifica **Accesso HTTPS e operatori**, l'abilitazione del portale e gli account autorizzati. Se HA non ha un URL esterno, puoi specificare l'origine HTTPS nelle opzioni dell'integrazione.
5. Nel pannello **Varchi → Aggiungi varco Shelly → Cerca dispositivi**, seleziona il relè, nome, tipo di accesso e durata impulso (0,5–5 secondi). Conferma l'applicazione del profilo.
6. Il componente configura e rilegge automaticamente il profilo del relè: avvio **OFF**, accensione automatica disabilitata, spegnimento automatico abilitato con la durata scelta. Prepara un QR permanente, salva il collegamento stabile al dispositivo e lascia il varco **inattivo**. Non serve creare script, helper, automazioni o YAML per ogni porta.
7. Dopo la verifica dell'installatore, usa **Abilita accesso**. La conferma controlla nuovamente il profilo, senza inviare un'apertura. Da **QR delle porte** visualizza e scarica il QR da stampare.

L'integrazione non configura Wi-Fi, credenziali Shelly, tunnel, DNS o Cloudflare e non modifica il comportamento dell'ingresso locale dello Shelly. Queste attività e la verifica elettrica restano parte dell'installazione. Il profilo automatico riguarda esclusivamente il relè scelto.

## Uso da parte del gestore

- **Prenotazioni:** scegli camera, date e porte autorizzate. Il codice viene mostrato una volta; nell'archivio resta un hash salato. Le autorizzazioni fisiche delle porte selezionate vengono associate nella stessa operazione.
- **QR delle porte:** mostra e scarica il QR già esistente senza rigenerarlo. Il QR resta uguale tra prenotazioni e riavvii; il codice personale stabilisce chi può aprire e quando.
- **Registro accessi:** mostra l'esito delle richieste. Un comando inviato non prova che la serratura si sia sbloccata: non viene inventato un feedback di apertura.
- **Varchi e impostazioni:** riservati agli amministratori. Disattivare una porta conserva il QR; sostituirlo richiede una conferma esplicita e rende inutilizzabile la vecchia stampa. Il blocco di emergenza revoca QR e relativi permessi fisici.

Il pannello compare direttamente nella barra laterale HA e non richiede CL Control. Gli amministratori hanno accesso; un account attivo non amministratore deve essere selezionato nelle opzioni dell'integrazione. Il backend verifica il ruolo per ogni richiesta: nascondere i pulsanti non è il controllo di sicurezza.

## Aggiornamento da Bausan / versioni precedenti

L'aggiornamento conserva archivio, QR **fisici**, prenotazioni e stati di abilitazione già salvati; non abilita automaticamente porte o vecchie prenotazioni. Le associazioni esistenti Strada/Scala continuano a usare i due script già predisposti, come compatibilità. Il nuovo flusso nativo si applica ai nuovi varchi.

I percorsi di prova `/demo/`, `/public-demo/` e `/permanent-demo/` non vengono più registrati. I QR operativi usano esclusivamente `/api/cl_bb_manager/physical/…`. Un vecchio QR virtuale non viene convertito in una chiave fisica. Gli identificatori interni storici restano solo per leggere i dati esistenti e mantenere i test di regressione.

Il difetto degli operatori è corretto in `permissions.operator_user_ids`: le opzioni HA sono una `MappingProxyType`, ora accettata come `Mapping`. Non è necessario rendere amministratore l'utente selezionato. Il precedente fix HTTP 403 sul form PIN resta attivo: `Referrer-Policy: strict-origin`, controllo dell'origine, nonce monouso e rifiuto dei replay.

## Verifiche automatiche

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
npm ci --ignore-scripts
npm test
node --check custom_components/cl_bb_manager/frontend/panel.js
```

I test coprono installazione vuota, configurazione Shelly senza apertura, controllo identità e profilo, operatore selezionato/non selezionato/revocato, prenotazione, QR, GET/POST PIN, replay e riavvio con archivio persistente. Le prove di apertura usano esclusivamente RPC fittizie.

È disponibile anche un controllo Chromium isolato in `tests/browser_product_smoke.cjs`. Con `playwright-core` e Chromium già installati:

```sh
CL_BB_CHROMIUM_PATH=/percorso/chromium node tests/browser_product_smoke.cjs
```

In alternativa si può indicare il modulo con `CL_BB_PLAYWRIGHT_MODULE`; `CL_BB_SCREENSHOT_DIR` abilita screenshot locali. Ogni richiesta del browser è intercettata e servita da fixture locali. Il controllo visita tutte le schede per amministratore e operatore, a 390 e 1366 pixel.

Vedi [verifica della trasformazione](docs/PRODUCT-READINESS.md) per evidenze, limiti e collaudo prima dell'installazione reale. La documentazione delle vecchie release è materiale storico, non la procedura di installazione corrente.
