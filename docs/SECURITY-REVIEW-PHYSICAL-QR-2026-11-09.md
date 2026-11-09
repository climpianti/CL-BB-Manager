# Revisione tecnica del percorso QR fisico — 9 novembre 2026

## Ambito ed evidenze

Analisi del codice alpha.13 del repository e verifica di sola lettura su Home Assistant 1W Bausan Residency. I due script locali Shelly sono stati collaudati manualmente in una sessione precedente. Questo documento è una **revisione tecnica interna**, non un penetration test indipendente, né un'attestazione di sicurezza del reverse proxy Cloudflare o delle connessioni Internet.

Il codice attivo mantiene `PHYSICAL_RELEASE_ENABLED = False`. Il QR permanente pubblico esistente richiama soltanto script demo; non diventa un token fisico. Nessuna serratura è stata comandata durante la presente revisione.

## Esiti della revisione e mitigazioni

| Rischio | Osservazione | Intervento |
|---|---|---|
| Sostituzione di script con entità arbitrarie | Il candidato hardware era validato solo come `script.*`, senza il controllo del relè effettivamente collegato. | In alpha.14, allowlist delle coppie script/Shelly del pilota. Rifiuto degli script non censiti. |
| Shelly offline, ON o con stato incerto | La presenza di uno script `off` non prova che l'attuatore sia disponibile. | In alpha.14, controllare **anche** il relè associato che deve essere `off`; fail closed negli altri casi. |
| Timestamp del cooldown non finito | `NaN` era accettato come timestamp e può compromettere il blocco delle ripetizioni. | In alpha.14, rifiuto di `NaN`, valori infiniti e booleani nello stato e nel tempo corrente. |
| Credenziali QR già stampate | Il QR demo è stato distribuito senza capacità fisica. Non deve ereditare accesso alla serratura. | I token fisici devono essere differenti dai token demo; nessuna migrazione automatica. |
| Autorizzazione automatica delle prenotazioni | Prenotazioni demo già valide non devono sbloccare serrature. | Richiesto `physical_gate_ids` esplicito, oltre al PIN e alla finestra di soggiorno; il provisioning dei permessi fisici non è ancora implementato. |
| Tentativi, CSRF, ripetizione | Richieste concorrenti o ripetute potrebbero causare più impulsi. | Lock serializzato, nonce consumato una volta sola, limiti persistenti e cooldown registrato prima dell'attuazione. |
| Conferma apertura fisica | Home Assistant segnala un comando accettato, non necessariamente serratura sbloccata. | Messaggio di conferma limitato a «comando inviato»; mancano sensori indipendenti di conferma. |
| Disabilitazione immediata | Una disconnessione o compromissione del portale deve poter interrompere il percorso fisico. | Kill switch a livello di codice è attualmente **OFF**; futura procedura amministrativa di emergenza da implementare/testare. |

## Blocchi residui prima del rilascio con comandi reali

- [ ] Verifica indipendente del percorso completo HTTP/Cloudflare/autorizzazione/HA/Shelly, inclusi i proxy header e la superficie di attacco pubblica.
- [ ] Provisioning amministrativo auditabile di token fisici separati, doppia abilitazione globale e per-varco, permessi fisici per nuova prenotazione e revoca.
- [ ] Test del comando di disabilitazione di emergenza e revoca token in caso di compromissione.
- [ ] Collaudo end-to-end supervisionato sul posto con prova fisica Porta Strada e Porta Scala e verifica di **un solo impulso** per autorizzazione.
- [ ] Verifica con Shelly scollegato, riavvio HA, revoca prenotazione, PIN errato, richiesta duplicata e rete mobile esterna.
- [ ] Piano di ripristino e responsabilità operativa per la porta, nel rispetto della scelta dell'utente di non effettuare adesso un nuovo backup.

**Esito:** preparazione e test software possibili, **attivazione fisica pubblica NON approvata**. La release alpha.14 resta deliberatamente con `PHYSICAL_RELEASE_ENABLED = False` e `hardware_control = disabled`; la revisione interna non sostituisce quella indipendente.
