#!/usr/bin/env python3
"""Import Azure + GCP service icons from official kits.

Iconify only mirrors AWS service icons (`logos:aws-*`); for Azure and GCP
the maintained sources are Microsoft's "Azure Public Service Icons" SVG
ZIP and the GCP icons community mirror. Both are free.

This script:
  1. Downloads the Azure kit (if not already cached at SOURCE_KITS/azure)
  2. Downloads the GCP icons mirror (if not already cached at SOURCE_KITS/gcp)
  3. For each entry in the CURATED_AZURE / CURATED_GCP maps below:
       - locates the source SVG by filename pattern
       - rasterizes to a transparent 256x256 PNG (scale-to-fit centered, so
         aspect ratios are preserved — same pipeline as sync_icons.py)
       - writes assets/icons/cloud/<key>.png
  4. Prints what was added; does NOT touch icon_registry.json (registry
     entries are checked in by hand alongside this script).

Usage:
    python3 scripts/import_cloud_kits.py            # idempotent
    python3 scripts/import_cloud_kits.py --force    # re-rasterize even if cached
"""
import argparse
import io
import os
import sys
import urllib.request
import zipfile

import cairosvg
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_KITS = os.path.join(ROOT, 'source_kits')
ASSETS_OUT  = os.path.join(ROOT, 'assets', 'icons', 'cloud')
CANVAS_SIZE = 256

AZURE_ZIP_URL = 'https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V23.zip'
GCP_ZIP_URL   = 'https://codeload.github.com/AwesomeLogos/google-cloud-icons/zip/refs/heads/main'


# canonical_key -> exact ".../icon-service-<X>.svg" name to match (we only
# match the trailing portion, ignoring the numeric prefix)
CURATED_AZURE = {
    'azure_vm':                'Virtual-Machine',
    'azure_vmss':              'Virtual-Machine-Scale-Sets',
    'azure_vnet':              'Virtual-Networks',
    'azure_load_balancer':     'Load-Balancers',
    'azure_app_gateway':       'Application-Gateways',
    'azure_front_door':        'Front-Door-and-CDN-Profiles',
    'azure_dns':               'DNS-Zones',
    'azure_storage':           'Storage-Accounts',
    'azure_disks':             'Disks',
    'azure_data_lake':         'Data-Lake-Storage-Gen1',
    'azure_cosmos':            'Azure-Cosmos-DB',
    'azure_sql':               'SQL-Database',
    'azure_sql_server':        'SQL-Server',
    'azure_sql_managed':       'SQL-Managed-Instance',
    'azure_postgres':          'Azure-Database-PostgreSQL-Server',
    'azure_mysql':             'Azure-Database-MySQL-Server',
    'azure_synapse':           'Azure-Synapse-Analytics',
    'azure_databricks':        'Azure-Databricks',
    'azure_data_factory':      'Data-Factories',
    'azure_app_service':       'App-Services',
    'azure_function':          'Function-Apps',
    'azure_logic_apps':        'Logic-Apps',
    'azure_aks':               'Kubernetes-Services',
    'azure_aci':               'Container-Instances',
    'azure_acr':               'Container-Registries',
    'azure_apim':              'API-Management-Services',
    'azure_event_hub':         'Event-Hubs',
    'azure_service_bus':       'Azure-Service-Bus',
    'azure_key_vault':         'Key-Vaults',
    'azure_monitor':           'Monitor',
    'azure_app_insights':      'Application-Insights',
    'azure_backup':            'Backup-Vault',
    'azure_recovery_vault':    'Recovery-Services-Vaults',
    'azure_defender':          'Microsoft-Defender-for-Cloud',
    'azure_sentinel':          'Azure-Sentinel',
    'azure_resource_groups':   'Resource-Groups',
}

