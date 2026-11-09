# Verifica della trasformazione — 0.6.0-beta.2

Data: 9 novembre 2026. Base: `main` alpha.17, commit `478ef2860934ccf0c6e59b22faee15a82c6cdc99`.

## Modifiche verificabili

| Problema | Correzione | Evidenza automatica |
| --- | --- | --- |
| Operatori selezionati rifiutati | `permissions.operator_user_ids` accetta `collections.abc.Mapping`, inclusa `MappingProxyType` di HA | Utente attivo selezionato ammesso; estraneo, revocato e inattivo negati; configurazione sempre riservata ad admin |
| Configurazione specifica Strada/Scala | `gate_setup` e `shelly_gate` usano registro entità, identità nativa e connessione autenticata dell'integrazione Shelly | Installazione vuota con nomi, struttura ed entità diversi dal sito Bausan |
| Script e timer da creare a mano | Configurazione `Switch.SetConfig` del solo profilo apriporta, rilettura e verifica uscita OFF | Nessun `Switch.Set` durante aggiunta/abilitazione; errori, offline e risposte incoerenti bloccano il flusso |
| Grafica di collaudo | Pannello operativo con prenotazioni, QR delle porte e registro; pagina PIN senza etichette di prova | DOM reale, testo renderizzato e browser Chromium desktop/mobile |
| Confusione fra QR | Solo endpoint pubblico `/physical/`; visualizzazione QR separata dalla sua sostituzione | Route di prova assenti, lettura QR non cambia token/armamento |
| Doppio passaggio sui permessi | Le nuove prenotazioni ricevono esattamente i varchi fisici selezionati | Flusso WebSocket reale dei callback, codice salvato solo come hash, POST isolata autorizzata |
| Rinomina entità | Risoluzione tramite unique ID, device ID, config entry e canale | Rinomina conserva QR e prenotazione; sostituzione identità rifiutata |
| Esito incerto del comando | Una sola RPC di impulso con timer locale, nessun retry automatico | Timeout simulato: nessuna seconda apertura |
| Errore di salvataggio | Aggiunta annullata con ripristino condizionato del profilo; abilitazione ripristinata allo stato precedente | Fault injection dello storage; nessun varco aggiunto/abilitato per errore |

Il driver si appoggia a `entry.runtime_data.rpc.device.call_rpc` della componente Shelly nativa. La forma dell'adattatore è stata confrontata con il codice ufficiale Home Assistant/aioshelly; i test usano registri e risposte con quella forma. Essendo un punto interno di HA, la compatibilità deve essere ricontrollata quando HA cambia struttura del runtime Shelly.

## Separazione dei ruoli

| Attività | Amministratore | Operatore abilitato | Altro utente HA |
| --- | --- | --- | --- |
| Panoramica, prenotazioni, codici, QR già predisposti, registro ospiti | Sì | Sì | No |
| Cercare/configurare Shelly e modificare varchi | Sì | No | No |
| Abilitare/disabilitare porta o sostituire QR | Sì | No | No |
| Selezionare gli operatori | Sì | No | No |

La revoca è verificata lato server alla richiesta successiva. Il pannello cancella codici e dati al cambio account/connessione e ignora risposte asincrone della sessione precedente. Un errore di autorizzazione consente di riprovare dopo l'abilitazione.

Il collegamento Home Assistant disponibile non consente l'elenco nominativo degli account. Non è stato aggirato questo limite: il difetto associato al caso John Felice è riprodotto e corretto, ma l'accesso del suo account reale non è stato verificato.

## Sicurezza HTTP e dispositivo

Restano obbligatori HTTPS e origine configurata, Origin/Fetch Metadata coerenti, form CSRF monouso, QR fisico valido, stessa struttura, porta abilitata, prenotazione non revocata nel proprio intervallo e permesso fisico esplicito. Persistono limiti dei tentativi e intervallo fra comandi. Il timer di spegnimento è nel dispositivo; prima del comando vengono riletti profilo e stato OFF. Non sono accettati host, credenziali, metodi RPC o servizi arbitrari dal client.

La registrazione di un varco può scrivere le impostazioni Shelly dopo conferma dell'installatore. Non invia ON e non altera le impostazioni dell'ingresso locale. L'abilitazione è separata; non richiede una prenotazione fittizia. Le associazioni storiche restano compatibili senza modificare QR, permessi o stato durante l'aggiornamento.

## Risultati e limiti

