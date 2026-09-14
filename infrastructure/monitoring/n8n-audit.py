"""Read-only local n8n workflow/execution metadata; never prints credentials.

Mount the existing n8n data volume read-only at /n8n when running this script in
monitoring-init. Saved execution payloads and credential tables are not read.
Successful execution metadata may have been pruned by n8n retention settings;
an empty execution list is not proof a schedule has run.
"""
import json
import sqlite3


def main():
    connection = sqlite3.connect("file:/n8n/database.sqlite?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    workflow_ids = ("roadsignal-health", "roadsignal-daily-report", "roadsignal-evidence")
    workflows = connection.execute(
        'SELECT id, name, active, settings FROM workflow_entity WHERE id IN (?, ?, ?)', workflow_ids
    ).fetchall()
    executions = connection.execute(
        'SELECT id, "workflowId", mode, status, "startedAt", "stoppedAt" '
        'FROM execution_entity WHERE "workflowId" = ? ORDER BY id DESC LIMIT 12',
        ("roadsignal-daily-report",),
    ).fetchall()
    daily = connection.execute(
        'SELECT nodes FROM workflow_entity WHERE id = ?', ("roadsignal-daily-report",)
    ).fetchone()
    assert len(workflows) == 3 and all(row["active"] for row in workflows), "Expected three published workflows"
    schedule = [node.get("parameters") for node in json.loads(daily["nodes"])
                if node["type"] == "n8n-nodes-base.scheduleTrigger"]
    metadata = [{"id": row["id"], "active": bool(row["active"]),
                 "timezone": json.loads(row["settings"] or "{}").get("timezone")}
                for row in workflows]
    print(json.dumps({"workflows": metadata, "daily_schedule": schedule,
                      "daily_execution_metadata": [dict(row) for row in executions],
                      "execution_payloads_read": False, "credential_tables_read": False}))
    connection.close()


if __name__ == "__main__":
    main()
