#!/bin/sh
set -eu
# Run while the editor container is stopped: one CLI process at a time stays
# inside the laptop memory budget and avoids concurrent SQLite migrations.
n8n import:credentials --input=/import/credentials.json
n8n import:workflow --separate --input=/workflows
n8n publish:workflow --id=roadsignal-health
n8n publish:workflow --id=roadsignal-daily-report
n8n publish:workflow --id=roadsignal-evidence
