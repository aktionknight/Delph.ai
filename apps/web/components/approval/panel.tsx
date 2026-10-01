"use client";
import { ContentPanel } from "@/components/canvas/panel";
import type { Brand, Campaign } from "@/lib/api";
import type { Action } from "@/components/campaign/workspace";

export function ApprovalPanel(props: { campaign: Campaign; brand?: Brand; action: Action; busy: boolean }) {
  return <ContentPanel {...props} approvalsOnly />;
}
