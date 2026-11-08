"""Canonical Salesforce simulator schema name exposed to UI and APIs."""

SFDC_SCHEMA = "sfdc_schema"

# Historical dumps and live-FDW exports may still use this name until re-dumped.
LEGACY_SFDC_SCHEMAS = frozenset({"sfdc_itxp2dev"})
