# ArchGram MVP - Build Plan

**Created**: 2026-04-09
**Last Updated**: 2026-04-17
**Project**: ArchGram - Enterprise IT Architecture Diagram Generator
**Location**: `/home/marek/Projects/ArchGramMVP/`
**GitHub**: https://github.com/marekhulva/ArchGramMVP (private)

---

## Recent Changes

- **2026-04-17**: Component model refactor. Replaced hand-coded "detail level"
  render functions with declarative components (`components/` package). Each
  component declares its own `preferred_size()` / `min_size()` / `render()` and
  composes via `VStack` / `HStack`. Layout engine now centers sites at natural
  size — no more stretching. The 1-site sizing bug that motivated the refactor
  is fixed as a side effect. Multi-density variants and 2D grid packing are
  documented below as deferred work.

---

## What We're Building

A tool that generates professional, dark-themed IT architecture diagrams as fully editable PowerPoint files. Users describe their infrastructure (via form or natural language), see a live canvas preview, and download a .pptx where every shape, line, and text box is editable.

**One JSON data model is the single source of truth.** It renders to both a browser canvas (Fabric.js) and a PowerPoint file (python-pptx).

---

## Core Architecture (3 Modules)

```
User Input → AI Parser → Design Tokens + Layout Engine → Renderer (Canvas + PPTX)
```

### Module 1: Parser
- AI (Claude API) converts natural language into structured graph JSON
- Outputs: nodes, edges, grouping, relationships
- AI decides MEANING only — never pixels, sizes, or colors
- Strict output schema — only approved component types and fields

### Module 2: Layout Engine
- Rule-based + constraint-based (NOT AI, NOT hardcoded if-then)
- Each component has: minWidth, minHeight, preferredWidth, preferredHeight, canShrink, canGrow
- Layout families: linear, mirrored DR, hub-and-spoke, grouped multi-tenant, etc.
- Handles variable counts (1 Azure tenant = large box, 3 = smaller grouped boxes)
- Fallback tiers: standard → compact → wrapped → split to second slide

### Module 3: Renderer (Dumb Drawer)
- Takes fully positioned JSON + design tokens → draws shapes
- Canvas renderer: Fabric.js (live preview, drag-and-drop)
- PPTX renderer: python-pptx (editable PowerPoint output)
- Design tokens: lookup table (azure = blue + Azure logo, aws = orange + AWS logo, etc.)
- Renderer makes ZERO layout decisions

---

## Component Model (Canonical Architecture)

This is **how we actually build things now**. Every diagram primitive — a
workload chip, an HSX table, a whole data center — is a `Component` object
with three responsibilities:

```python
class Component:
    def preferred_size(self) -> (w, h)            # natural visual size in inches
    def min_size(self)       -> (w, h)            # smallest it can shrink to
    def render(self, x, y, w, h) -> [shape dicts] # paint into the given box
    def variants(self) -> [(name, w, h), ...]     # density options (default: just 'full')
```

### Composition

Components are composed of other components. A site is a `VStack` of sub-zones.
A sub-zone is a `VStack` of a header bar + content. Content is a row (`HStack`)
of chips. The leaves emit shape dicts. The composites delegate to their children.

This means:
- **Adding a new component (cloud, M365, AirGap) = one new file in `components/`.**
- **Sizing is automatic** — the parent asks each child its preferred size, sums
  them, that's the parent's size.
- **No render function ever calculates "where am I on the slide?"** — it gets
  told `(x, y, w, h)` and paints into that box. The layout engine owns position.

### Files

```
components/
  base.py            ← Component base class + shape helpers (rect/text/oval/image)
  tokens.py          ← COLORS, IMAGES, FONT, SPACE
  layout_helpers.py  ← VStack, HStack
  workload_chip.py   ← WorkloadChip (leaf)
  header_bar.py      ← HeaderBar (leaf)
  hsx_table.py       ← HSXTable (leaf)
  pure_target.py     ← PureStorageTarget (leaf)
  status_label.py    ← ProtectionStatus (leaf)
  clients_box.py     ← ClientsAndStorage (composite: header + chips + summary)
  backup_stack.py    ← BackupSoftwareStack (composite: logo + label + badge)
  protected_layer.py ← ProtectedDataLayer (composite: header + target body)
  site.py            ← OnPremSite (composes the four sub-zones above)
layout_engine.py     ← Builds component tree, asks preferred sizes, centers, emits shapes
renderer_pptx.py     ← Shape list → PPTX (unchanged — already shape-list based)
templates/index.html ← Shape list → Fabric.js canvas (unchanged)
```

