from app.audit import write_audit
from app.mock_db import PENDING_REQUESTS, STUDENTS


def decide(request_id: str, approve: bool, approver: str) -> dict:
    decision = "approve" if approve else "reject"
    req = PENDING_REQUESTS.get(request_id)

    if req is None:
        result = {"ok": False, "error": "request_not_found",
                  "message": f"No request {request_id}"}
    elif req["status"] != "pending_approval":
        result = {"ok": False, "error": "already_decided",
                  "message": f"{request_id} is already {req['status']}"}
    elif approve:
        STUDENTS[req["student_id"]]["scores"][req["subject"]] = req["new_score"]
        req["status"] = "approved"
        result = {"ok": True, "request_id": request_id,
                  "status": "approved", "message": "Grade change applied"}
    else:
        req["status"] = "rejected"
        result = {"ok": True, "request_id": request_id, "status": "rejected",
                  "message": "Request rejected. No change was made"}

    if result["ok"]:
        outcome = "approved_executed" if approve else "rejected_no_action"
    else:
        outcome = result["error"]
    write_audit("approval_decision", "grade_change", {
                "request_id": request_id, "decision": decision}, outcome, actor=approver)
    return result
