"""
Provenance tracking utilities for data artifacts.
"""

import json
import datetime
import subprocess
import logging
from pathlib import Path


def get_git_commit() -> str:
    """Gets the current git commit hash."""
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
    except Exception:
        return "not-a-git-repo"


def write_provenance(artifact_path: Path, source_info: dict, parameters: dict):
    """
    Write a metadata sidecar file for a generated artifact.

    Args:
        artifact_path: Path to the artifact (file or directory)
        source_info: Dictionary of source data information
        parameters: Dictionary of processing parameters
    """
    meta = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "code_version": {
            "git_commit": get_git_commit()
        },
        "source_data": source_info,
        "processing_parameters": parameters,
    }

    # Handle both file and directory paths
    if artifact_path.is_dir():
        meta_path = artifact_path.parent / f"{artifact_path.name}.meta.json"
    else:
        meta_path = artifact_path.with_suffix(artifact_path.suffix + ".meta.json")

    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    logging.getLogger("provenance").info(f"Wrote provenance to {meta_path.name}")
