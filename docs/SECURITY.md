# Sicurezza — Alpha 0.3 (non pronta per produzione)

- **Portale ospiti disattivato per impostazione predefinita**: `demo_guest_portal` non ha ancora alcuna opzione UI e quindi non può essere abilitato normalmente dalla dashboard.
- Gli unici target permessi dal portale, quando attivato in futuro, sono cinque script virtuali identificati esplicitamente nel codice; non sono autorizzate entità `lock`, `switch` o `button`.
- I PIN sono numerici di 8 cifre, generati casualmente e memorizzati tramite PBKDF2 salato; non vengono restituiti nelle liste.
- La pagina non incorpora credenziali HA nel QR. Verifica data, revoca e appartenenza del varco ad ogni tentativo.
- Limite tentativi per client e globale **solo in memoria**: non protegge in modo sufficiente da distribuzione degli attacchi o restart.
- La richiesta POST deve avere l'Origin corrispondente al servizio: i proxy devono preservare Host e schema.
- Necessari TLS, monitoraggio, reverse proxy anti-bot, test penetrazione, audit, policy privacy e retention prima dell'utilizzo su ospiti reali.
- Nessuno script identificato come virtuale deve essere ricollegato a serrature fisiche: la sola corrispondenza dell'entity_id non prova che il dispositivo sia simulato.
- Non pubblicare su GitHub token, PIN, backup, indirizzi privati o credenziali.
