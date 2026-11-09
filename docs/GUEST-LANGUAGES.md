# Lingue della pagina ospiti — 0.6.0-beta.3

Questa revisione seleziona automaticamente italiano o inglese per il portale fisico `/api/cl_bb_manager/physical/…`.

## Comportamento

| Preferenze del browser | Lingua della pagina |
| --- | --- |
| Italiano / `it-IT` | Italiano |
| Inglese / `en-US` / `en-GB` | Inglese |
| Più lingue | Prima lingua supportata secondo priorità `q` e ordine dichiarati |
| Solo lingue non supportate | Inglese |
| Header assente o vuoto | Italiano, per compatibilità |

Il rilevamento usa `Accept-Language` lato server, senza JavaScript né servizi esterni. L’header è analizzato con limiti di dimensione e numero di voci; i valori non validi vengono ignorati. La risposta include `Content-Language`, `Vary: Accept-Language` e `html lang` coerenti.

Le traduzioni coprono istruzioni, pulsanti, conferma ed errori attesi 400/403/404/429/503. I testi sono rivolti all’ospite: per esempio «Inserisci il codice di accesso ricevuto dalla struttura» / «Enter the access code provided by the property». Il successo indica «Richiesta inviata» / «Request sent» e invita a verificare lo sblocco. Non viene affermato un riscontro fisico della serratura.

Nomi configurati delle porte e marchio rimangono invariati. Il pannello del gestore e le impostazioni HA conservano la lingua attuale: la modifica riguarda le pagine viste dagli ospiti.

## Sicurezza e aggiornamento

Non cambiano URL e token QR, PIN, permessi, stati delle porte o archivio. Non servono ristampe. Non vengono introdotti cookie, parametri di form o script della pagina. Restano `Cache-Control: no-store`, CSP, `Referrer-Policy: strict-origin`, controlli Origin/Fetch Metadata, nonce monouso, limiti dei tentativi e rifiuto dei replay. Lo stesso stato HTTP e il tipo di eccezione vengono conservati per gli errori tradotti; i dettagli interni delle eccezioni non sono mostrati.

Il rilevamento segue ciò che il browser invia: una preferenza modificata nel browser viene applicata alla successiva richiesta. Un eventuale browser che omette le preferenze riceve l’italiano.

## Verifiche riproducibili

- `python -m pytest tests -q`: **355 test superati**, di cui 65 per la localizzazione, comprese le due porte in entrambe le lingue e gli esiti 200/400/403/404/429/503.
- `npm test`: **13 test DOM superati**, mantenendo i controlli del pannello e dei ruoli.
- Chromium 138 mobile: quattro combinazioni Strada/Scala × italiano/inglese, preferenze native `it-IT` e `en-US`, GET → codice errato → riprova → codice corretto. Confermati traduzioni, status 403/200, un solo comando simulato per flusso, assenza di errori JavaScript e assenza di scorrimento orizzontale.

Esecuzione facoltativa del browser, con Chromium e `playwright-core` già disponibili:

```sh
CL_BB_CHROMIUM_PATH=/percorso/chromium \
CL_BB_PYTHON=/percorso/venv/bin/python \
node tests/browser_guest_languages.cjs
```

`CL_BB_PLAYWRIGHT_MODULE` consente di indicare il modulo Playwright; `CL_BB_SCREENSHOT_DIR` abilita screenshot locali. Il server di prova ascolta solo su loopback e carica gli handler effettivi con Home Assistant e attuatori fittizi. Tutte le richieste della pagina sono intercettate e inoltrate a quel server; nessuna richiesta raggiunge Home Assistant o dispositivi reali.

Questa revisione richiede approvazione separata per merge e installazione sul sistema reale. Non è stata distribuita durante lo sviluppo.
