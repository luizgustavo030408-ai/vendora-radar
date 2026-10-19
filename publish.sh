#!/usr/bin/env bash
# Gera dist/ e copia a versão minificada para a raiz do repositório (o que a Vercel publica).
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
rm -rf js && mkdir -p js
for f in dist/js/*.js; do npx --yes terser@5.31.0 "$f" -c -m -o "js/$(basename "$f")"; done
npx --yes html-minifier-terser@7.2.0 --collapse-whitespace --remove-comments --minify-css true --minify-js true dist/index.html -o index.html
npx --yes html-minifier-terser@7.2.0 --minify-css true dist/style.css -o /dev/null >/dev/null 2>&1 || true
python3 - <<'PY'
import re
c = open("dist/style.css").read()
c = re.sub(r"/\*.*?\*/", "", c, flags=re.S); c = re.sub(r"\s+", " ", c); c = re.sub(r"\s*([{};,>])\s*", r"\1", c)
open("style.css", "w").write(c.strip() + "\n")
PY
wc -c index.html style.css js/*.js
