> Documento storico delle release precedenti. Per installazione e stato attuali vedere [README](../README.md) e [PRODUCT-READINESS](PRODUCT-READINESS.md).

# Sicurezza — CL B&B Manager 0.4.0-alpha.1

**Prototipo per collaudo virtuale. Non installare su accessi fisici attivi.**

## Portale pubblico permanente
- **Disattivato** senza opzione pubblica per attivarlo.
- Il QR permanente resta solo un'anteprima in attesa di verifica completa del modello di sicurezza del prodotto.

## Nuovo percorso demo locale
- Un amministratore autenticato genera una sessione **temporanea di 600 secondi** con token casuale a elevata entropia, associata a un solo varco virtuale.
- Accetta soltanto URL locali con indirizzi privati 10/8, 172.16/12, 192.168/16 o domini `*.local`. Gli URL con credenziali, percorsi o destinazioni Internet sono rifiutati.
- La richiesta è autorizzata soltanto quando l'hostname corrisponde a quello generato, il mittente è locale e la sessione non è scaduta.
- Il PIN numerico resta obbligatorio e viene verificato tramite hash PBKDF2 salato. Sono applicati limiti persistenti di tentativi globali e per varco, prima delle verifiche costose.
- Il comando può attivare soltanto gli script virtuali della demo inclusi nell'allowlist. L'entità deve esistere e il varco essere ancora abilitato.
- Ogni POST richiede la stessa Origin che ha creato la sessione; la pagina imposta CSP, no-store e no-referrer.
- Il token di sessione resta in memoria, non viene scritto in storage e non sopravvive a un riavvio.

## Limiti ancora da risolvere
- L'autorizzazione alla rete locale **non** sostituisce una configurazione sicura e verificata del reverse proxy: tunnel non standard che cambiano Host o indirizzo remoto possono invalidare le assunzioni. Mai esporre il percorso demo attraverso un proxy pubblicamente accessibile.
- Il PIN di 8 cifre non deve essere considerato sufficiente per una serratura reale senza controlli ulteriori (lockout, attacchi distribuiti, scenari offline, allarmi e revisione).
- Non sono certificati il controllo della provenienza degli script di demo né la protezione contro modifiche all'hardware sottostante: tutti e cinque gli script devono continuare a comandare **solo input_boolean virtuali**.
- Mancano penetration test, test di concorrenza su HA reale, verifica completa HTTPS/Cloudflare, gestione identità e privacy, conservazione e cancellazione dati, fail-closed in presenza di crash e ruoli utente specifici.
- Le sessioni locali temporanee non sono equivalenti a un portale ospiti di produzione.

Non pubblicare QR o token di prova in chat, ticket pubblici o repository; anche una sessione di 10 minuti è un segreto temporaneo.