### Sizing rule (this is what fixed the 1-site bug)

The layout engine **never stretches** components. It asks each site for its
preferred size, packs them with gaps, and **centers the cluster** in the usable
slide area. Whitespace lives outside containers, not inside them. If something
doesn't fit at preferred size, the engine drops to a smaller variant
(`variants()` — see "Future: Multi-Site Density Layouts" below).

---

## Tech Stack

| Layer    | Technology           | Why                                              |
|----------|----------------------|--------------------------------------------------|
| Frontend | Vanilla HTML/JS/CSS  | No framework overhead, fast vibe-coding iteration |
| Canvas   | Fabric.js 5.3.1      | 2D rendering, drag-and-drop, PNG export          |
| Backend  | Python 3 + Flask     | Lightweight, handles PPTX endpoint               |
| PPTX     | python-pptx + lxml   | Real editable PowerPoint with XML-level control  |
| AI       | Claude API           | Natural language → JSON parsing                  |

---

## Two-Stage JSON Model

### Stage 1: Semantic JSON (what the user means)
```json
{
  "nodes": [
    { "id": "dc1", "type": "site", "platform": "onprem", "label": "Primary DC" },
    { "id": "az1", "type": "cloudZone", "provider": "azure", "label": "Azure Tenant" }
  ],
  "edges": [
    { "from": "dc1", "to": "az1", "relation": "replication" }
  ]
}
```

### Stage 2: Positioned JSON (what gets rendered)
```json
{
  "type": "site",
  "platform": "onprem",
  "label": "Primary DC",
  "x": 40,
  "y": 80,
  "width": 340,
  "height": 450
}
```

Flow: user input → AI → semantic JSON → layout engine → positioned JSON → renderer

---

## Design Token System

Deterministic lookup — never AI-decided:

```js
providerStyles = {
  azure:    { fill: "#0F6CBD", stroke: "#2B88D8", icon: "azure_logo.svg", textColor: "#FFF" },
  aws:      { fill: "#FF9900", stroke: "#FFB84D", icon: "aws_logo.svg", textColor: "#FFF" },
  gcp:      { fill: "#4285F4", stroke: "#669DF6", icon: "gcp_logo.svg", textColor: "#FFF" },
  onprem:   { fill: "#1A1A2E", stroke: "#6C3AED", icon: null, textColor: "#FFF" },
  commvault: { fill: "#6C3AED", stroke: "#8B5CF6", icon: "commvault_logo.svg", textColor: "#FFF" }
}
```

---

## Component Rules Per Scenario (PAUSED — BASICS DONE, RESUME LATER)

**This is the domain knowledge layer — what components belong in each context.**
**Built by walking through PPT Template Slide 6 with Marek.**

### ⏸️ RESUME POINT — READ THIS WHEN COMING BACK

**Status**: On-Prem Data Center recipe is PARTIALLY defined (basics only).
We stopped here to test the layout engine with what we have.

**What's DONE**:
- ✅ Universal container rule (transparent, white border, dynamic sizing)
- ✅ Top bar color rule (purple = Commvault, grey = non-Commvault)
- ✅ Clients & Protected Storage sub-box (workload chips, summary line)
- ✅ Backup Software Stack (Commvault fully defined, other vendors = backlog)
- ✅ Backup Target sub-box (HSX table fully defined, Pure Storage icon extracted)
- ✅ Status Labels (green = good, red = gaps)
- ✅ Stacking order: Clients & Protected Storage → Backup Software Stack → Backup Target → Status Labels
- ✅ Storage card noted but NOT yet defined (vendor + product + capacity)

