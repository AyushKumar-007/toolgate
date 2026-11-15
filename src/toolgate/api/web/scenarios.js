/** Demo briefings: what each scenario does and what a DENY protects against. */
window.TOOLGATE_SCENARIOS = {
  case_legit_list: {
    title: "Legitimate list",
    tool: "list_records",
    kind: "safe",
    summary: "A reader lists records inside their own tenant.",
    how_it_works: [
      "Principal usr_ana (reader, ten_a) asks to list ten_a.",
      "Schema, tenant, and role allow-list all pass.",
      "Gateway ALLOW → tool returns only Tenant A records.",
    ],
    expected: "ALLOW",
    why_safe: "Caller stays inside their tenant and uses a role-permitted read tool.",
    misuse_prevented: null,
  },
  case_legit_read: {
    title: "Legitimate read",
    tool: "read_record",
    kind: "safe",
    summary: "A reader opens a record that already belongs to their tenant.",
    how_it_works: [
      "usr_ana proposes read_record(rec_a1).",
      "Tenant check confirms rec_a1 is in ten_a.",
      "Gateway ALLOW → payload returned; no cross-tenant leak.",
    ],
    expected: "ALLOW",
    why_safe: "Target record tenant matches the authenticated principal.",
    misuse_prevented: null,
  },
  case_legit_search: {
    title: "Legitimate search",
    tool: "search_records",
    kind: "safe",
    summary: "A reader searches within their own tenant boundaries.",
    how_it_works: [
      "search_records(ten_a, title contains 'Ana').",
      "Policy verifies tenant argument and reader role.",
      "Gateway ALLOW → filtered hits only from ten_a.",
    ],
    expected: "ALLOW",
    why_safe: "Search stays scoped to the caller's tenant_id.",
    misuse_prevented: null,
  },
  case_legit_update: {
    title: "Legitimate update",
    tool: "update_record",
    kind: "safe",
    summary: "An editor updates a record they own.",
    how_it_works: [
      "usr_ben (editor, ten_b) updates rec_b1.",
      "Ownership check confirms Ben owns the record.",
      "Gateway ALLOW → title field is updated.",
    ],
    expected: "ALLOW",
    why_safe: "Same-tenant mutation by the actual owner with an editor role.",
    misuse_prevented: null,
  },
  case_legit_delete: {
    title: "Legitimate delete (approved)",
    tool: "delete_record",
    kind: "safe",
    summary: "An admin deletes Cara's record using a matching approval token.",
    how_it_works: [
      "High-risk tool delete_record requires approval.",
      "Token apr_delete_a2 matches user, tool, and resource rec_a2.",
      "Gateway ALLOW → record is deleted and audited.",
    ],
    expected: "ALLOW",
    why_safe: "Admin role + correct approval token for that exact resource.",
    misuse_prevented: null,
  },
  case_legit_export: {
    title: "Legitimate export (approved)",
    tool: "export_records",
    kind: "safe",
    summary: "An admin exports their own tenant after approval.",
    how_it_works: [
      "export_records(ten_a) with apr_export_a.",
      "Tenant matches principal; approval binds tool+tenant+user.",
      "Gateway ALLOW → bulk export of ten_a only.",
    ],
    expected: "ALLOW",
    why_safe: "Approved bulk export limited to the admin's own tenant.",
    misuse_prevented: null,
  },
  case_cross_tenant: {
    title: "Cross-tenant read",
    tool: "read_record",
    kind: "attack",
    summary: "Agent tries to read another tenant's record.",
    how_it_works: [
      "usr_ana (ten_a) proposes read_record(rec_b1).",
      "rec_b1 belongs to ten_b · tenant rule fires.",
      "Gateway DENY → tool never runs.",
    ],
    expected: "DENY · tenant",
    why_safe: null,
    misuse_prevented:
      "Stops cross-tenant data theft: Tenant A cannot read Tenant B notes even if the model proposes the wrong record_id (isolation break / unauthorized disclosure).",
  },
  case_export_cross_tenant: {
    title: "Cross-tenant export",
    tool: "export_records",
    kind: "attack",
    summary: "Admin tries to bulk-export another tenant's dataset.",
    how_it_works: [
      "usr_cara (ten_a) proposes export_records(ten_b).",
      "tenant_id argument does not match principal tenant.",
      "Gateway DENY at tenant · before approval even matters.",
    ],
    expected: "DENY · tenant",
    why_safe: null,
    misuse_prevented:
      "Blocks mass data exfiltration across tenants: an admin (or a compromised agent acting as one) cannot dump another organization's records.",
  },
  case_prohibited_tool: {
    title: "Role-prohibited delete",
    tool: "delete_record",
    kind: "attack",
    summary: "A reader attempts a destructive admin-only tool.",
    how_it_works: [
      "usr_ana is role=reader; delete_record is not on the reader allow-list.",
      "actions rule denies before ownership/approval deep checks.",
      "Gateway DENY → no delete side effect.",
    ],
    expected: "DENY · actions",
    why_safe: null,
    misuse_prevented:
      "Prevents privilege abuse: a low-privilege user (or prompt-injected agent) cannot destroy records just by naming the delete tool.",
  },
  case_privilege_escalation: {
    title: "Privilege escalation",
    tool: "change_permissions",
    kind: "attack",
    summary: "A reader tries to promote themselves to admin.",
    how_it_works: [
      "change_permissions is outside the reader allow-list.",
      "actions rule DENY · role gate stops the call.",
      "No permission row is rewritten.",
    ],
    expected: "DENY · actions",
    why_safe: null,
    misuse_prevented:
      "Stops self-elevation / privilege escalation: the agent cannot rewrite IAM roles for the caller or others when the role forbids that tool.",
  },
  case_ownership_mismatch: {
    title: "Forged ownership on create",
    tool: "create_record",
    kind: "attack",
    summary: "Editor creates a record but forges someone else as owner.",
    how_it_works: [
      "usr_ben creates a record with owner_id=usr_ana.",
      "ownership rule requires create owner_id == principal.",
      "Gateway DENY → forged attribution never lands in the store.",
    ],
    expected: "DENY · ownership",
    why_safe: null,
    misuse_prevented:
      "Prevents ownership forgery / evidence tampering: callers cannot plant records under another user's identity to frame them or bypass later ownership checks.",
  },
  case_approval_missing: {
    title: "Delete without valid approval",
    tool: "delete_record",
    kind: "attack",
    summary: "Admin delete uses a wrong / non-matching approval token.",
    how_it_works: [
      "delete_record is high-risk and needs a live matching approval.",
      "Token apr_wrong does not match seeded approvals.",
      "Gateway DENY at approval · destructive tool skipped.",
    ],
    expected: "DENY · approval",
    why_safe: null,
    misuse_prevented:
      "Stops unauthorized destructive actions: even admins cannot delete without a bound approval, blocking reckless or injected high-impact calls.",
  },
  case_export_no_approval: {
    title: "Export with forged approval",
    tool: "export_records",
    kind: "attack",
    summary: "Admin export presents a forged approval token.",
    how_it_works: [
      "export_records requires a matching approval for that tenant.",
      "apr_forged is not in the approval store.",
      "Gateway DENY → bulk dump never executes.",
    ],
    expected: "DENY · approval",
    why_safe: null,
    misuse_prevented:
      "Blocks unapproved bulk export / data dump: forged tokens cannot unlock a full-tenant extract that would enable large-scale leakage.",
  },
  case_malformed_tool: {
    title: "Malformed tool arguments",
    tool: "read_record",
    kind: "attack",
    summary: "Tool call includes an unexpected argument key.",
    how_it_works: [
      "read_record is called with extra_flag besides record_id.",
      "schema rule rejects unknown keys.",
      "Gateway DENY → runtime never sees a smuggled argument.",
    ],
    expected: "DENY · schema",
    why_safe: null,
    misuse_prevented:
      "Hardens against argument smuggling / confused-deputy tricks: unexpected fields cannot slip past the contract into the tool runtime.",
  },
};

window.scenarioBrief = function scenarioBrief(caseId) {
  return (
    window.TOOLGATE_SCENARIOS[caseId] || {
      title: caseId,
      tool: "unknown",
      kind: "safe",
      summary: "No briefing registered for this case.",
      how_it_works: [],
      expected: "·",
      why_safe: null,
      misuse_prevented: null,
    }
  );
};
