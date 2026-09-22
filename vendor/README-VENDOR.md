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
  public half. Send only that to whoever builds the application.
- **Import key…** takes custody of an existing key, encrypting it on the way in.
- Replacing a key invalidates every license issued under it, so neither button
  will overwrite an existing key file.

## Adding another product

`vendor/zenith_license_manager/products.py` holds the catalogue. A product needs
its own product id, its own keypair and its own license rules. D-Clinic is
listed but not issuable: it uses a different key format, and claiming support
before that exists would produce keys that silently do not work.
