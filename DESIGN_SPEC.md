# ArchGram Design Spec — Extracted from PPT Template Slide 6

**Source**: `PPT Template - Copy.pptx`, Slide 6 ("Future State – 2 Site with AGP & Cleanroom")
**Extracted**: 2026-04-10

---

## Color Palette (Commvault "Final CVLT Colors 2024")

| Token             | Hex       | Usage                                          |
|-------------------|-----------|-------------------------------------------------|
| bg-primary        | #000000   | Slide background, dark fills                    |
| purple-primary    | #7030A0   | Data flow ovals, Commvault fill, HSX accents    |
| purple-secondary  | #834895   | Borders, badges, oval borders                   |
| purple-light      | #C1A3C9   | Lighter purple accents                          |
| text-primary      | #FFFFFF   | All main text on dark backgrounds               |
| text-muted        | #E6E8F0   | HSX labels, airgap labels                       |
| border-dark       | #3C3F48   | Dark gray borders                               |
| border-medium     | #5C5F6B   | Connector line color, secondary borders         |
| positive          | #00B050   | Green callouts ("Protected", "All Backups Immutable") |
| negative          | #FF0000   | Red callouts ("Not Immutable", "Not Protected") |
| accent-blue       | #0070C0   | Cloud Cleanroom accent                          |
| accent-deepblue   | #00053A   | Dark blue (theme dk2)                           |
| accent-pink       | #E92B62   | Theme accent3                                   |

---

## Typography

| Element             | Font   | Size  | Weight | Color    |
|---------------------|--------|-------|--------|----------|
| Slide title         | Arial  | 28pt  | Normal | #FFFFFF  |
| Site label          | Arial  | 10.5pt| Normal | #FFFFFF  |
| Sub-zone header     | Arial  | 9pt   | Bold   | #FFFFFF  |
| Workload summary    | Arial  | 10pt  | Normal | #FFFFFF  |
| Workload chip       | Arial  | 8pt   | Normal | #FFFFFF  |
| Backup product name | Arial  | 12pt  | Normal | —        |
| Data flow number    | Arial  | 16pt  | Normal | #FFFFFF  |
| Callout (positive)  | Arial  | 12pt  | Normal | #00B050  |
| Callout (negative)  | Arial  | 12pt  | Normal | #FF0000  |
| HSX table cell      | Arial  | 6pt   | Normal | #FFFFFF  |
| HSX label           | Arial  | 8pt   | Bold   | #E6E8F0  |
| M365 labels         | Arial  | 9pt   | Normal | #FFFFFF  |
| M365 sub-label      | Arial  | 8pt   | Normal | #FFFFFF  |
| Design notes        | Arial  | 10pt  | Normal | #000000  |
| Protection status   | Arial  | 10pt  | Normal | #FFFFFF  |

---

## Component Visual Specs

