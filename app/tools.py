from pydantic import BaseModel, Field, ValidationError, field_validator

from app.mock_db import PENDING_REQUESTS, SCHOOL_INFO, STUDENTS

from app.audit import write_audit


class SearchSchoolInfoArgs(BaseModel):
    """Search school information such as policies, fees, exam dates, courses and grading. Read only."""
    query: str = Field(min_length=2, max_length=200,
                       description="What to look up in school information")


class CalculateGradeArgs(BaseModel):
    """Calculate a student's average from scores, or the exam score needed to reach a target final mark. Read only."""
    scores: list[float] = Field(min_length=1, max_length=20,
                                description="Continuous assessment scores, each 0 to 100")
    target_average: float | None = Field(
        default=None, ge=0, le=100, description="Final mark the student wants")
    exam_weight: float = Field(
        default=0.6, gt=0, le=1, description="Share of the final mark that comes from the exam")

    @field_validator("scores")
    @classmethod
    def scores_in_range(cls, v):
        if any(s < 0 or s > 100 for s in v):
            raise ValueError("each score must be between 0 and 100")
        return v


class LookupStudentArgs(BaseModel):
    """Look up one student's record (name, class and subject scores) by student ID. Read only."""
    student_id: str = Field(
        pattern=r"^STU\d{3}$", description="Student ID such as STU001")


def search_school_info(args: SearchSchoolInfoArgs) -> dict:
    words = set(args.query.lower().split())
    matches = []
    for item in SCHOOL_INFO:
        searchable = set(item["keywords"]) | set(item["topic"].lower().split())
        score = len(words & searchable)
        if score > 0:
            matches.append((score, item))
    matches.sort(key=lambda m: m[0], reverse=True)
    if not matches:
        return {"ok": False, "error": "no_results", "message": "No school information matched that query"}
    return {"ok": True, "results": [{"topic": i["topic"], "text": i["text"]} for _, i in matches[:3]]}


def calculate_grade(args: CalculateGradeArgs) -> dict:
    ca_average = sum(args.scores) / len(args.scores)
    if args.target_average is None:
        return {"ok": True, "average": round(ca_average, 2)}
    needed = (args.target_average - ca_average *
              (1 - args.exam_weight)) / args.exam_weight
    needed = round(needed, 2)
    return {
        "ok": True,
        "ca_average": round(ca_average, 2),
        "required_exam_score": max(needed, 0),
        "achievable": needed <= 100,
    }


def lookup_student_record(args: LookupStudentArgs) -> dict:
    record = STUDENTS.get(args.student_id)
    if record is None:
        return {"ok": False, "error": "student_not_found", "message": f"No record for {args.student_id}"}
    return {
        "ok": True,
        "student_id": args.student_id,
        "name": record["name"],
        "class": record["class"],
        "scores": record["scores"],
    }


class PrepareGradeChangeArgs(BaseModel):
    """Prepare a request to change a student's score. This does NOT change anything. A human must approve the request before it is applied."""
    student_id: str = Field(
        pattern=r"^STU\d{3}$", description="Student ID such as STU001")
    subject: str = Field(min_length=2, max_length=40,
                         description="Subject whose score should change")
    new_score: float = Field(ge=0, le=100, description="Proposed new score")
    reason: str = Field(min_length=10, max_length=300,
                        description="Why the change is requested")


def prepare_grade_change(args: PrepareGradeChangeArgs) -> dict:
    record = STUDENTS.get(args.student_id)
    if record is None:
        return {"ok": False, "error": "student_not_found", "message": f"No record for {args.student_id}"}
    if args.subject not in record["scores"]:
        return {
            "ok": False,
            "error": "invalid_subject",
            "message": f"{args.subject} is not a subject for this student",
            "valid_subjects": list(record["scores"]),
        }
    request_id = f"REQ{len(PENDING_REQUESTS) + 1:03d}"
    PENDING_REQUESTS[request_id] = {
        "student_id": args.student_id,
        "subject": args.subject,
        "old_score": record["scores"][args.subject],
        "new_score": args.new_score,
        "reason": args.reason,
        "status": "pending_approval",
    }
    return {
        "ok": True,
        "request_id": request_id,
        "status": "pending_approval",
        "message": "No change has been made. Waiting for explicit human approval.",
    }


TOOLS = {
    "search_school_info": (SearchSchoolInfoArgs, search_school_info),
    "calculate_grade": (CalculateGradeArgs, calculate_grade),
    "lookup_student_record": (LookupStudentArgs, lookup_student_record),
    "prepare_grade_change": (PrepareGradeChangeArgs, prepare_grade_change),
}


def _execute(name: str, raw_args: dict) -> dict:
    if name not in TOOLS:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}"}
    model, fn = TOOLS[name]
    try:
        args = model(**raw_args)
    except ValidationError as e:
        details = [{"field": ".".join(
            str(p) for p in err["loc"]), "message": err["msg"]} for err in e.errors()]
        return {"ok": False, "error": "invalid_arguments", "details": details}
    try:
        return fn(args)
    except Exception:
        return {"ok": False, "error": "tool_failed", "message": "The tool failed unexpectedly"}


def run_tool(name: str, raw_args: dict) -> dict:
    result = _execute(name, raw_args)
    outcome = "success" if result["ok"] else result["error"]
    write_audit("tool_call", name, raw_args, outcome)
    return result
