# School Support Workflow Assistant

A tool using AI assistant for a school, built with FastAPI, Pydantic and the Gemini API. The assistant answers school questions, calculates grades and looks up student records through function calling. Sensitive actions need explicit human approval, and every tool attempt is written to an audit log.


## What it does

Read only tools the model can call:

1. search_school_info: finds school policies, fees, exam dates, courses and the grading scale.

2. calculate_grade: calculates an average, or the exam score needed to reach a target final mark.

3. lookup_student_record: returns a student's name, class and subject scores from a mock database.

Sensitive action with an approval gate:

4. prepare_grade_change: creates a pending grade change request. It changes nothing. A human must approve it through a separate endpoint. Rejecting it prevents the action completely. The model has no tool to approve or reject.

## Project structure

app/main.py: FastAPI endpoints

app/assistant.py: Gemini function calling loop and system prompt

app/tools.py: tool schemas (Pydantic), tool functions and the tool dispatcher

app/approvals.py: approve and reject logic

app/audit.py: audit logging with redaction

app/mock_db.py: mock school database and pending requests

docs/test_scenarios.md: 14 test scenarios with results

docs/failure_and_permission_notes.md: failure examples, permission boundaries and limitations

docs/sample_audit_log.jsonl: sample audit log with sensitive data removed

.env.example: environment variable template

requirements.txt: dependencies with versions


## Setup (Windows, Git Bash)

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file and add your own Gemini API key (from Google AI Studio):

```bash
cp .env.example .env
```

Then edit .env and replace your_key_here. Never commit .env.

Environment variables:

GEMINI_API_KEY: your Gemini API key

GEMINI_MODEL: model name, default gemini-3.5-flash-lite

AUDIT_LOG_PATH: where the audit log is written, default audit.log


4. Run the server:

```bash
uvicorn app.main:app
```

The interactive API docs are at http://127.0.0.1:8000/docs

## API endpoints

GET /tools: lists the tools with descriptions and parameter schemas

POST /tools/{tool_name}: calls a tool directly with {"arguments": {...}}

POST /chat: sends a message to the assistant with {"message": "..."}

GET /approvals: lists pending requests

POST /approvals/{request_id}/approve: approves a request with {"approver": "name"}

POST /approvals/{request_id}/reject: rejects a request with {"approver": "name"}


## Example usage

Ask the assistant to prepare a grade change:

```bash
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message": "Change the Mathematics score of STU002 to 70 because the script was remarked after an appeal"}'
```

The reply gives a request id such as REQ001 with status pending approval. The score is still unchanged. A human then decides:

```bash
curl -s http://127.0.0.1:8000/approvals
curl -s -X POST http://127.0.0.1:8000/approvals/REQ001/approve -H "Content-Type: application/json" -d '{"approver": "Mrs Ade"}'
```

Use /reject instead of /approve to reject. A rejected request never changes the score.

## Mock data

Students STU001 to STU004 with scores in Mathematics, English and Physics. The school information has six entries (attendance, exam calendar, fees, uniform, mathematics course, grading scale). All data is fictional and in memory, so it resets when the server restarts.

## Testing

The assistant was tested manually. The 14 scenarios and their results are in docs/test_scenarios.md. They cover valid inputs, missing information, invalid parameters, tool failure, approval, rejection, prompt injection and an LLM provider failure. The audit log from the test runs is in docs/sample_audit_log.jsonl.

## Security notes

Permission boundaries, failure examples, known limitations and the mapping to the OWASP Top 10 for LLM Applications are in docs/failure_and_permission_notes.md. In short: the model can only prepare requests, approval lives outside its tools, inputs are validated before any tool runs, the phone number is never returned to the model, and the audit log records every attempt without tool results.

## Library versions

Recorded in requirements.txt and docs/test_scenarios.md, because tool calling behaviour can change between versions. Tested with Python 3.13, fastapi 0.162.4, pydantic 2.14.3, google-genai 3.1.0.