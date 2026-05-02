# Arbetsregler för Claude – Rison Bevakning

## Vid sessionsstart
- Kör `md5 ~/rison-bevakning/bevakning_serper.py` och jämför med senaste checksumma i git-loggen
- Läs denna fil och bekräfta att reglerna är förstådda

## Kvalitetskontroll vid varje ändring
- Läs igenom hela det berörda blocket INNAN du föreslår en ändring
- Gör alltid minimala kirurgiska ändringar – skriv aldrig om hela block
- Kör alltid syntaxkontroll efter varje ändring: `python3 -c "import py_compile; py_compile.compile('/Users/jesperlovkvist/rison-bevakning/bevakning_serper.py', doraise=True); print('Syntax OK')"`
- Verifiera att inget befintligt innehåll har försvunnit efter varje ändring

## Prompt-innehåll som alltid måste finnas i kopiera_prompt
- Rubrik på max 8 ord
- Källreferenser och organisationshänvisningar naturligt i brödtexten
- STEG 1: Faktaverifiering mot oberoende källor innan utkastet skrivs
- STEG 2: Utkast i klartext utan @-slugs
- STEG 3: Slug-sökning först efter att utkastet är klart
- Max 3000 tecken
- Hashtags och URL på sista raden

## Generella arbetsregler
- Aldrig skriva om hela block – gör minimala ändringar
- Syntaxkontroll körs alltid av Claude INNAN kod föreslås och EFTER att ändring bekräftats – aldrig av Jesper
- Aldrig generera HTML utan att syntaxkontroll passerat
- Aldrig föreslå nedladdning av filer – gör ändringar direkt i terminalen
- Om Jesper påtalar fel i arbetssättet – addera ny regel i denna fil omedelbart

## Versionssynk
- Läs alltid checksumman från senaste git-commit i sessionsstart: `git -C ~/rison-bevakning log --oneline -1`
- Om checksumman inte matchar – kör `sed -n` på relevanta rader innan någon ändring föreslås
- Aldrig anta att filen ser ut på ett visst sätt – verifiera alltid

## HTML-generering
- Ge alltid hela HTML-genereringskommandot i samma svarsblock som ändringen
- Aldrig lämna Jesper att fråga efter det separat

## Cache-hantering
- Påminn alltid om vilka cache-filer som behöver rensas när en ändring påverkar bedömningar eller sökord:
  - Prompt-ändringar → rensa bedomning_cache.json
  - Zeitgeist-prompt → rensa zeitgeist_cache.json
  - Dagsaktuella-prompt → rensa dagsaktuella_cache.json

## Feldiagnostik
- Kör alltid `sed -n` och `grep` för att hitta exakt vad som finns i filen innan en fix föreslås
- Aldrig be Jesper debugga – det är Claudes ansvar

## Cloudflare Worker
- Spara alltid senaste fungerande Worker-kod här nedan så att den kan återställas utan att leta
- Uppdatera efter varje lyckad deploy

### Senaste fungerande Worker-kod
Se Cloudflare dashboard: risonbevakning.jesper-75b.workers.dev

### Worker-kod (senast bekräftat fungerande)
```javascript
export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
    if (request.method === 'OPTIONS') return new Response(null, { headers: corsHeaders });
    const { action, query, url, fulltext } = await request.json();
    if (action === 'kontext') {
      const r = await fetch('https://google.serper.dev/news', {
        method: 'POST',
        headers: { 'X-API-KEY': env.SERPER_API_KEY, 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: query, gl: 'se', hl: 'sv', num: 5, tbs: 'qdr:m' }),
      });
      const data = await r.json();
      return new Response(JSON.stringify(data), { headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
    }
    if (action === 'linkedin' || action === 'linkedin_kort') {
      const stil = await fetch('https://raw.githubusercontent.com/jeslov/rison-bevakning/main/linkedin_stil.txt')
        .then(r => r.text()).catch(() => '');
      const kortFormat = action === 'linkedin_kort';
      const prompt = kortFormat ? `kort prompt` : `lång prompt`;
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 1500, tools: [{"type": "web_search_20250305", "name": "web_search"}], messages: [{ role: 'user', content: prompt }] }),
      });
      const data = await r.json();
      const textBlocks = (data.content || []).filter(b => b.type === 'text');
      const text = textBlocks.length > 0 ? textBlocks[textBlocks.length - 1].text : '';
      return new Response(JSON.stringify({ text }), { headers: { ...corsHeaders, 'Content-Type': 'application/json' } });
    }
    return new Response('Unknown action', { status: 400, headers: corsHeaders });
  }
};
```
