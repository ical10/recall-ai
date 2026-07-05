import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  buildIconSvg,
  buildOgSvg,
  siteMeta,
} from "../scripts/brand-assets.mjs";

const simpleDescription =
  "A pocket-sized vocabulary trainer that learns how you forget, then feeds you the right word at exactly the right moment.";

describe("brand assets", () => {
  it("generates the branded svg assets", () => {
    const icon = buildIconSvg();
    const og = buildOgSvg();

    expect(icon).toContain("<svg");
    expect(icon).toContain('stroke="#1A1A2E"');
    expect(og).toContain("Words that stick.");
    expect(og).toContain("ephemeral");
    expect(og).toContain("recallai.app");
  });

  it("matches index metadata and manifest", () => {
    const currentDir = path.dirname(fileURLToPath(import.meta.url));
    const indexHtml = readFileSync(path.resolve(currentDir, "../index.html"), "utf8");
    const manifest = JSON.parse(
      readFileSync(path.resolve(currentDir, "../public/site.webmanifest"), "utf8"),
    );

    expect(indexHtml).toContain(`<title>${siteMeta.title}</title>`);
    expect(indexHtml).toContain(`content="${simpleDescription}"`);
    expect(indexHtml).toContain('content="/og.png"');
    expect(indexHtml).toContain('href="/icon.png"');
    expect(indexHtml).toContain('href="/site.webmanifest"');

    expect(manifest.name).toBe(siteMeta.name);
    expect(manifest.theme_color).toBe(siteMeta.themeColor);
    expect(manifest.icons[0]?.src).toBe("/icon.png");
  });
});
