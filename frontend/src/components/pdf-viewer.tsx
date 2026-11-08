"use client";

import {
  useState,
  useRef,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export interface PdfViewerHandle {
  scrollToPosition: (page: number, bbox: number[]) => void;
}

interface PdfViewerProps {
  url: string;
  className?: string;
}

const PdfViewer = forwardRef<PdfViewerHandle, PdfViewerProps>(
  function PdfViewer({ url, className = "" }, ref) {
    const [numPages, setNumPages] = useState(0);
    const [scale, setScale] = useState(1.0);
    const [pulseTarget, setPulseTarget] = useState<{
      page: number;
      bbox: number[];
    } | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

    const onDocumentLoadSuccess = useCallback(
      ({ numPages }: { numPages: number }) => {
        setNumPages(numPages);
      },
      []
    );

    const zoomIn = useCallback(() => setScale((s) => Math.min(3, s + 0.25)), []);
    const zoomOut = useCallback(
      () => setScale((s) => Math.max(0.5, s - 0.25)),
      []
    );
    const resetZoom = useCallback(() => setScale(1.0), []);

    // Expose scrollToPosition to parent
    useImperativeHandle(
      ref,
      () => ({
        scrollToPosition(page: number, bbox: number[]) {
          const pageEl = pageRefs.current.get(page);
          if (!pageEl || !containerRef.current) return;

          // Scroll the page into view
          pageEl.scrollIntoView({ behavior: "smooth", block: "center" });

          // Show pulse overlay
          setPulseTarget({ page, bbox });
          setTimeout(() => setPulseTarget(null), 2500);
        },
      }),
      []
    );

    const setPageRef = useCallback(
      (pageNum: number) => (el: HTMLDivElement | null) => {
        if (el) {
          pageRefs.current.set(pageNum, el);
        }
      },
      []
    );

    return (
      <div className={`flex flex-col ${className}`}>
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900">
          <span className="text-xs text-zinc-600 dark:text-zinc-400">
            {numPages > 0 ? `${numPages} pages` : "Loading..."}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={zoomOut}
              className="h-7 w-7 p-0 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="min-w-[3rem] text-center text-xs text-zinc-600 dark:text-zinc-400">
              {Math.round(scale * 100)}%
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={zoomIn}
              className="h-7 w-7 p-0 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetZoom}
              className="h-7 w-7 p-0 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* PDF Pages */}
        <div
          ref={containerRef}
          className="flex-1 overflow-auto bg-zinc-100 p-4 dark:bg-zinc-950"
        >
          <Document
            file={url}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={
              <div className="flex items-center justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand border-t-transparent" />
              </div>
            }
            error={
              <div className="py-20 text-center text-sm text-red-400">
                Failed to load PDF
              </div>
            }
          >
            <div className="mx-auto flex flex-col items-center gap-4">
              {Array.from({ length: numPages }, (_, i) => (
                <div key={i} ref={setPageRef(i)} className="relative">
                  <Page
                    pageNumber={i + 1}
                    scale={scale}
                    className="shadow-lg"
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                  />
                  {/* Pulse overlay when scrolled to */}
                  {pulseTarget && pulseTarget.page === i && (
                    <PulseOverlay bbox={pulseTarget.bbox} scale={scale} />
                  )}
                </div>
              ))}
            </div>
          </Document>
        </div>
      </div>
    );
  }
);

export default PdfViewer;

function PulseOverlay({
  bbox,
  scale,
}: {
  bbox: number[];
  scale: number;
}) {
  const [x0, y0, x1, y1] = bbox;
  return (
    <div
      className="pointer-events-none absolute animate-pulse rounded border-2 border-brand bg-brand/15"
      style={{
        left: x0 * scale,
        top: y0 * scale,
        width: (x1 - x0) * scale,
        height: (y1 - y0) * scale,
        animationDuration: "0.8s",
        animationIterationCount: "3",
      }}
    />
  );
}
