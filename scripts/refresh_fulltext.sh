#!/usr/bin/env bash
# Полный цикл «PDF → сопоставление → текст → эмбеддинги (ПК) → назад».
# Запускать после того, как докачка полных текстов отработала:
#   bash scripts/refresh_fulltext.sh
set -eu
cd "$(dirname "$0")/.."
PY=/home/hun/.venvs/agent-researcher/bin/python
export -n PYTHONPATH || true
PC=pc
FT=data/fulltext

echo "== 1/6 сопоставление PDF =="
env -u PYTHONPATH "$PY" scripts/_fulltext_match.py | tail -11

echo "== 2/6 извлечение текста =="
env -u PYTHONPATH "$PY" scripts/fulltext_corpus.py | tail -12

echo "== 3/6 эмбеддинги полных текстов на ПК =="
scp -q -i ~/.ssh/pc $FT/../fulltext-corpus.jsonl $PC:'/C:/Users/hun/tmp/ft/fulltext-corpus.jsonl'
scp -q -i ~/.ssh/pc scripts/embed_fulltext_pc.py $PC:'/C:/Users/hun/tmp/ft/embed_fulltext_pc.py'
ssh -o ConnectTimeout=10 $PC 'python C:\Users\hun\tmp\ft\embed_fulltext_pc.py' 2>&1 | grep -E "papers=|device:|chunk-emb|paper-emb"
scp -q -i ~/.ssh/pc $PC:'/C:/Users/hun/tmp/ft/fulltext-emb.npy' $FT/
scp -q -i ~/.ssh/pc $PC:'/C:/Users/hun/tmp/ft/fulltext-slugs.json' $FT/

echo "== 4/6 тексты разборов для тех же работ =="
env -u PYTHONPATH "$PY" scripts/review_corpus.py

echo "== 5/6 эмбеддинги разборов на ПК =="
scp -q -i ~/.ssh/pc $FT/review-corpus.jsonl $PC:'/C:/Users/hun/tmp/ft/review-corpus.jsonl'
scp -q -i ~/.ssh/pc scripts/embed_review_pc.py $PC:'/C:/Users/hun/tmp/ft/embed_review_pc.py'
ssh -o ConnectTimeout=10 $PC 'python C:\Users\hun\tmp\ft\embed_review_pc.py' 2>&1 | grep -E "review-emb"
scp -q -i ~/.ssh/pc $PC:'/C:/Users/hun/tmp/ft/review-emb.npy' $FT/
scp -q -i ~/.ssh/pc $PC:'/C:/Users/hun/tmp/ft/review-slugs.json' $FT/

echo "== 6/6 карта и сверка =="
env -u PYTHONPATH "$PY" scripts/fulltext_map.py 2>&1 | grep -v UserWarning | grep -v "warn("
echo "ГОТОВО"
