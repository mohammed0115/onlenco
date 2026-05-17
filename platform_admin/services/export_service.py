from __future__ import annotations

import csv

from django.http import HttpResponse

from platform_admin.services.audit_log_service import log_action


def csv_response(request, *, filename: str, rows: list[dict], action_type: str):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    if rows:
        writer = csv.DictWriter(response, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log_action(
        request,
        action_type=action_type,
        object_type="export",
        object_id=filename,
        description=f"Exported {filename}",
        metadata={"rows": len(rows)},
    )
    return response
