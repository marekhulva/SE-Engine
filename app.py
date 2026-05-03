from flask import Flask, request, jsonify, send_file, render_template
import json, os, tempfile, re
from layout_engine import generate_layout
from renderer_pptx import render_pptx
import anthropic

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

PARSER_SYSTEM_PROMPT = """You are an expert at converting natural-language descriptions of IT infrastructure into a structured JSON scenario for a Commvault architecture diagram tool.

Output ONLY valid JSON. No explanation, no markdown fences, no commentary — just the raw JSON object.

## Schema

```
{
  "title": "string — short descriptive title",
  "sites": [ <site>, ... ],
  "connections": [ <connection>, ... ],   // optional
  "agp": <agp_config>                     // optional
}
```

### Site object
```
{
  "id": "snake_case_unique_id",
  "name": "Human-readable site name",
  "type": "onprem",                        // default; use "saas" for SaaS-only sites
  "workloads": ["VMs", "Databases", "File Systems", "Active Directory", "Applications", "Exchange", "SAP", "NAS"],
  "vm_count": 100,                         // number of VMs / endpoints
  "storage_tb": 10,                        // raw protected data in TB
  "backup_software": "commvault",
  "backup_target": "hsx" | "pure" | "netapp" | "none",
  // backup_target rules:
  //   "hsx"    — Commvault HyperScale X appliance on-prem (most common). Has MA built in.
  //   "pure"   — Pure Storage FlashArray on-prem (DR sites or Pure-only shops). Needs separate MAs.
  //   "netapp" — NetApp storage as backup target (renders as labelled NetApp box). Needs separate MAs.
  //              Use when user says NetApp, ONTAP, or names a NetApp model.
  //   "none"   — NO on-prem backup storage; data goes directly to cloud/AGP via Media Agent.
  //              Use when user says: "no on-prem storage", "direct to cloud", "cloud-first",
  //              "no HSX", "no local storage", "just a media agent".
  "hsx_nodes": 3,                          // required only when backup_target == "hsx"
  "hsx_tb": 150,                           // required only when backup_target == "hsx"
  "media_agents": 1,                       // standalone MAs (auto-set for non-HSX; always 1+ when backup_target=="none")
  "retention_days": 30                     // optional
}
```

For a grouped SaaS card (multiple apps, one shared AGP):
```
{
  "id": "saas",
  "type": "saas",
  "name": "SaaS Tenants",
  "apps": ["M365", "Active Directory", "Salesforce", "Google Workspace", "ServiceNow"]
}
```

For a cloud workload site (AWS / Azure / GCP — workloads run IN the cloud, not on-prem):
```
{
  "id": "aws_prod",
  "type": "cloud",
  "cloud": "aws" | "azure" | "gcp",     // REQUIRED — drives container chrome + brand color
  "region": "us-east-1",                // optional but recommended — shown as a pill
  "name": "AWS Production",
  "workloads": ["EC2", "S3", "RDS", "Lambda", "EKS"],   // cloud service names
  "vm_count": 200,                      // EC2 instances / VMs / similar
  "storage_tb": 80,                     // S3 + EBS volume in TB
  "backup_software": "commvault",
  "backup_target": "none",              // default for cloud — direct to AGP via cloud-resident MA
  "media_agents": 2,                    // Commvault calls these "Gateways" in cloud
                                        //   (the field name stays media_agents in JSON;
                                        //    the renderer auto-relabels to "Gateway" / "Gateways"
                                        //    + "GW" badge for type:"cloud" sites).
  "retention_days": 30
}
```
**RULE for `type: "cloud"`:** the workloads array must use cloud SERVICE names (EC2, S3, RDS, Lambda, EKS, Azure VM, Cosmos DB, AKS, BigQuery, GKE, Cloud Storage, etc.) — these resolve to the cloud-provider's official service icons. Do NOT use generic terms like "VMs" or "Databases" inside a cloud site. If user says "we run on AWS with VMs and a SQL database", translate to ["EC2", "RDS"]. If user names a service we don't have an icon for, fall back to a generic chip but emit the service name.

**RULE on Media Agents vs Gateways:** the JSON schema field is always `media_agents` regardless of site type, but Commvault CALLS them "Gateways" inside cloud environments. Cloud sites auto-render the label/badge as "Gateway" / "GW". On-prem sites render "Media Agent" / "MA". The user might say "two cloud gateways" or "a Gateway in our AWS account" — that's just media_agents=N on a `type: "cloud"` site, no special field needed.

For individual SaaS app cards (each app gets its own card + its own AGP):
```
{
  "id": "m365",
  "type": "saas_app",
  "app": "M365",
  "cloud": "azure"        // REQUIRED — which cloud AGP this app backs up to
}
```
**RULE: Every `saas_app` MUST have a `cloud` field.** If the user does not specify which cloud a SaaS app goes to, you MUST ask before generating JSON. Never assume or default the cloud for a saas_app — it is always an explicit user decision.

### Connection object (for replication between sites)
```
{ "from": "site_id", "to": "site_id", "speed": "Replication" }
```
Use when user mentions: replication, replicate, DR, disaster recovery, secondary copy between sites.
The "to" site is always the DR / secondary.

### AGP config (Air Gap Protection — Commvault's immutable cloud backup)
```
{
  "cloud_provider": "azure" | "aws" | "gcp",
  "tier": "Hot Tier" | "Cool Tier" | "Infrequent Access" | "Archive",
  "capacity_tb": 200,
  "retention_days": 180,
  "callout": "Short label shown on diagram",
  "cleanroom": {                           // optional — only if user mentions Cleanroom / isolated recovery
    "tenant": "Customer Tenant",
    "capacity_tb": 50
  }
}
```

Tier mapping from user language:
- "frequent / hot / fast recovery" → "Hot Tier"
- "cool / standard" → "Cool Tier"
- "infrequent / rarely / less frequent" → "Infrequent Access"
- "archive / long-term / compliance" → "Archive"
- If no tier mentioned, default to "Cool Tier"

## Rules

1. **Primary DC is always listed first**, DR site listed second (or later).
2. **DR sites** typically have fewer VMs, use Pure or fewer HSX nodes, and are replication *targets*.
3. **When backup_target is "none"**: set media_agents to at least 1. Do NOT include hsx_nodes or hsx_tb.
4. **HSX nodes**: if user says "N nodes", set hsx_nodes=N. Default hsx_tb = hsx_nodes × 50.
5. **Workloads**: map natural language → schema values. "Active Directory" → "Active Directory", "databases" → "Databases", "VMs" → "VMs", "files" → "File Systems", "apps" → "Applications".
6. If the user mentions AGP / Air Gap / cloud backup, include the agp block.
7. If the user mentions Cleanroom / isolated recovery environment, add the cleanroom sub-object inside agp.
8. If the user says "no Cleanroom" or doesn't mention it, omit cleanroom.
9. Make up reasonable values for anything not specified (vm_count, storage_tb, hsx_tb, etc.).
10. Grouped SaaS (one card, multiple apps, one AGP) → use `type: "saas"`.
    Individual SaaS (each app its own card, each to its own AGP) → use `type: "saas_app"` with `cloud` field.
11. **CRITICAL — SaaS app cloud target**: If the user mentions individual SaaS apps going to Air Gap but does NOT say which cloud each one goes to, do NOT guess. Output a JSON error object instead: `{"error": "missing_saas_cloud", "apps": ["M365", ...]}`. The caller will prompt the user to clarify.

Output only the JSON. Start with `{` and end with `}`.
"""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/layout', methods=['POST'])
def layout():
    scenario = request.get_json()
    data = generate_layout(scenario)
    return jsonify(data)

