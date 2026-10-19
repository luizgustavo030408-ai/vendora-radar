# Vendora Radar

Radar comercial da Vendora Labs: leads captados todos os dias, missão de envio, pipeline, faturamento, contratos e assinaturas mensais.

- **Dados e login:** Supabase (tabelas `leads`, `config`, `membros`). Só e-mails cadastrados em `membros` entram.
- **Site:** HTML estático na Vercel (`index.html` + `app.js`).
- **Código-fonte:** `src/radar.html` (mesma app do artefato no Claude). `build.py` gera a versão com Supabase e `publish.sh` minifica para a raiz.

```
./publish.sh   # gera index.html e app.js
```
