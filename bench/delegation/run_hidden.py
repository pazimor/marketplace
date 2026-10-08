"""Suite cachée du banc de délégation : python3 -I bench/delegation/run_hidden.py <dossier contenant duree.py>"""
import importlib.util
import sys

VALID = {
    "1h": 3600, "90m": 5400, "45s": 45, "2j": 172800, "1J": 86400,
    "1h30m": 5400, "1h 30m": 5400, "1h  30m": 5400, "1h 30m 0s": 5400,
    "2j3h4m5s": 183845, "  1H30M  ": 5400, "05m": 300, "0s": 0,
    "1.5h": 5400, "1,5h": 5400, "1.5m": 90, "2h0.5m": 7230,
    "0.1h": 360, "2.3h": 8280,
    "1h30": 5400, "1H30": 5400, "10h05": 36300, "0h00": 0,
    "1:30": 5400, "0:00:45": 45, "12:34:56": 45296, "100:00": 360000, "0:00": 0,
}

INVALID = [
    "", "   ", "-5m", "+5m", "90", "1h1h", "30m1h", "1s1m", "1x", "1d", "1 h",
    "1.5h30m", "0.5s", "1.01m", "1.333h", ".5h", "1.h", "1.5.2h", "1,5,5h",
    "1h5", "1h75", "1h300", "1h 30", "2j 1h30", "1h30m30",
    "1:5", "1:60", ":30", "1:30:", "1:30:60", "1::30", "1:30m",
    "h", "m", "1hh", "١h", "1٠:00",
]


def main(folder):
    spec = importlib.util.spec_from_file_location("duree", f"{folder}/duree.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fails = []
    for s, want in VALID.items():
        try:
            got = mod.parse_duree(s)
            if got != want or type(got) is not int:
                fails.append(f"{s!r}: attendu {want}, obtenu {got!r}")
        except Exception as e:
            fails.append(f"{s!r}: attendu {want}, exception {type(e).__name__}")
    for s in INVALID:
        try:
            got = mod.parse_duree(s)
            fails.append(f"{s!r}: attendu ValueError, obtenu {got!r}")
        except ValueError:
            pass
        except Exception as e:
            fails.append(f"{s!r}: attendu ValueError, exception {type(e).__name__}")
    total = len(VALID) + len(INVALID)
    print(f"{total - len(fails)}/{total}")
    for f in fails:
        print("  KO", f)


if __name__ == "__main__":
    main(sys.argv[1])
