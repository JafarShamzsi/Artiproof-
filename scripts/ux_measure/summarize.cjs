const fs = require('node:fs');
const report = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const median = values => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
for (const profile of ['native', 'slow4g-cpu4']) {
  for (const width of [375, 1440]) {
    const runs = report.runs.filter(r => r.profile === profile && r.width === width);
    if (!runs.length) continue;
    const lcp = runs.map(r => r.metrics.observedLcpMs);
    const cls = runs.map(r => r.metrics.observedCls);
    const fonts = runs.map(r => r.metrics.resources.filter(e => /\.ttf(?:\?|$)/.test(e.name)));
    const sum = (items, key) => items.reduce((n, e) => n + (e[key] ?? 0), 0);
    console.log(JSON.stringify({ profile, width, runs: runs.length, lcp, cls,
      lcpMedian: lcp.includes(null) ? null : median(lcp), clsMedian: cls.includes(null) ? null : median(cls),
      fontCounts: fonts.map(f => f.length), fontEncodedBodyBytes: fonts.map(f => sum(f, 'encodedBodySize')),
      fontDecodedBodyBytes: fonts.map(f => sum(f, 'decodedBodySize')),
      fontResourceTimingTransferBytes: fonts.map(f => sum(f, 'transferSize')),
      fontCdpEncodedTransferBytes: runs.map(r => sum(r.transfers.filter(t => t.type === 'Font'), 'cdpEncodedTransferBytes')),
      pageErrors: runs.map(r => r.errors), consoleErrors: runs.map(r => r.consoleErrors ?? null),
      failedRequests: runs.map(r => r.failedRequests ?? null), blocked: runs.map(r => r.blocked),
      fontPreloadCounts: runs.map(r => r.metrics.fontPreloads.length), linkHeaders: runs.map(r => r.linkHeader),
    }));
  }
}
console.log(JSON.stringify({ rawFontProbes: report.rawFontProbes.map(f => ({ url: f.url,
  status: f.status, encoding: f.headers['content-encoding'], bytes: f.rawCompressedBodyBytes })) }));
