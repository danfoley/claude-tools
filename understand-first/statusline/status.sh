#!/bin/sh
data_dir="${UNDERSTAND_FIRST_DATA:-$HOME/.claude/understand-first}"
ledger="${data_dir}/ledger.md"
byte_order_mark="$(printf '\357\273\277')"
carriage_return="$(printf '\r')"

[ -r "$ledger" ] || exit 0

while IFS= read -r line || [ -n "$line" ]; do
  line="${line#"$byte_order_mark"}"
  line="${line%"$carriage_return"}"
  case "$line" in
    "stage:"*)
      stage="${line#stage:}"
      stage="${stage#"${stage%%[! ]*}"}"
      case "$stage" in
        "" | *[!0-9]*) exit 0 ;;
      esac
      printf '[understand:stage %s]' "$stage"
      exit 0
      ;;
    "#"*)
      exit 0
      ;;
  esac
done < "$ledger"
