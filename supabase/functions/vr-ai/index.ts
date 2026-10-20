// Vendora Radar · assistente de mensagens
// Recebe o lead e a mensagem atual, aplica o treino salvo em config/ia e devolve uma versão melhorada.
import { createClient } from "jsr:@supabase/supabase-js@2";

const MODEL = Deno.env.get("ANTHROPIC_MODEL") ?? "claude-sonnet-5-5";
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const NL = String.fromCharCode(10);
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

const BASE = `Você escreve mensagens de primeiro contato no WhatsApp para a Vendora Labs, agência que cria sites para pequenos negócios do Brasil.
Filosofia: "vendedor não vende, ele se mostra na vitrine e deixa o cliente vir". A mensagem apresenta quem envia, valoriza o negócio e deixa a porta aberta, sem pressão.
Regras fixas:
- Português do Brasil, natural, como uma pessoa real escreveria no WhatsApp.
- Mantenha exatamente o marcador {{eu}} onde entra o nome de quem envia (ex.: "Aqui é o {{eu}}, da Vendora"). Nunca troque {{eu}} por um nome.
- Use só fatos que estão nos dados do lead. Não invente nota, avaliações, prêmios, tempo de mercado ou nomes de pessoas.
- Não fale de preço e não prometa resultados.
- Responda somente com o texto final da mensagem, sem aspas, sem título e sem explicação.`;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "metodo" }, 405);

  const url = Deno.env.get("SUPABASE_URL")!;
  const anon = Deno.env.get("SUPABASE_ANON_KEY")!;
  const service = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const auth = req.headers.get("Authorization") ?? "";

  const asUser = createClient(url, anon, { global: { headers: { Authorization: auth } } });
  const { data: u } = await asUser.auth.getUser();
  const email = u?.user?.email;
  if (!email) return json({ error: "login" }, 401);

  const admin = createClient(url, service);
  const { data: membro } = await admin.from("membros").select("papel,nome").ilike("email", email).maybeSingle();
  if (!membro) return json({ error: "acesso" }, 403);

  const key = Deno.env.get("ANTHROPIC_API_KEY");
  if (!key) return json({ error: "sem_chave" }, 503);

  let body: Record<string, unknown> = {};
  try { body = await req.json(); } catch { return json({ error: "corpo" }, 400); }
  if (body.acao === "status") return json({ ok: true, modelo: MODEL });

  const lead = (body.lead ?? {}) as Record<string, unknown>;
  const mensagem = String(body.mensagem ?? "").slice(0, 4000);
  const pedido = String(body.pedido ?? "").slice(0, 500);

  const { data: cfg } = await admin.from("config").select("data").eq("id", "ia").maybeSingle();
  const ia = (cfg?.data ?? {}) as Record<string, any>;
  const regras = String(ia.regras ?? "").trim();
  const aprendizados: string[] = (ia.aprendizados ?? []).map((a: any) => String(a.t ?? "")).filter(Boolean).slice(-25);
  const exemplos: string[] = (ia.exemplos ?? []).map((e: any) => String(e.texto ?? "")).filter(Boolean).slice(-6);

  if (ia.autoAprender !== false) {
    const { data: deram } = await admin
      .from("leads")
      .select("data")
      .in("data->>status", ["potencial", "fechado", "concluido"])
      .order("updated_at", { ascending: false })
      .limit(5);
    for (const r of deram ?? []) {
      const t = String((r as any).data?.mensagem ?? "");
      if (t && !exemplos.includes(t)) exemplos.push(t);
    }
  }

  let system = BASE;
  if (regras) system += `${NL}${NL}Treino da equipe (como as mensagens devem ser):${NL}${regras}`;
  if (aprendizados.length) system += `${NL}${NL}Aprendizados (correções que a equipe já pediu, siga sempre):${NL}${aprendizados.map((a) => `- ${a}`).join(NL)}`;
  if (exemplos.length) system += `${NL}${NL}Mensagens que funcionaram (inspire-se no tom, não copie):${NL}${exemplos.slice(0, 8).map((e, i) => `Exemplo ${i + 1}:${NL}${e}`).join(NL + NL)}`;

  const dados = Object.entries(lead)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k}: ${v}`)
    .join(NL);
  const tarefa = lead.trafego
    ? "Este lead veio de anúncio (tráfego pago): a pessoa demonstrou interesse. A mensagem deve agradecer o interesse, se apresentar e puxar conversa sobre o negócio dela."
    : "Este é um primeiro contato frio com um negócio que ainda não tem site.";
  const user = `${tarefa}${NL}${NL}Dados do lead:${NL}${dados || "(sem dados)"}${NL}${NL}Mensagem atual:${NL}${mensagem || "(vazia)"}${NL}${NL}${
    pedido ? `Ajuste pedido pela equipe: ${pedido}${NL}${NL}Reescreva aplicando o ajuste.` : "Melhore a mensagem seguindo o treino. Se ela já estiver boa, faça só ajustes finos."
  }`;

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" },
    body: JSON.stringify({ model: MODEL, max_tokens: 700, system, messages: [{ role: "user", content: user }] }),
  });
  if (!r.ok) {
    const detalhe = await r.text();
    console.error("anthropic", r.status, detalhe.slice(0, 500));
    return json({ error: r.status === 401 ? "chave_invalida" : "ia_indisponivel" }, 502);
  }
  const out = await r.json();
  let texto = (out.content ?? []).filter((c: any) => c.type === "text").map((c: any) => c.text).join("").trim();
  texto = texto.replace(/^["“]+/, "").replace(/["”]+$/, "").trim();
  if (!texto) return json({ error: "vazio" }, 502);
  if (!texto.includes("{{eu}}") && mensagem.includes("{{eu}}")) texto = texto.replace(/Aqui é (o|a) [A-ZÀ-Ú][A-Za-zÀ-ú]+/, "Aqui é o {{eu}}");
  return json({ mensagem: texto });
});
