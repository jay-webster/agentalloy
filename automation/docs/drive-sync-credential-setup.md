# Drive-sync credential setup

One-time provisioning for the service-account credential that
`automation/routines/scheduled-drive-sync.md` uses to reach Google Drive
REST-direct (see `docs/design/automation-drive-sync/approach.md` §6 for
why a service account was chosen over a `drive.file`-scoped OAuth refresh
token). Done once by Jay; the routine only ever reads the resulting env
config, never provisions or rotates it itself.

## 1. Create the service account

1. Create a Google Cloud project (or reuse an existing one).
2. Enable the Google Drive API for that project.
3. Create a service account in that project.
4. Generate a JSON key for the service account and download it. The key
   contains (among other fields) `client_email` and `private_key` — the
   only two fields this routine needs.

## 2. Create and share a Shared Drive

Must be a **Shared Drive** (Workspace-only feature, e.g. `activelab`), not
a folder in a personal My Drive account. A service account has zero
storage quota of its own — it can only create/own files inside a Shared
Drive, whose storage is pooled at the drive level, not attached to
whichever account is signed into a personal My Drive. Discovered
2026-07-15 when the live proof failed against a personal-account folder
with `403 storageQuotaExceeded`.

1. In Jay's Workspace account, create a Shared Drive named
   `agentalloy-automation`.
2. Share that Shared Drive with the service account's email address
   (`<name>@<project>.iam.gserviceaccount.com`, from the JSON key's
   `client_email` field), role **Content Manager** (Shared Drives don't
   have an "Editor" role — Content Manager is the equivalent for
   creating/editing/deleting files).
3. This is the *only* sharing grant this credential ever needs. Both
   well-known files the routine manages —
   `agentalloy-automation-candidates.db` (created by the service account
   itself, on its first upload) and `agentalloy-automation-newsletter-export.jsonl`
   (created by the Apps Script under Jay's own account, then made visible
   to the service account by living inside this shared drive) — are
   covered by this one drive-level share. No file is ever shared with the
   service account individually.

## 3. Store the credential as routine-only config

Set three values in the `RemoteTrigger` routine's own config — never
committed to this repo, never typed or entered by an interactive Claude
session, same bar as `GH_DISPATCH_TOKEN` and the Discord webhook URL
(`docs/spec/automation-discord-relay.md`'s equivalent framing for its own
credential):

- `DRIVE_SERVICE_ACCOUNT_EMAIL` — the JSON key's `client_email` field.
- `DRIVE_SERVICE_ACCOUNT_PRIVATE_KEY` — the JSON key's `private_key` field,
  copied exactly as it appears in the JSON file: one line, with literal
  `\n` escape sequences rather than real line breaks. Don't reformat it
  into a multi-line PEM block — the routine expands the `\n` escapes back
  into real newlines itself (`printf '%b'`) at the point it signs the JWT,
  so the single-line form is what it expects to receive.
- `DRIVE_FOLDER_ID` — the ID of the `agentalloy-automation` Shared Drive
  (the `...` segment in its URL,
  `https://drive.google.com/drive/folders/<shared-drive-id>` — Shared
  Drives use the same folder-URL shape as regular folders).

Once set, delete the downloaded JSON key file locally — nothing else
needs it, and it should not persist anywhere outside the routine's own
config store.

## Access boundary — what this credential can and can't do

- **Scope on the token itself**: `drive.file`, the narrowest OAuth scope
  Drive offers.
- **Concrete boundary**: the one Shared Drive membership above. Because
  the drive was explicitly shared with the service account's email
  (rather than the service account merely creating files under an
  app-scoped identity), Drive's own sharing UI on `agentalloy-automation`
  is the complete, inspectable record of this credential's access — open
  the Shared Drive's member list and confirm exactly one non-owner member
  (the service account) with Content Manager role, and no other file,
  folder, or Shared Drive shared with that same service account. That
  inspection is what AC9 requires, and it's a Drive-ACL fact to look at,
  not a claim about what the routine's code happens to do.
- This credential cannot read, write, or list anything outside the one
  Shared Drive it's a member of — a service account has no access to any
  Drive content that hasn't been explicitly shared with it, regardless of
  the scope named on its token.
