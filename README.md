# Feedback Sentiment Hub

A serverless portfolio project that collects feedback about health applications, analyzes its sentiment with Amazon Comprehend, stores submissions in Amazon DynamoDB, and presents sentiment summaries in a public dashboard.

> **Showcase/demo only:** This project is intended for technical demonstration and recruiter review. It is not a healthcare service or a production-ready system. The form collects a name, email address, and feedback text. Records are not automatically deleted. Do not submit real personal, medical, or sensitive information.

## Project status

- Rebuild branch: `rebuild-v2`
- AWS region configured for the project: `ap-south-1` (Mumbai)
- Automated source and infrastructure checks: GitHub Actions
- AWS deployment: **not performed**
- Live AWS integration: **not verified**

No live demo link is published for this rebuild. The older deployment URL from the original project is intentionally not presented as the rebuild.

## Architecture

```text
Browser
  |
  +-- Feedback form / public dashboard
  |
API Gateway (REST)
  |
AWS Lambda (Python)
  |                  |
  |                  +--> Amazon Comprehend (sentiment detection)
  |
  +--> Amazon DynamoDB (feedback records)
  |
  +--> AWS AppSync (IAM-authenticated GraphQL)
          |
          +--> DynamoDB AppNameCreatedAtIndex
```

The browser calls same-origin API Gateway routes. Lambda signs its AppSync GraphQL requests with AWS Signature Version 4 using its execution role. The browser receives no AWS credentials or AppSync API key.

## Features

### Feedback submission
- Name and email fields retained from the original project.
- Select from 12 supported health applications.
- Input validation and a 16 KB request-body limit.
- Amazon Comprehend sentiment labels: `POSITIVE`, `NEGATIVE`, `MIXED`, and `NEUTRAL`.

### Public sentiment dashboard
- Public app-selection and dashboard pages.
- Five KPI values: total, positive, negative, mixed, and neutral feedback.
- Four Google Charts visualizations.
- Refreshes every 30 seconds.
- Handles AppSync/DynamoDB pagination and guards against repeated cursors and excessive page counts.
- Dashboard data is restricted to app name, sentiment, and timestamp. Submitter name, email, and feedback text are not part of the GraphQL response.

### Data storage
- DynamoDB table: `pranaytable` (configurable in the SAM template).
- Partition key: `feedbackId`.
- GSI: `AppNameCreatedAtIndex`, partitioned by app name and sorted by creation time.
- On-demand billing mode.
- No TTL or automatic record expiry. Demo records remain until manually deleted or the table is removed.

## Repository structure

```text
graphql/                  GraphQL schema and AppSync resolver templates
src/lambda_function.py    Python Lambda handler
src/static/               Feedback, app-selection, dashboard, and thank-you pages
tests/                    Lambda unit tests with mocked AWS services
scripts/                  Frontend validation
docs/                     Architecture, data design, setup, and review notes
template.yaml             AWS SAM / CloudFormation infrastructure
.github/workflows/        Automated project checks
```

## Run checks locally

The GitHub Actions workflow runs Python compilation, unit tests, JavaScript syntax validation, and CloudFormation linting.

Typical local commands (after installing the listed tools/dependencies):

```bash
python -m py_compile src/lambda_function.py
python -m unittest discover -s tests -v
python scripts/validate_frontend.py
cfn-lint template.yaml
```

These checks do not deploy resources or prove live AWS integration.

## Security and privacy notes

- Lambda uses IAM roles for DynamoDB writes and AppSync field access.
- The AppSync data-source role is restricted to querying the dashboard GSI.
- Name, email, and free-text feedback are stored in DynamoDB.
- No automatic retention or deletion is configured.
- The dashboard is intentionally public and exposes app name, sentiment, and timestamp only.
- The submission endpoint is public. API Gateway throttling is a baseline safeguard, not comprehensive abuse protection or a cost ceiling.
- The form warns visitors not to submit real personal, medical, or sensitive information.

See [docs/pre-deployment-review.md](docs/pre-deployment-review.md) for known limitations and checks required before any deployment.

## Technologies

- AWS Lambda (Python 3.12)
- Amazon API Gateway
- Amazon DynamoDB
- AWS AppSync (GraphQL, IAM authorization)
- Amazon Comprehend
- AWS SAM / CloudFormation
- GitHub Actions
- HTML, CSS, JavaScript, Tailwind CSS, Google Charts
