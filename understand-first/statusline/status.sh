#!/bin/sh
data_dir="${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}"
ledger="${data_dir}/ledger.md"

[ -r "$ledger" ] || exit 0

while IFS= read -r line; do
  case "$line" in
    "stage: "*)
      printf '[understand:stage %s]' "${line#stage: }"
      exit 0
      ;;
    "### "*)
      exit 0
      ;;
  esac
done < "$ledger"
