import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const siteMeta = {
  name: "RecallAI",
  shortName: "RecallAI",
  title: "RecallAI | Spaced Repetition Vocabulary for ESL Learners",
  description:
    "A spaced-repetition vocabulary trainer that generates fresh, kid-safe English practice and brings each word back right before you forget it.",
  url: "https://recallai.app",
  themeColor: "#FFF8E7",
  backgroundColor: "#FFFDF7",
  ogImagePath: "/og.svg",
  iconPath: "/icon.svg",
};

const palette = {
  cream50: "#FFFDF7",
  cream100: "#FFF8E7",
  ink: "#1A1A2E",
  inkSoft: "#2D2D44",
  tangerine: "#FF6B35",
  teal: "#06A77D",
  sky: "#3A86FF",
  honey: "#FFB627",
  tealLight: "#D2F4E8",
  skyLight: "#D7E6FF",
  tangerineLight: "#FFE4D6",
};

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function buildIconSvg() {
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="512" height="512" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="512" height="512" rx="120" fill="${palette.cream100}"/>
  <circle cx="118" cy="108" r="72" fill="${palette.tangerineLight}"/>
  <circle cx="408" cy="396" r="86" fill="${palette.skyLight}"/>
  <rect x="82" y="92" width="348" height="328" rx="48" fill="${palette.cream50}" stroke="${palette.ink}" stroke-width="20"/>
  <rect x="118" y="126" width="130" height="28" rx="14" fill="${palette.teal}"/>
  <path d="M150 346V178H212C243.333 178 268.333 184.833 287 198.5C305.667 212.167 315 231 315 255C315 280.333 305.333 300.333 286 315C266.667 329.667 241.667 337 211 337H191V346H150ZM191 301H210C225.333 301 237.167 297.167 245.5 289.5C253.833 281.833 258 270.667 258 256C258 242 253.833 231.167 245.5 223.5C237.167 215.833 225.333 212 210 212H191V301Z" fill="${palette.ink}"/>
  <path d="M328 152L374 118" stroke="${palette.honey}" stroke-width="22" stroke-linecap="round"/>
  <path d="M332 206L394 206" stroke="${palette.tangerine}" stroke-width="22" stroke-linecap="round"/>
  <path d="M328 260L378 294" stroke="${palette.sky}" stroke-width="22" stroke-linecap="round"/>
</svg>
`;
}

export function buildOgSvg() {
  const title = escapeHtml("Words that stick.");
  const subtitle = escapeHtml("Memory that grows.");
  const body = escapeHtml(
    "Fresh, kid-safe vocabulary every night. SM-2 brings each word back right before it fades.",
  );

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1200" height="630" viewBox="0 0 1200 630" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect width="1200" height="630" fill="${palette.cream100}"/>
  <circle cx="156" cy="126" r="118" fill="${palette.tangerineLight}"/>
  <circle cx="1050" cy="520" r="152" fill="${palette.skyLight}"/>
  <circle cx="1044" cy="118" r="72" fill="${palette.tealLight}"/>
  <g opacity="0.14" fill="${palette.ink}">
    <circle cx="78" cy="78" r="2"/>
    <circle cx="118" cy="78" r="2"/>
    <circle cx="158" cy="78" r="2"/>
    <circle cx="198" cy="78" r="2"/>
    <circle cx="238" cy="78" r="2"/>
    <circle cx="78" cy="118" r="2"/>
    <circle cx="118" cy="118" r="2"/>
    <circle cx="158" cy="118" r="2"/>
    <circle cx="198" cy="118" r="2"/>
    <circle cx="238" cy="118" r="2"/>
    <circle cx="78" cy="158" r="2"/>
    <circle cx="118" cy="158" r="2"/>
    <circle cx="158" cy="158" r="2"/>
    <circle cx="198" cy="158" r="2"/>
    <circle cx="238" cy="158" r="2"/>
  </g>
  <rect x="72" y="78" width="620" height="430" rx="42" fill="${palette.cream50}" stroke="${palette.ink}" stroke-width="8"/>
  <rect x="118" y="112" width="202" height="46" rx="23" fill="${palette.teal}"/>
  <text x="118" y="248" fill="${palette.ink}" font-size="88" font-weight="900" font-family="Fraunces, Georgia, serif">${title}</text>
  <rect x="116" y="266" width="338" height="22" rx="11" fill="${palette.honey}" opacity="0.55"/>
  <text x="118" y="338" fill="${palette.ink}" font-size="76" font-weight="900" font-family="Fraunces, Georgia, serif">${subtitle}</text>
  <text x="118" y="416" fill="${palette.inkSoft}" font-size="34" font-weight="500" font-family="'DM Sans', Arial, sans-serif">
    <tspan x="118" dy="0">${body}</tspan>
  </text>
  <g transform="translate(772 118) rotate(-3)">
    <rect width="310" height="352" rx="34" fill="${palette.cream50}" stroke="${palette.ink}" stroke-width="8"/>
    <rect x="34" y="38" width="116" height="24" rx="12" fill="${palette.tangerine}"/>
    <text x="34" y="126" fill="${palette.inkSoft}" font-size="22" font-weight="600" font-family="'JetBrains Mono', monospace">English · Adv.</text>
    <text x="34" y="196" fill="${palette.ink}" font-size="64" font-weight="900" font-family="Fraunces, Georgia, serif">ephemeral</text>
    <text x="34" y="244" fill="${palette.inkSoft}" font-size="28" font-weight="500" font-family="'DM Sans', Arial, sans-serif">Lasting for a very short time.</text>
    <rect x="34" y="274" width="252" height="22" rx="11" fill="${palette.honey}" opacity="0.55"/>
    <text x="34" y="292" fill="${palette.inkSoft}" font-size="24" font-style="italic" font-family="'DM Sans', Arial, sans-serif">"The cherry blossoms are gone in a week."</text>
    <rect x="34" y="314" width="56" height="16" rx="8" fill="${palette.tangerine}"/>
    <rect x="102" y="314" width="56" height="16" rx="8" fill="${palette.honey}"/>
    <rect x="170" y="314" width="56" height="16" rx="8" fill="${palette.teal}"/>
    <rect x="238" y="314" width="38" height="16" rx="8" fill="${palette.sky}"/>
  </g>
  <rect x="712" y="420" width="196" height="110" rx="26" fill="${palette.cream50}" stroke="${palette.ink}" stroke-width="8"/>
  <rect x="748" y="402" width="94" height="30" rx="6" fill="${palette.teal}" opacity="0.92"/>
  <text x="744" y="478" fill="${palette.inkSoft}" font-size="22" font-weight="700" font-family="'JetBrains Mono', monospace">Streak</text>
  <text x="742" y="520" fill="${palette.ink}" font-size="58" font-weight="900" font-family="Fraunces, Georgia, serif">12· days</text>
  <text x="72" y="570" fill="${palette.inkSoft}" font-size="26" font-weight="600" font-family="'DM Sans', Arial, sans-serif">recallai.app</text>
</svg>
`;
}

