---
id: e011-01-workman-pm-domain
title: "AKM Graph Foundation + PM Domain Expansion + PMIntent Schema"
tier: B
owner: benthepsychologist
goal: "pm.work_item.update op with partial payload schema (title, description, kind, state, priority, severity, labels, assignees, due_at, time_estimate, time_spent)"
branch: feat/pm-domain-expansion
repo:
  name: workman
  url: /workspace/workman
status: refined
created: 2026-02-11T21:24:25Z
updated: 2026-02-11T21:45:00Z
---

# e011-01-workman-pm-domain: AKM Graph Foundation + PM Domain Expansion + PMIntent Schema

**Epic:** e011-pm-system
**Branch:** `feat/pm-domain-expansion`
**Tier:** B

## Schema Reference

**All entity and operation schemas are defined normatively in [../resources.md](../resources.md):**
- AKM Foundation schemas: Atom, Link, Source (§1.1-1.3)
- Update operation schemas: pm.work_item.update, pm.project.update, pm.deliverable.update (§2.1-2.3)
- OpsStream schemas: pm.opsstream.create, pm.opsstream.update (§2.4-2.5)
- Link operation schemas: link.create, link.remove (§2.6-2.7)
- Artifact schemas: pm.artifact.create, update, finalize, deliver, supersede, archive (§2.8-2.13)
- Field registry: pm.fields.yaml definitions (§4)
- PMIntent envelope schema (§3)

The acceptance criteria below reference these schemas. Implementers should consult resources.md for the exact field definitions, types, and validation rules.

## Objective

Establish the AKM (Atomic Knowledge Model) graph foundation and expand the PM domain in workman with update operations, OpsStream entity, Artifact entity with dual content strategy, PMIntent compilation, and a declarative field registry. This creates the universal entity-relation substrate (every entity is an atom, every relation is a Link) while completing the PM operational vocabulary.

## Problem

1. **No update operations**: PM entities can only be created and completed/closed, but not updated with new field values
2. **Missing OpsStream entity**: Ongoing operational work (clinical ops, consulting ops) needs a container separate from time-bounded projects
3. **No artifact management**: Session notes, reports, and documents need lifecycle management with dual content strategy (WAL-native + delivered)
4. **No bulk operations**: Each PM command requires separate compile+execute calls, no PMIntent envelope for multi-op transactions
5. **No universal graph substrate**: PM relations are ad-hoc events rather than Links in a universal AKM graph
6. **Implicit field definitions**: PM field types, enums, and defaults are scattered across JSON schemas rather than declaratively defined

## Current Capabilities

### kernel.surfaces

```yaml
- command: "from workman import compile"
  usage: "plan = compile('pm.work_item.create', payload, ctx)"
- command: "from workman import execute"
  usage: "result = execute({'op': 'pm.work_item.create', 'payload': {...}, 'ctx': {...}})"
```

### modules

```yaml
- name: public_surface
  provides: ['compile', 'execute']
- name: compile
  provides: ['compile(op, payload, ctx, pins=None)']
- name: execute
  provides: ['execute(params) -> dict']
- name: catalog
  provides: ['OpSpec (dataclass)', 'OP_CATALOG', 'get_op_spec(op) -> OpSpec | None']
- name: builders
  provides: ['generic_pm_builder(op_spec, payload, ctx) -> wal.append op', 'build_wal_append(event_type, aggregate_type, aggregate_id, payload, idempotency_key) -> op']
- name: assertions
  provides: ['assert_exists(aggregate_type, id)', 'assert_not_exists(aggregate_type, id)']
- name: ids
  provides: ['generate_id(prefix) -> string', 'make_idempotency_key(op, aggregate_type, aggregate_id, correlation_id) -> string']
- name: schema
  provides: ['resolve_schema(iglu_ref) -> dict', 'validate_payload(payload, schema) -> None | raises']
- name: errors
  provides: ['WorkmanError (base)', 'CompileError (op field)', 'ValidationError (errors field)']
```

### layout

```yaml
- path: src/workman/__init__.py
  role: "Public API: compile, execute"
- path: src/workman/compile.py
  role: "compile() entrypoint — op+payload+ctx → Storacle plan"
- path: src/workman/execute.py
  role: "execute() entrypoint — params dict → domain event items (no Storacle wrapper)"
- path: src/workman/catalog.py
  role: "OpSpec dataclass, OP_CATALOG dict, get_op_spec()"
- path: src/workman/builders.py
  role: "generic_pm_builder(), build_wal_append() — parameterized by OpSpec"
- path: src/workman/assertions.py
  role: "assert.exists/assert.not_exists op constructors"
- path: src/workman/ids.py
  role: "ID generation (generate_id) + idempotency_key helpers"
- path: src/workman/schema.py
  role: "Schema resolution + validation against Iglu refs"
- path: src/workman/errors.py
  role: "WorkmanError, CompileError, ValidationError"
```

## Proposed build_delta

