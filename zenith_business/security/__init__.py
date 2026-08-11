"""Security foundation (Prompt 01 §25-§29).

Stage 01 establishes *architectural boundaries* only:
    * Password hashing readiness (never plaintext) — :mod:`.passwords`.
    * Licensing/activation architecture boundary (no crypto, no keys) —
      :mod:`.licensing`.

The full authentication, authorization, and Licensing/Activation engines are
deliberately deferred to dedicated future prompts. Nothing here generates
cryptographic keys or stores secrets.
"""
