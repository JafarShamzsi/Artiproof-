// @vitest-environment node
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const app = path.resolve("src/app");
const layout = readFileSync(path.join(app, "layout.tsx"), "utf8");
const require = createRequire(import.meta.url);
// Use the real font parser already shipped with the installed Next local loader.
const parser = require("next/dist/compiled/@next/font/dist/fontkit").default;
const parseFont = parser.default || parser;
const faces = [
  ["inter", "Inter.ttf", "Inter", "normal", "100 900", "--font-sans"],
  ["fraunces", "Fraunces.ttf", "Fraunces", "normal", "400 800", "--font-display"],
  ["fraunces", "Fraunces-Italic.ttf", "Fraunces", "italic", "400 800", "--font-display"],
  ["newsreader", "Newsreader-Italic.ttf", "Newsreader", "italic", "400 500", "--font-editorial"],
  ["jetbrains", "JetBrainsMono.ttf", "JetBrains Mono", "normal", "400 500", "--font-mono"],
] as const;

describe("BUILD-02 production font contract", () => {
  it("uses only the supported local loader, never Google CSS or remote font sources", () => {
    expect(layout).not.toMatch(/next\/font\/google|fonts\.(googleapis|gstatic)\.com/);
    expect(layout).toContain('import localFont from "next/font/local"');
    const sourceFiles = (dir: string): string[] => readdirSync(dir, { withFileTypes: true })
      .flatMap((entry) => entry.isDirectory() ? sourceFiles(path.join(dir, entry.name))
        : /\.(tsx?|css)$/.test(entry.name) ? [path.join(dir, entry.name)] : []);
    for (const file of sourceFiles(path.resolve("src"))) {
      if (file === path.resolve("src/app/font-build.contract.test.ts")) continue;
      const code = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
      expect(code, file).not.toMatch(/next\/font\/google|https?:\/\/fonts\.(googleapis|gstatic)\.com/);
    }
  });

  it.each(faces)("preserves %s / %s real family, style, range and CSS variable", (binding, file, family, style, weight, variable) => {
    const source = ts.createSourceFile("layout.tsx", layout, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    let options: Record<string, unknown> | undefined;
    function visit(node: ts.Node) {
      if (ts.isVariableDeclaration(node) && node.name.getText(source) === binding && node.initializer) {
        expect(ts.isCallExpression(node.initializer)).toBe(true);
        const call = node.initializer as ts.CallExpression;
        expect(call.expression.getText(source)).toBe("localFont");
        // Parse literal loader options, not a mocked next/font execution.
        const literal = (value: ts.Node): unknown => {
          if (ts.isStringLiteral(value)) return value.text;
          if (ts.isArrayLiteralExpression(value)) return value.elements.map(literal);
          if (ts.isObjectLiteralExpression(value)) return Object.fromEntries(value.properties.map((prop) => {
            if (!ts.isPropertyAssignment(prop)) throw new Error("Expected literal font options");
            return [prop.name.getText(source), literal(prop.initializer)];
          }));
          throw new Error("Expected literal font options");
        };
        options = literal(call.arguments[0]) as Record<string, unknown>;
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
    expect(options?.variable).toBe(variable);
    expect(options?.display).toBe("swap");
    expect(options?.src).toEqual(expect.arrayContaining([{ path: `./fonts/${file}`, weight, style }]));
    const buffer = readFileSync(path.join(app, "fonts", file));
    const font = parseFont(buffer);
    expect(font.name.records.preferredFamily?.en || font.familyName).toBe(family);
    expect(Boolean(font.italicAngle)).toBe(style === "italic");
    const [min, max] = weight.split(" ").map(Number);
    expect(font.variationAxes.wght.min).toBeLessThanOrEqual(min);
    expect(font.variationAxes.wght.max).toBeGreaterThanOrEqual(max);
    for (const char of "Research Əə İı Şş Ğğ Çç Öö Üü 0123456789") {
      expect(font.hasGlyphForCodePoint(char.codePointAt(0)), `${family}: ${char}`).toBe(true);
    }
    const provenance = readFileSync(path.join(app, "fonts/README.md"), "utf8");
    expect(provenance).toContain(createHash("sha256").update(buffer).digest("hex"));
    expect(layout).toContain(`${binding}.variable`);
  });

  // Explicit opt-in: this performs a real production build, not a unit mock.
  // Run separately from other builds; they all own the same .next directory.
  it.skipIf(process.env.BUILD02_NETWORK_BUILD !== "1")("builds webpack with Node network permission denied", () => {
    const env = {
      ...process.env,
      NEXT_TELEMETRY_DISABLED: "1",
      NODE_OPTIONS: "--permission --allow-fs-read=* --allow-fs-write=* --allow-child-process --allow-worker --allow-addons",
    };
    // OS socket/DNS operations are denied by Node's real permission system.
    // No response fixtures, DNS substitution, proxy, or machine-wide changes.
    const probe = spawnSync(process.execPath, ["-e", `
      Promise.all(['https://fonts.googleapis.com/css2?family=Inter',
        'https://fonts.gstatic.com/'].map(async url => {
        try { await fetch(url); process.exitCode = 1; }
        catch (error) {
          if (error.cause?.code !== 'ERR_ACCESS_DENIED') throw error;
          console.log('ERR_ACCESS_DENIED ' + url);
        }
      })).catch(error => { console.error(error); process.exitCode = 1; });
    `], { env, encoding: "utf8", timeout: 30_000 });
    console.log(probe.stdout, probe.stderr);
    expect(probe.status).toBe(0);
    expect(probe.stdout).toContain("ERR_ACCESS_DENIED https://fonts.googleapis.com");
    expect(probe.stdout).toContain("ERR_ACCESS_DENIED https://fonts.gstatic.com");
    const build = spawnSync(process.execPath, ["node_modules/next/dist/bin/next", "build", "--webpack"], {
      env, encoding: "utf8", timeout: 240_000, maxBuffer: 16 * 1024 * 1024,
    });
    console.log(build.stdout, build.stderr);
    expect(build.error).toBeUndefined();
    expect(build.status).toBe(0);
    expect(build.stdout).toContain("Generating static pages");
    const media = path.resolve(".next/static/media");
    const emittedHashes = readdirSync(media).filter((file) => file.endsWith(".ttf"))
      .map((file) => createHash("sha256").update(readFileSync(path.join(media, file))).digest("hex"));
    for (const [, file] of faces) {
      expect(emittedHashes).toContain(createHash("sha256")
        .update(readFileSync(path.join(app, "fonts", file))).digest("hex"));
    }
    const cssDir = path.resolve(".next/static/css");
    const css = readdirSync(cssDir).filter((file) => file.endsWith(".css"))
      .map((file) => readFileSync(path.join(cssDir, file), "utf8")).join("\n");
    expect(css).not.toMatch(/https?:\/\/fonts\.(googleapis|gstatic)\.com/);
    for (const [binding, , , style, weight] of faces) {
      const face = [...css.matchAll(/@font-face\{([^}]+)\}/g)]
        .map((match) => match[1]).find((rule) => rule.includes(`font-family:${binding};`)
          && rule.includes(`font-style:${style}`));
      expect(face).toContain(`font-weight:${weight}`);
      expect(face).toContain("font-display:swap");
      expect(face).toContain("/_next/static/media/");
    }
  }, 280_000);
});