```yaml
target: "projects/workman/workman.build.yaml"
summary: "Add intent module, field registry config, expand catalog with ~16 new PM+AKM+artifact ops, establish AKM graph foundation"

adds:
  kernel_surfaces:
    - surface: python_api
      entrypoint:
        import: "from workman import compile_intent"
        usage: "result = compile_intent({'intent_id': '...', 'ops': [...]})"
  layout:
    - path: "src/workman/intent.py"
      module: intent
      role: "compile_intent() — PMIntent dict to CallableResult (plans + diff + plan_hash in result fields)"
    - path: "pm.fields.yaml"
      module: field_registry
      role: "Declarative PM field definitions (enums, types, editability, defaults)"
  modules:
    - name: intent
      kind: module
      provides:
        - "compile_intent(intent: dict) -> CallableResult"
        - "CallableResult with items (plans), diff, and plan_hash fields"
      depends_on: [compile, catalog, ids]
    - name: field_registry
      kind: config
      provides:
        - "PM field definitions (kind, state, priority, severity, labels, etc.)"
        - "Artifact entity definition, artifact_kind enum, artifact_status enum, delivered_via enum"
        - "OpsStream entity definition, opsstream_type enum, opsstream_status enum"
        - "AKM entity definitions (Atom, Link, Source)"
  boundaries:
    - name: intent_api
      type: inbound
      contract: "compile_intent(intent: dict) -> CallableResult (with items, diff, plan_hash)"
      consumers: ["lorchestra (via call op with callable: workman)"]
modifies:
  modules:
    - name: public_surface
      change: "Add compile_intent to provides list (returns CallableResult)"
    - name: catalog
      change: "Add ~17 OpSpec entries: pm.work_item.update, pm.work_item.cancel, pm.project.update, pm.deliverable.update, pm.deliverable.reject, pm.opsstream.create, pm.opsstream.update, pm.opsstream.close, link.create, link.remove, pm.artifact.create, pm.artifact.update, pm.artifact.finalize, pm.artifact.deliver, pm.artifact.defer, pm.artifact.supersede, pm.artifact.archive"
```

## Acceptance Criteria

- [ ] pm.work_item.update op with partial payload schema (title, description, kind, state, priority, severity, labels, assignees, due_at, time_estimate, time_spent)
- [ ] pm.project.update op with partial payload schema (name, description, owner, status, target_end_date)
- [ ] pm.deliverable.update op with partial payload schema (name, description, status, acceptance_criteria)
- [ ] pm.work_item.cancel op with payload (work_item_id, cancelled_at?, reason?) — dedicated lifecycle op
- [ ] pm.deliverable.reject op with payload (deliverable_id, rejected_at?, reason?) — dedicated lifecycle op
- [ ] pm.opsstream.close op with payload (opsstream_id, closed_at?, reason?) — dedicated lifecycle op
- [ ] pm.work_item.move evolves to support project_id, opsstream_id, parent_id (container fields removed from update)
- [ ] pm.work_item.move supports container reassignment with inheritance resolution
- [ ] pm.opsstream.create op with payload schema (name, type, owner, status, description, meta)
- [ ] pm.opsstream.update op with partial payload schema (name, type, owner, status, description)
- [ ] WorkItem inherits container ownership hierarchically: WorkItem → Deliverable → Project → OpsStream
- [ ] pm.fields.yaml includes opsstream_type enum (CLINICAL_OPS|CONSULTING_OPS|INTERNAL_OPS|OTHER)
- [ ] pm.fields.yaml includes opsstream_status enum (ACTIVE|PAUSED|CLOSED)
- [ ] artifact aggregate type in workman catalog, id_prefix: art
- [ ] pm.artifact.create op: {title, kind, content?, content_ref?, status (default DRAFT), work_item_id?, deliverable_id?, project_id?, opsstream_id?, contact_ref?, tags, meta}
- [ ] pm.artifact.create enforces at least one container FK present
- [ ] pm.artifact.create validates kind against artifact_kind enum
- [ ] pm.artifact.update op: partial payload {artifact_id, title?, kind?, content?, tags?, meta?} — does NOT change status
- [ ] pm.artifact.finalize op: {artifact_id, finalized_at?, finalized_by?} — sets status to FINAL
- [ ] pm.artifact.deliver op: {artifact_id, content_ref, delivered_via, delivered_at?} — records delivery, does NOT perform it
- [ ] pm.artifact.deliver preserves original content field (source stays in WAL)
- [ ] pm.artifact.supersede op: {artifact_id, superseded_by_id, reason?} — sets status to SUPERSEDED (terminal)
- [ ] pm.artifact.archive op: {artifact_id, archived_at?, reason?} — sets status to ARCHIVED (terminal)
- [ ] pm.artifact.defer op: {artifact_id, deferred_at?, reason?} — sets status to DEFERRED (pausable state)
- [ ] Finalize is optional — artifacts can be delivered directly from DRAFT
- [ ] WAL-native: content field holds inline markdown (session notes, memos, LLM outputs)
- [ ] Delivered: content_ref holds external URL (GDrive doc, email message_id)
- [ ] Both can coexist: content is source of truth, content_ref is delivered copy
- [ ] Atom schema: atom_id, atom_type (work|concept|entity|note|event), label, summary?, domain_ref?, curation_level (default 0), epistemic_status?, processing_status (unprocessed|triaged|processed, default unprocessed), lifecycle_status (active|deprecated|archived, default active), tags[]
- [ ] Link schema: link_id, from_atom_id, to_atom_id, predicate, note?, evidence_strength_band?, sources[]
- [ ] Source schema: source_id, source_type (document|transcript|dataset|audio|video|web_page|other), title, locator
- [ ] iglu schemas for Atom, Link, Source registered in local-governor/registries/iglu
- [ ] BQ tables for atoms, links, sources (WAL events + current-state views)
- [ ] All PM entity create ops auto-generate atom_id, set atom_type=work, derive label from title/name
- [ ] All PM entities carry optional domain_ref for external import traceability
- [ ] link.create op: {from_atom_id, to_atom_id, predicate, note?, evidence_strength_band?}
- [ ] link.remove op: {from_atom_id, to_atom_id, predicate}
- [ ] Unified predicate vocabulary: blocks, blocked_by, depends_on, part_of, has_part, continues, branches_from, superseded_by, implements, applies, refines, informed_by, related_to, broader_than, narrower_than, example_of, supports, conflicts_with, contrasts_with, child_of, parent_of, student_of, teacher_of, influenced_by
- [ ] Links stored as WAL events (link.created, link.removed) with from/to/predicate
- [ ] Work-structural predicates (blocks, depends_on, part_of) validated: both atoms must be atom_type=work
- [ ] Bridge predicates (implements, applies, refines) accept cross-type atoms (for future AKM use)
- [ ] All new ops have iglu schemas registered in local-governor/registries/iglu
- [ ] pm.fields.yaml at workman repo root declaring all PM fields with name, type, editability, defaults
- [ ] pm.fields.yaml includes kind enum (TASK|ISSUE|CHANGE|RISK|DECISION|MILESTONE|OTHER)
- [ ] pm.fields.yaml includes state enum (NEW|PLANNED|IN_PROGRESS|BLOCKED|DONE|CANCELLED|DEFERRED)
- [ ] pm.fields.yaml includes project status enum (IDEA|PLANNED|ACTIVE|PAUSED|COMPLETED|CANCELLED)
- [ ] pm.fields.yaml includes artifact_kind enum (SESSION_NOTE|REPORT|TEMPLATE|CORRESPONDENCE|POLICY|INTAKE|MEMO|OTHER)
- [ ] pm.fields.yaml includes artifact_status enum (DRAFT|DEFERRED|FINAL|DELIVERED|SUPERSEDED|ARCHIVED)
- [ ] pm.fields.yaml includes delivered_via enum (gdrive|email|other)
- [ ] pm.fields.yaml includes artifact entity definition with all fields
- [ ] workman.intent module with compile_intent(intent: dict) -> CallableResult
- [ ] compile_intent returns CallableResult with items (plans: list[dict]), diff (list[str]), and plan_hash (str) fields
- [ ] plan_hash is SHA256 of the serialized plans for integrity verification and audit cross-referencing
- [ ] PMIntent JSON schema defined (intent_id, ops, description, source, actor, issued_at)
- [ ] compile_intent handles N ops in a single intent (bulk-native)
- [ ] compile_intent CallableResult structure: items contains StoraclePlan list (one per op), diff contains human-readable strings, plan_hash for audit verification
- [ ] All existing tests continue to pass
- [ ] New tests for update ops, relation ops, intent compilation, diff generation, and plan hashing
- [ ] New tests for all artifact ops (create, update, finalize, deliver, defer, supersede, archive)
- [ ] Tests for content strategy (WAL-native, delivered, both)
- [ ] Tests for container FK validation (at least one required, assert.exists generated)
- [ ] Intent compilation tests with artifact ops
- [ ] Test PMIntent with @ref:N cross-operation references
- [ ] Test invalid @ref (out of range, forward refs, malformed)
- [ ] Test complex reference chains (op 2 refs op 1, op 3 refs both)

