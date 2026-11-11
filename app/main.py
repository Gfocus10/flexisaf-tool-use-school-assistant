from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.approvals import decide
from app.mock_db import PENDING_REQUESTS
from app.tools import TOOLS, run_tool
from app.assistant import chat
app = FastAPI(title="School Support Workflow Assistant")

STATUS_FOR_ERROR = {
    "invalid_arguments": 422,
    "invalid_subject": 422,
    "unknown_tool": 404,
    "student_not_found": 404,
    "request_not_found": 404,
    "no_results": 404,
    "already_decided": 409,
    "tool_failed": 500,
}


class ToolCallRequest(BaseModel):
    arguments: dict = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=2, max_length=60)


def to_response(result: dict) -> JSONResponse:
    status = 200 if result["ok"] else STATUS_FOR_ERROR.get(
        result["error"], 400)
    return JSONResponse(status_code=status, content=result)


@app.get("/tools")
def list_tools():
    tools = []
    for name, (model, _) in TOOLS.items():
        schema = model.model_json_schema()
        tools.append({"name": name, "description": schema.get(
            "description", ""), "parameters": schema})
    return tools


@app.post("/tools/{tool_name}")
def call_tool(tool_name: str, body: ToolCallRequest):
    return to_response(run_tool(tool_name, body.arguments))


@app.get("/approvals")
def list_pending():
    return {rid: req for rid, req in PENDING_REQUESTS.items() if req["status"] == "pending_approval"}


@app.post("/approvals/{request_id}/approve")
def approve(request_id: str, body: ApprovalRequest):
    return to_response(decide(request_id, True, body.approver))


@app.post("/approvals/{request_id}/reject")
def reject(request_id: str, body: ApprovalRequest):
    return to_response(decide(request_id, False, body.approver))


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@app.post("/chat")
def chat_endpoint(body: ChatRequest):
    result = chat(body.message)
    if not result["ok"]:
        return JSONResponse(status_code=502, content=result)
    return result
