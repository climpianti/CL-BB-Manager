# CL B&B Manager — checklist pre-beta (9 novembre 2026)

Questa checklist distingue test eseguiti da attività ancora aperte. La release **0.5.0-alpha.7** non è un prodotto per il controllo di serrature fisiche.

## Stato del pilot verificato

- [x] Aggiornamento HACS al commit `397de94` (pre-alpha.7), riavvio e integrazione nuovamente caricata.
- [x] Archivio migrato a schema 3, con vecchi e nuovi record dotati di `property_id`.
- [x] Prenotazione di prova creata con proprietà assegnata e revocata, senza contaminare i dati di altre strutture.
- [x] Rifiuto server-side di un identificativo varco inesistente/non associato alla struttura.
- [x] Generazione QR LAN temporaneo (scadenza 600 s) dal WebSocket amministratore.
- [x] Script virtuale `script.cl_bb_demo_apri_cancello` ispezionato: modifica solamente `input_boolean.cl_bb_demo_cancello`, non dispositivi fisici.
- [x] Attivazione diretta dello script virtuale: nello storico Home Assistant si vede `off → on → off` in circa 2 secondi.
- [ ] Test completo con **PIN valido** attraverso il backend `cl_bb_manager/demo_check_pin` e verifica dell'impulso, senza accesso fisico.
- [ ] Test completo con PIN errato/scaduto/revocato e camere differenti tramite i portali HTTP.
- [ ] Scansione di QR LAN da smartphone fisico con browser reale e PIN di collaudo (nessuna serratura fisica).
- [ ] Scansione di QR HTTPS dietro reverse proxy con verifica host, origine, CSRF, revoca, scadenza e monouso.
- [ ] Verifiche visuali mobile/desktop del pannello.
- [ ] Monitoraggio dei log dopo il ciclo end-to-end; non confondere i rifiuti di test intenzionali con crash applicativi.

## Criteri vincolanti prima della beta pubblica

- [ ] Distinguere l'architettura **una struttura per installazione** dall'eventuale gestione multi-struttura nella stessa istanza: quest'ultima **non è ancora disponibile**.
- [ ] Eseguire test end-to-end riproducibili di tutte le interfacce WebSocket, LAN e HTTPS e controllare la rate limit persistente.
- [ ] Eseguire review sicurezza indipendente su PIN, token QR, proxy HTTPS, concorrenza e isolamento tenant.
- [ ] Preparare migrazione/rollback **con backup** per installazioni commerciali: il bypass esplicito nel solo pilot non è un modello di distribuzione.
- [ ] Validare backup, ripristino e aggiornamento da versione precedente su una seconda istanza Home Assistant indipendente.
- [ ] Aggiungere diagnostica redatta (nessun PIN, token, dati personali) e istruzioni di troubleshooting.
- [ ] Verificare comportamento di autorizzazioni amministratore/operatore e minimizzazione GDPR, tempi di conservazione e cancellazione.
- [ ] Rimuovere riferimenti specifici alla struttura pilota dai percorsi di configurazione e collaudo prodotto.
- [ ] Verificare CI compatibile con versioni Home Assistant e Python supportate; release/tag HACS e changelog pubblicati.
- [ ] Beta controllata su più installazioni, senza comandi a dispositivi reali.

## Sicurezza

L'integrazione mantiene `hardware_control: disabled`. Gli endpoint permanenti ospite restano inattivi. I soli script ammessi per i test sono i cinque `script.cl_bb_demo_apri_*`, *dopo aver verificato* che attivino esclusivamente helper virtuali. La beta non deve essere dichiarata pronta né usata per porte reali finché le attività sopra non risultano completate e documentate.


## Revisione QR fisico — alpha.11 (9 novembre 2026)

- [x] Collaudo manuale separato dei due Shelly: Porta Strada e Porta Scala, feedback fisico positivo dell'operatore.
- [x] Associazioni hardware salvate come candidati non eseguibili, senza sostituire script virtuali, prenotazioni o token QR.
- [x] Controllo esplicito dell'Origin HTTPS: un Origin diverso, `null`, protocollo HTTP, Sec-Fetch-Site `cross-site` o `same-site` sono respinti anche se il CSRF è valido.
- [x] Moduli mobili senza Origin restano ammessi solo con fetch metadata compatibili e CSRF monouso valido; l'assenza di Origin non sostituisce il controllo CSRF.
- [x] Preflight amministrativo di sola lettura: stato candidato, esistenza script, varco virtuale e motivi di blocco.
- [x] Test automatici dei casi di origine non valida, preflight non attivante e isolamento QR.
- [ ] Revisione di sicurezza indipendente e prove negative end-to-end effettuate dall'esterno su rete mobile, inclusi Origin/Host/proxy, CSRF/replay, PIN errato, scaduto, revocato, concorrenza, rate limit e riavvio.
- [ ] Piano documentato e verificato di recupero/rollback, backup e monitoraggio per porte reali.
- [ ] Verifica del comportamento con Shelly offline, stato incerto e comando accettato senza reale apertura; eventuali sensori di conferma porta.
- [ ] Approvazione esplicita di un rilascio successivo con attivazione fisica gestita; **alpha.11 non abilita nessuna apertura fisica via QR**.

