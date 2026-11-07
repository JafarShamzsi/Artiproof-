import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const ALLOWED_KINDS = new Set(["original", "annotated"]);

/**
 * Same-origin PDF proxy. The browser's pdf.js can't attach an Authorization
 * header to its fetch, so we proxy the backend's authenticated PDF endpoint
 * through Next.js: this route reads the user's NextAuth session server-side,
 * forwards the request with the bearer token, and streams bytes back.
 */
export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ id: string; kind: string }> }
) {
  const { id, kind } = await ctx.params;

  if (!ALLOWED_KINDS.has(kind)) {
    return NextResponse.json({ detail: "Invalid PDF kind" }, { status: 400 });
  }

  const session = await getServerSession(authOptions);
  const accessToken = (session as { accessToken?: string } | null)?.accessToken;
  if (!accessToken) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const upstream = await fetch(
    `${BACKEND_URL}/api/source-check/${encodeURIComponent(id)}/pdf/${kind}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken}` },
      // Don't cache — PDFs may be regenerated server-side.
      cache: "no-store",
    }
  );

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    return NextResponse.json(
      { detail: detail || `Upstream returned ${upstream.status}` },
      { status: upstream.status }
    );
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/pdf",
      "Cache-Control": "private, no-store",
    },
  });
}
