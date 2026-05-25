"""Design tokens — extracted from PPT Template Slide 6."""

COLORS = {
    'bg':               '#000000',
    'purple_primary':   '#7030A0',
    'purple_secondary': '#834895',
    'purple_light':     '#C1A3C9',
    'dark_purple':      '#1A0A2E',
    'text_primary':     '#FFFFFF',
    'text_muted':       '#E6E8F0',
    'border_dark':      '#3C3F48',
    'border_medium':    '#5C5F6B',
    'positive':         '#00B050',
    'negative':         '#FF0000',
    'subzone_bg':       '#0E0E16',   # slightly lifted vs slide bg for nested boxes
}

# Gradient stops — per-pixel sampled from PPT Template Slide 6.
# The bars go from vibrant purple at top all the way down to near-black,
# which is what gives the Commvault "shiny glossy" look.
GRADIENTS = {
    'purple_bar':   ['#7843A0', '#04031C'],   # vibrant → near-black
    'purple_stack': ['#7843A0', '#04031C'],   # same for Commvault card
    'purple_deep':  ['#7843A0', '#0D0727'],   # HSX wrapper, almost as dark
}

IMAGES = {
    'commvault_logo':    'extracted/slide6_Picture_5_0accdd8f.png',
    'pure_storage':      'extracted/slide5_Picture_4_788cf27a.png',
    'azure':             'extracted/slide6_Picture_2_a850ef43.png',
    'm365':              'extracted/slide6_Picture_2_cc4a9c1c.png',
    # Backup vendor UI screenshots (used by BackupSoftwareStack card)
    'commvault_ui':      'vendor-ui/commvault.png',
    # Vendor logos used as fallback when a vendor has no UI screenshot
    # (synced via scripts/sync_icons.py from Iconify).
    'veeam_logo':        'icons/vendor/veeam.png',
    'dell_logo':         'icons/vendor/dell.png',
    'cisco_logo':        'icons/vendor/cisco.png',
    'netapp_logo':       'icons/vendor/netapp.png',
    'data_domain_logo':  'icons/vendor/data_domain.png',
    # Commvault Unity dashboard thumbnail (used by UnityCard)
    'unity_ui':          'vendor-ui/unity_ui.png',
    # Shared CommServe / backup-server indicator pieces
    'cs_server':         'vendor-icons/cs_server.png',
    'cs_lock':           'vendor-icons/cs_lock.png',
    # Air Gap Protect + Cloud Cleanroom icons
    'agp_cloud':         'vendor-icons/agp_cloud.png',
    'agp_shield':        'vendor-icons/agp_shield.png',
    'agp_cleanroom':     'vendor-icons/agp_cleanroom.png',
    'agp_bolt':          'vendor-icons/agp_bolt.png',
    'agp_firewall':      'vendor-icons/agp_firewall.png',
    # Cloud provider logos
    'cloud_azure':       'vendor-icons/azure_logo.png',
    'cloud_aws':         'vendor-icons/aws_logo.png',
    'cloud_gcp':         'vendor-icons/gcp_logo.png',
    # Workload chip icons (white outline, transparent bg)
    'chip_devices':      'chip-icons/devices.png',
    'chip_database':     'chip-icons/database.png',
    'chip_files':        'chip-icons/files.png',
    'chip_vms':          'chip-icons/vms.png',
    'chip_applications': 'chip-icons/applications.png',
    # SaaS application logos (brand-colored tiles)
    'saas_m365':             'saas-icons/m365.png',
    'saas_ad_entra':         'saas-icons/ad_entra.png',
    'saas_salesforce':       'saas-icons/salesforce.png',
    'saas_google_workspace': 'saas-icons/google_workspace.png',
}

# Maps workload chip label → icon key (case-insensitive).
# Aliases let users write human-natural labels ("SQL DBs", "File Systems")
# and still get the right icon.
CHIP_ICON = {
    'devices':      'chip_devices',
    'database':     'chip_database',
    'databases':    'chip_database',
    'db':           'chip_database',
    'dbs':          'chip_database',
    'sql':          'chip_database',
    'sql db':       'chip_database',
    'sql dbs':      'chip_database',
    'files':        'chip_files',
    'file system':  'chip_files',
    'file systems': 'chip_files',
    'vms':          'chip_vms',
    'vm':           'chip_vms',
    'applications': 'chip_applications',
    'apps':         'chip_applications',
    # SaaS applications — match by common names / aliases
    'm365':                'saas_m365',
    'microsoft 365':       'saas_m365',
    'office 365':          'saas_m365',
    'o365':                'saas_m365',
    'ad':                  'saas_ad_entra',
    'entra':               'saas_ad_entra',
    'entra id':            'saas_ad_entra',
    'ad/entra':            'saas_ad_entra',
    'ad/entra id':         'saas_ad_entra',
    'ad / entra':          'saas_ad_entra',
    'ad / entra id':       'saas_ad_entra',
    'active directory':    'saas_ad_entra',
    'salesforce':          'saas_salesforce',
    'sfdc':                'saas_salesforce',
    'google workspace':    'saas_google_workspace',
    'gsuite':              'saas_google_workspace',
    'g suite':             'saas_google_workspace',
}

# ─────────── Per-vendor architecture vocabulary ───────────
# Each vendor has its own naming for the controller (CommServe-equivalent)
# and the data movers (Media-Agent-equivalent). The renderer uses these
# labels and badges to title the in-site Backup Software Stack card and
# the row of data-mover server icons next to it. Keep keys lowercase.
#
# Hyperconverged vendors (rubrik, cohesity, unitrends) intentionally
# don't appear here — they fuse all three roles into a cluster appliance
# rendered by ClusterAppliance, so the three-tier vocabulary doesn't apply.
VENDOR_ARCH = {
    'commvault': {
        'cs_badge': 'CS',
        'cs_label': 'Commvault Command Center',
        'ma_badge': 'MA',
        'ma_label_singular': 'Media Agent',
        'ma_label_plural':   'Media Agents',
        'badge_fill': '#7030A0',     # Commvault purple
    },
    'veeam': {
        'cs_badge': 'VBR',
        'cs_label': 'Veeam Backup Server',
        'ma_badge': 'PX',
        'ma_label_singular': 'Backup Proxy',
        'ma_label_plural':   'Backup Proxies',
        'badge_fill': '#00B143',     # Veeam green
    },
    'networker': {
        'cs_badge': 'NW',
        'cs_label': 'NetWorker Server',
        'ma_badge': 'SN',
        'ma_label_singular': 'Storage Node',
        'ma_label_plural':   'Storage Nodes',
        'badge_fill': '#0076CE',     # Dell blue
    },
    'avamar': {
        'cs_badge': 'AV',
        'cs_label': 'Avamar Server',
        'ma_badge': 'DM',
        'ma_label_singular': 'Data Mover',
        'ma_label_plural':   'Data Movers',
        'badge_fill': '#0076CE',     # Dell blue
    },
}

FONT = 'Arial'

# Spacing scale (inches) — use these instead of magic numbers
SPACE = {
    'xs': 0.05,
    'sm': 0.08,
    'md': 0.10,
    'lg': 0.16,
    'xl': 0.24,
}