## Constraints

- All new ops follow the existing OpSpec pattern in catalog.py
- generic_pm_builder is reused; no new builder functions unless schema requires it
- execute() callable protocol entry point handles all new ops via get_op_spec dispatch
- pm.fields.yaml is declarative YAML, not Python code
- PMIntent does NOT know about storage — it produces plans, not commits
- Diff output is a list of human-readable strings
- AKM schemas (Atom, Link, Source) are domain-agnostic — no PM-specific fields in Atom schema
- atom_id is system-generated, opaque, globally unique
- domain_ref is optional and supports external system identifiers
- Link predicates are a single unified vocabulary, not domain-partitioned
- Artifact content strategy is a payload-level concern, not a structural concern
- WAL-native artifacts store content inline in payload; delivered artifacts store content_ref
- pm.artifact.deliver records delivery metadata — actual delivery is egret's job (e010)
- At least one container FK (work_item_id, deliverable_id, project_id, opsstream_id) required on create
- contact_ref is a string (not a FK) until contacts are formalized in a future epic
- Status transitions via dedicated lifecycle ops (finalize, deliver, supersede, archive), not update
- Workman generates both atom_id and domain_ref at compile time, embedded in WAL event payloads
- For PM entities, domain_ref format is `aggregate_type:aggregate_id` (e.g., "project:proj_01ABC")
- BQ views extract both atom_id and domain_ref from payloads using ARRAY_AGG pattern
- Views do not construct these fields—they are normative values set by workman

---

## compile_intent Operation Specification

### Operation: pm.compile_intent

**Type:** Meta-operation (processes multiple ops, returns plans without executing)

**Signature:**
```python
def compile_intent(intent: dict, ctx: dict) -> dict
```

**Input Schema (PMIntent):**

Passed via workman.execute() as:
```python
{
    "op": "pm.compile_intent",
    "intent": {
        "intent_id": "pmi_01ABC...",    # ULID, generated by caller (life/API)
        "description": "Create task",    # Optional, human-readable summary
        "source": "life-cli",            # Required, origin system
        "actor": {                       # Required, who is making changes
            "actor_type": "human",       # Enum: human|service|system
            "actor_id": "ben"            # Identifier in that system
        },
        "issued_at": "2026-02-12T...", # Required, ISO 8601 timestamp
        "ops": [                         # Required, min 1 operation
            {
                "op": "pm.work_item.create",  # Operation name
                "payload": {                  # Operation-specific payload
                    "title": "Fix bug",
                    "kind": "TASK",
                    "priority": "HIGH",
                    "project_id": "proj_01ABC"
                }
            }
        ]
    },
    "ctx": {                         # Optional execution context
        "correlation_id": "pmi_...", # Derived from intent_id
        "producer": "life-cli"       # Derived from source
    }
}
```

