# Exercise 3 Report

This directory contains the final report source and compiled output for the
third exercise.

## Files

- `main.tex`: LaTeX source.
- `03121026_3.pdf`: compiled report PDF.

The report uses figures from `../benchmarks/diagrams/` through the configured
`\graphicspath`.

## Build

Compile with XeLaTeX because the source uses `fontspec`, `unicode-math`, and
Greek text:

```bash
latexmk -xelatex main.tex
```

If `latexmk` is unavailable, run `xelatex main.tex` enough times to resolve
references and the table of contents.
