# Project Structure Utility

This directory contains a small helper for producing a readable repository
tree.

## Files

- `project_struct.py`: walks the repository, honors `.gitignore`, and writes an
  ASCII tree.
- `project_struct.txt`: generated snapshot of the repository layout.

## Regeneration

From the repository root:

```bash
python3 docs/project_structure/project_struct.py
```

The script requires the Python package `pathspec`.
