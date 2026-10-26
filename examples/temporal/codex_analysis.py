"""Compatibility entry point for Kura's default headless Codex analysis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from kura.analysis import (  # noqa: E402, F401
    MODEL,
    SCHEMA,
    INSTRUCTIONS,
    read_chats,
    prepare_prompt,
    validate_analysis,
    export_profile,
    analyze_chats,
    main,
)

if __name__ == "__main__":
    main()