**Output Schema (return value):**

compile_intent returns a dict matching CallableResult:
```python
{
    "schema_version": "1.0",
    "items": [                          # Plans for each operation
        {
            "plan_id": "plan_01ABC",
            "op": "pm.work_item.create",
            "domain_events": [          # Events to write to WAL
                {
                    "event_type": "work_item.created",
                    "aggregate_type": "work_item",
                    "aggregate_id": "wi_01ABC",
                    "payload": {...},
                    "idempotency_key": "..."
                }
            ]
        }
    ],
    "stats": {
        "input": 1,                    # Number of ops in intent
        "output": 1,                   # Number of plans generated
        "skipped": 0,
        "errors": 0
    },
    # Additional PM-specific fields (stored alongside standard CallableResult):
    "diff": [
        "CREATE work_item wi_01ABC (title='Fix bug', kind=TASK, ...)"
    ],
    "plan_hash": "a3f5b2e9..."         # SHA256 of serialized plans
}
```

**Processing Logic:**

1. **Validate PMIntent schema** — all required fields present and valid
2. **Construct context** — derive correlation_id, producer from intent
3. **For each op in intent.ops:**
   - Call `pm.<entity>.<action>.compile(op.payload, ctx)`
   - Generates StoraclePlan with domain_event items
   - Generate human-readable diff describing the change
   - Collect plan in plans array
4. **Compute integrity hash** — SHA256(json.dumps(sorted(plans)))
5. **Return CallableResult** — items=plans, diff=changes, plan_hash=hash

**Example Usage:**

```python
from workman import execute

intent = {
    "intent_id": "pmi_01ABC123",
    "description": "Create task for bug fix",
    "source": "life-cli",
    "actor": {"actor_type": "human", "actor_id": "ben"},
    "issued_at": "2026-02-12T10:00:00Z",
    "ops": [
        {
            "op": "pm.work_item.create",
            "payload": {
                "title": "Fix bug",
                "kind": "TASK",
                "priority": "HIGH",
                "project_id": "proj_01ABC"
            }
        }
    ]
}

result = execute({
    "op": "pm.compile_intent",
    "intent": intent,
    "ctx": {}
})

# result["items"]: [StoraclePlan1, ...]
# result["diff"]: ["CREATE work_item wi_01ABC (title='Fix bug', ...)"]
# result["plan_hash"]: "a3f5b2..."
```

### Multi-Operation Intent Example

```python
intent = {
    "intent_id": "pmi_01ABC123",
    "description": "Create project with first milestone and task",
    "source": "life-cli",
    "actor": {"actor_type": "human", "actor_id": "ben"},
    "issued_at": "2026-02-12T10:00:00Z",
    "ops": [
        {
            "op": "pm.project.create",
            "payload": {
                "name": "Launch Product X",
                "owner": "ben",
                "status": "ACTIVE"
            }
        },
        {
            "op": "pm.deliverable.create",
            "payload": {
                "name": "MVP Release",
                "project_id": "@ref:0",  # References project from op[0]
                "status": "PLANNED"
            }
        },
        {
            "op": "pm.work_item.create",
            "payload": {
                "title": "Design landing page",
                "deliverable_id": "@ref:1",  # References deliverable from op[1]
                "kind": "TASK",
                "priority": "HIGH"
            }
        }
    ]
}

result = execute({
    "op": "pm.compile_intent",
    "intent": intent,
    "ctx": {}
})

# result["items"]: [Plan for op[0], Plan for op[1], Plan for op[2]]
# result["diff"]:
#   - "CREATE project proj_01DEF (name='Launch Product X', owner=ben, status=ACTIVE)"
#   - "CREATE deliverable del_01JKL (name='MVP Release', project=proj_01DEF)"
#   - "CREATE work_item wi_01PQR (title='Design landing page', deliverable=del_01JKL, kind=TASK)"
# result["plan_hash"]: "c1d3e5f..."
```

**Constraints:**

- compile_intent does NOT write to WAL — it only generates plans
- All plans share same intent_id/correlation_id for traceability
- compile_intent is deterministic — same intent always produces same plans (and plan_hash)
- Diff output is informational only (for human preview) — not persisted
- plan_hash enables integrity verification between plan (compile_intent) and apply (storacle.submit) steps
- Max 100 ops per intent (batch limit for performance)

**Error Handling:**

- CompileError: Invalid intent structure or unknown operation
- ValidationError: Missing required fields or invalid payload schema
- Errors are propagated (not collected) — first error stops compilation

---

## @ref Cross-Operation References

### Purpose

PMIntent supports multi-operation transactions where later ops reference IDs generated by earlier ops. The `@ref:N` syntax enables this.

### Syntax

```json
{
  "ops": [
    {
      "op": "pm.project.create",
      "payload": {"name": "Alpha", "owner": "ben"}
    },
    {
      "op": "pm.deliverable.create",
      "payload": {
        "name": "MVP",
        "project_id": "@ref:0"  // References project created by op[0]
      }
    }
  ]
}
```

### Resolution Mechanism

**When**: During compile_intent execution (before plan building)

