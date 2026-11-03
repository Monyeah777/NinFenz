// NinFenz 站点 Worker：www.* 301 到裸域；首页支持机器面内容协商；其余交给静态资产。
//
// 三件事，按序：
//   1) www.* -> 裸域 301（Redirect Rules 需要 Zone Rules 权限，Worker 自持不依赖额外授权）
//   2) 首页与 /en/ 上出现 Accept: text/markdown 时，回 /llms-full.txt 单文件机器面
//      （生成式引擎与 agent 常用该协商；浏览器不会发这个 Accept，故对人无影响）
//   3) 其余一律原样交回 env.ASSETS.fetch()（_headers 规则照旧生效）
//
// 另有一个同源写入口：POST /api/lead 把标识体检线索写入 env.LEAD_KV（可选绑定）。
// 未绑定 KV 时返回 501 与 {ok:false, fallback:"mailto"}，前端据此打开邮件兜底。
//
// 配合 wrangler.jsonc 的 assets.run_worker_first = true 与 assets.binding = "ASSETS"。

const MARKDOWN_ROUTES = new Set(['/', '/en/', '/en']);

// 线索接口：只收 JSON，body 上限 12KB；KV 可选，没有绑定不算故障（前端有邮件兜底）。
const LEAD_PATH = '/api/lead';
const LEAD_MAX_BYTES = 12 * 1024;

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

function leadField(value, max) {
  return typeof value === 'string' ? value.trim().slice(0, max) : '';
}

async function handleLead(request, env) {
  const mediaType = String(request.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
  if (mediaType !== 'application/json') {
    return jsonResponse(415, { ok: false, error: 'content_type_must_be_application_json' });
  }
  const declared = Number(request.headers.get('content-length') || '');
  if (Number.isFinite(declared) && declared > LEAD_MAX_BYTES) {
    return jsonResponse(413, { ok: false, error: 'payload_too_large' });
  }
  let raw;
  try {
    raw = await request.text();
  } catch (e) {
    return jsonResponse(400, { ok: false, error: 'unreadable_body' });
  }
  if (new TextEncoder().encode(raw).byteLength > LEAD_MAX_BYTES) {
    return jsonResponse(413, { ok: false, error: 'payload_too_large' });
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    return jsonResponse(400, { ok: false, error: 'invalid_json' });
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return jsonResponse(400, { ok: false, error: 'invalid_json' });
  }
  const name = leadField(data.name, 80);
  const contact = leadField(data.contact, 120);
  if (!name || !contact) {
    return jsonResponse(400, { ok: false, error: 'name_and_contact_required' });
  }
  // 蜜罐：机器人填了隐藏字段就安静丢弃，不落库、不回显判断依据。
  if (leadField(data.company_url, 200)) {
    return jsonResponse(200, { ok: true, stored: false });
  }
  if (!env.LEAD_KV || typeof env.LEAD_KV.put !== 'function') {
    return jsonResponse(501, { ok: false, fallback: 'mailto', error: 'lead_storage_not_configured' });
  }
  const record = {
    name,
    contact,
    company: leadField(data.company, 200),
    fileType: leadField(data.fileType, 80),
    timeline: leadField(data.timeline, 80),
    brief: leadField(data.brief, 2000),
    source: 'https://ninfenz.dev/label/',
    receivedAt: new Date().toISOString(),
    country: leadField(request.headers.get('cf-ipcountry'), 8),
    userAgent: leadField(request.headers.get('user-agent'), 200),
  };
  const key = 'lead:' + Date.now() + ':' + Math.random().toString(36).slice(2, 10);
  try {
    await env.LEAD_KV.put(key, JSON.stringify(record));
  } catch (e) {
    return jsonResponse(502, { ok: false, fallback: 'mailto', error: 'lead_storage_failed' });
  }
  return jsonResponse(200, { ok: true });
}

// 客户端是否**明确**点名 markdown（2026-10-08 修）：
// - `q=0` 按 RFC 9110 §12.5.1 = 明确不要，旧实现用 includes() 会照回 markdown；
// - 通配 `*/*` / `text/html` 不触发——curl 等通用客户端默认发 `*/*`，据此回 markdown 会让
//   它们拿到「意外类型」；协商只在客户端点名 text/markdown（或 text/*）时生效。
function wantsMarkdown(accept) {
  for (const part of String(accept).split(',')) {
    const [raw, ...params] = part.split(';');
    const type = raw.trim().toLowerCase();
    if (type !== 'text/markdown' && type !== 'text/*') continue;
    const q = params.map((p) => p.trim().toLowerCase()).find((p) => p.startsWith('q='));
    if (q !== undefined && Number(q.slice(2)) === 0) continue;
    return true;
  }
  return false;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname.startsWith('www.')) {
      url.hostname = url.hostname.slice(4);
      return Response.redirect(url.toString(), 301);
    }
    if (request.method === 'POST' && url.pathname === LEAD_PATH) {
      return handleLead(request, env);
    }
    if (request.method === 'GET' && MARKDOWN_ROUTES.has(url.pathname)) {
      const accept = request.headers.get('accept') || '';
      if (wantsMarkdown(accept)) {
        try {
          const assetReq = new Request(new URL('/llms-full.txt', url.origin), { headers: request.headers });
          const res = await env.ASSETS.fetch(assetReq);
          if (res.ok) {
            return new Response(res.body, {
              status: 200,
              headers: {
                'content-type': 'text/markdown; charset=utf-8',
                'cache-control': 'public, max-age=300',
                'vary': 'Accept',
                'x-ninfenz-negotiated': 'llms-full.txt',
              },
            });
          }
        } catch (e) {
          // 协商失败不改变正常行为：回落到静态资产
        }
      }
    }
    return env.ASSETS.fetch(request);
  },
};
