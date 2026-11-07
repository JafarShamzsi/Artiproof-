"use client";

import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  const { data: session } = useSession();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-zinc-400">Manage your account and preferences.</p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-white">Profile</CardTitle>
            <Badge
              variant="secondary"
              className="bg-emerald-500/10 text-emerald-400"
            >
              {(session?.user as { role?: string })?.role || "FREE"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-zinc-300">Name</Label>
            <Input
              defaultValue={session?.user?.name || ""}
              className="border-zinc-700 bg-zinc-800/50 text-white"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-zinc-300">Email</Label>
            <Input
              defaultValue={session?.user?.email || ""}
              disabled
              className="border-zinc-700 bg-zinc-800/50 text-zinc-400"
            />
          </div>
          <Button className="bg-emerald-500 text-white">
            Save Changes
          </Button>
        </CardContent>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-white">Subscription</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-white">Free Plan</p>
              <p className="text-sm text-zinc-400">
                10 scans/day, basic features
              </p>
            </div>
            <Button className="bg-emerald-500 text-white">
              Upgrade to Pro
            </Button>
          </div>
          <Separator className="my-6 bg-zinc-800" />
          <div className="space-y-2 text-sm text-zinc-400">
            <p>
              Pro plan includes unlimited scans, detailed DISARM reports, export
              capabilities, and priority processing.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
