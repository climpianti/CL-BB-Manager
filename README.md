# CL B&B Manager

Integrazione Home Assistant di CL Impianti per gestire prenotazioni, codici personali e QR permanenti delle porte. Un amministratore configura la struttura e i varchi; gli operatori espressamente abilitati gestiscono gli ospiti senza diventare amministratori di Home Assistant.

**Versione in revisione: 0.6.0-beta.2.** L'interfaccia usa il flusso operativo del gestionale. Questa revisione introduce il driver Shelly nativo e gli attuatori basati su entità HA: prima della distribuzione ai clienti resta necessario il collaudo del driver su hardware e su un'installazione Home Assistant reale pulita. La suite automatica usa dispositivi simulati e non certifica il cablaggio dell'impianto.

## Installazione su un nuovo Home Assistant

1. Aggiungi i dispositivi alle rispettive integrazioni Home Assistant: per esempio Yale tramite l’integrazione che espone la serratura, un relè KNX/MQTT/Z-Wave/Zigbee come `switch`, oppure un pulsante/script apriporta. La configurazione automatica Shelly dedicata supporta **Shelly 1 Mini Gen3** già presente nell’integrazione Shelly ufficiale. Verifica disponibilità e cablaggio; i relè devono essere OFF.
2. Installa questo repository come integrazione personalizzata in HACS, oppure copia `custom_components/cl_bb_manager` nella cartella `custom_components` di HA. È richiesto Home Assistant 2026.10 o successivo; riavvia Home Assistant.
3. Da **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL B&B Manager**, assegna il nome alla struttura. È supportata una struttura per istanza HA.
4. Configura una volta l'indirizzo HTTPS esterno in **Impostazioni → Sistema → Rete**. Nelle opzioni di CL B&B Manager verifica **Accesso HTTPS e operatori**, l'abilitazione del portale e gli account autorizzati. Se HA non ha un URL esterno, puoi specificare l'origine HTTPS nelle opzioni dell'integrazione.
5. Nel pannello **Varchi → Aggiungi varco Shelly → Cerca dispositivi**, seleziona il relè, nome, tipo di accesso e durata impulso (0,5–5 secondi). Conferma l'applicazione del profilo.
6. Il componente configura e rilegge automaticamente il profilo del relè: avvio **OFF**, accensione automatica disabilitata, spegnimento automatico abilitato con la durata scelta. Prepara un QR permanente, salva il collegamento stabile al dispositivo e lascia il varco **inattivo**. Non serve creare script, helper, automazioni o YAML per ogni porta.
7. Dopo la verifica dell'installatore, usa **Abilita accesso**. La conferma controlla nuovamente il profilo, senza inviare un'apertura. Da **QR delle porte** visualizza e scarica il QR da stampare.

L'integrazione non configura Wi-Fi, credenziali Shelly, tunnel, DNS o Cloudflare e non modifica il comportamento dell'ingresso locale dello Shelly. Queste attività e la verifica elettrica restano parte dell'installazione. Il profilo automatico riguarda esclusivamente il relè scelto.

## Varchi di qualsiasi marca tramite Home Assistant

Il componente non è limitato agli Shelly. Da **Varchi → Aggiungi varco Home Assistant → Cerca entità apriporta**, seleziona l’entità già funzionante in HA, il comando, il nome e il tipo. L’associazione non esegue servizi e prepara un QR inattivo. Nelle opzioni dell’integrazione la stessa scelta è in **Aggiungi varco → Entità Home Assistant**.

| Tipo entità | Comando consentito | Comportamento |
| --- | --- | --- |
| `lock` (es. `lock.porta_d_ingresso_yale_linus_l2_3`) | `lock.unlock` oppure `lock.open` se supportato | Sblocca oppure aziona lo scrocco; nessuna richiusura automatica aggiunta dal gestionale |
| `switch` di qualsiasi marca | `switch.turn_on` | Impulso ON/OFF gestito da HA, oppure singolo ON con timer locale già configurato e confermato |
| `button`, `input_button` | `button.press`, `input_button.press` | Un solo comando al pulsante apriporta |
| `script` | `script.turn_on` | Un solo avvio dello script apriporta scelto dall’amministratore |
| `cover` | `cover.open_cover` se supportato | Un solo comando di apertura a cancello/portone |

**Sbloccare e aprire lo scrocco sono azioni distinte:** il selettore mostra solo le funzioni dichiarate da HA. La compatibilità riguarda l’entità e il servizio esposti dall’integrazione del dispositivo, non il nome del produttore. Non viene inviata alcuna istruzione generica `toggle`.

Per i relè generici puoi scegliere un impulso di 0,5–5 secondi gestito dal componente, senza creare automazioni o script. Lo spegnimento dipende da HA e dalla rete: se si interrompono può ritardare. Il componente salva l’intento di ripristino prima dell’ON, tenta OFF anche su timeout/cancellazione e ripristina solo OFF al caricamento; se non conferma OFF, mantiene il varco bloccato e mostra il ripristino riservato all’amministratore. Un timer locale del dispositivo è preferibile; per marche senza API dedicata deve essere configurato e verificato sul dispositivo, poi confermato nella procedura. La configurazione hardware automatica resta disponibile per gli Shelly supportati.

Il PIN della prenotazione **non viene inoltrato alla serratura** come codice hardware. Le serrature che richiedono un codice dispositivo esplicito vengono escluse dalla selezione diretta: possono essere gestite tramite uno script locale dedicato già configurato. Per dispositivi con altri tipi di entità o azioni proprietarie si può usare lo stesso adattamento tramite script, senza consentire servizi arbitrari al portale ospite.

## Uso da parte del gestore

- **Prenotazioni:** scegli camera, date e porte autorizzate. Il codice viene mostrato una volta; nell'archivio resta un hash salato. Le autorizzazioni fisiche delle porte selezionate vengono associate nella stessa operazione.
- **QR delle porte:** mostra e scarica il QR già esistente senza rigenerarlo. Il QR resta uguale tra prenotazioni e riavvii; il codice personale stabilisce chi può aprire e quando.
- **Registro accessi:** mostra l'esito delle richieste. Un comando inviato non prova che la serratura si sia sbloccata: non viene inventato un feedback di apertura.
- **Varchi e impostazioni:** riservati agli amministratori. Disattivare una porta conserva il QR; sostituirlo richiede una conferma esplicita e rende inutilizzabile la vecchia stampa. Il blocco di emergenza revoca QR e relativi permessi fisici.

Il pannello compare direttamente nella barra laterale HA e non richiede CL Control. Gli amministratori hanno accesso; un account attivo non amministratore deve essere selezionato nelle opzioni dell'integrazione. Il backend verifica il ruolo per ogni richiesta: nascondere i pulsanti non è il controllo di sicurezza.

## Aggiornamento da Bausan / versioni precedenti

L'aggiornamento conserva archivio, QR **fisici**, prenotazioni e stati di abilitazione già salvati; non abilita automaticamente porte o vecchie prenotazioni. Le associazioni esistenti Strada/Scala continuano a usare i due script già predisposti, come compatibilità. I nuovi flussi Shelly ed entità HA si applicano ai nuovi varchi.

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