# canonical_key -> exact filename in the GCP kit images dir (without .svg)
CURATED_GCP = {
    'gcp_compute_engine':      'compute_engine',
    'gcp_app_engine':          'app_engine',
    'gcp_cloud_run':           'cloud_run',
    'gcp_cloud_functions':     'cloud_functions',
    'gcp_gke':                 'google_kubernetes_engine',
    'gcp_anthos':              'anthos',
    'gcp_cloud_storage':       'cloud_storage',
    'gcp_filestore':           'filestore',
    'gcp_cloud_sql':           'cloud_sql',
    'gcp_spanner':             'cloud_spanner',
    'gcp_bigtable':            'bigtable',
    'gcp_firestore':           'firestore',
    'gcp_memorystore':         'memorystore',
    'gcp_bigquery':            'bigquery',
    'gcp_dataflow':            'dataflow',
    'gcp_dataproc':            'dataproc',
    'gcp_pubsub':              'pubsub',
    'gcp_looker':              'looker',
    'gcp_cloud_dns':           'cloud_dns',
    'gcp_cloud_cdn':           'cloud_cdn',
    'gcp_load_balancing':      'cloud_load_balancing',
    'gcp_cloud_nat':           'cloud_nat',
    'gcp_cloud_armor':         'cloud_armor',
    'gcp_cloud_interconnect':  'cloud_interconnect',
    'gcp_cloud_router':        'cloud_router',
    'gcp_iam':                 'identity_and_access_management',
    'gcp_kms':                 'cloud_hsm',
    'gcp_secret_manager':      'secret_manager',
    'gcp_cloud_logging':       'cloud_logging',
    'gcp_cloud_monitoring':    'cloud_monitoring',
    'gcp_cloud_build':         'cloud_build',
    'gcp_artifact_registry':   'artifact_registry',
    'gcp_container_registry':  'container_registry',
}


def download(url: str, dst: str) -> None:
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        return
    print(f'  downloading {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'SEEngine-import/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(dst, 'wb') as f:
        f.write(data)


def extract(zip_path: str, dst_dir: str) -> None:
    if os.path.exists(dst_dir) and any(
        f.endswith('.svg') for r, _, fs in os.walk(dst_dir) for f in fs):
        return
    os.makedirs(dst_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dst_dir)


def find_svg(root: str, predicate) -> str | None:
    """Walk root and return first SVG whose basename satisfies predicate."""
    for r, _, files in os.walk(root):
        for f in files:
            if f.endswith('.svg') and predicate(f):
                return os.path.join(r, f)
    return None


def rasterize(svg_bytes: bytes, size: int = CANVAS_SIZE) -> bytes:
    raw = cairosvg.svg2png(bytestring=svg_bytes, output_height=size * 2)
    img = Image.open(io.BytesIO(raw)).convert('RGBA')
    w, h = img.size
    if w == 0 or h == 0:
        return raw
    scale = min(size / w, size / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - nw) // 2, (size - nh) // 2), img)
    out = io.BytesIO()
    canvas.save(out, 'PNG')
    return out.getvalue()


def import_set(label: str, source_root: str, curated: dict, predicate_for):
    print(f'== {label} ==')
    fetched = skipped = missed = 0
    for key, pattern in curated.items():
        out_path = os.path.join(ASSETS_OUT, f'{key}.png')
        if not args.force and os.path.exists(out_path) and os.path.getsize(out_path) > 200:
            skipped += 1
            continue
        src = find_svg(source_root, predicate_for(pattern))
        if not src:
            print(f'  MISS  {key:30s} (pattern: {pattern})')
            missed += 1
            continue
        with open(src, 'rb') as f:
            svg = f.read()
        png = rasterize(svg)
        with open(out_path, 'wb') as f:
            f.write(png)
        fetched += 1
        print(f'  OK    {key:30s} <- {os.path.basename(src)}')
    print(f'  fetched={fetched}  skipped={skipped}  missed={missed}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    os.makedirs(SOURCE_KITS, exist_ok=True)
    os.makedirs(ASSETS_OUT, exist_ok=True)

    # Azure
    az_zip = os.path.join(SOURCE_KITS, 'azure_icons.zip')
    az_dir = os.path.join(SOURCE_KITS, 'azure')
    download(AZURE_ZIP_URL, az_zip)
    extract(az_zip, az_dir)
    import_set('Azure', az_dir, CURATED_AZURE,
               lambda pat: (lambda f: f.endswith(f'icon-service-{pat}.svg')))

    # GCP
    gc_zip = os.path.join(SOURCE_KITS, 'gcp_icons.zip')
    gc_dir = os.path.join(SOURCE_KITS, 'gcp')
    download(GCP_ZIP_URL, gc_zip)
    extract(gc_zip, gc_dir)
    import_set('GCP', gc_dir, CURATED_GCP,
               lambda pat: (lambda f: f == f'{pat}.svg'))
