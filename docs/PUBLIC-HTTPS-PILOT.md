> Documento storico delle release precedenti. Per installazione e stato attuali vedere [README](../README.md) e [PRODUCT-READINESS](PRODUCT-READINESS.md).

# Collaudo QR HTTPS temporaneo (0.5.0-alpha.1)

**SOLO COLLAUDO CON SCRIPT VIRTUALI. NON PER PORTE FISICHE.**

Il portale permanente `/api/cl_bb_manager/guest/{token}` rimane disattivato. Il percorso pubblico di prova è separato: `/api/cl_bb_manager/public-demo/{token}`.

## Requisiti
- Versione 0.5.0-alpha.1 installata su Home Assistant, configurazione verificata e backup completo.
- Solo varchi che puntano ai cinque script dimostrativi autorizzati, e ogni script deve comandare **esclusivamente un helper `input_boolean`**.
- Origine HTTPS esatta, ad esempio `https://1wbausanresidency.climpianti.eu`, instradata via Cloudflare Tunnel. Nessun port forwarding o esposizione diretta del server.
- Verificare il proxy e le intestazioni Host, Origin, `Sec-Fetch-Site` prima di dichiarare superata la prova.

## Configurazione
1. Aggiornare l'integrazione tramite Marketplace/HACS, con backup e verifica delle modifiche.
2. Riavviare HA in una finestra concordata e verificare che il pannello e gli altri componenti siano tornati online.
3. In **Impostazioni > Dispositivi e servizi > CL B&B Manager > Configura**, attivare **Collaudo QR temporaneo via HTTPS** e inserire il dominio HTTPS esatto senza slash, percorsi o porta. La funzionalità è **disattivata per impostazione predefinita**.
4. Nel pannello **CL B&B Manager > Collaudo accessi**, selezionare uno dei varchi **virtuali** e generare il **QR HTTPS di prova**.
5. Generare una prenotazione fittizia con PIN e permesso solo per il varco scelto. Conservare il PIN in modo riservato, senza pubblicarlo in chat, ticket o repository.

## Proprietà del QR di prova
- Sessione generata esclusivamente da amministratore HA autenticato, con token casuale ad alta entropia.
- Scadenza **10 minuti**, **al massimo 5** sessioni pubbliche concorrenti, nessuna persistenza dopo il riavvio.
- **Monouso dopo apertura riuscita**, PIN di prenotazione obbligatorio, CSRF e limiti persistenti di tentativi globali/per varco.
- Vincolo al dominio HTTPS impostato, all'hostname della richiesta, alla validità del varco e all'allowlist di script dimostrativi.
- Nessun URL o PIN registrato negli eventi; le azioni negative e positive vengono registrate solo per ID del varco.
- La disattivazione del flag nelle opzioni causa il rifiuto immediato delle sessioni ancora in corso.

## Prove richieste prima di concludere il pilota
- Test da smartphone esterno in 4G/5G: GET della pagina, POST di PIN valido e impulso di **solo `input_boolean`**.
- Ripetizione del POST/QR dopo apertura: rifiuto.
- PIN errato, prenotazione fuori orario, revocata, altro varco: rifiuto.
- Origine/host diversi, CSRF invalido, token scaduto: rifiuto.
- Rate limit: blocco dopo tentativi eccessivi.
- Ricontrollare il comportamento del precedente QR **LAN**.
- Il percorso permanente `/guest/` deve restituire **404**.
- Nessuna regressione nelle altre automazioni, script e integrazioni di HA.

## Chiusura o incidente
Disattivare **Collaudo QR temporaneo via HTTPS** nelle opzioni dell'integrazione; tutte le richieste alla pagina pubblica devono tornare 404 senza bisogno di cancellare prenotazioni. Se necessario ripristinare la versione precedente e riavviare da finestra concordata. Non collegare mai questa versione agli attuatori delle porte reali.

**Questa versione è una alpha di prova.** I controlli qui descritti non sostituiscono un penetration test o una verifica indipendente del reverse proxy e dei requisiti privacy.

