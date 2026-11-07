"use client";

import { use, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Users,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Share2,
  Download,
  BookOpen,
  GitBranch,
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  ExternalLink,
} from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface Publication {
  id: string;
  title: string;
  journal: string | null;
  year: number | null;
  doi: string | null;
  citation_count: number;
  suspicious_citations: number;
  topic_match_score: number | null;
  is_self_cited_heavily: boolean;
  flags: string[] | null;
}

interface GraphNode {
  id: string;
  name: string;
  type: string;
  citation_count: number;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  papers: string[];
}

interface ProfileData {
  id: string;
  researcher_name: string;
  scopus_id: string | null;
  google_scholar_id: string | null;
  orcid: string | null;
  institution: string | null;
  official_h_index: number | null;
  official_citation_count: number | null;
  adjusted_h_index: number | null;
  adjusted_citation_count: number | null;
  integrity_score: number | null;
  self_citation_rate: number | null;
  citation_ring_flags: any;
  topic_relevance_score: number | null;
  analysis_status: string;
  last_analyzed_at: string | null;
  created_at: string;
  publications: Publication[];
}

function scoreColor(s: number) {
  if (s >= 70) return "text-emerald-400 border-emerald-500";
  if (s >= 40) return "text-amber-400 border-amber-500";
  return "text-red-400 border-red-500";
}

function scoreTextColor(s: number) {
  if (s >= 70) return "text-emerald-400";
  if (s >= 40) return "text-amber-400";
  return "text-red-400";
}

