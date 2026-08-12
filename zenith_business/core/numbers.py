"""Number-to-words for printed documents (Prompt 01F §10).

Converts an amount to words in English and Dari/Persian, based on the actual
value (never hard-coded). Used by the printed invoice's "Amount in Words" line.

Only the integer part is spelled (currency subunits are not used in these
invoices); the value is rounded to the nearest whole unit.
"""

from __future__ import annotations

# ---- English -----------------------------------------------------------

_EN_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
            "eighty", "ninety"]
_EN_SCALES = ["", "thousand", "million", "billion", "trillion"]


def _en_three(n: int) -> str:
    parts: list[str] = []
    if n >= 100:
        parts.append(_EN_ONES[n // 100] + " hundred")
        n %= 100
    if n >= 20:
        t = _EN_TENS[n // 10]
        parts.append(t + ("-" + _EN_ONES[n % 10] if n % 10 else ""))
    elif n > 0:
        parts.append(_EN_ONES[n])
    return " ".join(parts)


def _int_to_words_en(n: int) -> str:
    if n == 0:
        return "zero"
    groups: list[str] = []
    scale = 0
    while n > 0:
        chunk = n % 1000
        if chunk:
            words = _en_three(chunk)
            if _EN_SCALES[scale]:
                words += " " + _EN_SCALES[scale]
            groups.insert(0, words)
        n //= 1000
        scale += 1
    return " ".join(groups)


# ---- Dari / Persian ----------------------------------------------------

_FA_ONES = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
_FA_TEENS = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده",
             "هفده", "هجده", "نوزده"]
_FA_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_FA_HUNDREDS = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد",
                "هشتصد", "نهصد"]
_FA_SCALES = ["", "هزار", "میلیون", "میلیارد", "بیلیون"]


def _fa_three(n: int) -> str:
    parts: list[str] = []
    if n >= 100:
        parts.append(_FA_HUNDREDS[n // 100])
        n %= 100
    if n >= 20:
        parts.append(_FA_TENS[n // 10])
        if n % 10:
            parts.append(_FA_ONES[n % 10])
    elif n >= 10:
        parts.append(_FA_TEENS[n - 10])
    elif n > 0:
        parts.append(_FA_ONES[n])
    return " و ".join(parts)


def _int_to_words_fa(n: int) -> str:
    if n == 0:
        return "صفر"
    groups: list[str] = []
    scale = 0
    while n > 0:
        chunk = n % 1000
        if chunk:
            words = _fa_three(chunk)
            if _FA_SCALES[scale]:
                words += " " + _FA_SCALES[scale]
            groups.insert(0, words)
        n //= 1000
        scale += 1
    return " و ".join(groups)


# ---- public ------------------------------------------------------------

# Currency spelling per language (extend as new currencies are configured).
_CURRENCY = {
    "AFN": ("Afghanis", "افغانی"),
    "USD": ("US Dollars", "دالر امریکایی"),
    "PKR": ("Pakistani Rupees", "کلدار"),
    "EUR": ("Euros", "یورو"),
}


def amount_in_words(amount: float, currency: str = "AFN", lang: str = "en") -> str:
    """Return the amount spelled out, with currency, for the given language."""
    whole = int(round(amount))
    name_en, name_fa = _CURRENCY.get(currency, (currency, currency))
    if lang == "fa_AF":
        return f"{_int_to_words_fa(whole)} {name_fa} تنها"
    words = _int_to_words_en(whole)
    return f"{words[:1].upper()}{words[1:]} {name_en} Only"
