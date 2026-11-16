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

### 1. Personal-data notice and retention – showcase decision recorded

The form collects a name, email address, and free-text feedback. The owner has confirmed that these fields remain for continuity with the original showcase. The owner has also chosen no automatic retention/TTL policy: records remain until manually deleted. This is an explicit portfolio-demo trade-off, not a production privacy recommendation.

**Agreed showcase handling:**
- Keep the name and email fields, matching the original project.
- Do not configure DynamoDB TTL. Records remain until manually deleted or the table is removed.
- Display a notice on the form explaining what is stored, that records are not automatically deleted, and that visitors must not submit real personal, medical, or sensitive information.
- This demo is not a healthcare service and must not be presented as production-ready.

### 2. Public submission endpoint and abuse controls – high priority

The POST route has no authentication, CAPTCHA, or per-client rate limit. API Gateway's configured 5 requests/second and burst 10 throttles are stage-level best-effort limits; they do not prevent distributed abuse or guarantee a cost ceiling. Repeated submissions can invoke Comprehend and write to DynamoDB.

**Recommended decision:**
- Decide whether anonymous public submissions are required for the portfolio demo.
- Before public exposure, add an abuse-control layer appropriate to the audience (for example, AWS WAF rate-based rules and/or a CAPTCHA or verified submission flow).
- Add request-size limits and consider duplicate/spam controls. Keep the current field validation as a second layer.
- Set AWS Budgets and billing alerts before any approved deployment; alerts are notifications, not hard spending caps.

### 3. Public dashboard access – owner-approved showcase behavior

The dashboard and `/api/sentiments` route are intentionally public for recruiter demonstrations. The owner approved this behavior. The GraphQL response exposes only app name, sentiment, and timestamp—not names, email addresses, or message text. Public submission activity is therefore visible, but submitter identity and free-text feedback are not.

### 4. Full-history polling and pagination – medium priority

The browser retrieves every page sequentially and repeats that work every 30 seconds. This correctly follows pagination, but request volume and response time grow with the complete history. A single refresh can still issue many API and AppSync calls.

**Recommended improvements before scaling:**
- For a small portfolio demo, consider a bounded date window; the current dashboard already uses a 30-second refresh interval and a 100-page ceiling.
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

## Showcase decisions and deployment gate

The owner-approved showcase choices are:
- Keep name and email fields.
- Do not configure automatic data expiry or DynamoDB TTL; records remain until manually deleted.
- Keep the dashboard public, exposing only app name, sentiment, and timestamp.
- Display a clear demo/privacy notice on the submission form and discourage real or sensitive data.

These choices are for a portfolio demonstration and are not a production privacy or abuse-prevention design. Public submissions can still be abused and may incur AWS service costs. Before any public deployment, review abuse controls, billing alerts, privacy wording, and the expected cost exposure. Deployment still requires the owner's separate explicit approval.

**Status:** source review and showcase decisions documented; no AWS deployment or live integration test performed.
