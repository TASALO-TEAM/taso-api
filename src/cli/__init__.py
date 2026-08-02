"""CLI de gestión de taso-api (backups, restore, poda de tasas).

python -m src.cli db --help

Fuente de verdad para todas las operaciones de datos. Se ejecuta directo
en el VPS por SSH. `restore` vive EXCLUSIVAMENTE aquí — nunca se expone
por HTTP ni por Telegram, por seguridad. Ver
docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md.
"""
