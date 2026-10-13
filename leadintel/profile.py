"""Data-only research profiles; never execute downloaded configuration."""
import json
from pathlib import Path

DEFAULT_PROFILE=Path(__file__).resolve().parents[1]/"profiles/dfw-construction.json"


def load_profile(path=DEFAULT_PROFILE):
    if Path(path).stat().st_size>65536:
        raise ValueError("Research profile too large")
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data.get("id"),str) or not data["id"] or len(data["id"])>100:
        raise ValueError("Profile ID required")
    for field in ("signals","geography"):
        mapping=data.get(field)
        if not isinstance(mapping,dict) or not 1<=len(mapping)<=50:
            raise ValueError("Bounded signal and geography mappings required")
        for key,words in mapping.items():
            if not isinstance(key,str) or not key or len(key)>100 or not isinstance(words,list) or not 1<=len(words)<=50:
                raise ValueError("Invalid profile vocabulary")
            if any(not isinstance(w,str) or not w.strip() or len(w)>200 for w in words):
                raise ValueError("Invalid profile term")
    return data
