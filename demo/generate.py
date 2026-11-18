"""Regenerate replay evidence from the real compiler; never hand-edit bundles."""
import json
import argparse
from pathlib import Path

from compose import FRONTEND_EXAMPLES, console_run, default_run
from .presets import PRESETS


def main(only=None, directory=None):
    directory = Path(directory) if directory else Path(__file__).with_name("bundles")
    directory.mkdir(exist_ok=True)
    count = 0
    for preset in PRESETS:
        if only and preset["id"] != only:
            continue
        bundle = default_run(preset["source"])
        (directory / f"{preset['id']}.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        count += 1
    for frontend in ["builder", "nl", "elastic"]:
        if only and frontend != only:
            continue
        bundle = console_run(FRONTEND_EXAMPLES[frontend], frontend_id=frontend)
        assert not bundle["errors"], bundle["errors"]
        (directory / f"{frontend}.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        count += 1
    print(f"Generated {count} real QueryRun bundles in {directory}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=[preset["id"] for preset in PRESETS] + ["builder", "nl", "elastic"])
    main(only=parser.parse_args().only)