**How**:
1. compile_intent processes ops sequentially
2. For each op, generate aggregate_id (e.g., `proj_01ABC`)
3. Replace `@ref:N` with actual ID from op[N]
4. Validate: N must be < current op index (no forward refs)
5. Validate: Referenced op must have generated an ID

**Example**:
```python
# Input intent
ops = [
  {"op": "pm.project.create", "payload": {"name": "Alpha"}},
  {"op": "pm.work_item.create", "payload": {"title": "Task 1", "project_id": "@ref:0"}}
]

# After resolution
ops_resolved = [
  {"op": "pm.project.create", "payload": {"name": "Alpha"}, "aggregate_id": "proj_01ABC"},
  {"op": "pm.work_item.create", "payload": {"title": "Task 1", "project_id": "proj_01ABC"}}
]
```

### Error Handling

- **Invalid reference** (`@ref:5` when only 3 ops exist): CompileError with message "Invalid @ref:5 in op 1 - only 3 ops available"
- **Forward reference** (`@ref:2` in op 1): CompileError with message "Forward reference @ref:2 not allowed in op 1"
- **Malformed syntax** (`@ref:abc`): CompileError with message "Malformed reference @ref:abc - must be @ref:N where N is integer"

### Constraints

- References resolved **before** plan building (not at WAL write time)
- No circular dependencies possible (sequential processing)
- Max ops per intent: 100 (prevents excessive reference chains)

---

## AKM Graph Foundation & Field Registry

### Objective
Establish the AKM (Atomic Knowledge Model) substrate with Atom, Link, and Source entities, and create the declarative field registry (pm.fields.yaml) that defines all PM field types, enums, and validation rules.

### Files to Touch
- `local-governor/registries/iglu/org1.workman/atom/jsonschema/1-0-0/schema.json` (create) — Atom entity schema
- `local-governor/registries/iglu/org1.workman/link/jsonschema/1-0-0/schema.json` (create) — Link entity schema
- `local-governor/registries/iglu/org1.workman/source/jsonschema/1-0-0/schema.json` (create) — Source entity schema
- `pm.fields.yaml` (create) — Declarative field definitions for all PM entities

### Implementation Notes
- Atom schema includes atom_type enum (work|concept|entity|note|event), processing_status (unprocessed|triaged|processed), lifecycle_status (active|deprecated|archived)
- Link schema uses unified predicate vocabulary covering work-structural, knowledge, and lifecycle relations
- Source schema supports diverse content types (document|transcript|dataset|audio|video|web_page|other)
- pm.fields.yaml follows declarative pattern with fields[], enums{}, and entities{} sections
- All PM entities get atom_id and optional domain_ref fields for graph integration

### Verification
- `python3 -c "from workman.schema import resolve_schema; schema = resolve_schema('iglu:org1.workman/atom/jsonschema/1-0-0'); print('Atom schema OK')"` → succeeds
- `python3 -c "from workman.schema import resolve_schema; schema = resolve_schema('iglu:org1.workman/link/jsonschema/1-0-0'); print('Link schema OK')"` → succeeds
- `python3 -c "from workman.schema import resolve_schema; schema = resolve_schema('iglu:org1.workman/source/jsonschema/1-0-0'); print('Source schema OK')"` → succeeds
- `ls pm.fields.yaml` → exists
- `python3 -c "import yaml; fields = yaml.safe_load(open('pm.fields.yaml')); print(f'Loaded {len(fields[\"fields\"])} field definitions')"` → loads successfully

---

## Container Ownership Model

### Hierarchy

```
OpsStream (top level)
  └─> Project
      └─> Deliverable
          └─> WorkItem
```

Artifacts can attach to any level: WorkItem, Deliverable, Project, or OpsStream.

### Inheritance Rules

**Principle**: Ownership flows downhill. When an entity belongs to a parent, it inherits the parent's container relationships. **Parent overrides is the real working rule.**

**Examples**:

1. **WorkItem → Project → OpsStream** (inherits OpsStream from Project)
   ```json
   {
     "work_item_id": "wi_01ABC",
     "project_id": "proj_01XYZ",  // Direct ownership
     "opsstream_id": null          // Inherited from project
   }
   ```
   Resolved OpsStream: `project.opsstream_id`

2. **WorkItem → Deliverable → Project → OpsStream** (inherits through chain)
   ```json
   {
     "work_item_id": "wi_01ABC",
     "deliverable_id": "del_01XYZ",  // Direct ownership
     "project_id": null,              // Inherited from deliverable
     "opsstream_id": null             // Inherited from project
   }
   ```
   Resolved chain: WorkItem → Deliverable → Project → OpsStream

3. **Standalone WorkItem → OpsStream** (no project/deliverable)
   ```json
   {
     "work_item_id": "wi_01ABC",
     "opsstream_id": "ops_01XYZ",  // Direct ownership (no parent)
     "project_id": null,
     "deliverable_id": null
   }
   ```
   Allowed when no higher-level parent exists.

### Validation Rules

**No multiple parents at same level**:
- ✗ WorkItem cannot belong to both Project A and Project B
- ✗ Deliverable cannot belong to both Project A and Project B
- ✓ WorkItem can belong to Project AND OpsStream (OpsStream inherited from Project)

**Direct ownership when no parent**:
- ✓ WorkItem with no Deliverable → can set project_id directly
- ✓ WorkItem with no Deliverable or Project → can set opsstream_id directly
- ✗ WorkItem with Deliverable → cannot set project_id (inherited)

