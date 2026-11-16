# Pre-deployment review – security, privacy, and operations

**Review scope:** source and infrastructure definitions on `rebuild-v2`. This is a code review only. No AWS account was accessed and no resources were created or deployed.

## Current strengths

- The browser calls a same-origin API; it does not receive AWS credentials or an AppSync API key.
- Lambda writes feedback to one DynamoDB table, while AppSync has a separate role limited to querying the dashboard GSI.
- The GraphQL dashboard type omits submitter name, email, and feedback message.
- Lambda validates required fields, limits their lengths, and restricts app names to the supported list.
- Logs record the feedback ID, app name, and sentiment rather than the submitted name, email, or message.
- API Gateway has an initial stage throttle configuration. This is a protective baseline, not a per-user abuse control or throughput guarantee.

## Findings to resolve before public launch

### 1. Personal-data notice and retention – high priority

The form collects a name, email address, and free-text feedback. The DynamoDB design currently has no TTL attribute or documented retention period, and the form does not explain why these details are collected, who operates the service, how long they are retained, or how a submitter can request deletion.

**Recommended decision:**
- Decide whether name and email are genuinely required. If not, remove them from the form and storage.
- Add a concise privacy notice before accepting real submissions, including purpose, retention, contact/deletion process, and any third-party processing.
- Agree a retention period and implement a tested deletion/TTL strategy. DynamoDB TTL deletion is asynchronous, so it should not be described as immediate erasure.
- Avoid collecting sensitive health details in free text; make clear that this is a demo feedback project, not a healthcare service.

### 2. Public submission endpoint and abuse controls – high priority

The POST route has no authentication, CAPTCHA, or per-client rate limit. API Gateway's configured 5 requests/second and burst 10 throttles are stage-level best-effort limits; they do not prevent distributed abuse or guarantee a cost ceiling. Repeated submissions can invoke Comprehend and write to DynamoDB.

**Recommended decision:**
- Decide whether anonymous public submissions are required for the portfolio demo.
- Before public exposure, add an abuse-control layer appropriate to the audience (for example, AWS WAF rate-based rules and/or a CAPTCHA or verified submission flow).
- Add request-size limits and consider duplicate/spam controls. Keep the current field validation as a second layer.
- Set AWS Budgets and billing alerts before any approved deployment; alerts are notifications, not hard spending caps.

### 3. Public dashboard access – medium priority

The dashboard and `/api/sentiments` route are publicly callable. The current GraphQL response exposes only app name, sentiment, and timestamp—not names, email addresses, or message text—but it still reveals submission activity.

**Recommended decision:**
- Confirm that public sentiment counts and timestamps are intended.
- If not, protect the dashboard/API with an access-control mechanism before launch.
- Keep personal fields out of the GraphQL type and dashboard response.

### 4. Full-history polling and pagination – medium priority

The browser retrieves every page sequentially and repeats that work every five seconds. This correctly follows pagination, but request volume and response time grow with the complete history. A single refresh can issue many API and AppSync calls.

**Recommended improvements before scaling:**
- For a small portfolio demo, consider a longer refresh interval and a bounded date window.
- For larger datasets, return server-side aggregates or query a time window rather than downloading every record.
- Add a maximum page/record budget and a clear “data is too large; narrow the date range” response if full-history loading is retained.
- Test pagination with enough records to force multiple pages, including a DynamoDB 1 MB page boundary, after deployment is explicitly approved.

### 5. CORS and browser security headers – partially resolved

The frontend uses same-origin requests. Wildcard CORS response headers and the broad API Gateway CORS configuration have been removed from the source, so cross-origin browser clients are not intentionally supported. CORS is not authentication and does not stop direct HTTP clients.

**Remaining improvement:**
- Consider a Content-Security-Policy and a Referrer-Policy after reviewing the external Google Charts, Tailwind, and Google Fonts dependencies.
- Keep `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.

### 6. Operational and integration verification – required after approval

Current GitHub Actions checks validate Python compilation, unit tests with mocks, inline JavaScript syntax, and CloudFormation template linting. They do **not** prove that deployed API Gateway routes, Lambda packaging, IAM field authorization, AppSync resolver templates, DynamoDB index queries, or real pagination work together in AWS.

After explicit deployment approval, verify:
- A test submission is stored once and gets the expected sentiment.
- Invalid input and unsupported app names are rejected.
- IAM-authorized Lambda-to-AppSync calls succeed while unauthorized calls fail.
- Queries return the expected app's records in descending timestamp order.
- Pagination works across multiple pages and produces no duplicate or skipped records.
- The public dashboard exposes no name, email, or free-text feedback.
- Throttling, alarms, logs, retention/deletion, and cost alerts behave as intended.

## Launch gate

Do not deploy until the owner has explicitly approved the deployment and made decisions on data minimization, privacy notice, retention/deletion, public dashboard visibility, and abuse controls.

**Status:** source review documented; no AWS deployment or live integration test performed.
