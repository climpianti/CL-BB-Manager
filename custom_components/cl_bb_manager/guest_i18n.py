"""Guest-only Italian/English copy and bounded browser language negotiation."""
from __future__ import annotations

import re

COPY = {
    'it': {
        'title': 'CL B&B Manager · Accesso',
        'brand_subtitle': 'ACCESSO OSPITI',
        'eyebrow': 'Accesso alla struttura',
        'generic_gate': 'Accesso ospiti',
        'prompt': 'Inserisci il codice di accesso ricevuto dalla struttura.',
        'code_label': 'Codice di accesso',
        'continue': 'Continua',
        'retry': 'Riapri la pagina del codice',
        'security': 'Codice personale · Connessione protetta',
        'help': 'Per assistenza, contatta la struttura.',
        'success_title': 'Richiesta inviata',
        'success_body': 'Verifica che la porta si sia sbloccata. Se non si apre, contatta la struttura.',
        'success': 'Attendi qualche istante e prova ad aprire la porta.',
        'invalid_code': 'Codice non valido o non autorizzato per questa porta. Verifica il codice e le date del soggiorno.',
        'too_many': 'Troppi tentativi. Attendi prima di riprovare.',
        'cooldown': 'Attendi qualche secondo prima di inviare una nuova richiesta.',
        'origin': 'Impossibile verificare la pagina. Riapri il collegamento dal QR della porta.',
        'session': 'Sessione scaduta o già utilizzata. Riapri la pagina del codice.',
        'unavailable': 'Non è stato possibile confermare la richiesta. Contatta la struttura prima di riprovare.',
        'not_found': 'Questo accesso non è disponibile. Contatta la struttura.',
        'bad_request': 'Richiesta non valida. Riapri il collegamento dal QR della porta.',
    },
    'en': {
        'title': 'CL B&B Manager · Access',
        'brand_subtitle': 'GUEST ACCESS',
        'eyebrow': 'Property access',
        'generic_gate': 'Guest access',
        'prompt': 'Enter the access code provided by the property.',
        'code_label': 'Access code',
        'continue': 'Continue',
        'retry': 'Reopen the code page',
        'security': 'Personal code · Secure connection',
        'help': 'For assistance, contact the property.',
        'success_title': 'Request sent',
        'success_body': 'Check that the door has unlocked. If it does not open, contact the property.',
        'success': 'Wait a moment, then try opening the door.',
        'invalid_code': 'The code is invalid or not authorised for this door. Check your code and stay dates.',
        'too_many': 'Too many attempts. Please wait before trying again.',
        'cooldown': 'Wait a few seconds before sending another request.',
        'origin': 'We could not verify this page. Reopen the link from the door’s QR code.',
        'session': 'This session has expired or has already been used. Reopen the code page.',
        'unavailable': 'We could not confirm the request. Contact the property before trying again.',
        'not_found': 'This access is unavailable. Please contact the property.',
        'bad_request': 'Invalid request. Reopen the link from the door’s QR code.',
    },
}

_LANGUAGE = re.compile(r'^(?:[a-z]{1,8}(?:-[a-z0-9]{1,8})*|\*)$', re.ASCII)
_QUALITY = re.compile(r'^(?:0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?)$', re.ASCII)


def browser_language(header: str | None) -> str:
    """Prefer the highest-ranked supported browser language, including regions.

    Preserve Italian for absent/blank headers. If no positive supported choice
    exists, use English for international guests. Invalid ranges are ignored;
    the header never supplies HTML or dictionary keys directly.
    """
    if not isinstance(header, str) or not header.strip():
        return 'it'
    candidates = []
    for index, item in enumerate(header[:4096].split(',')[:100]):
        parts = [part.strip().lower() for part in item.split(';')]
        tag = parts[0]
        if not _LANGUAGE.fullmatch(tag) or len(parts) > 2:
            continue
        quality = 1.0
        if len(parts) == 2:
            if not parts[1].startswith('q=') or not _QUALITY.fullmatch(parts[1][2:]):
                continue
            quality = float(parts[1][2:])
        language = tag.split('-')[0]
        if language in COPY and quality > 0:
            candidates.append((-quality, index, language))
    return min(candidates)[2] if candidates else 'en'


def text(language: str, key: str) -> str:
    return COPY.get(language, COPY['it'])[key]
