// @vitest-environment node
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
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

describe("Local font contract", () => {
  it("uses only the supported local loader, never Google CSS or remote font sources", () => {
    expect(layout).not.toMatch(/next\/font\/google|fonts\.(googleapis|gstatic)\.com/);
    expect(layout).toContain('import localFont from "next/font/local"');
    const sourceFiles = (dir: string): string[] => readdirSync(dir, { withFileTypes: true })
      .flatMap((entry) => entry.isDirectory() ? sourceFiles(path.join(dir, entry.name))
        : /\.(tsx?|css)$/.test(entry.name) ? [path.join(dir, entry.name)] : []);
    for (const file of sourceFiles(path.resolve("src"))) {
      if (file === path.resolve("src/app/font-build.contract.test.ts")) continue;
      expect(readFileSync(file, "utf8"), file).not.toMatch(/next\/font\/google|https?:\/\/fonts\.(googleapis|gstatic)\.com/);
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
    expect(font.familyName).toBe(family);
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
});
