#!/usr/bin/env python3
"""Check enamel.tooth_type against the manifest's own notation derivation.

Invariant 5 exists because 28 hand-entered tooth numbers is 28 chances to
mislabel a tooth, and enamel.py adds a 29th chance by mapping Universal numbers
to tooth TYPES in Python, away from that derivation. This closes it: the
manifest derives Universal from arch/side/position and names the type; the two
must agree on all 28. The first draft of tooth_type had two quadrants counted
backwards AND the type table reversed, and every value it returned looked
plausible in isolation.

Run it with `npm run test:enamel`, which derives the truth table from
tools/manifest.mjs first. Do not hand-write that file: deriving it from the
manifest is the entire point, since a hand-written table could be wrong in the
same direction as the code it checks.

Usage: enamel_test.py <manifest-types.json>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from enamel import tooth_type                              # noqa: E402


def main():
    truth = json.load(open(sys.argv[1]))
    bad = []
    for uni, full in sorted(truth.items(), key=lambda kv: int(kv[0])):
        want = ("incisor" if "incisor" in full else
                "canine" if "canine" in full else
                "premolar" if "premolar" in full else "molar")
        got = tooth_type(int(uni))
        if got != want:
            bad.append(f"  tooth {uni}: manifest says {full!r} -> {want}, "
                       f"tooth_type says {got}")
    for u in (1, 16, 17, 32):        # third molars: absent here, still mapped
        if tooth_type(u) != "molar":
            bad.append(f"  tooth {u}: third molar mapped to {tooth_type(u)}")
    for u in (0, 33, -1):
        try:
            tooth_type(u)
            bad.append(f"  tooth {u}: accepted, should have raised")
        except ValueError:
            pass
    if bad:
        print(f"FAIL  {len(bad)} disagreement(s) with the manifest:")
        print("\n".join(bad))
        raise SystemExit(1)
    print(f"PASS  tooth_type agrees with the manifest on all {len(truth)} teeth, "
          "third molars map to molar, and out-of-range numbers raise")


if __name__ == "__main__":
    main()