Comando di verifica: `cl_bb_manager/hardware_preflight` via WebSocket autenticato amministratore, oppure pulsante **Verifica prerequisiti QR fisico** nel pannello Varchi. Nessun campo del report può abilitare serrature; `hardware_control` resta `disabled` e `physical_qr_enabled` sempre `false`.


## QR security regression candidate alpha.12 — 9 novembre 2026

Il pacchetto di regressione automatica `tests/test_qr_release_gate.py` esercita le view HTTP reali con un Home Assistant simulato, **senza alcun comando alle serrature reali**. Controlla: isolamento dello script candidato Shelly, PIN errato, prenotazioni revocate/scadute/non ancora iniziate, stanza/varco errati, proprietà differenti, origine HTTP/HTTPS non autorizzata, CSRF mancante/errato/scaduto, doppio invio concorrente del modulo, limiti persistenti per varco, varco disabilitato, script virtuale indisponibile e fallimento della chiamata servizio.

### Criterio di pubblicazione

- [ ] CI verde di alpha.12 e revisione del codice.
- [ ] Installazione HACS e riavvio pilota con verifica di `hardware_control: disabled` e `physical_qr_enabled: false`.
- [ ] Test reale HTTPS da connessione mobile: codice valido ed errato, revoca, tentativi ripetuti e gestione dei messaggi su iOS/Android. I test simulati in CI **non** sostituiscono il collaudo da rete esterna.
- [ ] Backup aggiornato dopo l'ultimo intervento; verificare ripristino su istanza separata prima di aprire serrature reali da Internet.
- [ ] Audit di sicurezza **indipendente** dell'integrazione, dell'accesso Internet, del reverse proxy e del percorso verso le serrature.
- [ ] Convalida operativa degli stati di guasto Shelly offline, guasto di rete e mancata apertura confermata da sensore.
- [ ] Pubblicazione release hardware disponibile solo dopo i precedenti requisiti: la release alpha.12 resta un rilascio **virtual-only**.

**Roll-back software:** tornare al commit HACS `56123ec` (alpha.11) o al backup Home Assistant verificato. Non ruotare i token QR se non si sospetta compromissione; in quel caso revocarli con il comando amministrativo e sostituire fisicamente le stampe.


## Physical QR protected path — alpha.13 (staging only)

A separate HTTP route `/api/cl_bb_manager/physical/{token}` now exists behind a **code-level kill switch** `PHYSICAL_RELEASE_ENABLED = False`. It returns 404 for all requests in this release, regardless of PIN, QR, HA state or caller privileges. The existing `permanent-demo` QR remains unchanged, and continues to target only virtual scripts. **No physical QR is issued.**

A future reviewed release must separately provision a strong `physical_token`, explicitly opt in per gate and per installation, grant `physical_gate_ids` for each booking, inspect live Shelly health and source/CSRF checks, and enforce persisted attempt limits, cooldown, property isolation and audit. The new design makes none of these permissions inherited from demo bookings.

Mocked end-to-end tests verify default unavailability, distinct tokens, missing physical grants, unavailable hardware, repeated submissions, invalid PIN, cross-site submissions and cooldown. All simulated service calls are captured by the fake Home Assistant object; CI never connects to a real actuator.

- [ ] Complete independent code/security review, load testing and real mobile/browser HTTPS acceptance prior to any change of kill-switch state.
- [ ] Define administrative approval and instant disable/rollback operation; do not expose an unreviewed enable endpoint.
- [ ] Verify how an accepted Home Assistant service call is confirmed by a physical door sensor, or present its uncertainty explicitly.
- [ ] Only after the above: release a separate, reviewed production build that intentionally enables the physical route and provisions new tokens; no existing printed demo QR should become a physical key automatically.
