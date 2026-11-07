# Collaudo pilota B&B Covone — CL B&B Manager 0.4.0-alpha.4

**Stato: preparazione, non installato su B&B Covone.** Data: 7 novembre 2026.

Sorgente bloccata per il pilota: commit `b66c2d78014f3a480af005627781ff9c7287dfdc`, branch `pilot/bb-covone-alpha4`. Il codice è ancora una alpha e il repository deve restare privato.

## Regole di sicurezza
- Nessun comando a serrature, relè, cancelli, citofoni o script esistenti del B&B. Simulare le aperture esclusivamente con helper `input_boolean` e script dedicati, dopo averne verificato il contenuto.
- Il percorso QR permanente `/guest/` resta disattivato. Il QR `/demo/` ha validità di 10 minuti e funziona solo sulla LAN; non esporlo tramite Cloudflare, porte inoltrate o proxy Internet.
- Non pubblicare PIN, token del QR o informazioni personali delle prenotazioni.
- Identificare inequivocabilmente l'Home Assistant Covone prima di ogni operazione; non usare la connessione della demo.

## Preflight — da completare prima dell'installazione
- [ ] Connettore B&B Covone raggiungibile con accesso adeguato; identità e URL dell'istanza verificati.
- [ ] Versione Home Assistant, stato sistema e presenza di errori rilevati.
- [ ] Accesso controllato a `/config/custom_components/`.
- [ ] Presenza di un'eventuale vecchia installazione CL B&B Manager e dati da conservare verificata.
- [ ] Backup integrale di HA creato, validato e con percorso di ripristino identificato.
- [ ] Finestra di manutenzione concordata per l'eventuale riavvio.

## Distribuzione controllata
1. Se esiste un componente precedente, copiarne i file e definire il rollback senza perdere configurazioni o dati.
2. Copiare `custom_components/cl_bb_manager/` dal commit bloccato in `/config/custom_components/cl_bb_manager/`.
3. Verificare `manifest.json`: versione `0.4.0-alpha.4`, dipendenze risolte.
4. Preparare esclusivamente cinque script demo dedicati (Cancello, Portone, Camera 1, Camera 2, Camera 3), ciascuno collegato a un helper virtuale. Non collegarli ad attuatori fisici.
5. Eseguire controllo di configurazione HA; riavviare una sola volta se richiesto e verificare il ritorno online e l'assenza di regressioni.
6. Aggiungere **una sola** istanza CL B&B Manager da Impostazioni > Dispositivi e servizi; non duplicarne una preesistente.
7. Usare prenotazioni di prova e revocarle dopo il collaudo.

## Matrice prove
| Test | Risultato atteso | Stato |
| --- | --- | --- |
| Caricamento integrazione e pannello | Nessun errore o duplicato | Da eseguire |
| QR temporaneo con PIN valido, stanza e orario corretti | Conferma e solo impulso virtuale previsto | Da eseguire |
| PIN errato, di altra stanza, scaduto, revocato o fuori orario | Rifiuto senza impulso | Da eseguire |
| QR scaduto (10 min) o dopo riavvio | Rifiuto | Da eseguire |
| Limitazione tentativi e logging | Limitazioni applicate; nessun segreto nei log | Da eseguire |
| Android/iOS sulla stessa rete locale | Invio modulo senza 403 imprevisto | Da eseguire |
| Richiesta da Internet o via dominio pubblico | Rifiuto | Da eseguire |
| QR permanente `/guest/` | Disabilitato | Da eseguire |
| Ripartenza di HA e altre integrazioni | Nessuna regressione | Da eseguire |

## Rollback
Se fallisce il collaudo, disabilitare l'integrazione, ripristinare i file salvati o rimuovere solo i file nuovi (senza cancellare dati); controllare la configurazione prima di riavviare. Ripristinare il backup dell'istanza se necessario. Non effettuare riavvii ripetuti non controllati.

## Criterio di passaggio alla beta
Completare il collaudo pilota su Covone e i test di regressione sulla demo. **Portale pubblico e hardware reale restano in una fase separata**, con verifica HTTPS/reverse proxy, rate limit, CSRF, autorizzazioni, fail-closed, backup/recupero, audit, GDPR e revisione di sicurezza. Nessuna promozione automatica da alpha a beta.
