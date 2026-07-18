"""Hydra is intentionally not shipped in Cerberus-X images."""


def scan(target, args=None):
    return {
        "tool": "hydra",
        "target": target,
        "error": "hydra is not available in this build",
        "raw_output": "hydra is not available in this build",
    }
