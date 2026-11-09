# PIN form POST correction — 0.5.0-alpha.17

Native HTML form POSTs inherit the document referrer policy. With `no-referrer`,
the browser sends `Origin: null`, which the existing HTTPS origin check rejects
before checking the PIN. Both HTTP Referrer-Policy and HTML meta referrer now use
`strict-origin`: the expected HTTPS Origin is preserved and the Referer excludes
the QR path, token and query. The backend continues rejecting `Origin: null`.

Physical and permanent-demo routes retain their separate credentials and guards.
Origin and CSRF rejections retain HTTP 403, provide a readable error and log only
fixed route/reason categories. Forms without a usable nonce are replaced by a
link that obtains a fresh GET; no empty or consumed nonce is offered for retry.

The update changes no persisted schema, QR tokens, arming flags, booking grants,
hardware targets, rate limits or cooldowns. Existing pending form nonces are
volatile and must be reacquired after the required Home Assistant restart.

Validation: 232 Python tests and 12 frontend tests; controlled aiohttp GET/POST
flows for both approved door mappings, all using in-memory HA/device fakes.
Before correction, the specification-derived Origin null POST returns 403;
after correction, the normal HTTPS Origin POST returns 200 in isolation.
These are HTTP tests, not a captured real-phone/browser trace.

Deployment requires restarting Home Assistant after updating component files.
Recovery is reinstalling the previous source revision
`51657455809be4106f9680e1878a99940188bc3a` and restarting; no data restore is needed
because this hotfix changes no storage format or permissions.

Do not submit a valid PIN to a physical endpoint solely to verify installation:
such a POST can dispatch a real actuator command. Check the loaded version,
integration startup, state preservation and fresh GET response instead.
