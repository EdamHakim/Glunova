import re

_OCR_TYPO_REPLACEMENTS: list[tuple[str, str]] = [
    (r"g\s*1\s*ucose", "glucose"),
    (r"gluc\s*0\s*se", "glucose"),
    (r"hb\s*a\s*1\s*c", "hba1c"),
    (r"cho\s*1\s*esterol", "cholesterol"),
]


def normalize_ocr_text(text: str) -> str:
    if not text:
        return ""
    out = text
    for pat, rep in _OCR_TYPO_REPLACEMENTS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
