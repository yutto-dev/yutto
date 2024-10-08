from __future__ import annotations

import json
from pathlib import Path

from yutto.cli.settings import YuttoSettings


def main():
    schema = YuttoSettings.model_json_schema()
    with Path("schemas/config.json").open("w") as f:
        json.dump(schema, f, indent=2)


if __name__ == "__main__":
    main()