export default function ResearcherResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [data, setData] = useState<ProfileData | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${BACKEND_URL}/api/researcher/${id}`).then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      }),
      fetch(`${BACKEND_URL}/api/researcher/${id}/citation-graph`).then((r) =>
        r.ok ? r.json() : { nodes: [], edges: [] }
      ),
    ])
      .then(([profile, graph]) => {
        setData(profile);
        setGraphData(graph);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/researcher" className="flex items-center gap-1 text-sm text-zinc-400 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <p className="text-red-400">Researcher profile not found.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const integrity = data.integrity_score ?? 0;
  const ringFlags = data.citation_ring_flags || {};
  const flags = ringFlags.flags || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/researcher" className="text-zinc-400 hover:text-white">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-white">Researcher Analysis</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400">
            <Share2 className="mr-1.5 h-4 w-4" /> Share
          </Button>
          <Button size="sm" className="bg-emerald-500 text-white hover:bg-emerald-600">
            <Download className="mr-1.5 h-4 w-4" /> Report
          </Button>
        </div>
      </div>

      {/* Status */}
      {data.analysis_status !== "completed" && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            {data.analysis_status === "processing" ? (
              <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-amber-400" />
            )}
            <span className="text-sm text-zinc-300">Status: {data.analysis_status}</span>
          </CardContent>
        </Card>
      )}

      {/* Profile Card */}
      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardContent className="flex flex-col items-center gap-6 py-8 md:flex-row">
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-purple-500/20">
            <Users className="h-10 w-10 text-purple-400" />
          </div>
          <div className="flex-1 text-center md:text-left">
            <h2 className="text-xl font-semibold text-white">{data.researcher_name}</h2>
            {data.institution && <p className="text-sm text-zinc-400">{data.institution}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {data.orcid && <Badge className="bg-zinc-500/20 text-zinc-400">ORCID: {data.orcid}</Badge>}
              {data.publications.length > 0 && (
                <Badge className="bg-purple-500/20 text-purple-400">
                  {data.publications.length} publications
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metrics Comparison + Integrity */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Official Metrics */}
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="text-sm text-zinc-400">Official Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-zinc-400">h-index</span>
              <span className="text-xl font-bold text-white">{data.official_h_index ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Citations</span>
              <span className="text-xl font-bold text-white">
                {data.official_citation_count?.toLocaleString() ?? "—"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Adjusted Metrics */}
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-emerald-400">
              <TrendingUp className="h-4 w-4" /> Adjusted Metrics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">h-index</span>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-emerald-400">{data.adjusted_h_index ?? "—"}</span>
                {data.official_h_index != null && data.adjusted_h_index != null && data.adjusted_h_index < data.official_h_index && (
                  <TrendingDown className="h-4 w-4 text-amber-400" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Citations</span>
              <span className="text-xl font-bold text-emerald-400">
                {data.adjusted_citation_count?.toLocaleString() ?? "—"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Integrity Score */}
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="text-sm text-zinc-400">Integrity Score</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            <div className={`flex h-20 w-20 items-center justify-center rounded-full border-4 ${scoreColor(integrity)}`}>
              <span className="text-2xl font-bold">{Math.round(integrity)}</span>
            </div>
            <div className="mt-3 space-y-1 text-center">
              {data.self_citation_rate != null && (
                <p className="text-xs text-zinc-500">
                  Self-citation: {(data.self_citation_rate * 100).toFixed(1)}%
                </p>
              )}
              {data.topic_relevance_score != null && (
                <p className="text-xs text-zinc-500">
                  Topic relevance: {(data.topic_relevance_score * 100).toFixed(0)}%
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Flags */}
      {flags.length > 0 && (
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Integrity Flags ({flags.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {flags.map((flag: string, i: number) => (
              <div key={i} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                <p className="text-sm text-zinc-300">{flag}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Citation Network */}
      {graphData && graphData.nodes.length > 1 && (
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-400">
              <GitBranch className="h-4 w-4" /> Citation Network
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CitationGraph nodes={graphData.nodes} edges={graphData.edges} />
          </CardContent>
        </Card>
      )}

      {/* Publications Table */}
      {data.publications.length > 0 && (
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-400">
              <BookOpen className="h-4 w-4" /> Publications ({data.publications.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                    <th className="pb-2 pr-4">Title</th>
                    <th className="pb-2 pr-4">Journal</th>
                    <th className="pb-2 pr-4">Year</th>
                    <th className="pb-2 pr-4 text-right">Citations</th>
                    <th className="pb-2 pr-4 text-right">Topic Match</th>
                    <th className="pb-2">Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {data.publications.slice(0, 50).map((pub) => (
                    <tr key={pub.id} className="border-b border-zinc-800/50">
                      <td className="max-w-[300px] truncate py-2 pr-4 text-white">
                        {pub.doi ? (
                          <a
                            href={`https://doi.org/${pub.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-emerald-400 hover:underline"
                          >
                            {pub.title}
                          </a>
                        ) : (
                          pub.title
                        )}
                      </td>
                      <td className="max-w-[150px] truncate py-2 pr-4 text-zinc-400">{pub.journal || "—"}</td>
                      <td className="py-2 pr-4 text-zinc-400">{pub.year || "—"}</td>
                      <td className="py-2 pr-4 text-right text-zinc-300">{pub.citation_count}</td>
                      <td className="py-2 pr-4 text-right">
                        {pub.topic_match_score != null ? (
                          <span className={
                            pub.topic_match_score >= 0.7 ? "text-emerald-400"
                            : pub.topic_match_score >= 0.4 ? "text-amber-400"
                            : "text-red-400"
                          }>
                            {(pub.topic_match_score * 100).toFixed(0)}%
                          </span>
                        ) : "—"}
                      </td>
                      <td className="py-2">
                        {pub.flags && pub.flags.length > 0 && (
                          <AlertTriangle className="h-4 w-4 text-amber-400" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/**
 * SVG-based force-directed citation graph visualization.
 */
function CitationGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const W = 700, H = 400;

  // Simple circular layout — target in center, citers around
  const target = nodes.find((n) => n.type === "target");
  const citers = nodes.filter((n) => n.type !== "target");

  const positions: Record<string, { x: number; y: number }> = {};
  if (target) {
    positions[target.id] = { x: W / 2, y: H / 2 };
  }

  citers.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / citers.length;
    const radius = Math.min(W, H) * 0.35;
    positions[node.id] = {
      x: W / 2 + Math.cos(angle) * radius,
      y: H / 2 + Math.sin(angle) * radius,
    };
  });

  // Determine max weight for edge thickness scaling
  const maxWeight = Math.max(1, ...edges.map((e) => e.weight));

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ minHeight: 300, maxHeight: 450 }}
      >
        {/* Edges */}
        {edges.map((edge, i) => {
          const from = positions[edge.source];
          const to = positions[edge.target];
          if (!from || !to) return null;
          const isSuspicious = edge.weight >= 5;
          const thickness = 1 + (edge.weight / maxWeight) * 4;
          return (
            <line
              key={i}
              x1={from.x} y1={from.y}
              x2={to.x} y2={to.y}
              stroke={isSuspicious ? "#ef4444" : "#3f3f46"}
              strokeWidth={thickness}
              strokeOpacity={isSuspicious ? 0.8 : 0.4}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          const isTarget = node.type === "target";
          const radius = isTarget ? 18 : 8 + Math.min(8, node.citation_count / 2);
          const isSuspicious = edges.some(
            (e) => e.source === node.id && e.weight >= 5
          );

          return (
            <g key={node.id}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r={radius}
                fill={isTarget ? "#a855f7" : isSuspicious ? "#ef4444" : "#10b981"}
                fillOpacity={isTarget ? 1 : 0.7}
                stroke={isTarget ? "#c084fc" : isSuspicious ? "#f87171" : "#34d399"}
                strokeWidth={isTarget ? 3 : 1.5}
              />
              {/* Label */}
              <text
                x={pos.x}
                y={pos.y + radius + 14}
                textAnchor="middle"
                fill="#a1a1aa"
                fontSize={isTarget ? 11 : 9}
                fontWeight={isTarget ? 600 : 400}
              >
                {node.name.length > 18 ? node.name.slice(0, 16) + "..." : node.name}
              </text>
              {/* Citation count on hover area */}
              {!isTarget && (
                <title>
                  {node.name} — {node.citation_count} citation(s) to target
                </title>
              )}
            </g>
          );
        })}

        {/* Legend */}
        <g transform={`translate(16, ${H - 60})`}>
          <circle cx={0} cy={0} r={6} fill="#a855f7" />
          <text x={12} y={4} fill="#a1a1aa" fontSize={9}>Target Researcher</text>
          <circle cx={0} cy={18} r={5} fill="#10b981" />
          <text x={12} y={22} fill="#a1a1aa" fontSize={9}>Citing Author</text>
          <circle cx={0} cy={36} r={5} fill="#ef4444" />
          <text x={12} y={40} fill="#a1a1aa" fontSize={9}>Suspicious (5+ cites)</text>
        </g>
      </svg>
    </div>
  );
}
