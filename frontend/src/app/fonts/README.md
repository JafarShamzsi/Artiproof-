# Checked-in production fonts

Source: the official [Google Fonts repository](https://github.com/google/fonts),
pinned commit `86aced91de05cd4f96a06838124cca45be337b2b` (retrieved 2026-11-06).
Each binary is an **unmodified** upstream variable TrueType file; only its local
filename is simplified. No font compilation, subsetting, conversion or private
metadata was added. Downloads are assets, not executable installation scripts.

## Exact asset URLs and SHA-256

Prefix every relative source below with:
`https://raw.githubusercontent.com/google/fonts/86aced91de05cd4f96a06838124cca45be337b2b/`
(URL-encode square brackets and commas when downloading).

| Local file | Relative upstream source | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Inter.ttf | `ofl/inter/Inter[opsz,wght].ttf` | 876576 | `29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031` |
| Fraunces.ttf | `ofl/fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf` | 360440 | `177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb` |
| Fraunces-Italic.ttf | `ofl/fraunces/Fraunces-Italic[SOFT,WONK,opsz,wght].ttf` | 414904 | `b24448c43702fac4ee856781d461a0dfba8d8e594b6e8e190234b75fed2c0e01` |
| Newsreader-Italic.ttf | `ofl/newsreader/Newsreader-Italic[opsz,wght].ttf` | 495684 | `796668611f80b64d5adf182fde3b6f29ed83b4e7cbec7b96937e84ac01364792` |
| JetBrainsMono.ttf | `ofl/jetbrainsmono/JetBrainsMono[wght].ttf` | 187208 | `48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda` |

Checksums computed with PowerShell `Get-FileHash -Algorithm SHA256` and checked
by the font contract against the actual binary bytes.

## Licensing

All four families are SIL Open Font License 1.1. Complete, unmodified copyright
and license texts accompany the binaries:

| Family | Copyright | Local license | Upstream license (same prefix) |
| --- | --- | --- | --- |
| Inter | 2020 The Inter Project Authors | inter-OFL.txt | `ofl/inter/OFL.txt` |
| Fraunces | 2018 The Fraunces Project Authors | fraunces-OFL.txt | `ofl/fraunces/OFL.txt` |
| Newsreader | 2020 The Newsreader Project Authors | newsreader-OFL.txt | `ofl/newsreader/OFL.txt` |
| JetBrains Mono | 2020 The JetBrains Mono Project Authors | jetbrainsmono-OFL.txt | `ofl/jetbrainsmono/OFL.txt` |

OFL permits bundling/redistribution with software when copyright and license
notices are retained; fonts may not be sold by themselves. No font modification
or family renaming is performed. These notices must travel with redistributed
source/assets. The application itself is not relicensed by the OFL.

## Coverage, ranges and footprint

Full upstream character coverage is retained, not a Latin-only subset. The old
`subsets: ["latin"]` selected **preloads**, not exclusive downloaded coverage.
Keeping full files avoids silently losing Azerbaijani Latin extensions or other
upstream characters. Tests check actual glyph coverage including Əə İı Şş Ğğ.

Five variable faces total **2,334,812 bytes** (~2.23 MiB) before HTTP compression.
This is larger than Latin-only WOFF2, deliberately traded for pinned, unmodified
assets with broad coverage and only five files (no per-weight duplicates).
Inter exposes 100–900 normal; Fraunces exposes 400–800 normal/italic;
Newsreader exposes 400–500 italic; JetBrains Mono exposes 400–500 normal.
Source variable axes may span wider ranges; CSS limits use to the intended
ranges. No unrelated styles or families are loaded.

`next/font/local` defaults to `preload: true`; the layout does not override
that option. This is configuration, **not evidence of delivered font preloads**.
On the manager-integrated head `4b8226131295b549e37553a6aa871e4bab2eed45`,
local webpack production verification at 1440px and 375px found an empty
`app`/`pages` next-font manifest, no HTTP response `Link` header, and zero
`as="font"` preload links in the raw HTML or live DOM. The one HTML preload was
a script, not a font. All five fonts nevertheless loaded from same-origin CSS
URLs. No preload-delivery or performance clearance is claimed.

Each fresh Firefox context received all five font responses, totalling
**2,334,812 decoded bytes**. Responses used gzip and chunked transfer; compressed
wire bytes were not measured. Mobile load performance and CLS were not measured.
The opt-in network-denied contract does not clear `.next`: a cold build requires
manual removal or moving aside of generated `.next` before running it. See
`docs/FONT-BUILD.md` for the bounded desktop/mobile evidence and limitations.

Optical-size axes remain in upstream files and browsers can apply automatic
optical sizing; Google-served instances may have frozen these axes. Same family
is not proof of pixel-identical historical output. See `docs/FONT-BUILD.md` for
verification and remaining visual limitations.