@app.route('/scenario')
def scenario():
    with open(os.path.join(BASE_DIR, 'scenario_current.json')) as f:
        return f.read(), 200, {'Content-Type': 'application/json'}

@app.route('/scenario/<name>')
def scenario_named(name):
    """Load a named scenario file (e.g. /scenario/showcase_density)."""
    safe = re.sub(r'[^a-z0-9_]', '', name.lower())
    path = os.path.join(BASE_DIR, f'scenario_{safe}.json')
    if not os.path.exists(path):
        return jsonify({'error': f'unknown scenario: {safe}'}), 404
    with open(path) as f:
        return f.read(), 200, {'Content-Type': 'application/json'}

@app.route('/download', methods=['POST'])
def download():
    scenario = request.get_json()
    layout_data = generate_layout(scenario)
    tmp = tempfile.NamedTemporaryFile(suffix='.pptx', delete=False)
    tmp.close()
    render_pptx(layout_data, tmp.name)
    return send_file(tmp.name, as_attachment=True, download_name='diagram.pptx',
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

@app.route('/parse', methods=['POST'])
def parse():
    body = request.get_json()
    user_text = body.get('text', '').strip()
    if not user_text:
        return jsonify({'error': 'No text provided'}), 400
    if not ANTHROPIC_API_KEY:
        return jsonify({'error': 'ANTHROPIC_API_KEY not set'}), 500
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2048,
        system=PARSER_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': user_text}],
    )
    raw = message.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = re.sub(r'^```[a-z]*\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)
    try:
        scenario = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'JSON parse failed: {e}', 'raw': raw}), 500
    return jsonify(scenario)


@app.route('/assets/<path:filename>')
def assets(filename):
    return send_file(os.path.join(BASE_DIR, 'assets', filename))

@app.route('/output/<path:filename>')
def output(filename):
    return send_file(os.path.join(BASE_DIR, 'output', filename),
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

if __name__ == '__main__':
    # SE Engine runs on 5051; ArchGramMVP keeps 5050 so both can run side-by-side.
    # Avoiding 5060 (Firefox/Chrome block it as the SIP port).
    app.run(debug=True, port=5051, host='0.0.0.0')