**What STILL NEEDS DEFINING** (come back here after layout engine works):
- [ ] Storage card details (Dell, NetApp, Pure, etc. — visual spec + rules)
- [ ] Cloud Environment recipe (Azure/AWS/GCP — same container, provider-specific styling)
- [ ] DR Site recipe (mirrors primary, what's different?)
- [ ] M365/SaaS recipe (M365 block, AD/Entra ID, user counts)
- [ ] Air-Gap / Immutable Storage recipe (AirGap Protect, Cloud Cleanroom)
- [ ] Security Stack recipe (Anomaly Detection, Threat Analysis, DSPM tables)
- [ ] Data Flow connectors (dashed arrows, numbered ovals, routing rules)
- [ ] Design Notes sidebar
- [ ] Slide Title component
- [ ] Commvault banner
- [ ] Current State vs Future State visual differences (full pass)
- [ ] Default components when user just says "add a DC" with no details

**HOW TO RESUME**: Walk through PPT Template slides with Marek, same as before.
Record each component with: what it is, what it looks like (from extraction), 
when it appears (rules), and what goes inside it. Add to this section, 
under the appropriate scenario heading below.

**WHERE TO WRITE**: Add new recipes under the scenario headings below 
(Cloud Environment, DR Site, M365, etc.) using same format as On-Prem recipe.

### Universal Container Rule
**Any large environment** (On-Prem Site, Azure Site, AWS Site) gets wrapped in the same container type:
- Container: **TRANSPARENT** fill (blends with dark background), **visible white border/outline**
- Shape: Rectangle or square depending on content inside
- Label above container with purple underline (Future State) or grey (Current State)
- Container **sizes dynamically** — taller if more components, shorter if fewer

### On-Prem Data Center Recipe

```
ON-PREM DATA CENTER:
├── Container: Transparent, white border outline
├── Label: "[user-provided name]" (e.g., "Primary DC", "DR Site")
├── STACKING ORDER (top to bottom, fixed):
│   1. Clients & Protected Storage (TOP)
│   2. Backup Software Stack (MIDDLE)
│   3. Backup Target (BOTTOM)
│   4. Status Labels (BELOW CONTAINER)
│   └── If any section is missing, ones below move up, container shrinks
│
├── IF APPLICABLE: "Clients & Protected Storage" sub-box
│   ├── Style: Transparent body, top bar with label
│   │   ├── CURRENT STATE: Grey top bar, white text
│   │   └── FUTURE STATE (Commvault): Purple top bar, white text
│   │
│   ├── Workload chips (user selects which apply):
│   │   ├── KNOWN (from template, have icons): Files, Devices, Database, VMs, Applications
│   │   ├── FUTURE: SAP, Oracle, Exchange, Linux, NAS, and others — need icons (see backlog)
│   │   └── Each chip: black rectangle + icon + white label (8pt Arial)
│   │
│   ├── Summary line: "[X] VMs | [X]TB" (user provides numbers)
│   │   └── May also include: Physical Servers count, File/Object data amounts
│   │   └── Exact format TBD — user always provides the numbers
│   │
│   └── Input method: Manual form OR AI engine parses user description
│
├── IF has storage: Storage card (vendor + product + capacity)
│   └── (Details TBD — next to define)
│
├── IF has backup software: **Backup Software Stack**
│   ├── What it is: Visual representation of the backup software at this site
│   ├── Structure: UI screenshot + server badge (abbreviation) + lock icon
│   ├── COMMVAULT: Command Center screenshot, "CS" purple badge, lock icon
│   │   ├── Colors: Purple (#7030A0 fill, #834895 border), white text
│   │   ├── DR variant: Label says "Command Center (Standby)"
│   │   └── Exact visual match to template Slide 6 Shape 56
│   ├── OTHER VENDORS (Veeam, Avamar, Rubrik, etc.): Same structure,
│   │   different UI screenshot, different badge abbreviation
│   │   └── DEFINE LATER — same component, just swap images/text per vendor
│   └── Only appears if customer has backup software at this site
│
├── IF has local backup target: **Backup Target** sub-box
│   ├── Style: Transparent body, white border outline
│   ├── Top bar: Same rule — purple (Commvault) or grey (non-Commvault)
│   ├── Label: "Protected Data Layer" (or contextual name)
│   │
│   ├── IF HyperScale X (HSX):
│   │   ├── TABLE: rows × 2 columns
│   │   ├── Each NODE = 2 rows (2U server units)
│   │   │   Row 1: [slot#] | [HSX - 0X] ← purple fill (#7030A0)
│   │   │   Row 2: [slot#] | [blank]     ← purple fill (#7030A0)
│   │   ├── Active nodes: purple fill, node label
│   │   ├── Empty slots: dark fill, "Future expansion"
│   │   ├── MVP: Fixed 12 rows (6-node max capacity)
│   │   ├── User provides: node count + usable TB
│   │   ├── Dynamic: "4 nodes" → 8 purple rows + 4 empty rows
│   │   ├── Font: 6pt Arial white
│   │   └── Label below: "[X]-Node HSX Appliance | [X]TB Usable"
│   │       (8pt bold Arial, #E6E8F0)
│   │
│   ├── IF Pure Storage:
│   │   ├── Pure Storage logo image (extracted from Slide 5, Shape 57)
│   │   ├── Saved: assets/vendor-icons/pure_storage.png
│   │   ├── Size in template: 1.39" × 0.53"
│   │   └── Just the logo inside the Backup Target box (no node table)
│   ├── IF other backup target (non-HSX, non-Pure): TBD — define later
│   │
│   └── Protection status labels (below target)
│   └── NOTE: If no local target (everything to cloud), this section is OMITTED
│         and the container is SHORTER
│
└── Callouts (conditional):
    ├── IF protected: Green callout ("All Backups Immutable")
    └── IF gaps exist: Red callouts ("Not Immutable", "No Detection")
```

### Cloud Environment (Azure/AWS/GCP)
- [ ] Define — uses same universal container rule
- [ ] Provider-specific styling (blue for Azure, orange for AWS, etc.)

### DR Site
- [ ] Define — likely mirrors primary DC structure

### M365/SaaS
- [ ] Define

### Air-Gap / Immutable Storage
- [ ] Define

### Security Stack
- [ ] Define

---

## BACKLOG — Future Enhancements

### Workload Icon Expansion
- **Priority**: After MVP functionality is proven
- **Problem**: Template only has 5 workload types with icons (Files, Devices, Database, VMs, Applications)
- **Need**: Users will request SAP, Oracle, Exchange, Linux, NAS, Kubernetes, and others
- **Solution**: Define icon set for each workload type. Options:
  - Vendor-provided SVG icons
  - Iconify library (has most enterprise vendor icons)
  - Custom simple icons matching template style
- **Rule**: Every workload chip must have an icon + label, same visual style as existing ones
- **NOTE**: Do not block MVP on this. MVP ships with the 5 known workloads. Others get a generic server icon + custom label until proper icons are added.

### Workload Summary Line Flexibility
- **Priority**: After MVP
- **Current**: "100 VMs | 10TB Physical Servers"
- **Need**: Flexible format — sometimes no physical servers, sometimes File/Object data
- **Solution**: User provides the numbers, system formats them

### HSX Table — More Than 6 Nodes
- **Priority**: Much later
- **Problem**: MVP caps at 12 rows (6 nodes). Some customers could have more.
- **Solution**: Expand table beyond 12 rows dynamically
- **NOTE**: Do NOT solve this now. MVP = 6 node max. Revisit only if real users need it.

### Non-HSX Backup Targets
- **Priority**: After MVP
- **Problem**: Backup Target box currently only defines HSX visual. Other targets (generic disk, NAS, tape, etc.) need their own visual representation.
- **Solution**: Define alternate visual for non-HSX backup targets

### Backup Software Stack — Other Vendors
- **Priority**: After MVP
- **Problem**: Only Commvault is fully defined (Command Center screenshot, CS badge, lock icon)
- **Need**: Veeam, Avamar, Rubrik, Cohesity, Veritas, etc.
- **Solution**: Same component structure, swap UI screenshot + badge abbreviation per vendor

---

## Layout Engine Rules

The current engine is a 1D horizontal packer:
1. Build component tree from scenario JSON.
2. Ask each site its `preferred_size()`.
3. Sum widths + gaps → total content width.
4. Center the cluster horizontally in `USABLE_W`, vertically in `USABLE_H`.
5. Emit shape list.

If sites don't fit at preferred size, the current engine truncates and shows
an overflow note. **The proper fix is the deferred work below.**

### Layout Families (aspirational — not all built)
- **linear** ← built (1D row, centered)
- **grid** ← deferred (2D row × col packer — see Multi-Site Density)
- **mirrored_dr**: primary + DR side by side, with data-flow arrows
- **hub_and_spoke**: central hub with satellite nodes
- **grouped_multi_tenant**: grouped repeated items (e.g., 3 Azure tenants)
- **layered**: top-down layers (control plane → sites → security)

---

## Future: Multi-Site Density Layouts (DEFERRED)

**Status**: Not built. Documented here so the design isn't re-relitigated.

**Trigger to revisit**: A real user hits the 6+ site case, OR we decide to
demo a "global enterprise" scenario with many regions.

### The problem

The current engine handles 1-3 sites at full detail beautifully. At 4+ sites,
they don't fit horizontally at preferred size. Real PPT decks solve this by:
- Going to multiple rows on one slide (2×3, 3×4, etc.)
- Reducing each site's visual density (drop chips, drop logos, keep counts)
- Splitting to multiple slides as a last resort

### The design

**1. Each component declares variants.** Site grows multiple `_render_X()`
methods, one per density:

| Variant   | Size (~)    | Bricks shown                                                        |
|-----------|-------------|---------------------------------------------------------------------|
| full      | 3.0 × 4.7"  | Label + ClientsBox + BackupStack + HSXTable + Status                |
| reduced   | 2.3 × 3.5"  | Label + Workload chips row + Vendor badge + HSX text + Status (sm)  |
| compact   | 1.5 × 2.5"  | Label + Workload icon row + VM/TB count + Vendor badge              |
| tile      | 1.0 × 1.5"  | Label + VM count + Vendor badge                                     |

Each variant uses **different bricks** (not the same bricks resized).

**2. Must-keep info hierarchy** (drops in this order as density tightens):
1. Site name — always visible
2. VM count + TB total — always visible
3. Vendor identifier (CV badge) — always visible
4. Workload types (icons → chips → labeled chips) — drops at tile
5. Backup target capacity (e.g., "3-Node HSX | 150TB") — drops at compact
6. Sub-zone headers + container structure — drops at reduced
7. Logo images, status text — drops at compact

At every density you still know: *which site, how big, what workloads, what vendor*.

**3. Grid packer in the layout engine.**

```
For each candidate (rows × cols) where rows × cols ≥ N:
  cell_w = (USABLE_W − col_gaps) / cols
  cell_h = (USABLE_H − row_gaps) / rows
  Find DENSEST variant where (variant_w ≤ cell_w AND variant_h ≤ cell_h)
  Score = (density_rank, balance_score)
Pick the highest-scoring (rows × cols × variant) combo.
```

**Worked example: 12 sites**

| Grid | Cell size      | Best fit variant | Verdict                              |
|------|----------------|------------------|--------------------------------------|
| 2×6  | 1.86 × 2.90"  | **compact**      | ✓ winner — workload icons still shown|
| 3×4  | 2.96 × 1.83"  | tile only        | too short for compact                |
| 4×3  | 4.04 × 1.30"  | tile only        | wasted width                         |

So 12 sites → 2×6 in compact density.

### What needs to be built (when triggered)

1. **`Component.variants()`** — already stubbed in `base.py` returning
   `[('full', preferred_w, preferred_h)]`. Site overrides to declare
   multiple variants.
2. **New leaf bricks for compact/tile**: `WorkloadIconRow`, `VendorBadge`,
   `VMCountText`. Small, single-purpose.
3. **Site `_render_full()` / `_render_reduced()` / `_render_compact()` /
   `_render_tile()`** methods, each composing the appropriate bricks.
4. **Grid packer in `layout_engine.py`** — replaces current `_pack_sites()`.
   Tries (rows × cols × variant), picks densest fit.
5. **Multi-slide fallback** — if grid still doesn't fit, overview slide +
   detail slides (2-3 full per slide).

---

## AI Parser Rules (System Prompt Guidelines)

When parsing user input, AI must:
- Only output valid JSON matching our schema
- Only use approved component types
- Never decide pixel values, colors, or sizes
- If user is vague, make safest reasonable assumption
- Infer relationships from context (e.g., "backup to Azure" = dataFlow edge)

AI CAN suggest:
- Layout family
- Grouping of repeated items
- Relative importance of components
- Region preferences (left, center, right)

---

## PPTX Coordinate System

```
Slide: 13.33" x 7.5" = 1280 x 720 px canvas
914400 EMU = 1 inch

SCALE_X = 13.33 / 1280  (0.01041 inches per pixel)
SCALE_Y = 7.5 / 720     (0.01042 inches per pixel)

px_to_emu_x(val) = int(val * SCALE_X * 914400)
px_to_emu_y(val) = int(val * SCALE_Y * 914400)
```

---

## Component Types (15+)

### Container Components
- **zone** — data center / site boundary
- **cloudZone** — cloud provider area (gradient fill, nested items)
- **subZone** — nested section within zones (Clients, Protected Data)

### Content Components
- **serverRow** — row of workload icons (VMs, Files, SQL, Mail, Linux)
- **storageBlock** — storage product (Dell PowerStore, Pure, NetApp + capacity)
- **backupProduct** — backup software (Commvault, Veeam, Rubrik)
- **protectedLayer** — data protection status (Immutable, Deduped, Encrypted)
- **securityTable** — security feature (Anomaly Detection, Threat Analysis)
- **airgapSection** — air-gapped immutable storage with break symbol
- **m365Block** — M365 + AD/Entra ID protection
- **hxsTable** — HSX appliance node grid
- **controlPlane** — purple bar spanning zones
- **designNotes** — sidebar with text notes
- **callout** — warning/success/info annotations

### Connectors
- **dataFlow** — dashed arrow with numbered oval and label

---

## Build Order

### Done ✓
- [x] Project structure + Flask app + dual-renderer pipeline (canvas + PPTX)
- [x] Design tokens (`components/tokens.py`)
- [x] Component model + base class + VStack/HStack
- [x] Leaf components: `WorkloadChip`, `HeaderBar`, `HSXTable`, `PureStorageTarget`, `ProtectionStatus`
- [x] Composite components: `ClientsAndStorage`, `BackupSoftwareStack`, `ProtectedDataLayer`
- [x] Site composite: `OnPremSite`
- [x] Layout engine v1 — 1D centered packer (no stretching)

### Next up — new component types
Each becomes one new file in `components/`, one `class CloudSite(Component)` etc.
- [ ] **`CloudSite`** (Azure / AWS / GCP) — same container shape, provider-specific styling (blue/orange/red), gradient fill option
- [ ] **`DRSite`** — explicit DR variant of `OnPremSite` (or just a `mode='dr'` flag — TBD)
- [ ] **`M365Block`** — rounded rect, M365 + AD/Entra Id split, user counts
- [ ] **`AirGapBlock`** — AirGap Protect + Cleanroom table, lightning-bolt break symbol
- [ ] **`SecurityStack`** — Anomaly Detection / Threat Analysis tables
- [ ] **`StorageCard`** — Dell / NetApp / Pure Storage product card (the one TODO from on-prem recipe)

### Connectors + page chrome
- [ ] **`DataFlowArrow`** — dashed arrow + numbered oval + label
- [ ] **`SlideTitle`** — already inline in layout engine; pull into a real component
- [ ] **`CommvaultBanner`** — top-center logo image
- [ ] **`DesignNotesSidebar`** — left sidebar text box

### Layout engine evolution
- [ ] **2D grid packer** — rows × cols, tries each and picks best fit (see "Future: Multi-Site Density")
- [ ] **Multi-density variants on `OnPremSite`** — `full` / `reduced` / `compact` / `tile`
- [ ] **Layout families** — `mirrored_dr`, `hub_and_spoke`, `grouped_multi_tenant`
- [ ] **Multi-slide fallback** — overview + detail slides when single slide can't hold it

### AI parser
- [ ] Claude API integration (system prompt drives natural-language → semantic JSON)
- [ ] Schema validation — only approved component types, never pixels/colors
- [ ] System prompt generated FROM the component registry (so AI never drifts from what we can render)

### Polish
- [ ] Form-based input (alternative to free-text chat)
- [ ] Pre-built scenario templates (1-site, 2-site DR, hybrid, etc.)
- [ ] Canvas drag-and-drop editing (low priority — see CTO note: editable PPTX is the real value prop)
- [ ] Golden-file tests for the layout engine (scenario → expected shape list)

---

## Previous Versions (Reference Only)
- `/home/marek/Projects/ArchDiagram/` — V1 original prototype
- `/home/marek/Projects/ArchDiagramTEST/` — V2 with 10-step upgrade (port 4040)
- `/home/marek/Projects/ArchDiagramTEST2/` — BluePrint V3 (port 4050)

---

## Next Step

**Define the component rules per scenario.** Marek needs to specify:
- What components appear in an on-prem environment?
- What components appear in a cloud environment?
- What components appear in a DR site?
- What appears in M365/SaaS protection?
- What appears with air-gap/immutable storage?
- What appears in the security stack?

These rules are the domain knowledge that makes the product smart.
