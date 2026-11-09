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
