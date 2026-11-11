# Failure Examples and Permission Boundary Notes


## 1. Permission boundaries


1. Read only tools and the sensitive action are separated. search_school_info, calculate_grade and lookup_student_record never change data. The only sensitive action, a grade change, is exposed to the model as prepare_grade_change, which only creates a pending request and changes nothing.

2. The model cannot approve. The approve and reject functions are in app/approvals.py and are exposed only as the HTTP endpoints /approvals/{request_id}/approve and /reject. They are not in the TOOLS registry, so the model has no tool it could call to approve its own request. Scenarios 9 and 10 confirm this.

3. Rejection stops the action completely. A rejected request is marked rejected and the stored score is never touched (scenario 8). A request that was already approved or rejected cannot be decided again (scenario 13).

4. Least privilege on data. lookup_student_record does not return the guardian phone number, because the assistant does not need it. The audit log also redacts known sensitive keys (guardian_phone, api_key) in tool arguments as a second layer.

5. Every tool input is validated by Pydantic before the function runs: student ID pattern, score range 0 to 100, reason length, query length, list size. Invalid input never reaches the tool logic.

6. Unknown tool names are refused with unknown_tool (HTTP 404).

7. The tool loop is capped at 5 steps per chat message, and chat messages are limited to 1000 characters.

8. Secrets are read from environment variables. .env is in .gitignore and only .env.example is committed.


## 2. Audit logging


Every tool attempt writes one JSON line to the audit log: timestamp, event, actor, tool, arguments (redacted) and outcome. This includes successes, invalid arguments, unknown tools, not found errors, approval decisions, repeated decisions and LLM provider errors. Tool results are never written to the log, so student names and scores do not appear in it. A cleaned sample is in docs/sample_audit_log.jsonl.


## 3. Failure examples


1. Invalid parameter (scenario 5). The model passed a score of 150. Pydantic rejected it with invalid_arguments, no request was created, and the assistant explained the valid range.

2. Missing information (scenario 4). With no scores given, the model made no tool call and asked for them.

3. Student not found (scenario 6). The tool returned student_not_found and the assistant asked the user to check the ID.

4. Tool called for something it cannot do (scenario 11). For a request to send a notice, the assistant said it cannot do that. No notice tool exists.

5. Prompt injection (scenario 10). The model refused to bypass approval. Even if it had followed the instruction, the best it could have done was create a pending request, because the approval step is outside its tools.

6. Provider failure (scenario 12). Gemini returned a ServerError. The app returned llm_unavailable with HTTP 502, wrote an llm_error audit line, ran no tools and changed no data.

7. Repeated and incomplete approvals (scenarios 13 and 14). A second decision returns 409 already_decided. A missing approver returns 422 before reaching the gate.


## 4. Known limitations


1. The mock database and pending requests live in memory and reset when the server restarts.

2. The approver is a name typed into the request body and is not authenticated. A real system would need login and roles, and the approval endpoints should not be open to the same users who chat with the assistant.

3. The endpoints have no authentication or rate limiting.

4. The audit log is a plain local file. It is not tamper proof and is not rotated.

5. The reason text for a grade change is free text written by the model from the user's message and is logged as given. A real system should limit what goes in it.

6. There is no retry for temporary provider errors. The user has to send the message again.

7. Model behaviour is not deterministic. The tests show the behaviour I observed, but wording and occasional extra read only tool calls (scenario 11) can differ between runs. The safety guarantees come from validation and the approval gate, not from the model.

8. School information search is simple keyword matching over six entries.


## 5. Mapping to the course security resources


OWASP Top 10 for LLM Applications (2025):
LLM01 Prompt Injection: handled by keeping approval outside the model's tools (scenarios 9 and 10).

LLM02 Sensitive Information Disclosure: phone number not returned to the model, redaction in the audit log.

LLM05 Improper Output Handling: model output is treated as untrusted input and validated by Pydantic before any tool runs.

LLM06 Excessive Agency: the model can only prepare a request. Humans decide.

LLM10 Unbounded Consumption: step cap and message length limit.

NIST AI Risk Management Framework: the audit log and approval gate support the Manage function (human oversight and traceability), and the written tests and limitations support Measure.


## 6. Library versions


Tool calling behaviour changes between library and model versions, so the versions used are recorded in docs/test_scenarios.md and requirements.txt.