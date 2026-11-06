# CL B&B Manager

**Versione 0.2.0-alpha.1 — pannello gestionale di prova per Home Assistant.**

Integrazione CL Impianti per strutture ricettive: gestione di un numero variabile di varchi, prenotazioni e PIN temporanei, con interfaccia grafica nel menu laterale di Home Assistant.

## Disponibile nel codice

- Configurazione iniziale da **Impostazioni → Dispositivi e servizi**.
- Pannello amministratore **CL B&B Manager**, responsive, con sezioni **Varchi**, **Prenotazioni** e **Registro**.
- Aggiunta, modifica, abilitazione, disabilitazione e cancellazione di varchi, con nome, tipo comune/privato, entità Home Assistant e comando mappato. Massimo tecnico alpha: 200 varchi.
- Azioni configurabili in allowlist: `script.turn_on`, `button.press`, `lock.unlock`. **I comandi di apertura NON vengono eseguiti dall'integrazione in questa alpha.**
- Prenotazioni con check-in/check-out, associazione esplicita dei varchi e revoca. PIN numerico casuale di 8 cifre, memorizzato solo come hash con salt e mostrato una sola volta all'amministratore.
- Registrazione locale delle modifiche amministrative (senza PIN).
- Test unitari Python del modello e workflow GitHub Actions di convalida.

## Installazione manuale sulla demo

1. Eseguire un backup della configurazione Home Assistant di prova.
2. Copiare la cartella `custom_components/cl_bb_manager` in `/config/custom_components/cl_bb_manager`.
3. Verificare la configurazione e riavviare Home Assistant.
4. Aprire **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → CL B&B Manager**.
5. Impostare il nome della struttura, poi aprire il pannello **CL B&B Manager** nel menu laterale.
6. Aggiungere i varchi associandoli, per esempio, agli script demo `script.cl_bb_demo_apri_cancello`, `script.cl_bb_demo_apri_portone` e `script.cl_bb_demo_apri_camera_1`, `_2`, `_3`.
7. Abilitare i varchi di prova e creare una prenotazione, annotando il PIN mostrato una sola volta.

**Nota:** questa procedura non è stata ancora eseguita sul server Home Assistant demo nella presente versione del progetto. L'esito effettivo dell'installazione e della resa grafica deve essere verificato prima di considerare la fase collaudata.

## Non ancora disponibile

- Portale pubblico QR/PIN ospiti e stampa QR: intenzionalmente disabilitati fino all'hardening.
- Apertura diretta dei varchi dall'integrazione (simulati o fisici).
- Accesso gestionale con ruolo limitato non amministratore, calendario avanzato, integrazione con Booking/Airbnb e flussi pulizie.
- Verifiche complete di sicurezza, GDPR, validazione su Home Assistant 2026.10.4 e screenshot mobile/desktop.

## Test

- `python -m pip install -r requirements-dev.txt`
- `python -m pytest tests -q`
- `python -m compileall -q custom_components tests`
- `node --check custom_components/cl_bb_manager/frontend/panel.js`

Il workflow `.github/workflows/tests.yml` esegue questi controlli sui push e pull request, se GitHub Actions è abilitato per questo repository.

La licenza non è ancora stata definita; repository privato.

Ulteriori dettagli: [Roadmap](docs/ROADMAP.md) e [Sicurezza](docs/SECURITY.md).
