# Zenith Soft License Manager — vendor only

**Never give this program, its signing keys or its license history to a
customer.** It is the half of the licensing system that can *issue*; Zenith
Business is the half that can only *check*.

## Where things live

Nothing below is inside this repository, and nothing below is ever built into
Zenith Business.

| What | Where |
|---|---|
| Signing keys (encrypted) | `%APPDATA%\ZenithSoft\LicenseManager\keys\*.zkey` |
| License history | `%APPDATA%\ZenithSoft\LicenseManager\license-history.json` |
| Exported `.zlic` files | `%APPDATA%\ZenithSoft\LicenseManager\licenses\` |

A key file is AES-256-GCM encrypted with a key derived from your passphrase by
scrypt (n=2¹⁷). The passphrase is not stored anywhere. **If you lose it, every
license must be reissued under a new key and Zenith Business rebuilt with the
new public key.** Back the key file up somewhere safe and offline.

## Daily use

1. The customer presses **Copy Request Code** and sends you the `ZBR1-…` line.
2. Paste it into **Machine ID / Request Code**. The Machine ID appears beneath
   it — check it against what the customer told you.
3. Fill in the customer name, phone and city.
4. Choose **FULL**, or **DEMO** and how many days. The demo length is yours to
   set; the customer's program has no way to change or extend it.
5. **Generate License**, then **Copy Product Key**, and send that one line back.

`Save .zlic` is a fallback for when a long code gets mangled in transit — a file
cannot be. The customer imports it under **Advanced** on the activation screen.

## Keys

- **Create key…** makes a new signing key for the selected product and shows its
  public half and fingerprint. Send only that to whoever builds the application.
- **Import key…** takes custody of an existing key, encrypting it on the way in.
- **Unlock signing key…** opens the key already on this computer.
- Replacing a key invalidates every license issued under it, so neither button
  will overwrite an existing key file.

### The key has to be the one the application verifies with

A signing key can be perfectly valid and still be the *wrong* key. Only the
counterpart of the public key built into the shipped application will produce
licenses that application accepts; anything else produces a Product Key that
looks flawless here and is refused at the customer as **"This product key is
not genuine, or it was changed after it was issued."**

That is not left to memory. The strip under the toolbar always shows:

```
Product:                       Zenith Business (ZENITH-BUSINESS)
Key status:                    unlocked
Signing key fingerprint:       D618-6880-46FB-61C1
Zenith Business expects:       D618-6880-46FB-61C1
Key created / imported:        2026-09-22
✓  Signing key verified against the product's own key.
```

If those two fingerprints differ, **Generate License is disabled** and the strip
says so. Nothing will produce a Product Key in that state — not the button, not
the engine underneath it, not a script calling `issuing.issue`.

**A newly created key never matches an existing build.** That is the normal
sequence and the Manager says so when it makes one:

1. **Create key…** → copy the `PUBLIC KEY:` line.
2. Zenith Business is rebuilt with that public key
   (`zenith_business/security/vendor_key.py`).
3. Install the new build. Generate License becomes available.

Until step 3, licenses cannot be issued under that key — which is correct, since
no application in existence would accept them.

### Every license is checked before you see it

After signing, the Manager re-reads the finished Product Key through the
**customer's own** parser and verifier and checks the signature, the machine it
is bound to, the license type and the expiry. A key that fails is not shown, not
copied, not saved and not written to the history; you get the technical reason
instead. Verifying with the code that issued it would only prove the Manager
agrees with itself.

## Adding another product

`vendor/zenith_license_manager/products.py` holds the catalogue. A product needs
its own product id, its own keypair and its own license rules. D-Clinic is
listed but not issuable: it uses a different key format, and claiming support
before that exists would produce keys that silently do not work.
