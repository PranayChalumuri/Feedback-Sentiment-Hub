# Feedback Sentiment Hub – Rebuild v2

## Confirmed project decisions

- AWS Region: ap-south-1 (Mumbai)
- Feedback storage table: pranaytable
- API Gateway REST API for feedback submission and page delivery
- AWS Lambda (Python) for validation, Comprehend sentiment analysis, and persistence
- Amazon Comprehend sentiment labels: POSITIVE, NEGATIVE, MIXED, NEUTRAL
- AWS AppSync GraphQL API for dashboard reads
- Google Charts for dashboard visualizations
- Preserve the original 12 health-app options, including GOOD MED

## Request flow

1. Browser submits feedback to API Gateway.
2. API Gateway invokes the Python Lambda function.
3. Lambda validates the submitted fields and app name.
4. Lambda calls Comprehend DetectSentiment.
5. Lambda writes the feedback record to DynamoDB table pranaytable.
6. Dashboard requests sentiment records for the selected app through AppSync.
7. Google Charts renders sentiment totals and distribution.

## Initial data model direction

Use a generated feedback ID as the DynamoDB partition key. Store appName, sentiment, createdAt, and the submitted feedback fields. Add an appName-based index so dashboard reads can query one app rather than scanning the entire table.

The dashboard GraphQL type intentionally does not expose email addresses. Email is personal data and is not needed to calculate sentiment charts.

## AppSync schema

The initial schema is in graphql/schema.graphql. It adds an appName argument to getSentiments so the resolver can query the appName index.

## Security principles

- No API keys or credentials in source code.
- Lambda execution role receives only required DynamoDB and Comprehend permissions.
- Dashboard reads only the fields needed for charts.
- Validate appName against the single canonical 12-app list.
- Do not reuse old account IDs, API keys, or IAM policies.

## Deployment status

No AWS resources have been created and nothing has been deployed. This branch contains development work only.
