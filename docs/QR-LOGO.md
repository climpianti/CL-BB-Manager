# Logo al centro del QR — 0.6.0-beta.4

## Configurazione

1. Aprire **Impostazioni → Dispositivi e servizi → CL B&B Manager → Configura → Logo nei QR** con un account amministratore.
2. Caricare un PNG, JPG oppure WebP statico, massimo 1 MB e 2048 × 2048 pixel. PNG trasparente consigliato. Lasciare attiva la voce **Mostra il logo nei QR** e salvare.
3. Nel pannello CL B&B Manager premere **Aggiorna**. In Impostazioni compare l’anteprima del logo salvato; da **QR delle porte → Mostra / scarica QR** si ottengono automaticamente i QR personalizzati.
4. Scaricare SVG per la stampa oppure PNG per salvataggio e condivisione. Entrambi incorporano l’immagine e non richiedono risorse esterne.

Per sostituire il logo caricare un nuovo file. Per disattivarlo conservando l’immagine togliere la spunta; per eliminarlo selezionare **Rimuovi il logo salvato**. Non selezionare contemporaneamente caricamento e rimozione. Se il caricamento non riesce, selezionare nuovamente il file prima di riprovare.

Cambiare il logo non rigenera il token QR, non abilita porte e non cambia prenotazioni o permessi. I QR già stampati continuano a funzionare. Per ottenere il nuovo aspetto basta scaricare nuovamente il QR: **Mostra / scarica QR non sostituisce il codice della porta**. La sostituzione/revoca resta un’azione amministrativa distinta.

## Implementazione e leggibilità

- Caricamento nativo HA con `FileSelector` e `process_uploaded_file`. Il contesto e la rimozione del temporaneo sono eseguiti interamente nell’executor, come richiesto dall’API HA.
- Accesso alle opzioni protetto dalle API amministrative HA. Gli operatori selezionati possono scaricare QR già predisposti, senza modificare il logo o sostituire i token.
- Validazione effettiva del formato, della dimensione e dei pixel, non solo dell’estensione. File SVG, GIF, animazioni e contenuti non validi vengono rifiutati. L’immagine viene ridimensionata, convertita in PNG e privata di EXIF, commenti e profili. Il PNG normalizzato è limitato a 64 KB e 256 pixel per lato; le proporzioni sono conservate.
- Immagine salvata nello Store dell’integrazione, senza percorsi locali o URL esterni. Disabilitare il logo conserva l’immagine; rimuoverlo la elimina dal record. Un errore di salvataggio ripristina il record precedente.
- QR con logo: correzione degli errori **H**, zona centrale non oltre il 18% della larghezza del simbolo e bordo bianco attorno all’immagine. Il generatore restringe la zona o seleziona una versione QR superiore per coprire esclusivamente moduli dati, preservando finder, allineamento, timing, formato e versione. Il margine bianco esterno resta di quattro moduli.
- SVG vettoriale con PNG incorporato; PNG esportato con identica disposizione e sfondo bianco opaco. Nessuna chiamata a servizi di generazione o traduzione esterni.
- Il rendering avviene nell’executor. La preparazione esplicita di un nuovo QR genera l’immagine prima di cambiare il token: un errore del logo non può revocare il codice stampato. La normale lettura del QR non scrive token, permessi o armamento.
- Il componente usa Pillow già richiesto da Home Assistant; non forza una versione alternativa nelle dipendenze dell’integrazione. Il decoder ZXing viene usato soltanto nei test.

La correzione H non è una garanzia di leggibilità per qualsiasi stampa o superficie. Per le porte usare preferibilmente una stampa di almeno 5 × 5 cm, mantenere il bordo bianco e verificare la scansione della copia effettiva prima di applicarla. La scansione può essere verificata aprendo soltanto la pagina del codice, senza eseguire un’apertura.

## Verifiche

- Suite completa: **396 test Python** e **15 test DOM JavaScript**.
- Decoder reale ZXing su loghi normali, completamente scuri o chiari, diversi domini e lunghezze dei token, incluso un nome DNS di 253 caratteri. Il valore decodificato deve essere esattamente il collegamento originale.
- Verifica delle aree funzionali preservate, margine bianco, aspetto, trasparenza e rimozione dei metadati; rifiuto di formati/animazioni/dimensioni non ammessi e file corrotti.
- Options Flow, upload con pulizia, persistenza dopo riavvio simulato, immutabilità di token e permessi durante la modifica del logo, ruoli e ripristino in caso di salvataggio fallito.
- Chromium 138: amministratore e operatore a 390/1366 pixel. Decodifica del PNG esportato, dell’SVG effettivamente renderizzato dal browser e dell’anteprima visualizzata a schermo; logo visibile, nessun errore JavaScript e nessuno scorrimento orizzontale.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
npm ci --ignore-scripts
npm test
```

Browser facoltativo con Chromium e Playwright disponibili:

```sh
CL_BB_PYTHON=/percorso/venv/bin/python \
CL_BB_CHROMIUM_PATH=/percorso/chromium \
node tests/browser_qr_logo.cjs
```

`CL_BB_PLAYWRIGHT_MODULE` indica un modulo Playwright esterno; `CL_BB_SCREENSHOT_DIR` abilita screenshot locali. Tutto usa dati e QR sintetici, senza collegarsi a Home Assistant o dispositivi reali. Il caricamento del file attraverso l’interfaccia completa di HA reale richiede la verifica dopo un’installazione autorizzata.

La revisione è preparata per approvazione: nessun logo è stato caricato sul sistema reale e non sono stati modificati i QR esistenti durante lo sviluppo.
