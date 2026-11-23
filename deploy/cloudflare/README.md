# ContextPulse oflayn demo (Cloudflare)

Bu qovluq `../../static` faylını Cloudflare-də yalnız statik fayllardan ibarət Worker (`contextpulse-demo`) kimi yayımlayır. Python backend burada işləmir: `/api/bootstrap` 404 qaytarır və `app.js` avtomatik **oflayn demo** rejiminə keçir (məntiq brauzerdə, AI əvəzinə hazır mətnlər). API açarı lazım deyil və istifadə olunmur.

## Yayımlamaq

```bash
npm install
npm run deploy
```

`workers.dev` ünvanı söndürülüb. Demo yalnız öz subdomeninə bağlananda görünür.

## Subdomeni bağlamaq (nexusweb.az Cloudflare-ə keçəndən sonra)

`cloudflare.config.ts` faylında `defineWorker({...})` içinə əlavə et və yenidən yayımla:

```ts
domains: ["contextpulse.nexusweb.az"],
```

Sonra NexusWeb saytında `.env.production.local` faylına `NEXT_PUBLIC_CONTEXTPULSE_DEMO_URL=https://contextpulse.nexusweb.az` yaz və saytı yenidən yayımla.

## VPS-ə keçid (real AI ilə canlı versiya)

1. VPS-də backend-i Docker ilə qaldır (`docker build -t contextpulse-ai .`). `.env` faylına `GEMINI_API_KEY` və ya `ANTHROPIC_API_KEY`, həmçinin `AI_DAILY_LIMIT` yaz. Açarlar yalnız serverdə qalır, brauzerə getmir.
2. Bu Worker-dən `domains` sətrini sil və yenidən yayımla (subdomen boşalır).
3. Cloudflare DNS-də `contextpulse` üçün VPS-in IP-sinə `A` qeydi yarat, proxy açıq (narıncı bulud). HTTPS-i Cloudflare verir.
4. FastAPI eyni `static` fayllarını özü verir, ona görə ünvan dəyişmir və NexusWeb-də heç nəyi dəyişmək lazım deyil. Tətbiq `/api/bootstrap` cavab verəndə avtomatik canlı rejimə keçir.

Bundan sonra `contextpulse-demo` Worker-i ehtiyat kimi saxlanıla və ya silinə bilər.