### Site Box (Data Center)
- **Outer container**: 1×1 TABLE, dark fill (scheme:tx1 = #000000), white border
- **Size**: ~2.95" × 5.13" (preferred), shrinkable
- **Label**: TextBox above container, 10.5pt white, 4.5pt bottom border (purple underline effect)
- **Contains**: Clients zone, Protected Data Layer, backup product, HSX appliance

### Clients & Protected Storage (Sub-zone)
- **Type**: 2-row × 1-col TABLE
- **Header**: "Clients & Protected Storage", 9pt bold white
- **Content area**: Empty cell for workload chips to sit on top of
- **Size**: ~2.79" × 1.43"
- **Fill**: Dark (scheme:tx1)

### Workload Chip
- **Type**: GROUP (rectangle + icon)
- **Size**: 0.77" × 0.47" each
- **Fill**: #000000 (black)
- **Border**: 0.75pt solid
- **Text**: 8pt Arial white
- **Labels**: Files, Devices, Database, VMs, Applications
- **Layout**: Horizontal row, touching/adjacent
- **Files variant**: 0.77" × 0.13" (thinner, text only)

### Storage / Vendor Logo
- **Type**: PICTURE
- **Size**: ~0.98" × 0.15" (vendor logo bar) or ~0.88" × 0.52" (product icon)
- **Label below**: TextBox, 12pt Arial (e.g., "PowerStore")

### Backup Product (Commvault Stack)
- **Type**: GROUP (5 sub-shapes)
- **Size**: ~1.80" × 0.88"
- **Contains**: 
  - Commvault logo (PICTURE)
  - Label TextBox ("Command Center" / "Command Center (Standby)")
  - Product icons
  - CS/MA badge: Oval, #7030A0 fill, #834895 border, 1pt, white text
- **Badge size**: varies (CS = larger, MA = 0.62" × 0.62")

### Protected Data Layer (Sub-zone)
- **Type**: 2-row × 1-col TABLE  
- **Header**: "Protected Data Layer", 9pt white
- **Size**: ~2.71" × 2.14"
- **Fill**: Dark (scheme:tx1)
- **Contains**: HSX table, protection status labels

### HSX Appliance Table
- **Type**: TABLE, 12-row × 2-col
- **Size**: 1.35" × 1.33"
- **Font**: 6pt Arial white
- **Row pattern**: 
  - Col 1: slot number (1-12)
  - Col 2: "HSX - 01" (active) or "Future expansion" (empty) or blank
- **Active rows**: purple accent (#7030A0)
- **Empty rows**: dark fill
- **Label below**: "3-Node HSX Appliance | 150TB Usable", 8pt bold, #E6E8F0

### Protection Status
- **Type**: TextBox
- **Text**: "Immutable | Deduped | Encrypted"
- **Font**: 10pt Arial white
- **Size**: 1.04" × 0.61"

### Callout (Positive)
- **Type**: TextBox
- **Text**: " All Backups Immutable" (note leading space)
- **Font**: 12pt Arial, #00B050
- **Icon**: Green checkmark (implied by leading space + color)

### Callout (Negative)
- **Type**: TextBox
- **Text**: " Not Immutable" / " No Pre-Backup Detection"
- **Font**: 12pt Arial, #FF0000
- **Icon**: Red X (implied)

### Data Flow Connector
- **Arrow line**: 1.75pt, dash style, straightConnector1
- **Numbered oval**: 
  - Size: 0.37" × 0.37"
  - Fill: #7030A0
  - Border: 1pt solid #834895
  - Text: number, 16pt Arial white

### M365 Block
- **Type**: Rounded Rectangle (roundRect)
- **Size**: 2.94" × 1.07"
- **Fill**: Gradient or dark
- **Split**: Vertical divider line at center
- **Left**: M365 icon + "M365" label + user count
- **Right**: AD/Entra icon + "AD / ENTRA ID" label + user count
- **Labels**: 8-9pt Arial white
- **Status below**: "Protected" (#00B050)

### AirGap + Cleanroom Block
- **Type**: TABLE, 3-row × 2-col
- **Size**: 2.99" × 2.25"
- **Headers**: "AirGap Protect" | "Cloud Cleanroom"
- **Content**: Capacity, immutability, recovery features
- **Font**: 9pt Arial white
- **Break symbol**: Freeform lightning bolt shapes (scheme:accent1, accent3)
- **Label**: "Airgap", 8pt bold, #E6E8F0

### Design Notes Sidebar
- **Type**: TextBox
- **Size**: 2.52" × 3.77"
- **Position**: Far left
- **Fill**: Light (scheme:bg1 = #FFFFFF)
- **Font**: 10pt Arial black
- **Content**: Multi-line site design notes

### Slide Title
- **Type**: TextBox
- **Size**: 8.41" × 0.57"
- **Position**: Top left
- **Font**: 28pt Arial white
- **Text**: "Future State – [description]"

### Commvault Banner
- **Type**: PICTURE
- **Size**: 3.01" × 0.59"
- **Position**: Top center-right

---

## Slide Dimensions
- **Width**: 13.33" (12,192,000 EMU)
- **Height**: 7.50" (6,858,000 EMU)
- **Canvas equivalent**: 1280 × 720 px
- **Conversion**: 914,400 EMU = 1 inch

## Layout Zones (from Slide 6)
```
|  Notes  |   DR DC    |  Primary DC  | M365/Security |
| (0-2.7) | (2.9-5.8)  |  (6.5-9.4)   |  (9.9-13.0)   |
|         |            |              |               |
|         | [workloads]| [workloads]  | [M365 block]  |
|         | [storage]  | [storage]    |               |
|         | [commvault]| [commvault]  |               |
|         | [protected]| [protected]  | [AirGap+CR]   |
|         | [HSX]      | [HSX]        |               |
|         | [status]   | [status]     |               |
```

Data flows: horizontal dashed arrows between sites + to AirGap, with numbered ovals