**Schema updates needed**:
- **pm.work_item.create**: Allow `project_id` AND `opsstream_id` (inheritance resolves which parent applies)
- **pm.work_item.move**: Allow setting project_id or opsstream_id or both
- **Validation**: If deliverable_id set, project_id and opsstream_id must be null (inherited from deliverable's parent chain)

### BQ View Resolution

**view_pm_work_items**:
```sql
SELECT
  wi.work_item_id,
  wi.title,
  COALESCE(wi.project_id, d.project_id) AS resolved_project_id,
  COALESCE(
    wi.opsstream_id,
    p.opsstream_id,
    d_project.opsstream_id
  ) AS resolved_opsstream_id
FROM work_items wi
LEFT JOIN deliverables d ON wi.deliverable_id = d.deliverable_id
LEFT JOIN projects p ON COALESCE(wi.project_id, d.project_id) = p.project_id
LEFT JOIN projects d_project ON d.project_id = d_project.project_id
```

This resolves the full ownership chain for display/reporting.

---

## PM Domain Expansion - Update Operations & OpsStream

### Objective
Add update operations for existing PM entities (work_item, project, deliverable), introduce OpsStream entity for ongoing operational work, and expand pm.work_item.move to support container reassignment with hierarchical inheritance resolution.

### Files to Touch
- `src/workman/catalog.py` (modify) — Add OpSpec entries for update ops and OpsStream ops
- `local-governor/registries/iglu/org1.workman/opsstream/jsonschema/1-0-0/schema.json` (create) — OpsStream entity schema
- `local-governor/registries/iglu/org1.workman/pm.work_item.update/jsonschema/1-0-0/schema.json` (create) — Update op request schema
- `local-governor/registries/iglu/org1.workman/pm.project.update/jsonschema/1-0-0/schema.json` (create) — Project update request schema
- `local-governor/registries/iglu/org1.workman/pm.deliverable.update/jsonschema/1-0-0/schema.json` (create) — Deliverable update request schema
- `local-governor/registries/iglu/org1.workman/pm.opsstream.create/jsonschema/1-0-0/schema.json` (create) — OpsStream create request schema
- `local-governor/registries/iglu/org1.workman/pm.opsstream.update/jsonschema/1-0-0/schema.json` (create) — OpsStream update request schema
- `local-governor/registries/iglu/org1.workman/pm.work_item.cancel/jsonschema/1-0-0/schema.json` (create) — Cancel op request schema
- `local-governor/registries/iglu/org1.workman/pm.deliverable.reject/jsonschema/1-0-0/schema.json` (create) — Reject op request schema
- `local-governor/registries/iglu/org1.workman/pm.opsstream.close/jsonschema/1-0-0/schema.json` (create) — OpsStream close request schema

### Implementation Notes
- Update ops use partial payload schemas (all fields optional except ID)
- OpsStream entity includes type (CLINICAL_OPS|CONSULTING_OPS|INTERNAL_OPS|OTHER) and status (ACTIVE|PAUSED|CLOSED)
- pm.work_item.move validation enforces hierarchical inheritance: ownership flows downhill, parent overrides is the real working rule
- Cancel, reject, close ops include optional timestamps and reason fields
- All new entities auto-generate atom_id and derive label from name/title
- OpSpec entries reuse generic_pm_builder pattern

### Verification
- `python3 -c "from workman.catalog import get_op_spec; spec = get_op_spec('pm.work_item.update'); print(f'Update op: {spec.op}')"` → pm.work_item.update
- `python3 -c "from workman.catalog import get_op_spec; spec = get_op_spec('pm.opsstream.create'); print(f'OpsStream create: {spec.id_prefix}')"` → ops
- `python3 -c "from workman import execute; result = execute({'op': 'pm.work_item.update', 'payload': {'work_item_id': 'wi_test', 'title': 'Updated title'}, 'ctx': {}}); print('Update compiles')"` → succeeds

## Artifact Domain Model

### Objective
Add Artifact entity with dual content strategy (WAL-native inline content + delivered content_ref), seven lifecycle operations (create, update, finalize, deliver, defer, supersede, archive), and container FK validation requiring at least one link to work_item, deliverable, project, or opsstream.

### Files to Touch
- `src/workman/catalog.py` (modify) — Add artifact OpSpec entries (7 ops)
- `local-governor/registries/iglu/org1.workman/artifact/jsonschema/1-0-0/schema.json` (create) — Artifact entity schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.create/jsonschema/1-0-0/schema.json` (create) — Create request schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.update/jsonschema/1-0-0/schema.json` (create) — Update request schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.finalize/jsonschema/1-0-0/schema.json` (create) — Finalize request schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.deliver/jsonschema/1-0-0/schema.json` (create) — Deliver request schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.supersede/jsonschema/1-0-0/schema.json` (create) — Supersede request schema
- `local-governor/registries/iglu/org1.workman/pm.artifact.archive/jsonschema/1-0-0/schema.json` (create) — Archive request schema
- `src/workman/builders.py` (modify) — Add container FK validation for artifact.create

### Implementation Notes
- Artifact status flows: DRAFT → FINAL → DELIVERED, with SUPERSEDED/ARCHIVED as terminal states
- Content strategy: content (inline markdown) vs content_ref (external URL) - both can coexist
- Container FK validation: at least one of work_item_id, deliverable_id, project_id, opsstream_id required
- pm.artifact.deliver records delivery metadata but does NOT perform delivery (egret's job in e010)
- Status transitions via dedicated ops (finalize, deliver, supersede, archive), not update
- artifact_kind enum includes SESSION_NOTE, REPORT, TEMPLATE, CORRESPONDENCE, POLICY, INTAKE, MEMO, OTHER

### Verification
- `python3 -c "from workman.catalog import get_op_spec; spec = get_op_spec('pm.artifact.create'); print(f'Artifact prefix: {spec.id_prefix}')"` → art
- `python3 -c "from workman import execute; result = execute({'op': 'pm.artifact.create', 'payload': {'title': 'Test Note', 'kind': 'SESSION_NOTE', 'work_item_id': 'wi_123', 'content': '# Meeting Notes'}, 'ctx': {}}); print('Artifact creates')"` → succeeds
- `python3 -c "from workman.schema import resolve_schema; schema = resolve_schema('iglu:org1.workman/artifact/jsonschema/1-0-0'); print('status' in schema['properties'])"` → True

---

## Artifact Lifecycle State Machine

### States

- **DRAFT**: Initial state, content under development
- **DEFERRED**: Work paused, not finalized
- **FINAL**: Content locked, ready for delivery
- **DELIVERED**: External copy sent via delivery channel
- **SUPERSEDED**: Replaced by newer artifact (terminal)
- **ARCHIVED**: Removed from active use (terminal, delivered artifacts only)

### State Transitions

```
DRAFT ───finalize────> FINAL ───deliver────> DELIVERED ───archive────> ARCHIVED
  │                      │
  └──────supersede──────>│
  │                      │
  └──────defer──────────> DEFERRED ───supersede────> SUPERSEDED
                            │                          (terminal)
                            └──────finalize───────> FINAL
```

### Transition Rules

| From State | To State | Operation | Notes |
|------------|----------|-----------|-------|
| DRAFT | FINAL | pm.artifact.finalize | Recommended path |
| DRAFT | DELIVERED | pm.artifact.deliver | Direct delivery (skip finalize) |
| DRAFT | SUPERSEDED | pm.artifact.supersede | Abandon draft |
| DRAFT | DEFERRED | pm.artifact.defer | NEW op needed |
| FINAL | DELIVERED | pm.artifact.deliver | Standard path |
| FINAL | SUPERSEDED | pm.artifact.supersede | Replace without delivery |
| DELIVERED | ARCHIVED | pm.artifact.archive | Only delivered can archive |
| DEFERRED | FINAL | pm.artifact.finalize | Resume work |
| DEFERRED | SUPERSEDED | pm.artifact.supersede | Abandon deferred work |

### Operation Constraints

- **finalize**: Only from DRAFT or DEFERRED → FINAL
- **deliver**: Only from DRAFT or FINAL → DELIVERED
- **supersede**: From DRAFT, FINAL, or DEFERRED → SUPERSEDED (terminal)
- **archive**: Only from DELIVERED → ARCHIVED (terminal)
- **defer** (NEW): From DRAFT → DEFERRED

### Invalid Transitions (Validation Errors)

- ✗ DELIVERED → FINAL (cannot un-deliver)
- ✗ SUPERSEDED → any (terminal state)
- ✗ ARCHIVED → any (terminal state)
- ✗ DRAFT → ARCHIVED (must deliver first)
- ✗ DEFERRED → DELIVERED (must finalize first)

### Implementation

Validation enforced in workman OpSpec:
```python
ARTIFACT_TRANSITIONS = {
    "DRAFT": ["FINAL", "DELIVERED", "SUPERSEDED", "DEFERRED"],
    "DEFERRED": ["FINAL", "SUPERSEDED"],
    "FINAL": ["DELIVERED", "SUPERSEDED"],
    "DELIVERED": ["ARCHIVED"],
    "SUPERSEDED": [],  # terminal
    "ARCHIVED": [],    # terminal
}
```

---

## AKM Relations & PMIntent Compilation

### Objective
Implement link.create and link.remove operations using unified predicate vocabulary, add compile_intent() module for bulk PMIntent processing with diff generation and plan hashing returning CallableResult.

### Files to Touch
- `src/workman/intent.py` (create) — PMIntent compilation module
- `src/workman/__init__.py` (modify) — Export compile_intent (returns CallableResult)
- `src/workman/catalog.py` (modify) — Add link.create and link.remove OpSpec entries
- `local-governor/registries/iglu/org1.workman/link.create/jsonschema/1-0-0/schema.json` (create) — Link creation request schema
- `local-governor/registries/iglu/org1.workman/link.remove/jsonschema/1-0-0/schema.json` (create) — Link removal request schema
- `local-governor/registries/iglu/org1.workman/pmintent/jsonschema/1-0-0/schema.json` (create) — PMIntent envelope schema
- `src/workman/builders.py` (modify) — Add link validation for work-structural predicates

### Implementation Notes
- compile_intent(intent: dict) -> CallableResult processes N ops in single transaction
- CallableResult contains items (StoraclePlan list), diff (human-readable strings), plan_hash: str (SHA256)
- Link operations validate predicate vocabulary and atom existence
- Work-structural predicates (blocks, depends_on, part_of) require both atoms to be atom_type=work
- Bridge predicates (implements, applies, refines) accept cross-type atoms for future AKM use
- PMIntent schema includes intent_id, ops[], description, source, actor, issued_at

### Verification
- `python3 -c "from workman import compile_intent; result = compile_intent({'intent_id': 'pmi_test', 'ops': [{'op': 'pm.work_item.create', 'payload': {'title': 'Test'}}], 'description': 'Test intent', 'source': 'test', 'actor': {'actor_type': 'human', 'actor_id': 'test'}, 'issued_at': '2026-02-11T21:45:00Z'}); print(f'Plans: {len(result.plans)}')"` → Plans: 1
- `python3 -c "from workman.catalog import get_op_spec; spec = get_op_spec('link.create'); print(spec.aggregate_type)"` → link
- `python3 -c "from workman import execute; result = execute({'op': 'link.create', 'payload': {'from_atom_id': 'atom_1', 'to_atom_id': 'atom_2', 'predicate': 'depends_on'}, 'ctx': {}}); print('Link creates')"` → succeeds

## Test Coverage & Integration

### Objective
Add comprehensive test coverage for all new operations, PMIntent compilation, artifact lifecycle, content strategies, container FK validation, and AKM link validation. Ensure all existing tests continue to pass.

### Files to Touch
- `tests/test_intent.py` (create) — PMIntent compilation and diff generation tests
- `tests/test_artifacts.py` (create) — Artifact lifecycle and content strategy tests
- `tests/test_links.py` (create) — AKM Link creation and predicate validation tests
- `tests/test_updates.py` (create) — Update operation tests
- `tests/test_opsstream.py` (create) — OpsStream entity tests
- `tests/test_catalog.py` (modify) — Add tests for new OpSpec entries

### Implementation Notes
- Test PMIntent with single op, multi-op, and cross-references (@ref:0 syntax)
- Test artifact dual content strategy (WAL-native, delivered, both)
- Test container FK validation (at least one FK required, assert.exists generated)
- Test Link predicate vocabulary and atom_type validation
- Test update operations with partial payloads
- Verify diff output format and plan_hash generation

### Verification
- `pytest tests/test_intent.py -v` → all tests pass
- `pytest tests/test_artifacts.py -v` → all tests pass
- `pytest tests/test_links.py -v` → all tests pass
- `pytest tests/ -v` → all existing and new tests pass
- `ruff check src/workman/` → clean

## workman.build.yaml Diff (Post-e011)

The workman.build.yaml file will be updated to reflect the new modules and API surface:

```yaml
# ADDITIONS to kernel.surfaces.entrypoints:
kernel:
  surfaces:
    - name: python_api
      entrypoints:
        # Existing
        - import: "from workman import compile"
          usage: "plan = compile('pm.work_item.create', payload, ctx)"
        - import: "from workman import execute"
          usage: "result = execute({'op': 'pm.work_item.create', 'payload': {...}, 'ctx': {...}})"
        # NEW in e011
        - import: "from workman import compile_intent"
          usage: "result = compile_intent({'intent_id': '...', 'ops': [...]})"

# UPDATES to boundaries:
boundaries:
  # Existing
  - name: python_api
    type: inbound
    contract: "compile(op, payload, ctx, pins=None) -> Storacle plan"
    consumers:
      - "life"
      - "lorchestra (via callable)"
      - "tests"

  - name: execute_api
    type: inbound
    contract: "execute(params) -> domain event items"
    consumers:
      - "life (direct invocation)"
      - "tests"

  # NEW in e011
  - name: intent_api
    type: inbound
    contract: "compile_intent(intent: dict) -> CallableResult (with items, diff, plan_hash)"
    consumers:
      - "lorchestra (via call op with callable: workman)"
      - "tests"

# ADDITIONS to layout:
layout:
  # Existing modules (all unchanged)
  - path: "src/workman/__init__.py"
    module: public_surface
    role: "Public API: compile, execute, compile_intent"
  # ... existing modules unchanged ...

  # NEW in e011
  - path: "src/workman/intent.py"
    module: intent
    role: "compile_intent() — PMIntent dict to CallableResult (plans + diff + plan_hash in result fields)"
  - path: "pm.fields.yaml"
    module: field_registry
    role: "Declarative PM field definitions (enums, types, editability, defaults)"

# ADDITIONS to modules:
modules:
  # Existing public_surface UPDATED:
  - name: public_surface
    kind: entrypoint
    provides:
      - "compile"
      - "execute"
      - "compile_intent"  # NEW
    depends_on:
      - compile
      - execute
      - intent  # NEW
      - catalog
      - schema
      - assertions
      - ids

  # NEW MODULE in e011:
  - name: intent
    kind: module
    provides:
      - "compile_intent(intent: dict) -> CallableResult"
      - "CallableResult with items (plans), diff, and plan_hash fields"
    depends_on:
      - compile
      - catalog
      - ids

  # NEW CONFIG in e011:
  - name: field_registry
    kind: config
    provides:
      - "PM field definitions (kind, state, priority, severity, labels, etc.)"
      - "Artifact entity definition, artifact_kind enum, artifact_status enum, delivered_via enum"
      - "OpsStream entity definition, opsstream_type enum, opsstream_status enum"
      - "AKM entity definitions (Atom, Link, Source)"

  # Existing modules UPDATED:
  - name: catalog
    kind: module
    provides:
      - "OpSpec (dataclass)"
      - "OP_CATALOG"  # NOW includes ~17 new PM+AKM+artifact ops
      - "get_op_spec(op) -> OpSpec | None"

  # ... remaining existing modules unchanged ...
```

## Additional Context (Feedback/Requirements)

This spec implements the AKM graph foundation where every entity is an atom with global identity (atom_id) and optional external traceability (domain_ref). PM relations become AKM Links using unified predicate vocabulary, creating a universal substrate for future knowledge management. The artifact domain model supports dual content strategy for both inline WAL-native content and external delivered references. PMIntent provides bulk operation capability with diff preview and audit hashing. The declarative field registry (pm.fields.yaml) centralizes all PM field definitions, types, and validation rules in a single configuration file.