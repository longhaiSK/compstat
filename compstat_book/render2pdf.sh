#!/usr/bin/env bash
# Render the PDF book (CompStat-LLi.pdf).
#
# Default: fast. Uses the project settings in _quarto.yml, freeze: auto and
# cache: true. A chapter is re-executed only when its .qmd has changed since
# the last PDF render (frozen results are kept per format, in
# _freeze/<chapter>/execute-results/pdf.json), and inside a re-executed
# chapter knitr reuses cached chunks (<chapter>_cache/pdf/).
#
# Freeze does not notice changes outside the .qmd (data files, sourced R
# scripts, package updates). After such changes, rebuild everything with
#   ./render2pdf.sh --fresh
# which re-executes every chapter (chunk caches still apply).

cd "$(dirname "$0")" || exit 1

if [ "$1" = "--fresh" ]; then
  quarto render --to custombook-pdf -M freeze:false
else
  quarto render --to custombook-pdf
fi
