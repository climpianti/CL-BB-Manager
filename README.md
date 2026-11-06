# CL B&B Manager

Integrazione personalizzata per Home Assistant dedicata alla gestione dei varchi delle strutture ricettive.

**Stato: alpha 0.1.0 — prima base di sviluppo. Non ancora installazione operativa.**

La prima versione contiene il modello di configurazione, la persistenza locale e le regole pure per generare PIN, prenotazioni e autorizzazioni. Il numero di varchi è dinamico: i cinque varchi della demo non sono un limite.

L'integrazione non attiva ancora serrature, non dispone di un pannello gestionale completo e non espone il portale QR pubblico. Queste funzioni saranno aggiunte e testate nelle fasi successive.

Per iniziare i test unitari: installare pytest ed eseguire python -m pytest tests -q. Per la futura installazione Home Assistant, copiare custom_components/cl_bb_manager nella cartella custom_components della demo e configurare l'integrazione da Impostazioni > Dispositivi e servizi.

Vedere docs/ROADMAP.md e docs/SECURITY.md per lo stato delle funzioni e i requisiti prima della produzione.

Repository privato. Licenza non ancora scelta.
