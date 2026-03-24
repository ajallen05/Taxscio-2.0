"""
backend/utils/schemas.py
========================
Schema file loading utilities.

Moved from backend/main.py so that extracted microservices (Extraction Engine,
Data Integrity Engine) can load schemas without importing the Flask monolith.

Functions
---------
get_available_forms()   — list all form types that have a schema file
get_schema(form_type)   — load and return the JSON schema for a form type
"""

import json
import logging
import os

from backend.config import config

log = logging.getLogger("Taxscio.utils.schemas")


def get_available_forms() -> list[str]:
    """
    Return a sorted list of all IRS form types that have a local schema file.

    Scans config.schemas_dir for *.json files and returns the names without
    the .json extension.

    Returns:
        Sorted list of form type strings, e.g. ["1099-NEC", "W-2", ...].
    """
    schemas_dir = config.schemas_dir
    if not os.path.exists(schemas_dir):
        log.warning("schemas_dir does not exist: %s", schemas_dir)
        return []
    return sorted(
        f[:-5] for f in os.listdir(schemas_dir) if f.endswith(".json")
    )


def get_schema(form_type: str) -> dict | None:
    """
    Load the JSON schema for the given IRS form type.

    Tries an exact filename match first, then falls back to a
    case-insensitive scan of the schemas directory.

    Args:
        form_type: IRS form type string, e.g. "W-2", "1099-NEC".

    Returns:
        Parsed JSON dict, or None if no matching schema file exists.
    """
    schemas_dir = config.schemas_dir
    path = os.path.join(schemas_dir, f"{form_type}.json")

    if not os.path.exists(path):
        # Case-insensitive fallback scan
        try:
            for f in os.listdir(schemas_dir):
                if f.lower() == f"{form_type.lower()}.json":
                    path = os.path.join(schemas_dir, f)
                    break
        except OSError as exc:
            log.error("Cannot read schemas_dir %s: %s", schemas_dir, exc)
            return None

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    log.warning("No schema found for form_type='%s'", form_type)
    return None
