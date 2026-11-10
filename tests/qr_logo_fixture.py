"""Synthetic artwork for the isolated browser test; never uses live QR data."""
import json
from test_qr_branding import branding, image_bytes

if __name__=='__main__':
    logo=branding.normalize_logo(image_bytes())
    settings={'enabled':True,'logo':logo}
    url='https://hotel.example.org/api/cl_bb_manager/physical/'+'x'*48
    print(json.dumps({'url':url,'artwork':branding.render_qr(url,settings),
                      'status':branding.branding_status({'qr_branding':settings},preview=True)}))
