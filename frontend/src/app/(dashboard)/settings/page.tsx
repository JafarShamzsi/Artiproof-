"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, Bell, Save, Loader2 } from "lucide-react";

export default function SettingsPage() {
  const { data: session } = useSession();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [fullName, setFullName] = useState(session?.user?.name || "");
  const [institution, setInstitution] = useState("");

  async function handleSave() {
    setSaving(true);
    // TODO: Phase 2 — call PUT /api/auth/me
    await new Promise((r) => setTimeout(r, 500));
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-zinc-400">Manage your profile and preferences.</p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <User className="h-5 w-5 text-zinc-400" /> Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-zinc-300">Full Name</Label>
              <Input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="border-zinc-700 bg-zinc-800/50 text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-zinc-300">Email</Label>
              <Input
                defaultValue={session?.user?.email || ""}
                disabled
                className="border-zinc-700 bg-zinc-800/50 text-zinc-500"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label className="text-zinc-300">Institution / University</Label>
            <Input
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="e.g. ADA University"
              className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-zinc-300">Role</Label>
            <select className="w-full rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-white">
              <option value="researcher">Researcher</option>
              <option value="faculty">Faculty</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <Button onClick={handleSave} disabled={saving} className="bg-emerald-500 text-white hover:bg-emerald-600">
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            {saved ? "Saved!" : "Save Changes"}
          </Button>
        </CardContent>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Bell className="h-5 w-5 text-zinc-400" /> Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { label: "Email me when a source check completes", checked: true },
            { label: "Email me when a researcher analysis completes", checked: true },
            { label: "Weekly digest of activity", checked: false },
          ].map((pref) => (
            <label key={pref.label} className="flex items-center gap-3 text-sm text-zinc-300">
              <input type="checkbox" defaultChecked={pref.checked} className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-emerald-500" />
              {pref.label}
            </label>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
