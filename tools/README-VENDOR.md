# Zenith Soft — vendor licensing tool

**This folder is for Zenith Soft only. It is never given to a customer and is
never part of a Zenith Business build.** The PyInstaller spec collects the
`zenith_business` package alone, so nothing here can reach an installer.

`zenith_license_tool.py` needs **only a standard Python 3.11+ install** — no
pip, no internet, no extra packages. It can be run on an offline machine.

---

## 1. Create your signing key — once, ever

```
python zenith_license_tool.py generate --out zenith-signing-key.json
```

It prints one line like:

```
PUBLIC KEY: rPYAqRS/6YbTRI0imx/rZfzSFceTRBw+7sNzwMrHgUM=
```

* **Send only that PUBLIC KEY line** to your developer. It goes into the
  application so it can check licences.
* **Keep `zenith-signing-key.json` private and backed up**, offline, in more
  than one place. Anyone holding it can issue licences for your product. If it
  is lost, every licence must be re-issued under a new key and the application
  rebuilt.

The tool refuses to overwrite an existing key file unless you pass `--force`.

## 2. Issue a licence for a customer

The customer opens **Tools → License → Generate Activation Request** and sends
you the `.zreq` file. Then:

```
python zenith_license_tool.py sign ^
    --key zenith-signing-key.json ^
    --request zenith-activation-XXXXXXXX.zreq ^
    --out customer.zlic ^
    --license-id ZB-FULL-000001 ^
    --issued-to "Kabul Traders Ltd"
```

Send `customer.zlic` back. They import it under **Tools → License → Import
License**. It works on that computer only.

### Time-limited demo licence

```
python zenith_license_tool.py sign --key zenith-signing-key.json ^
    --request customer.zreq --out demo.zlic ^
    --license-id ZB-DEMO-000007 --type DEMO --expires 2027-01-31
```

### Look at a file without changing it

```
python zenith_license_tool.py show customer.zreq
```

---

## What the licence binds

The signature covers the product id, licence id, licence type, the customer's
machine fingerprint and traits, the issue information and any expiry. **Changing
any of those fields breaks the signature**, so an edited licence is refused.

The machine is identified by five traits with different weights, not by one
identifier. A customer can replace a disk, change a network card, rename the PC
or reinstall Windows and keep working; copying the folder to a second computer
does not activate it.

## Licence id convention

Free-form, but keeping a register helps: `ZB-FULL-000001`, `ZB-DEMO-000007`.
The id is shown on the customer's License screen and in their audit log.
