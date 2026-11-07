"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

export function ErrorMessage({
  title = "Something went wrong",
  message = "Failed to load data. Please try again.",
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="border-zinc-800 bg-zinc-900/50">
      <CardContent className="flex flex-col items-center py-12">
        <AlertTriangle className="mb-3 h-10 w-10 text-amber-400" />
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="mt-1 text-sm text-zinc-400">{message}</p>
        {onRetry && (
          <Button
            onClick={onRetry}
            variant="outline"
            size="sm"
            className="mt-4 border-zinc-700 text-zinc-400"
          >
            <RefreshCw className="mr-2 h-4 w-4" /> Try Again
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
