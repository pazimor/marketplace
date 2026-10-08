import re
from fractions import Fraction

UNITS = {"j": 86400, "h": 3600, "m": 60, "s": 1}
ORDER = "jhms"
COMP = re.compile(r"([0-9]+)(?:[.,]([0-9]+))?([jhms])", re.I)


def parse_duree(texte):
    s = texte.strip()
    if not s:
        raise ValueError("vide")
    m = re.fullmatch(r"([0-9]+):([0-9]{2})(?::([0-9]{2}))?", s)
    if m:
        h, mi, se = int(m[1]), int(m[2]), int(m[3] or 0)
        if mi >= 60 or se >= 60:
            raise ValueError(s)
        return h * 3600 + mi * 60 + se
    m = re.fullmatch(r"([0-9]+)[hH]([0-9]{2})", s)
    if m:
        if int(m[2]) >= 60:
            raise ValueError(s)
        return int(m[1]) * 3600 + int(m[2]) * 60
    parts = re.split(r" +", s)
    comps = []
    for p in parts:
        pos = 0
        while pos < len(p):
            c = COMP.match(p, pos)
            if not c:
                raise ValueError(s)
            comps.append(c)
            pos = c.end()
    total = Fraction(0)
    last = -1
    for i, c in enumerate(comps):
        u = c[3].lower()
        k = ORDER.index(u)
        if k <= last:
            raise ValueError(s)
        last = k
        if c[2] is not None and i != len(comps) - 1:
            raise ValueError(s)
        n = Fraction(f"{c[1]}.{c[2]}") if c[2] is not None else Fraction(int(c[1]))
        total += n * UNITS[u]
    if total.denominator != 1:
        raise ValueError(s)
    return int(total)