- Suite Python e regressioni HTTP: **290 test superati** (`python -m pytest tests -q`), inclusi i due percorsi compatibili Strada/Scala con attuatori fittizi.
- Suite DOM JavaScript: **13 test superati** (`npm test`); verifica il DOM realmente costruito e gli eventi del pannello.
- Chromium 138 ha inoltre confermato il comportamento del form nativo: con `no-referrer` invia `Origin: null`; con `strict-origin` invia l’origine HTTPS corretta e un Referer privo del percorso/token.
- Chromium 138, dati fittizi, richieste intercettate: 4 combinazioni ruolo/larghezza, 20 visite di schede; nessun errore JavaScript e nessuno scorrimento orizzontale.
- Installazione, salvataggio, riavvio e apertura sono simulati con gli handler effettivi del componente. Non è stata avviata una nuova istanza HA completa né comandato hardware reale.
- La configurazione hardware automatica supporta Shelly 1 Mini Gen3 online/OFF. Il driver generico supporta entità HA di qualsiasi marca nei domini `lock`, `switch`, `button`, `input_button`, `script` e `cover`, secondo le azioni disponibili e le conferme dell’installatore. Una struttura per istanza HA, fino a 200 varchi, massimo 20 operatori e soggiorni fino a 90 giorni.

Questa modifica è una versione candidata da revisionare, non una dichiarazione di collaudo hardware concluso. Il numero beta compare nel manifest e nella documentazione tecnica; non sostituisce le etichette operative dell'interfaccia con messaggi di prova.

## Collaudo per consegna al cliente

1. Su un HA pulito aggiungere il modello Shelly supportato e installare la revisione esatta. Verificare configurazione, reload e assenza di script/helper richiesti.
2. Con serratura disconnessa o banco prova, verificare prima/dopo le quattro impostazioni e l'uscita OFF durante la procedura. Controllare anche il comportamento elettrico dell'ingresso locale, lasciato invariato dal componente.
3. Accedere con un amministratore e un operatore selezionato; controllare l'accesso del secondo senza privilegi di amministratore e il rifiuto delle funzioni di configurazione. Provare revoca e riabilitazione.
4. Dopo autorizzazione esplicita al collaudo fisico, abilitare il varco, creare una prenotazione di prova e stampare il QR dalla sezione dedicata. Dal telefono, aprire il QR in HTTPS e inserire il codice della prenotazione. Verificare un solo comando. Per i relè con timer locale verificare durata e ritorno OFF anche durante l’interruzione di HA; per l’impulso HA verificare durata in condizioni normali e recupero OFF al ripristino della connessione.
5. Ripetere il flusso per due porte distinte e provare codice errato, scadenza, revoca e porta non autorizzata. Riavviare HA e verificare che il QR stampato resti valido con i soli permessi previsti.
6. Prima della consegna reale verificare cablaggio, backup/ripristino e procedura operativa del gestore. Per Bausan non sostituire i QR esistenti e non cambiare armamento o prenotazioni come effetto dell'aggiornamento.

Nessuna modifica di questa revisione è stata distribuita sul sistema reale durante lo sviluppo; non sono stati impartiti comandi di apertura, cambiati stati delle porte, token o autorizzazioni reali.

## Estensione entità HA — beta.2

`entity_gate.py` gestisce le azioni standard di serrature, relè, pulsanti, script e cancelli. L’amministratore associa un’entità e un’azione tipizzata: nessun servizio, codice dispositivo o target arbitrario viene accettato dalla pagina ospite. `lock.open` richiede la funzione OPEN dichiarata; `lock.unlock` non viene confuso con l’azionamento dello scrocco. La corrispondenza viene verificata di nuovo prima del comando. Se l’entità è registrata, l’identità di registro viene conservata per tollerare rinomine e rifiutare rimozioni/sostituzioni. Entità senza registro sono associate al loro entity ID: non possono seguire una rinomina automaticamente.

Per i relè generici è disponibile l’impulso gestito da HA oppure il timer locale già configurato. Il primo non garantisce lo spegnimento durante un’interruzione di HA/rete: l’intento viene salvato prima dell’ON e il ripristino invia solo OFF. L’avvio/scaricamento ha un budget di 12 secondi per i ripristini; quelli non completati restano bloccati e recuperabili dall’amministratore. Non vengono ritentati automaticamente comandi di apertura. Il timer locale generico richiede conferma esplicita e non viene configurato via API universali inesistenti.

I test aggiunti includono flusso WebSocket → prenotazione → GET/POST effettive per Yale simulata (`unlock`/`open`) e relè di altra marca, feature mancanti, codici hardware richiesti, servizi arbitrari rifiutati, identità sostituita, timeout, cancellazione, salvataggio fallito e recupero OFF persistente. Nessuna apertura reale è stata eseguita; l’entità Yale indicata dall’utente è usata come identificatore di fixture, non è stata comandata o interrogata sull’impianto.
