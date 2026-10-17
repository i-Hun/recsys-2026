#!/usr/bin/env bash
# Скачать полные тексты RecSys 2026 из ACM DL локальным Camoufox.
# Вход: TSV «slug<TAB>doi». Выход: ~/papers/recsys26/<slug>.pdf, лог по каждому.
set -u
TODO="${1:?usage: fetch_acm_fulltexts.sh todo.tsv outdir}"
OUT="${2:?outdir}"
FETCH=/home/hun/.hermes/bin/camoufox-fetch
PROFILE=/home/hun/.camoufox/profiles/acm
mkdir -p "$OUT"

ok=0; fail=0; skip=0
while IFS=$'\t' read -r slug doi; do
  [ -z "${slug:-}" ] && continue
  dest="$OUT/$slug.pdf"
  if [ -s "$dest" ] && file -b "$dest" | grep -q '^PDF'; then
    skip=$((skip+1)); continue
  fi
  url="https://dl.acm.org/doi/$doi"
  for attempt in 1 2; do
    rm -f "$dest"
    timeout 180 "$FETCH" "$url" --pdf-url "https://dl.acm.org/doi/pdf/$doi" \
        --profile "$PROFILE" --wait 18 --timeout 90 --out "$dest" --json \
        >/tmp/ft_one.json 2>/dev/null
    if [ -s "$dest" ] && file -b "$dest" | grep -q '^PDF'; then
      printf 'OK\t%s\t%s\t%s\n' "$slug" "$doi" "$(stat -c%s "$dest")"
      ok=$((ok+1)); break
    fi
    if [ "$attempt" = 2 ]; then
      rm -f "$dest"
      printf 'FAIL\t%s\t%s\n' "$slug" "$doi"
      fail=$((fail+1))
    else
      sleep 5
    fi
  done
  printf 'PROGRESS\tok=%d\tfail=%d\tskip=%d\n' "$ok" "$fail" "$skip"
  sleep 1
done < "$TODO"
printf 'DONE\tok=%d\tfail=%d\tskip=%d\n' "$ok" "$fail" "$skip"
