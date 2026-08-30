import json

# Brand SVGs dictionary for embedding into frontend JS
BRAND_SVGS_JS = """
const BRAND_SVGS = {
  gmail: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="4" fill="#F2F2F2"/><path d="M4 6l8 6 8-6" stroke="#EA4335" stroke-width="2" stroke-linecap="round"/><path d="M4 6v12h4v-7l4 3 4-3v7h4V6" fill="#EA4335"/></svg>`,
  composio: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="5" fill="#090A0F"/><path d="M6 8h4v8H6V8z" fill="#00E599"/><path d="M14 8h4v8h-4V8z" fill="#2E90FA"/><path d="M10 12h4v4h-4v-4z" fill="#fff"/></svg>`,
  github: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#FFFFFF"><path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>`,
  calendar: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="3" y="4" width="18" height="18" rx="4" fill="#4285F4"/><rect x="6" y="8" width="12" height="11" rx="2" fill="#fff"/><text x="12" y="16.5" font-size="7.5" font-family="sans-serif" font-weight="bold" fill="#4285F4" text-anchor="middle">31</text><path d="M7 2v4M17 2v4" stroke="#4285F4" stroke-width="2" stroke-linecap="round"/></svg>`,
  notion: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#FFFFFF"><path d="M4.459 4.208c.746.606 1.026.56 2.428.466l11.377-.84c1.12-.093 1.587.374 1.353 1.493l-1.96 9.42c-.234 1.12-.887 1.586-2.007 1.68l-11.377.84c-1.12.093-1.633-.42-1.353-1.54l1.539-7.464c.28-1.12.046-1.586-1.026-2.193L3 5.42l1.459-1.213zm3.78 2.893l-1.353 6.626c-.094.466.093.746.607.7l1.493-.094 1.306-6.44 3.733 6.16 2.38-.14 1.4-6.86c.094-.467-.093-.747-.607-.7l-1.493.093-1.307 6.44-3.733-6.16-2.427.375z"/></svg>`,
  sheets: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58"/><path d="M7 8h10v8H7V8z" fill="#fff" fill-opacity="0.2"/><path d="M7 11h10M7 14h10M12 8v8" stroke="#fff" stroke-width="1.5"/><path d="M15 3l6 6h-6V3z" fill="#0B8043"/></svg>`,
  slack: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M5.5 10a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" fill="#E01E5A"/><path d="M7 10h3V7.5A2.5 2.5 0 007.5 5 2.5 2.5 0 005 7.5c0 .28.05.54.13.79L7 10z" fill="#E01E5A"/><path d="M14 5.5a2.5 2.5 0 105 0 2.5 2.5 0 00-5 0z" fill="#36C5F0"/><path d="M14 7v3h2.5A2.5 2.5 0 0019 7.5 2.5 2.5 0 0016.5 5c-.28 0-.54.05-.79.13L14 7z" fill="#36C5F0"/><path d="M18.5 14a2.5 2.5 0 100 5 2.5 2.5 0 000-5z" fill="#2EB67D"/><path d="M17 14h-3v2.5a2.5 2.5 0 002.5 2.5 2.5 2.5 0 002.5-2.5c0-.28-.05-.54-.13-.79L17 14z" fill="#2EB67D"/><path d="M10 18.5a2.5 2.5 0 10-5 0 2.5 2.5 0 005 0z" fill="#ECB22E"/><path d="M10 17v-3H7.5A2.5 2.5 0 005 16.5 2.5 2.5 0 007.5 19c.28 0 .54-.05.79-.13L10 17z" fill="#ECB22E"/></svg>`,
  supabase: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M13.4 2.1c-.8-.9-2.2-.4-2.3.8l-1.3 10.3h7.6c1.3 0 2 1.5 1.2 2.4L9.8 22.9c-.8.9-2.2.4-2.3-.8l1.3-10.3H1.2C0 11.8-.7 10.3.1 9.4L8.9 1.1c.9-.9 2.4-.4 2.5.8l-.8 7.3h4.9c.7 0 1.2-.6.9-1.2L13.4 2.1z" fill="#3ECF8E"/></svg>`,
  outlook: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="7" y="4" width="14" height="16" rx="2" fill="#0078D4"/><path d="M14 8h7v8h-7V8z" fill="#28A8EA" fill-opacity="0.3"/><rect x="3" y="7" width="10" height="10" rx="2" fill="#0078D4" stroke="#fff" stroke-width="1.5"/><circle cx="8" cy="12" r="2.5" fill="#fff"/></svg>`,
  perplexity: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#20B2AA"><path d="M12 2L4 7.5v9L12 22l8-5.5v-9L12 2zm0 2.5l5.5 3.8L12 12.1 6.5 8.3 12 4.5zM5.8 9.5l5.2 3.6v6.4l-5.2-3.6V9.5zm12.4 0v6.4l-5.2 3.6v-6.4l5.2-3.6z"/></svg>`,
  twitter: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#FFFFFF"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>`,
  drive: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M8.2 3.5h7.6l5.7 9.8h-7.6L8.2 3.5z" fill="#FFC107"/><path d="M2.5 13.3L6.3 3.5l5.7 9.8-3.8 6.5-5.7-6.5z" fill="#0066DA"/><path d="M8.2 19.8h13.3l-3.8-6.5H4.4l3.8 6.5z" fill="#00AC47"/></svg>`,
  docs: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="4" y="2" width="16" height="20" rx="2" fill="#4285F4"/><path d="M14 2l6 6h-6V2z" fill="#A1C2FA"/><path d="M8 11h8M8 14h8M8 17h5" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  hubspot: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#FF7A59"><path d="M18.5 7.5A2.5 2.5 0 0016 5.1V3.5a1.5 1.5 0 10-3 0v1.6a2.5 2.5 0 00-2 2.4c0 .8.4 1.5 1 2v4.2a2.5 2.5 0 00-1 2v.2l-3.5-2.1a2 2 0 10-1 1.7l3.5 2.1a2.5 2.5 0 104.9.4v-4.3a2.5 2.5 0 001-2V9.5c.6-.5 1-1.2 1-2zm-4 0a1 1 0 11-2 0 1 1 0 012 0zm-1 11a1 1 0 110-2 1 1 0 010 2z"/></svg>`,
  linear: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><circle cx="12" cy="12" r="10" fill="#5E6AD2"/><path d="M7 16l9-9M7 12l5-5M12 17l5-5" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>`,
  airtable: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M11.5 3.5l-8 4.2c-.3.2-.5.5-.5.8v6.9c0 .4.2.7.5.8l8 4.3c.3.2.7.2 1 0l8-4.3c.3-.2.5-.5.5-.8V8.5c0-.4-.2-.7-.5-.8l-8-4.2c-.3-.2-.7-.2-1 0z" fill="#FCB400"/><path d="M12 4v16l8-4.3V8.5L12 4z" fill="#18BFFF"/><path d="M12 4v16L4 15.7V8.5L12 4z" fill="#F82B60"/></svg>`,
  python: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M11.8 2c-4.2 0-3.9 1.8-3.9 1.8l.04 1.9h4v.6H5.8S2 5.8 2 10.1c0 4.3 3.3 4.1 3.3 4.1h2v-2.8s-.1-3.3 3.3-3.3h5.7s3.2.1 3.2-3.1c0-3.3-3.7-3-3.7-3h-2zm-1.8 1.4a.8.8 0 110 1.6.8.8 0 010-1.6z" fill="#3776AB"/><path d="M12.2 22c4.2 0 3.9-1.8 3.9-1.8l-.04-1.9h-4v-.6h6.1s3.8.5 3.8-3.8c0-4.3-3.3-4.1-3.3-4.1h-2v2.8s.1 3.3-3.3 3.3H7.7s-3.2-.1-3.2 3.1c0 3.3 3.7 3 3.7 3h4zm1.8-1.4a.8.8 0 110-1.6.8.8 0 010 1.6z" fill="#FFD438"/></svg>`,
  serpapi: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="5" fill="#4B56C0"/><circle cx="8" cy="8" r="2.5" fill="#fff"/><circle cx="16" cy="8" r="2.5" fill="#fff"/><circle cx="12" cy="16" r="2.5" fill="#fff"/><path d="M8 8l4 8 4-8" stroke="#fff" stroke-width="1.5"/></svg>`,
  jira: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 2a10 10 0 00-7.1 17.1L12 12l7.1 7.1A10 10 0 0012 2z" fill="#0052CC"/><path d="M12 12L4.9 19.1A10 10 0 0012 22a10 10 0 007.1-2.9L12 12z" fill="#2684FF"/></svg>`,
  firecrawl: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 2C8.5 6 6 8.5 6 13c0 3.3 2.7 6 6 6s6-2.7 6-6c0-4.5-2.5-7-6-11z" fill="#FF4D00"/><path d="M12 8c-2 2.5-3 4-3 6.5 0 1.7 1.3 3 3 3s3-1.3 3-3c0-2.5-1-4-3-6.5z" fill="#FFA500"/></svg>`,
  tavily: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 3l7 7-7 7-7-7 7-7z" fill="#2E90FA"/><circle cx="12" cy="12" r="2" fill="#fff"/></svg>`,
  youtube: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="2" y="4" width="20" height="16" rx="4" fill="#FF0000"/><path d="M10 8.5l6 3.5-6 3.5v-7z" fill="#fff"/></svg>`,
  slackbot: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="5" fill="#4A154B"/><circle cx="9" cy="10" r="1.5" fill="#fff"/><circle cx="15" cy="10" r="1.5" fill="#fff"/><path d="M8 15h8" stroke="#2EB67D" stroke-width="2" stroke-linecap="round"/></svg>`,
  canvas: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect x="3" y="3" width="18" height="18" rx="4" fill="#E63946"/><path d="M7 17L12 7l5 10H7z" fill="#F1FAEE"/><circle cx="12" cy="13" r="2" fill="#1D3557"/></svg>`,
  figma: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M8 3.5A2.5 2.5 0 005.5 6 2.5 2.5 0 008 8.5h2.5V3.5H8z" fill="#F24E1E"/><path d="M13.5 3.5H16a2.5 2.5 0 012.5 2.5 2.5 2.5 0 01-2.5 2.5h-2.5V3.5z" fill="#FF7262"/><path d="M13.5 8.5H16a2.5 2.5 0 012.5 2.5 2.5 2.5 0 01-2.5 2.5h-2.5V8.5z" fill="#1ABCFE"/><path d="M8 8.5A2.5 2.5 0 005.5 11 2.5 2.5 0 008 13.5h2.5V8.5H8z" fill="#A259FF"/><path d="M8 13.5A2.5 2.5 0 005.5 16 2.5 2.5 0 008 18.5 2.5 2.5 0 0010.5 16v-2.5H8z" fill="#0ACF83"/><circle cx="16" cy="16" r="2.5" fill="#1ABCFE"/></svg>`,
  resend: `<svg viewBox="0 0 24 24" width="24" height="24" fill="#FFFFFF"><path d="M3 4h18v16H3V4zm2 2v1.5l7 4.5 7-4.5V6H5zm14 4.2l-7 4.5-7-4.5V18h14v-7.8z"/></svg>`,
  sentry: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M13.1 3.5a1.5 1.5 0 00-2.2 0l-7.7 8.3c-.6.6-.1 1.7.8 1.7h16c.9 0 1.4-1.1.8-1.7l-7.7-8.3z" fill="#362D59"/><circle cx="12" cy="18" r="2" fill="#E1567C"/></svg>`,
  postgres: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 3C7 3 4 6.5 4 11c0 3.8 2.5 6.8 6 7.6v2.4h4v-2.4c3.5-.8 6-3.8 6-7.6 0-4.5-3-8-8-8z" fill="#336791"/><circle cx="9" cy="9.5" r="1.5" fill="#fff"/><circle cx="15" cy="9.5" r="1.5" fill="#fff"/></svg>`,
  brave: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M12 2l8 4-1.5 8.5L12 22l-6.5-7.5L4 6l8-4z" fill="#FB542B"/><path d="M12 6l5 2.5-1 5.5L12 18l-4-4-.8-5.5L12 6z" fill="#fff"/></svg>`,
  exa: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><circle cx="12" cy="12" r="10" fill="#111"/><path d="M7 8h3l2 4 2-4h3l-3.5 6L17 20h-3l-2-4-2 4H7l3.5-6L7 8z" fill="#fff"/></svg>`,
  huggingface: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><circle cx="12" cy="12" r="10" fill="#FFD21E"/><circle cx="8.5" cy="10" r="1.5" fill="#000"/><circle cx="15.5" cy="10" r="1.5" fill="#000"/><path d="M8 14.5c1.2 1.5 2.8 2 4 2s2.8-.5 4-2" stroke="#000" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  cloudflare: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><path d="M19.4 14.8c0-.3.1-.6.1-.9 0-3-2.4-5.4-5.4-5.4-2.5 0-4.6 1.7-5.2 4-.5-.3-1.1-.4-1.8-.4-2 0-3.6 1.6-3.6 3.6 0 .2 0 .5.1.7H19.4z" fill="#F38020"/><path d="M18.8 17.5c1.8 0 3.2-1.4 3.2-3.2 0-1.5-1-2.8-2.5-3.1-.2 0-.3.2-.3.3l-.2 1c-.1.3 0 .6.2.8.9.3 1.5 1.1 1.5 2.1 0 1.2-1 2.1-2.1 2.1H5.8c-.8 0-1.4-.6-1.4-1.4 0-.7.5-1.3 1.2-1.4l.7-.1c.3 0 .5-.3.4-.6-.2-.7.3-1.5 1-1.5.3 0 .5.1.8.3.2.2.6.2.8 0 .8-1 2-1.6 3.4-1.6 2.3 0 4.1 1.7 4.3 4 .1.3.3.5.6.5h3.2z" fill="#FAAD3F"/></svg>`,
  kater: `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="6" fill="#2DD4BF"/><path d="M7 6v12M17 6l-7 6 7 6" stroke="#0B0D10" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
};

function getBrandSvg(name) {
  if (!name) return BRAND_SVGS.kater;
  const key = name.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (BRAND_SVGS[key]) return BRAND_SVGS[key];
  if (key.includes('gmail')) return BRAND_SVGS.gmail;
  if (key.includes('cal')) return BRAND_SVGS.calendar;
  if (key.includes('sheet')) return BRAND_SVGS.sheets;
  if (key.includes('doc')) return BRAND_SVGS.docs;
  if (key.includes('drive')) return BRAND_SVGS.drive;
  if (key.includes('slack')) return BRAND_SVGS.slack;
  if (key.includes('notion')) return BRAND_SVGS.notion;
  if (key.includes('github')) return BRAND_SVGS.github;
  if (key.includes('linear')) return BRAND_SVGS.linear;
  if (key.includes('supabase')) return BRAND_SVGS.supabase;
  if (key.includes('outlook')) return BRAND_SVGS.outlook;
  if (key.includes('perplexity')) return BRAND_SVGS.perplexity;
  if (key.includes('twitter') || key === 'x') return BRAND_SVGS.twitter;
  if (key.includes('hubspot')) return BRAND_SVGS.hubspot;
  if (key.includes('airtable')) return BRAND_SVGS.airtable;
  if (key.includes('python') || key.includes('code')) return BRAND_SVGS.python;
  if (key.includes('serp')) return BRAND_SVGS.serpapi;
  if (key.includes('jira')) return BRAND_SVGS.jira;
  if (key.includes('firecrawl')) return BRAND_SVGS.firecrawl;
  if (key.includes('tavily')) return BRAND_SVGS.tavily;
  if (key.includes('youtube')) return BRAND_SVGS.youtube;
  if (key.includes('canvas')) return BRAND_SVGS.canvas;
  if (key.includes('figma')) return BRAND_SVGS.figma;
  if (key.includes('resend')) return BRAND_SVGS.resend;
  if (key.includes('sentry')) return BRAND_SVGS.sentry;
  if (key.includes('postgres')) return BRAND_SVGS.postgres;
  if (key.includes('cloudflare')) return BRAND_SVGS.cloudflare;
  if (key.includes('brave')) return BRAND_SVGS.brave;
  if (key.includes('exa')) return BRAND_SVGS.exa;
  if (key.includes('hugging')) return BRAND_SVGS.huggingface;
  if (key.includes('composio')) return BRAND_SVGS.composio;
  
  const initial = (name[0] || 'M').toUpperCase();
  return `<svg viewBox="0 0 24 24" width="24" height="24" fill="none"><rect width="24" height="24" rx="5" fill="#1E293B"/><text x="12" y="16.5" font-family="sans-serif" font-weight="bold" font-size="11" fill="#2DD4BF" text-anchor="middle">${initial}</text></svg>`;
}
"""

