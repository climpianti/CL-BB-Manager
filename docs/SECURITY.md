# Sicurezza alpha

Questo codice non deve azionare varchi reali prima del collaudo.

- Il QR identificherà un varco, ma non conterrà credenziali.
- Il PIN è generato con un generatore crittograficamente sicuro e memorizzato solo come hash salato.
- Le regole di prenotazione e di autorizzazione devono essere controllate lato server.
- Non è attivo alcun endpoint pubblico per gli ospiti in questa versione.
- Non sono implementati limiti anti-bruteforce, audit, gateway sicuro, GDPR o interfaccia pubblica.
- Nessuna chiamata di apertura a entità Home Assistant è presente in questa versione.
