"""The vendor's PUBLIC verification key (Stage 10 §7).

This file holds a public key and nothing else. There is no private key here, in
any other module, or anywhere in this repository's application code, and there
is no code in the shipped package that can produce a signature. That is the
point of using an asymmetric scheme: the customer application can *check* a
licence without being able to *issue* one.

The key is kept in a module of its own so that a build can substitute it — the
vendor's real signing key is created and held outside this repository, and only
its public half is ever pasted in here.

``ZENITH_LICENSE_PUBLIC_KEY`` (environment) overrides the embedded value. That
exists for acceptance testing against a temporary key, and for the tests, which
inject their own throwaway key rather than relying on whatever is embedded.
"""

from __future__ import annotations

import base64
import os

#: Base64 of the 32-byte Ed25519 **public** key — the verification half, and the
#: only key material in this application. Its private counterpart was generated
#: in the Zenith Soft License Manager, is held encrypted on the vendor's own
#: machine, and has never been in this repository.
#:
#: This is safe to publish. A public key can check a signature and cannot make
#: one; anyone reading it gains the ability to verify Zenith Soft's licences,
#: which is exactly what every customer already does.
#:
#: An empty value here is not a failure mode to paper over: a build without a
#: key reports "no vendor key" and refuses to accept anything, rather than
#: appearing to verify against a placeholder.
EMBEDDED_PUBLIC_KEY_B64 = "aGixbaybmvVDEFA6RaqvCfLZmemWn/IE+hoPb1xT9S0="

#: Environment override, for acceptance testing with a temporary key.
PUBLIC_KEY_ENV = "ZENITH_LICENSE_PUBLIC_KEY"


def public_key() -> bytes | None:
    """The configured verification key, or None when the build has none."""
    text = (os.environ.get(PUBLIC_KEY_ENV) or EMBEDDED_PUBLIC_KEY_B64 or "").strip()
    if not text:
        return None
    try:
        raw = base64.b64decode(text.encode("ascii"), validate=True)
    except Exception:
        return None
    return raw if len(raw) == 32 else None


def is_configured() -> bool:
    return public_key() is not None