export function buildManifest() {
  return JSON.stringify(
    {
      name: siteMeta.name,
      short_name: siteMeta.shortName,
      description: siteMeta.description,
      start_url: "/",
      display: "standalone",
      background_color: siteMeta.backgroundColor,
      theme_color: siteMeta.themeColor,
      icons: [
        {
          src: siteMeta.iconPath,
          sizes: "any",
          type: "image/svg+xml",
        },
      ],
    },
    null,
    2,
  );
}

function updateIndexHtml(indexHtmlPath) {
  const head = `    <title>${siteMeta.title}</title>
    <meta name="description" content="${siteMeta.description}" />
    <meta name="theme-color" content="${siteMeta.themeColor}" />
    <meta name="application-name" content="${siteMeta.name}" />
    <meta name="apple-mobile-web-app-title" content="${siteMeta.name}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="${siteMeta.name}" />
    <meta property="og:title" content="${siteMeta.title}" />
    <meta property="og:description" content="${siteMeta.description}" />
    <meta property="og:url" content="${siteMeta.url}" />
    <meta property="og:image" content="${siteMeta.url}${siteMeta.ogImagePath}" />
    <meta property="og:image:type" content="image/svg+xml" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${siteMeta.title}" />
    <meta name="twitter:description" content="${siteMeta.description}" />
    <meta name="twitter:image" content="${siteMeta.url}${siteMeta.ogImagePath}" />
    <link rel="canonical" href="${siteMeta.url}/" />
    <link rel="icon" href="${siteMeta.iconPath}" type="image/svg+xml" />
    <link rel="manifest" href="/site.webmanifest" />`;

  const source = readFileSync(indexHtmlPath, "utf8");
  const updated = source.replace(/    <title>[\s\S]*?    <link rel="preconnect"/, `${head}\n\n    <link rel="preconnect"`);

  if (updated === source) {
    throw new Error("Could not update apps/web/index.html head block");
  }

  writeFileSync(indexHtmlPath, updated);
}

export function generateBrandAssets() {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const webDir = path.resolve(currentDir, "..");
  const publicDir = path.join(webDir, "public");

  mkdirSync(publicDir, { recursive: true });
  writeFileSync(path.join(publicDir, "icon.svg"), buildIconSvg());
  writeFileSync(path.join(publicDir, "og.svg"), buildOgSvg());
  writeFileSync(path.join(publicDir, "site.webmanifest"), buildManifest());
  updateIndexHtml(path.join(webDir, "index.html"));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  generateBrandAssets();
}