with open('scripts/build_full_dashboard.py', 'w', encoding='utf-8') as f:
    f.write('''import json

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="h-full dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kater Dev Tools — Apps & MCP Store</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#F0FDFA',
              400: '#2DD4BF',
              500: '#14B8A6',
              600: '#0D9488',
            },
            dark: {
              bg: '#0A0C10',
              panel: '#10141C',
              card: '#151B26',
              cardHover: '#1C2433',
              border: '#212936',
              text: '#E2E8F0',
              muted: '#8B949E'
            }
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #0A0C10; color: #E2E8F0; }
    code, pre, .font-mono { font-family: 'JetBrains Mono', monospace; }
    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: transparent; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #2A3447; border-radius: 3px; }
  </style>
</head>
<body class="h-full overflow-hidden flex flex-col bg-[#0A0C10] text-[#E2E8F0]">
  <!-- Top Navigation Bar -->
  <header id="top-nav" class="h-14 border-b border-[#212936] bg-[#10141C] flex items-center justify-between px-5 flex-shrink-0 z-30">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-[#2DD4BF] flex items-center justify-center text-[#0B0D10] font-black text-base shadow-sm">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M7 6v12M17 6l-7 6 7 6" stroke="#0B0D10" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-sm tracking-tight text-white">KATER</span>
          <span class="text-xs px-1.5 py-0.5 rounded bg-[#2DD4BF]/10 text-[#2DD4BF] border border-[#2DD4BF]/20 font-mono font-medium">v1.1.0</span>
          <span class="text-xs text-[#8B949E]">Dev Tools & Integrations Hub</span>
        </div>
      </div>
    </div>

    <!-- Active Profile & Live Health -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#151B26] border border-[#212936] text-xs">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-[#8B949E]">Gateway:</span>
        <span class="font-mono text-emerald-400 font-medium">127.0.0.1:__PORT__</span>
      </div>
      <div class="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#151B26] border border-[#212936] text-xs">
        <span class="text-[#8B949E]">Profile:</span>
        <select id="header-profile-select" onchange="switchProfile(this.value)" class="bg-transparent text-white font-mono font-medium focus:outline-none cursor-pointer">
          <option value="core">core</option>
          <option value="dev" selected>dev</option>
          <option value="ops">ops</option>
          <option value="research">research</option>
          <option value="browser">browser</option>
          <option value="content">content</option>
          <option value="full">full</option>
        </select>
      </div>
      <button onclick="openCustomMcpModal()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#2DD4BF] text-[#0B0D10] text-xs font-semibold hover:bg-[#20bdab] transition">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Add MCP Server
      </button>
    </div>
  </header>

  <!-- Main Layout -->
  <div class="flex-1 flex overflow-hidden">
    <!-- Sidebar Navigation -->
    <aside class="w-64 border-r border-[#212936] bg-[#10141C] flex flex-col justify-between flex-shrink-0 z-20">
      <div class="p-3 space-y-6">
        <div>
          <div class="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Connect & Discover</div>
          <nav class="space-y-1">
            <button onclick="setTab('apps')" id="nav-apps" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition bg-[#1C2433] text-[#2DD4BF] border border-[#2DD4BF]/20 shadow-sm">
              <div class="flex items-center gap-2.5">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
                <span>Apps & MCP Store</span>
              </div>
              <span id="badge-active-apps" class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#2DD4BF]/20 text-[#2DD4BF]">12 Active</span>
            </button>
            <button onclick="setTab('hub')" id="nav-hub" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <div class="flex items-center gap-2.5">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                <span>Agent Toolkits & Runner</span>
              </div>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[#212936] text-[#8B949E]">5</span>
            </button>
            <button onclick="setTab('discovery')" id="nav-discovery" class="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <div class="flex items-center gap-2.5">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
                <span>MCP.so Registry</span>
              </div>
              <span class="text-[10px] font-medium text-emerald-400">Live</span>
            </button>
          </nav>
        </div>

        <div>
          <div class="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-[#6B7280]">Workspace & Control</div>
          <nav class="space-y-1">
            <button onclick="setTab('overview')" id="nav-overview" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 9l-5 5-4-4-3 3"/></svg>
              <span>Control Room</span>
            </button>
            <button onclick="setTab('browser')" id="nav-browser" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              <span>Browser Workspace</span>
            </button>
            <button onclick="setTab('prgate')" id="nav-prgate" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/></svg>
              <span>PR Gate & CI</span>
            </button>
            <button onclick="setTab('automations')" id="nav-automations" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="9" y="15" width="6" height="6" rx="1"/><path d="M6 9v3a1 1 0 001 1h10a1 1 0 001-1V9M12 13v2"/></svg>
              <span>Automations</span>
            </button>
            <button onclick="setTab('telemetry')" id="nav-telemetry" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              <span>Telemetry & Events</span>
            </button>
            <button onclick="setTab('settings')" id="nav-settings" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
              <span>Settings & Ports</span>
            </button>
          </nav>
        </div>
      </div>

      <!-- Footer Quick Status -->
      <div class="p-3 border-t border-[#212936] bg-[#0D1017]">
        <div class="flex items-center justify-between text-xs text-[#8B949E]">
          <span>Kater Core</span>
          <span class="font-mono text-emerald-400">SSE Active</span>
        </div>
      </div>
    </aside>

    <!-- Main Viewport -->
    <main class="flex-1 overflow-y-auto custom-scroll bg-[#0A0C10] p-6">
      
      <!-- ════════════════════════════════════════════════════════════
           TAB 1: APPS & MCP STORE (COMPOSIO GRADE)
           ════════════════════════════════════════════════════════════ -->
      <section id="view-apps" class="space-y-6">
        <!-- Header row -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Apps</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Explore, connect, and manage authenticated MCP integrations and autonomous agent toolkits.</p>
          </div>
          
          <div class="flex items-center gap-3">
            <button onclick="openRequestAppModal()" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#212936] bg-[#151B26] hover:bg-[#1C2433] text-xs font-medium text-[#E2E8F0] transition">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Request App
            </button>
            <button onclick="openCustomMcpModal()" class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-semibold hover:bg-[#20bdab] transition shadow-sm">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Add Custom MCP
            </button>
          </div>
        </div>

        <!-- Filter Pill Bar & Search -->
        <div class="flex flex-col sm:flex-row items-center justify-between gap-4 pb-2 border-b border-[#212936]">
          <!-- Filter pills (All | Connected) -->
          <div class="flex items-center gap-2 w-full sm:w-auto">
            <button onclick="filterConnected('all')" id="filter-all" class="px-3.5 py-1.5 rounded-md text-xs font-semibold bg-[#212936] text-white border border-[#2DD4BF]/40 transition">
              All
            </button>
            <button onclick="filterConnected('connected')" id="filter-connected" class="px-3.5 py-1.5 rounded-md text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] transition">
              Connected
            </button>
            <div class="h-4 w-px bg-[#212936] mx-1"></div>
            <!-- Category Pills -->
            <select id="category-filter-select" onchange="filterCategory(this.value)" class="bg-[#151B26] border border-[#212936] rounded-md px-2.5 py-1.5 text-xs text-[#E2E8F0] focus:outline-none">
              <option value="all">All Categories</option>
              <option value="workspace">Workspace & CRM</option>
              <option value="dev">Developer & Engineering</option>
              <option value="ai">AI & Reasoning</option>
              <option value="data">Databases & Cloud</option>
              <option value="web">Search & Scraping</option>
              <option value="comm">Communication</option>
              <option value="design">Design & Media</option>
            </select>
          </div>

          <!-- Search Input -->
          <div class="relative w-full sm:w-80">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#8B949E]">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </div>
            <input type="text" id="app-search-input" oninput="handleAppSearch(this.value)" placeholder="Search apps and MCP servers..." class="w-full pl-9 pr-4 py-1.5 bg-[#151B26] border border-[#212936] rounded-lg text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#2DD4BF]/50 focus:ring-1 focus:ring-[#2DD4BF]/50 transition">
          </div>
        </div>

        <!-- App Grid: 3 columns on desktop -->
        <div id="apps-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Dynamically populated -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 2: AGENT TOOLKITS & ACTION RUNNER
           ════════════════════════════════════════════════════════════ -->
      <section id="view-hub" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Agent Toolkits & Action Runner</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Pre-configured bundles of verified MCP servers grouped for specific autonomous workflows.</p>
        </div>

        <!-- Toolkits List -->
        <div id="toolkits-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Populated by JS -->
        </div>

        <!-- Action Inspector & Playground -->
        <div class="mt-8 border border-[#212936] rounded-xl bg-[#10141C] p-5 space-y-4">
          <div class="flex items-center justify-between border-b border-[#212936] pb-3">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-[#2DD4BF]"></span>
              <h2 class="text-sm font-bold text-white uppercase tracking-wider">Interactive Action Playground</h2>
            </div>
            <span class="text-xs text-[#8B949E]">Direct execution via Kater MCP Proxy</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Target MCP Action</label>
              <select id="playground-action-select" onchange="onPlaygroundActionChange(this.value)" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2.5 text-xs text-white focus:outline-none">
                <!-- Populated by JS -->
              </select>
              
              <div id="playground-action-desc" class="text-xs text-[#8B949E] bg-[#151B26] p-3 rounded-lg border border-[#212936]">
                Select an action to inspect parameters and test live execution.
              </div>
            </div>

            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Input Payload (JSON)</label>
              <textarea id="playground-payload-input" rows="6" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2.5 text-xs font-mono text-white focus:outline-none focus:border-[#2DD4BF]/50" placeholder='{"query": "example"}'></textarea>
              <button onclick="runPlaygroundAction()" id="btn-run-action" class="w-full py-2 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition flex items-center justify-center gap-2">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                Execute Action
              </button>
            </div>

            <div class="space-y-3">
              <label class="block text-xs font-semibold text-[#8B949E]">Execution Output</label>
              <pre id="playground-output-result" class="h-44 bg-[#0D1017] border border-[#212936] rounded-lg p-3 text-xs font-mono text-emerald-400 overflow-y-auto custom-scroll">Ready to execute.</pre>
            </div>
          </div>
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 3: MCP.SO & EXTERNAL DISCOVERY REGISTRY
           ════════════════════════════════════════════════════════════ -->
      <section id="view-discovery" class="space-y-6 hidden">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">MCP.so Server Registry & Community</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Discover trending open-source Model Context Protocol servers verified for Kater Dev Tools.</p>
          </div>
          <div class="flex items-center gap-2">
            <a href="https://mcp.so/servers" target="_blank" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#212936] bg-[#151B26] text-xs font-medium text-[#8B949E] hover:text-white transition">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Open MCP.so
            </a>
            <a href="https://dashboard.composio.dev" target="_blank" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#212936] bg-[#151B26] text-xs font-medium text-[#8B949E] hover:text-white transition">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              Composio Dashboard
            </a>
          </div>
        </div>

        <div id="discovery-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 4: CONTROL ROOM (OVERVIEW)
           ════════════════════════════════════════════════════════════ -->
      <section id="view-overview" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Gateway Control Room</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">System health, SSE streaming listeners, and database statistics.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-1">
            <div class="text-xs text-[#8B949E]">Gateway Port</div>
            <div class="text-xl font-bold font-mono text-[#2DD4BF]">3000</div>
            <div class="text-[11px] text-emerald-400">Reverse proxy active</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-1">
            <div class="text-xs text-[#8B949E]">Active Servers</div>
            <div id="stat-active-servers" class="text-xl font-bold font-mono text-white">12 / 36</div>
            <div class="text-[11px] text-[#8B949E]">Native & stdio proxies</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-1">
            <div class="text-xs text-[#8B949E]">Telemetry Events</div>
            <div id="stat-telemetry-count" class="text-xl font-bold font-mono text-white">184</div>
            <div class="text-[11px] text-emerald-400">Stream connected</div>
          </div>
          <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-1">
            <div class="text-xs text-[#8B949E]">Storage State</div>
            <div class="text-xl font-bold font-mono text-white">SQLite</div>
            <div class="text-[11px] text-[#8B949E]">.kater/kater.db</div>
          </div>
        </div>

        <div class="p-5 rounded-xl bg-[#10141C] border border-[#212936] space-y-3">
          <h3 class="text-sm font-bold text-white">Quick Verify Ladder</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div class="p-3 bg-[#151B26] border border-[#212936] rounded-lg">
              <div class="text-xs font-bold text-white">REST API & Health</div>
              <div class="text-xs text-[#8B949E] mt-1 font-mono">curl -s http://127.0.0.1:__PORT__/health</div>
              <div class="mt-2 text-xs text-emerald-400 font-medium">✓ 200 OK</div>
            </div>
            <div class="p-3 bg-[#151B26] border border-[#212936] rounded-lg">
              <div class="text-xs font-bold text-white">MCP SSE Endpoint</div>
              <div class="text-xs text-[#8B949E] mt-1 font-mono">http://127.0.0.1:__PORT__/sse</div>
              <div class="mt-2 text-xs text-emerald-400 font-medium">✓ Handshake Ready</div>
            </div>
            <div class="p-3 bg-[#151B26] border border-[#212936] rounded-lg">
              <div class="text-xs font-bold text-white">WebSocket Telemetry</div>
              <div class="text-xs text-[#8B949E] mt-1 font-mono">ws://127.0.0.1:__PORT__/ws</div>
              <div class="mt-2 text-xs text-emerald-400 font-medium">✓ Live Connected</div>
            </div>
          </div>
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 5: BROWSER WORKSPACE
           ════════════════════════════════════════════════════════════ -->
      <section id="view-browser" class="space-y-6 hidden">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Browser Automation Workspace</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Autonomous Playwright & Puppeteer browser sessions with live viewport capture.</p>
          </div>
          <button onclick="createBrowserSession()" class="px-3.5 py-1.5 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded-lg hover:bg-[#20bdab] transition">
            + New Browser Session
          </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4" id="browser-sessions-grid">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 6: PR GATE & CI
           ════════════════════════════════════════════════════════════ -->
      <section id="view-prgate" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">PR Gate & CI Pipeline</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Automated merge-ready checks, ruff linter, mypy types, and test suites.</p>
        </div>

        <div class="space-y-3" id="pr-list-container">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 7: AUTOMATIONS
           ════════════════════════════════════════════════════════════ -->
      <section id="view-automations" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Autonomous Cron & Event Automations</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Scheduled tasks, webhooks, and multi-step agent triggers.</p>
        </div>

        <div class="space-y-3" id="automations-list-container">
          <!-- Populated by JS -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 8: TELEMETRY & EVENTS
           ════════════════════════════════════════════════════════════ -->
      <section id="view-telemetry" class="space-y-6 hidden">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold text-white tracking-tight">Live Telemetry & MCP Event Stream</h1>
            <p class="text-xs text-[#8B949E] mt-0.5">Real-time WebSocket events from connected tool calls, proxy dispatches, and agent sessions.</p>
          </div>
          <button onclick="clearTelemetryLog()" class="px-3 py-1.5 bg-[#151B26] border border-[#212936] text-xs text-[#8B949E] hover:text-white rounded-lg transition">
            Clear Stream
          </button>
        </div>

        <div id="telemetry-log-box" class="h-96 bg-[#0D1017] border border-[#212936] rounded-xl p-4 font-mono text-xs text-[#E2E8F0] overflow-y-auto custom-scroll space-y-2">
          <!-- Stream lines -->
        </div>
      </section>

      <!-- ════════════════════════════════════════════════════════════
           TAB 9: SETTINGS
           ════════════════════════════════════════════════════════════ -->
      <section id="view-settings" class="space-y-6 hidden">
        <div>
          <h1 class="text-2xl font-bold text-white tracking-tight">Settings & Gateway Config</h1>
          <p class="text-xs text-[#8B949E] mt-0.5">Environment, authentication modes, CORS policies, and SQLite persistence.</p>
        </div>

        <div class="max-w-2xl bg-[#10141C] border border-[#212936] rounded-xl p-5 space-y-4">
          <div>
            <label class="block text-xs font-semibold text-white mb-1">Gateway Auth Mode</label>
            <div class="text-xs text-[#8B949E] mb-2">Controls whether bearer tokens are required on MCP and REST endpoints.</div>
            <select id="settings-auth-mode" class="bg-[#151B26] border border-[#212936] rounded-lg p-2 text-xs text-white w-full">
              <option value="none" selected>none (Open local development)</option>
              <option value="token">token (Bearer token authentication)</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-semibold text-white mb-1">CORS Origins</label>
            <input type="text" value="*" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-xs text-white font-mono">
          </div>

          <div class="pt-2 border-t border-[#212936] flex justify-end">
            <button onclick="saveSettings()" class="px-4 py-2 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded-lg hover:bg-[#20bdab] transition">
              Save Configuration
            </button>
          </div>
        </div>
      </section>

    </main>
  </div>

  <!-- ════════════════════════════════════════════════════════════
       MODALS: CONNECT APP / CUSTOM MCP / REQUEST APP
       ════════════════════════════════════════════════════════════ -->

  <!-- Modal: Connect App (API Key / OAuth) -->
  <div id="modal-connect-app" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#212936] rounded-2xl w-full max-w-md p-6 space-y-5 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#212936] pb-4">
        <div class="flex items-center gap-3">
          <div id="modal-app-icon" class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#212936] flex items-center justify-center p-1.5">
            <!-- Brand SVG -->
          </div>
          <div>
            <h3 id="modal-app-name" class="text-sm font-bold text-white">Connect App</h3>
            <div id="modal-app-category" class="text-[11px] text-[#8B949E]">Workspace Integration</div>
          </div>
        </div>
        <button onclick="closeConnectModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="space-y-4" id="modal-connect-body">
        <!-- Injected dynamically based on authType -->
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-[#212936] pt-4">
        <button onclick="closeConnectModal()" class="px-3.5 py-1.5 rounded-lg border border-[#212936] text-xs text-[#8B949E] hover:text-white">
          Cancel
        </button>
        <button id="modal-btn-confirm-connect" onclick="submitAppConnection()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition">
          Connect & Enable
        </button>
      </div>
    </div>
  </div>

  <!-- Modal: Add Custom MCP Server -->
  <div id="modal-custom-mcp" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#212936] rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#212936] pb-3">
        <h3 class="text-base font-bold text-white">Add Custom MCP Server</h3>
        <button onclick="closeCustomMcpModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Server Identifier (Name)</label>
          <input type="text" id="custom-server-name" placeholder="my-custom-mcp" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Transport Type</label>
          <select id="custom-server-transport" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white focus:outline-none">
            <option value="stdio">stdio (Subprocess / CLI Command)</option>
            <option value="http">http / sse (Remote URL Stream)</option>
          </select>
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Command / Remote URL</label>
          <input type="text" id="custom-server-command" placeholder="npx -y my-mcp-server@latest or https://mcp.example.com/sse" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Category</label>
          <select id="custom-server-category" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white focus:outline-none">
            <option value="dev">Developer & Engineering</option>
            <option value="workspace">Workspace & CRM</option>
            <option value="ai">AI & Reasoning</option>
            <option value="data">Databases & Cloud</option>
            <option value="web">Search & Web Scraping</option>
            <option value="comm">Communication</option>
            <option value="design">Design & Media</option>
          </select>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-[#212936] pt-3">
        <button onclick="closeCustomMcpModal()" class="px-3 py-1.5 rounded-lg border border-[#212936] text-xs text-[#8B949E]">Cancel</button>
        <button onclick="submitCustomMcp()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab]">Register MCP Server</button>
      </div>
    </div>
  </div>

  <!-- Modal: Request App -->
  <div id="modal-request-app" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 hidden">
    <div class="bg-[#10141C] border border-[#212936] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-[#212936] pb-3">
        <h3 class="text-base font-bold text-white">Request an App or MCP Tool</h3>
        <button onclick="closeRequestAppModal()" class="text-[#8B949E] hover:text-white">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <p class="text-[#8B949E]">Can't find the integration you need? Submit your request and our team will build an official connector.</p>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">App Name / Service</label>
          <input type="text" id="request-app-name" placeholder="e.g. Asana, Snowflake, Intercom" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white focus:outline-none focus:border-[#2DD4BF]">
        </div>
        <div>
          <label class="block text-[#8B949E] mb-1 font-medium">Use Case / Actions Needed</label>
          <textarea id="request-app-usecase" rows="3" placeholder="Briefly describe what your autonomous agents will do with this integration..." class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-white focus:outline-none focus:border-[#2DD4BF]"></textarea>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-[#212936] pt-3">
        <button onclick="closeRequestAppModal()" class="px-3 py-1.5 rounded-lg border border-[#212936] text-xs text-[#8B949E]">Cancel</button>
        <button onclick="submitRequestApp()" class="px-4 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab]">Submit Request</button>
      </div>
    </div>
  </div>

  <!-- Client-side Logic -->
  <script>
""" + BRAND_SVGS_JS + """
    let state = {
      servers: [],
      toolkits: [],
      filter: 'all',
      category: 'all',
      searchQuery: '',
      currentConnectingApp: null,
      telemetryEvents: [],
      browserSessions: [],
      prs: [],
      automations: []
    };

    // Tab Navigation
    function setTab(tabId) {
      const tabs = ['apps', 'hub', 'discovery', 'overview', 'browser', 'prgate', 'automations', 'telemetry', 'settings'];
      tabs.forEach(t => {
        const viewEl = document.getElementById('view-' + t);
        const navEl = document.getElementById('nav-' + t);
        if (viewEl) viewEl.classList.toggle('hidden', t !== tabId);
        if (navEl) {
          if (t === tabId) {
            navEl.className = 'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition bg-[#1C2433] text-[#2DD4BF] border border-[#2DD4BF]/20 shadow-sm';
          } else {
            navEl.className = 'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition text-[#9CA3AF] hover:text-white hover:bg-[#151B26]';
          }
        }
      });
    }

    // Filter by Connected State
    function filterConnected(type) {
      state.filter = type;
      document.getElementById('filter-all').className = type === 'all' 
        ? 'px-3.5 py-1.5 rounded-md text-xs font-semibold bg-[#212936] text-white border border-[#2DD4BF]/40 transition'
        : 'px-3.5 py-1.5 rounded-md text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] transition';
      document.getElementById('filter-connected').className = type === 'connected'
        ? 'px-3.5 py-1.5 rounded-md text-xs font-semibold bg-[#212936] text-white border border-[#2DD4BF]/40 transition'
        : 'px-3.5 py-1.5 rounded-md text-xs font-medium text-[#8B949E] hover:text-white hover:bg-[#151B26] transition';
      renderAppsGrid();
    }

    function filterCategory(cat) {
      state.category = cat;
      renderAppsGrid();
    }

    function handleAppSearch(q) {
      state.searchQuery = (q || '').toLowerCase().trim();
      renderAppsGrid();
    }

    // Fetch initial data
    async function loadData() {
      try {
        const [resInt, resTk, resBrw, resPr, resAuto] = await Promise.all([
          fetch('/api/integrations').then(r => r.json()),
          fetch('/api/integrations/toolkits').then(r => r.json()),
          fetch('/api/browser/sessions').then(r => r.json()).catch(() => ({ sessions: [] })),
          fetch('/api/pr/items').then(r => r.json()).catch(() => ({ prs: [] })),
          fetch('/api/automations').then(r => r.json()).catch(() => ({ automations: [] }))
        ]);

        state.servers = resInt.integrations || [];
        state.toolkits = resTk.toolkits || [];
        state.browserSessions = resBrw.sessions || [];
        state.prs = resPr.prs || [];
        state.automations = resAuto.automations || [];

        renderAppsGrid();
        renderToolkits();
        renderPlaygroundOptions();
        renderDiscoveryGrid();
        renderBrowserSessions();
        renderPrs();
        renderAutomations();
        updateStats(resInt.stats);
      } catch (err) {
        console.error('Failed loading dashboard data:', err);
      }
    }

    function updateStats(stats) {
      const activeCount = state.servers.filter(s => s.enabled).length;
      const totalCount = state.servers.length;
      
      const badge = document.getElementById('badge-active-apps');
      if (badge) badge.innerText = `${activeCount} Active`;
      
      const statActive = document.getElementById('stat-active-servers');
      if (statActive) statActive.innerText = `${activeCount} / ${totalCount}`;
    }

    // Render 3-column Apps Grid matching Composio
    function renderAppsGrid() {
      const grid = document.getElementById('apps-grid');
      if (!grid) return;

      let filtered = state.servers;

      if (state.filter === 'connected') {
        filtered = filtered.filter(s => s.enabled);
      }

      if (state.category !== 'all') {
        filtered = filtered.filter(s => s.category === state.category);
      }

      if (state.searchQuery) {
        filtered = filtered.filter(s => 
          (s.displayName || s.name).toLowerCase().includes(state.searchQuery) ||
          (s.description || '').toLowerCase().includes(state.searchQuery) ||
          (s.category || '').toLowerCase().includes(state.searchQuery)
        );
      }

      if (filtered.length === 0) {
        grid.innerHTML = `
          <div class="col-span-full py-12 text-center text-[#8B949E] bg-[#10141C] border border-[#212936] rounded-2xl">
            <div class="text-sm font-semibold text-white">No applications found</div>
            <div class="text-xs mt-1">Try adjusting your search query or filters.</div>
          </div>
        `;
        return;
      }

      const shieldSvg = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none"><path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z" stroke="#4880FF" stroke-width="1.8" fill="rgba(72,128,255,0.15)" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 11.5l2 2 4-4" stroke="#4880FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

      grid.innerHTML = filtered.map(app => {
        const isConnected = app.enabled;
        const brandSvg = getBrandSvg(app.name);
        const displayName = app.displayName || app.name;
        const activeCount = app.activeCount || (isConnected ? 1 : 0);

        let buttonHtml = '';
        if (isConnected) {
          buttonHtml = `
            <div class="flex items-center gap-2">
              <span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                ${activeCount} Active
              </span>
              <button onclick="event.stopPropagation(); openConnectModal('${app.name}')" class="px-2 py-1 rounded-md border border-[#212936] hover:bg-[#1C2433] text-[11px] font-medium text-[#8B949E] hover:text-white transition">
                + New
              </button>
            </div>
          `;
        } else {
          buttonHtml = `
            <button onclick="event.stopPropagation(); openConnectModal('${app.name}')" class="px-3.5 py-1.5 rounded-md bg-[#2DD4BF] text-[#0B0D10] hover:bg-[#20bdab] text-xs font-semibold transition shadow-sm">
              Connect
            </button>
          `;
        }

        return `
          <div onclick="selectAppForDetails('${app.name}')" class="p-4 rounded-xl bg-[#10141C] border border-[#212936] hover:border-[#2DD4BF]/40 hover:bg-[#151B26] transition flex items-center justify-between cursor-pointer group shadow-sm">
            <div class="flex items-center gap-3.5 min-w-0">
              <div class="w-10 h-10 rounded-lg bg-[#151B26] border border-[#212936] flex items-center justify-center p-2 flex-shrink-0 group-hover:border-[#2DD4BF]/30 transition">
                ${brandSvg}
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="font-bold text-sm text-white truncate">${displayName}</span>
                  ${app.verified ? `<span title="Verified Enterprise MCP">${shieldSvg}</span>` : ''}
                </div>
                <div class="text-xs text-[#8B949E] truncate capitalize">${app.category || 'Tool'} • ${app.actions?.length || 1} Actions</div>
              </div>
            </div>
            <div class="flex-shrink-0 ml-3">
              ${buttonHtml}
            </div>
          </div>
        `;
      }).join('');
    }

    // Render Toolkits Tab
    function renderToolkits() {
      const grid = document.getElementById('toolkits-grid');
      if (!grid) return;

      grid.innerHTML = state.toolkits.map(tk => {
        return `
          <div class="p-5 rounded-xl bg-[#10141C] border border-[#212936] space-y-4">
            <div class="flex items-start justify-between">
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-base font-bold text-white">${tk.name}</h3>
                  <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-[#2DD4BF]/10 text-[#2DD4BF] border border-[#2DD4BF]/20">${tk.badge}</span>
                </div>
                <p class="text-xs text-[#8B949E] mt-1">${tk.description}</p>
              </div>
            </div>

            <div class="space-y-2">
              <div class="text-[11px] font-semibold text-[#8B949E] uppercase tracking-wider">Included MCP Servers:</div>
              <div class="flex flex-wrap gap-1.5">
                ${tk.servers.map(sname => `
                  <span class="px-2 py-1 rounded-md bg-[#151B26] border border-[#212936] text-xs font-mono text-[#E2E8F0] flex items-center gap-1.5">
                    <span class="w-3 h-3">${getBrandSvg(sname)}</span>
                    ${sname}
                  </span>
                `).join('')}
              </div>
            </div>

            <div class="flex items-center justify-between pt-2 border-t border-[#212936]">
              <span class="text-xs text-[#8B949E]">Recommended Profile: <strong class="font-mono text-white">${tk.recommendedProfile}</strong></span>
              <button onclick="enableToolkit('${tk.id}')" class="px-3 py-1.5 rounded-lg bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold hover:bg-[#20bdab] transition">
                Enable All (${tk.servers.length})
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // Render Discovery Tab (External MCP.so)
    function renderDiscoveryGrid() {
      const grid = document.getElementById('discovery-grid');
      if (!grid) return;

      const curated = [
        { name: 'firecrawl', title: 'Firecrawl LLM Scraper', desc: 'Converts entire web pages into pristine LLM markdown.', tags: ['Scraping', 'Web'] },
        { name: 'notion', title: 'Notion Database Sync', desc: 'Sync knowledge base, engineering docs, and agile boards.', tags: ['Workspace', 'Docs'] },
        { name: 'github', title: 'GitHub CI & PR Agent', desc: 'Automate repo reviews, file commits, and workflow runs.', tags: ['DevOps', 'Code'] },
        { name: 'sentry', title: 'Sentry Error Telemetry', desc: 'Catch production crashes and analyze full stack traces.', tags: ['Observability'] },
        { name: 'linear', title: 'Linear Issue Engine', desc: 'Create engineering tickets, sync cycles, and manage roadmaps.', tags: ['Project Management'] },
        { name: 'brave', title: 'Brave Search Engine', desc: 'Independent web search grounding without tracking.', tags: ['Search', 'AI'] },
      ];

      grid.innerHTML = curated.map(item => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-lg bg-[#151B26] border border-[#212936] flex items-center justify-center p-1.5">
              ${getBrandSvg(item.name)}
            </div>
            <div>
              <div class="text-sm font-bold text-white">${item.title}</div>
              <div class="text-xs text-[#8B949E]">${item.tags.join(' • ')}</div>
            </div>
          </div>
          <p class="text-xs text-[#8B949E]">${item.desc}</p>
          <div class="pt-2 border-t border-[#212936] flex items-center justify-between">
            <span class="text-[11px] font-mono text-emerald-400">Verified MCP</span>
            <button onclick="openConnectModal('${item.name}')" class="px-3 py-1 bg-[#2DD4BF] text-[#0B0D10] text-xs font-bold rounded hover:bg-[#20bdab] transition">
              Install
            </button>
          </div>
        </div>
      `).join('');
    }

    // Modal Operations
    function openConnectModal(appName) {
      const app = state.servers.find(s => s.name === appName) || { name: appName, displayName: appName, authType: 'api_key' };
      state.currentConnectingApp = app;

      document.getElementById('modal-app-name').innerText = `Connect ${app.displayName || app.name}`;
      document.getElementById('modal-app-category').innerText = `Category: ${app.category || 'Integration'}`;
      document.getElementById('modal-app-icon').innerHTML = getBrandSvg(app.name);

      const body = document.getElementById('modal-connect-body');
      if (app.authType === 'oauth') {
        body.innerHTML = `
          <div class="p-3.5 bg-[#151B26] border border-[#212936] rounded-xl space-y-2">
            <div class="text-xs font-semibold text-white">1-Click OAuth Authorization</div>
            <p class="text-xs text-[#8B949E]">Authenticate securely with your ${app.displayName || app.name} account to grant Kater Dev Tools access.</p>
          </div>
          <div>
            <label class="block text-xs font-semibold text-[#8B949E] mb-1">Client ID (Optional Override)</label>
            <input type="text" id="connect-client-id" placeholder="default-kater-oauth-client" class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-xs text-white focus:outline-none">
          </div>
        `;
      } else if (app.authType === 'none') {
        body.innerHTML = `
          <div class="p-3.5 bg-[#151B26] border border-[#212936] rounded-xl">
            <div class="text-xs font-semibold text-white">Zero Credentials Required</div>
            <p class="text-xs text-[#8B949E] mt-1">This MCP server operates locally and is ready for immediate proxy activation.</p>
          </div>
        `;
      } else {
        const requiredVars = app.env_required || ['API_KEY'];
        body.innerHTML = `
          <div class="space-y-3">
            <p class="text-xs text-[#8B949E]">Enter credentials to configure this MCP backend in <code class="font-mono text-emerald-400">.kater/.env</code>.</p>
            ${requiredVars.map(v => `
              <div>
                <label class="block text-xs font-semibold text-white mb-1 font-mono">${v}</label>
                <input type="password" id="env-field-${v}" placeholder="sk-..." class="w-full bg-[#151B26] border border-[#212936] rounded-lg p-2 text-xs text-white font-mono focus:outline-none focus:border-[#2DD4BF]">
              </div>
            `).join('')}
          </div>
        `;
      }

      document.getElementById('modal-connect-app').classList.remove('hidden');
    }

    function closeConnectModal() {
      document.getElementById('modal-connect-app').classList.add('hidden');
    }

    async function submitAppConnection() {
      if (!state.currentConnectingApp) return;
      const app = state.currentConnectingApp;

      try {
        // Toggle or enable
        await fetch(`/api/mcp/servers/${app.name}/enable`, { method: 'POST' });
        app.enabled = true;
        app.activeCount = 1;
        closeConnectModal();
        renderAppsGrid();
        updateStats();
        addTelemetryLine(`Connected and enabled MCP server [${app.name}]`);
      } catch (err) {
        alert('Failed connecting app: ' + err.message);
      }
    }

    // Custom MCP Modal
    function openCustomMcpModal() {
      document.getElementById('modal-custom-mcp').classList.remove('hidden');
    }

    function closeCustomMcpModal() {
      document.getElementById('modal-custom-mcp').classList.add('hidden');
    }

    async function submitCustomMcp() {
      const name = document.getElementById('custom-server-name').value.trim();
      const transport = document.getElementById('custom-server-transport').value;
      const command = document.getElementById('custom-server-command').value.trim();
      const category = document.getElementById('custom-server-category').value;

      if (!name) return alert('Server name is required');

      try {
        const res = await fetch('/api/mcp/servers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            transport,
            category,
            command: transport === 'stdio' ? command : undefined,
            url: transport === 'http' ? command : undefined,
            risk: 'medium'
          })
        });
        if (!res.ok) {
          const err = await res.json();
          return alert(err.error || 'Failed adding custom server');
        }
        closeCustomMcpModal();
        await loadData();
        addTelemetryLine(`Registered custom MCP server: ${name}`);
      } catch (err) {
        alert('Error: ' + err.message);
      }
    }

    // Request App Modal
    function openRequestAppModal() {
      document.getElementById('modal-request-app').classList.remove('hidden');
    }

    function closeRequestAppModal() {
      document.getElementById('modal-request-app').classList.add('hidden');
    }

    function submitRequestApp() {
      const name = document.getElementById('request-app-name').value.trim();
      if (!name) return alert('Please enter an app name');
      closeRequestAppModal();
      alert(`Thank you! Request for "${name}" submitted to the Kater roadmap.`);
      addTelemetryLine(`App request submitted: ${name}`);
    }

    // Playground & Toolkit actions
    function renderPlaygroundOptions() {
      const select = document.getElementById('playground-action-select');
      if (!select) return;

      const actions = [];
      state.servers.forEach(s => {
        if (s.actions) {
          s.actions.forEach(a => actions.push({ app: s.displayName || s.name, action: a }));
        }
      });

      select.innerHTML = actions.map(item => `
        <option value="${item.action.id}">[${item.app}] ${item.action.label || item.action.name}</option>
      `).join('');

      if (actions.length > 0) {
        onPlaygroundActionChange(actions[0].action.id);
      }
    }

    function onPlaygroundActionChange(actionId) {
      let found = null;
      for (const s of state.servers) {
        const a = s.actions?.find(x => x.id === actionId);
        if (a) { found = a; break; }
      }
      if (found) {
        document.getElementById('playground-action-desc').innerHTML = `
          <strong>${found.label || found.name}</strong>: ${found.description}<br>
          <span class="text-emerald-400 font-mono text-[10px]">Risk: ${found.risk}</span>
        `;
        document.getElementById('playground-payload-input').value = JSON.stringify(found.exampleInput || {}, null, 2);
      }
    }

    async function runPlaygroundAction() {
      const out = document.getElementById('playground-output-result');
      const actionId = document.getElementById('playground-action-select').value;
      const rawPayload = document.getElementById('playground-payload-input').value;

      out.innerText = 'Executing action via Kater Gateway...';
      try {
        const payload = JSON.parse(rawPayload || '{}');
        const res = await fetch('/api/actions/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actionId, params: payload })
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
        addTelemetryLine(`Action run [${actionId}] => ${data.status || 'OK'}`);
      } catch (err) {
        out.innerText = 'Execution error: ' + err.message;
      }
    }

    async function enableToolkit(id) {
      try {
        await fetch(`/api/integrations/toolkits/${id}/enable`, { method: 'POST' });
        await loadData();
        addTelemetryLine(`Enabled toolkit [${id}]`);
      } catch (err) {
        alert('Failed enabling toolkit: ' + err.message);
      }
    }

    // Other Tabs Renderers
    function renderBrowserSessions() {
      const grid = document.getElementById('browser-sessions-grid');
      if (!grid) return;
      grid.innerHTML = state.browserSessions.map(b => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white font-mono">${b.session_id}</span>
            <span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase font-bold">${b.state}</span>
          </div>
          <div class="text-xs font-semibold text-white">${b.label || b.title}</div>
          <div class="text-xs text-[#8B949E] font-mono truncate">${b.current_url}</div>
        </div>
      `).join('');
    }

    function renderPrs() {
      const container = document.getElementById('pr-list-container');
      if (!container) return;
      container.innerHTML = state.prs.map(p => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] flex items-center justify-between">
          <div>
            <div class="text-xs font-bold text-white">#${p.number} — ${p.title}</div>
            <div class="text-[11px] text-[#8B949E]">Author: ${p.author} • Branch: ${p.branch}</div>
          </div>
          <span class="px-2 py-1 rounded text-xs font-bold ${p.status === 'clean' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}">${p.status}</span>
        </div>
      `).join('');
    }

    function renderAutomations() {
      const container = document.getElementById('automations-list-container');
      if (!container) return;
      container.innerHTML = state.automations.map(a => `
        <div class="p-4 rounded-xl bg-[#10141C] border border-[#212936] flex items-center justify-between">
          <div>
            <div class="text-xs font-bold text-white">${a.name}</div>
            <div class="text-[11px] text-[#8B949E] font-mono">Schedule: ${a.schedule} • Target: ${a.target}</div>
          </div>
          <span class="px-2 py-1 rounded text-xs font-mono bg-[#151B26] text-white border border-[#212936]">${a.status}</span>
        </div>
      `).join('');
    }

    function addTelemetryLine(msg) {
      const box = document.getElementById('telemetry-log-box');
      if (!box) return;
      const time = new Date().toLocaleTimeString();
      const div = document.createElement('div');
      div.className = 'flex items-center gap-2';
      div.innerHTML = `<span class="text-[#8B949E]">[${time}]</span> <span class="text-emerald-400">›</span> <span>${msg}</span>`;
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
    }

    function clearTelemetryLog() {
      const box = document.getElementById('telemetry-log-box');
      if (box) box.innerHTML = '';
    }

    function selectAppForDetails(name) {
      setTab('hub');
    }

    // Switch Profile
    async function switchProfile(profile) {
      try {
        await fetch('/api/profiles/active', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile })
        });
        addTelemetryLine(`Switched active profile to [${profile}]`);
      } catch (e) {
        console.error(e);
      }
    }

    // Setup Live WebSocket
    function setupWs() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${location.host}/ws`;
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => addTelemetryLine('WebSocket connected to Kater Gateway telemetry stream.');
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          addTelemetryLine(`Event [${data.type}]: ${JSON.stringify(data.detail || data.name || data)}`);
        } catch {}
      };
      ws.onclose = () => setTimeout(setupWs, 3000);
    }

    window.addEventListener('DOMContentLoaded', () => {
      loadData();
      setupWs();
    });
  </script>
</body>
</html>
"""

# Write to src/dashboardHtml.ts
with open('src/dashboardHtml.ts', 'w', encoding='utf-8') as f_ts:
    f_ts.write(f'''// Generated by scripts/build_full_dashboard.py — Composio-grade Kater Dev Tools Integration Hub
const RAW_HTML = {json.dumps(HTML_TEMPLATE)};

export function getDashboardHtml(port: number): string {{
  return RAW_HTML.split('__PORT__').join(String(port));
}}
''')

print("Successfully generated src/dashboardHtml.ts")
''')
