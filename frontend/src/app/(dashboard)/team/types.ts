/**
 * Shared response types for the /team workspace.
 *
 * Kept in sync by hand with the backend Pydantic schemas in
 *   - backend/app/schemas/organization.py
 *   - backend/app/schemas/org_member.py
 *
 * If a field name changes here it must change there. We don't auto-
 * generate types — the FastAPI OpenAPI codegen pipeline is on the
 * roadmap; until then, hand-mirroring + a tsc check on every PR is
 * the contract.
 */

export type OrgRole = "admin" | "member";

export interface OrgDetail {
  id: string;
  name: string;
  slug: string | null;
  contact_email: string | null;
  seat_limit: number;
  seat_used: number;
  seat_remaining: number;
  is_trial: boolean;
  trial_ends_at: string | null;
  created_at: string;
  current_user_role: OrgRole;
}

export interface OrgMember {
  user_id: string;
  email: string;
  full_name: string;
  role: OrgRole;
  joined_at: string;
  invited_by: string | null;
  source_checks_mtd: number;
  researcher_analyses_mtd: number;
  reports_mtd: number;
}

export interface OrgMemberListResponse {
  items: OrgMember[];
  total: number;
}

export interface OrgInvite {
  id: string;
  email: string;
  role: OrgRole;
  status: "pending" | "accepted" | "revoked" | "expired";
  invited_by: string | null;
  created_at: string;
  expires_at: string;
}

export interface OrgInviteListResponse {
  items: OrgInvite[];
  total: number;
}

export interface OrgAuditLogItem {
  id: string;
  action: string;
  actor_user_id: string | null;
  actor_email: string | null;
  target_user_id: string | null;
  target_email: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface OrgAuditLogResponse {
  items: OrgAuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}
