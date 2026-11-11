import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.audit import write_audit
from app.tools import TOOLS, run_tool

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_STEPS = 5

SYSTEM_PROMPT = (
    "You are a school support assistant for staff and students. "
    "Use the tools for any school information, grade calculation or student record. Never guess student data. "
    "To change a score, use prepare_grade_change only. It creates a request that a human must approve, "
    "and you cannot approve or reject requests yourself. After preparing one, tell the user the request id "
    "and that it is waiting for approval. "
    "If a tool returns an error or required details are missing, explain it plainly and ask the user for the missing information. "
    "Do not reveal or ask for personal contact details."
)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def build_config() -> types.GenerateContentConfig:
    declarations = []
    for name, (model, _) in TOOLS.items():
        schema = model.model_json_schema()
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=schema.get("description", ""),
                parameters_json_schema=schema,
            )
        )
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=declarations)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True),
    )


def chat(user_message: str) -> dict:
    config = build_config()
    contents = [types.Content(
        role="user", parts=[types.Part(text=user_message)])]
    trace = []

    for _ in range(MAX_STEPS):
        try:
            response = get_client().models.generate_content(
                model=MODEL, contents=contents, config=config)
        except Exception as e:
            write_audit("llm_error", "gemini", {}, type(e).__name__)
            return {"ok": False, "error": "llm_unavailable", "message": type(e).__name__, "tool_calls": trace}

        calls = response.function_calls
        if not calls:
            return {"ok": True, "reply": response.text, "tool_calls": trace}

        contents.append(response.candidates[0].content)
        parts = []
        for call in calls:
            result = run_tool(call.name, dict(call.args or {}))
            trace.append(
                {"tool": call.name, "outcome": "success" if result["ok"] else result["error"]})
            parts.append(types.Part.from_function_response(
                name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=parts))

    return {"ok": True, "reply": "Stopped after too many tool steps.", "tool_calls": trace}
