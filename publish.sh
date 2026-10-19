#!/usr/bin/env bash
# Gera dist/ e copia a versão minificada para a raiz do repositório (o que a Vercel publica).
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
npx --yes terser@5.31.0 dist/app.js -c -m -o app.js
npx --yes html-minifier-terser@7.2.0 --collapse-whitespace --remove-comments --minify-css true --minify-js true dist/index.html -o index.html
ls -la index.html app.js
