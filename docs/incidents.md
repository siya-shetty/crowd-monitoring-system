# Incidents and CSV reports

Incidents provide operator-authored records on top of existing monitoring data. No CV,
AI, notifications, automatic incident detection, or new dependencies are involved.

## Models and lifecycle

`incidents`: UUID, owner, title, description, severity, status, occurred/resolved
 timestamps, optional context references, small JSON context snapshot, timestamps.
Severities reuse INFO, WARNING, CRITICAL as operator prioritization. Statuses are
OPEN, INVESTIGATING, RESOLVED, CLOSED. Operators can move between these statuses;
there is no workflow engine. RESOLVED/CLOSED supply a server resolution time when
omitted. OPEN/INVESTIGATING clear it. Resolution cannot precede occurrence.
Updates replace the record via PUT;
there is no append-only change log or optimistic concurrency version in this phase.

## Relationships and ownership

Optional references: camera, video, live session, video alert (`alert_event_id`),
or live alert (`live_alert_event_id`). Only one source alert can be linked. Manual
incidents need no context. Linked resources must belong to the active authenticated
user; inaccessible/missing references return 404 on create and update. A session's
camera and an alert's source must agree with any explicitly supplied reference;
inconsistent owned references return 422. Missing implied source links are filled
from the owned alert/session. No analysis payloads are copied.

The API uses the existing active-user ownership policy; records are private to their
owner, including admins. This phase does not introduce new role restrictions.

## API and interface

- `GET/POST /api/v1/incidents`; `GET/PUT/DELETE /api/v1/incidents/{id}`.
- Incident lists and CSV share `status`, `severity` filters.
- Incident lists accept `offset`, return at most 200,
  and use stable date/ID ordering. UI shows the first 200; full paging UI is deferred.
- `GET /api/v1/incidents/options`: latest 200 owned cameras/videos/sessions using
  small database projections, without frames, tracks or analysis arrays.
- `GET /api/v1/incidents/alert-context?source=video|live&alert_id={id}` returns a draft.

`/incidents` supports manual creation, editing, filters,
resolve/close, detail, saved context and export. Times entered in the UI are local
and sent with UTC offsets; API write timestamps must include a timezone.

## Alert versus incident

An alert is a stored rule result. An incident is a human/operator record. Create
incident links on uploaded-video alerts and live alert history open a prefilled form;
reading the draft writes nothing. The operator reviews and explicitly saves it.
Title/description/severity remain editable. Multiple incidents may reference one
alert: there is no automatic conversion or deduplication policy.

Snapshots include source labels, IDs, alert rule/type/severity, zone, recorded time,
and video trigger offset where applicable. Video capture wall time is unknown;
the UI asks the operator to confirm occurrence time rather than assigning upload
or processing time as the actual occurrence time. Live drafts use alert recording time
as an editable starting point, not a guaranteed physical occurrence timestamp.

## Deletion and history

Optional FKs use SET NULL. Deleting a camera, video, session, or source alert
preserves the incident and its saved human-readable context. Video rule re-evaluation
may delete/recreate source alerts; their incident snapshots likewise survive.
Snapshots remain unchanged while a link is unchanged, even after source renaming.
Relinking refreshes the affected snapshot; explicitly removing an existing link
removes that snapshot. Once deletion has nulled a link, ordinary edits retain its
saved context. Selecting a new source alert replaces the old alert snapshot.
Explicit incident deletion is permanent. Owner deletion cascades to their operational
records. These are current records with saved context, not an immutable audit ledger.

## CSV report

`GET /api/v1/incidents/export.csv` uses the same ownership and filters as the list.
It exports incident ID/title/description, severity/status, occurrence/resolution,
camera/video/session labels, alert rule/type/severity/zone/recorded time,
video offset and current linked IDs. Saved labels survive deleted sources.

UTF-8 CSV with BOM, quoted fields, fixed `incidents.csv` filename, `no-store`, and
`nosniff`. Cells with spreadsheet-formula prefixes are escaped with an apostrophe.
Authentication uses the existing bearer header, never a URL token. All matching
records are included up to 10,000; exceeding this returns 413 and asks for a narrower
filter rather than silently truncating. No secrets, media, biometric identifiers,
or tracker payloads are exported. Operators should avoid personal data in notes.

## Migration and verification

Revision `20260926_09` follows `20260916_08`; earlier revisions are unchanged.
Run `alembic upgrade head`. Migration tests upgrade/downgrade/re-upgrade only inside
an isolated transactional PostgreSQL schema. Runtime tests use rolled-back database
transactions. Coverage includes incident CRUD, ownership, supported foreign links,
alert drafts, status updates, CSV authorization/content/formula escaping, and FK
history retention. The workflow test creates an incident linked to a fixture alert, investigates/resolves
it, views filtered history, and exports CSV without inference.

Frontend tests cover forms, edit/resolve, draft-before-save, filters, downloads,
empty/error states and the alert link. CV and analytics pipelines remain unchanged.

## Retired Events compatibility

The manual Events feature, its routes, incident selectors and filters, and CSV
event columns have been removed. Incidents work independently of Events. Alert
events used by video/live monitoring remain supported.

Historical migration `20260926_09` is unchanged. The `operational_events` table, its
ORM mapping, and nullable `incidents.event_id` foreign key remain for database
compatibility; no destructive migration or data cleanup is performed. Existing
links and saved event snapshots survive incident edits, including status changes.
They are no longer accepted as incident input or exposed in incident responses,
UI, or CSV reports. Tests verify this preservation using rolled-back transactions.
