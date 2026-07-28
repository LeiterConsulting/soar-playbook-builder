"""Deterministic Playbook IR compiler.

The compiler is intentionally model-free.  It accepts already-validated IR and
produces a Python playbook plus an offline-inspectable visual JSON artifact.
"""

from .artifacts import (
    COMPILER_VERSION,
    CompiledPlaybook,
    compile_playbook,
    parse_python_ir,
    parse_visual_ir,
)

__all__ = [
    "COMPILER_VERSION",
    "CompiledPlaybook",
    "compile_playbook",
    "parse_python_ir",
    "parse_visual_ir",
]
