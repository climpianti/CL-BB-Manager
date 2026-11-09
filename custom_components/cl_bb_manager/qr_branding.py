"""Local raster-logo storage and conservative, self-contained QR exports."""
from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from io import BytesIO
import warnings
from xml.etree import ElementTree as ET

MAX_UPLOAD_BYTES = 1024 * 1024
MAX_IMAGE_SIDE = 2048
MAX_LOGO_BYTES = 64 * 1024
MAX_LOGO_SIDE = 256
BORDER = 4
SCALE = 8
SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', SVG_NS)
ET.register_namespace('xlink', XLINK_NS)


def normalize_logo(raw: bytes) -> dict:
    """Decode bounded PNG/JPEG/WebP and re-encode without metadata or animation."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_UPLOAD_BYTES:
        raise ValueError('Carica un logo PNG, JPG o WebP di massimo 1 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('Sono ammessi soltanto PNG, JPG e WebP. SVG e GIF non sono supportati.')
                if max(source.size) > MAX_IMAGE_SIDE or min(source.size) < 1:
                    raise ValueError('Il logo deve avere dimensioni massime di 2048 × 2048 pixel.')
                if getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('Carica un logo statico, senza animazioni.')
                image = ImageOps.exif_transpose(source).convert('RGBA')
                for size in (256, 192, 128, 96):
                    image.thumbnail((size, size), Image.Resampling.LANCZOS)
                    # A fresh image drops EXIF, ICC, comments and ancillary metadata.
                    clean = Image.new('RGBA', image.size)
                    clean.paste(image)
                    output = BytesIO();clean.save(output, format='PNG')
                    encoded = output.getvalue()
                    if len(encoded) <= MAX_LOGO_BYTES:
                        return {'png_base64': base64.b64encode(encoded).decode('ascii'),
                                'width': clean.width, 'height': clean.height}
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Immagine non valida. Carica nuovamente un logo PNG, JPG o WebP.') from exc
    raise ValueError('Logo troppo complesso. Carica un’immagine più semplice.')


def consume_upload(hass, file_id: str) -> dict:
    """Native upload context and cleanup both run inside the executor."""
    from homeassistant.components.file_upload import process_uploaded_file
    try:
        with process_uploaded_file(hass, file_id) as path:
            with path.open('rb') as handle:
                raw = handle.read(MAX_UPLOAD_BYTES + 1)
            return normalize_logo(raw)
    except OSError as exc:
        raise ValueError('Caricamento non disponibile. Seleziona nuovamente il file.') from exc


def branding_status(data: dict, *, preview=False) -> dict:
    branding = data.get('qr_branding', {})
    logo = branding.get('logo') if isinstance(branding, dict) else None
    encoded = logo.get('png_base64') if isinstance(logo, dict) else None
    has_logo = isinstance(encoded, str) and 0 < len(encoded) <= (MAX_LOGO_BYTES + 2) // 3 * 4
    result = {'has_logo': has_logo, 'enabled': has_logo and branding.get('enabled') is True}
    if preview and has_logo:
        result['preview'] = 'data:image/png;base64,' + encoded
    return result


async def async_update_branding(manager, *, enabled: bool, file_id=None, remove_logo=False):
    if type(enabled) is not bool or type(remove_logo) is not bool:
        raise ValueError('Impostazioni del logo non valide.')
    if file_id and remove_logo:
        raise ValueError('Scegli se caricare oppure rimuovere il logo.')
    new_logo = None
    if file_id:
        if not isinstance(file_id, str):
            raise ValueError('Caricamento non valido.')
        new_logo = await manager.hass.async_add_executor_job(consume_upload, manager.hass, file_id)
    async with manager.lock:
        had = 'qr_branding' in manager.data
        before = deepcopy(manager.data.get('qr_branding'))
        previous_events = deepcopy(manager.data['events'])
        old = before if isinstance(before, dict) else {}
        logo = None if remove_logo else new_logo or old.get('logo')
        if enabled and not logo and not remove_logo:
            raise ValueError('Carica un logo oppure disabilita il logo nei QR.')
        manager.data['qr_branding'] = {'enabled': enabled and bool(logo), 'logo': logo}
        manager.audit('qr_branding_updated', '')
        try:
            await manager.async_save()
        except Exception as exc:
            if had:manager.data['qr_branding'] = before
            else:manager.data.pop('qr_branding', None)
            manager.data['events'] = previous_events
            raise ValueError('Salvataggio non riuscito. Il logo precedente è stato conservato.') from exc


def _read_logo(branding):
    from PIL import Image
    if not isinstance(branding, dict) or branding.get('enabled') is not True:
        return None
    logo = branding.get('logo')
    if not isinstance(logo, dict):
        raise ValueError('Logo salvato non valido. Ricaricalo dalla configurazione.')
    encoded = logo.get('png_base64')
    try:
        if not isinstance(encoded, str) or len(encoded) > (MAX_LOGO_BYTES + 2) // 3 * 4:
            raise ValueError('Invalid image size')
        raw = base64.b64decode(encoded, validate=True)
        if not 0 < len(raw) <= MAX_LOGO_BYTES:
            raise ValueError('Invalid image size')
        with Image.open(BytesIO(raw)) as image:
            if image.format != 'PNG' or max(image.size) > MAX_LOGO_SIDE or min(image.size) < 1 or getattr(image, 'n_frames', 1) != 1:
                raise ValueError('Invalid normalized image')
            image.load()
            return image.convert('RGBA'), raw
    except (OSError, ValueError, binascii.Error, Image.DecompressionBombError) as exc:
        raise ValueError('Logo salvato non valido. Ricaricalo dalla configurazione.') from exc


def _qr_and_box(url, with_logo):
    import segno
    from segno import consts
    qr = segno.make_qr(url, error='h') if with_logo else segno.make_qr(url)
    if not with_logo:return qr, None
    for version in range(qr.version, 41):
        if version != qr.version:qr = segno.make_qr(url, error='h', version=version)
        count = len(qr.matrix)
        side = int(count * .18)
        if side % 2 == 0:side -= 1
        minimum = max(7, int(count * .10))
        types = list(qr.matrix_iter(scale=1, border=0, verbose=True))
        # Shrink within a conservative band before trying a larger symbol.
        # Cover DATA only: never alignment/timing/finder/version/format modules.
        for candidate in range(side, minimum - 1, -2):
            start = (count - candidate) // 2
            if all(types[y][x] in (consts.TYPE_DATA_DARK, consts.TYPE_DATA_LIGHT)
                   for y in range(start, start + candidate) for x in range(start, start + candidate)):
                return qr, (start, candidate)
    raise ValueError('Non è possibile inserire il logo mantenendo i riferimenti del QR.')


def render_qr(url: str, branding=None) -> dict:
    """Generate SVG + PNG locally. URL is untouched; logo covers <=18% width."""
    logo = _read_logo(branding)
    qr, box = _qr_and_box(url, logo is not None)
    svg = BytesIO();qr.save(svg, kind='svg', scale=SCALE, border=BORDER, light='white')
    png = BytesIO();qr.save(png, kind='png', scale=SCALE, border=BORDER, light='white')
    if logo is not None:
        from PIL import Image
        image, raw = logo
        start, side = box
        left = (BORDER + start) * SCALE;size = side * SCALE
        inset = SCALE  # One complete white module around the logo image.
        root = ET.fromstring(svg.getvalue())
        ET.SubElement(root, '{'+SVG_NS+'}rect', {'x':str(left),'y':str(left),'width':str(size),'height':str(size),'fill':'#fff'})
        uri = 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
        ET.SubElement(root, '{'+SVG_NS+'}image', {'x':str(left+inset),'y':str(left+inset),
            'width':str(size-2*inset),'height':str(size-2*inset),'preserveAspectRatio':'xMidYMid meet',
            'href':uri,'{'+XLINK_NS+'}href':uri})
        svg = BytesIO(ET.tostring(root, encoding='utf-8', xml_declaration=True))
        output = Image.open(BytesIO(png.getvalue())).convert('RGBA')
        output.paste((255,255,255,255),(left,left,left+size,left+size))
        image.thumbnail((size-2*inset,size-2*inset),Image.Resampling.LANCZOS)
        output.alpha_composite(image,(left+(size-image.width)//2,left+(size-image.height)//2))
        png = BytesIO();output.convert('RGB').save(png,format='PNG')
    return {'svg':svg.getvalue().decode('utf-8'),
            'png_base64':base64.b64encode(png.getvalue()).decode('ascii'),
            'logo_applied':logo is not None}
