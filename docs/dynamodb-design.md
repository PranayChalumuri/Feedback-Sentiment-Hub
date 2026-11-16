# DynamoDB table design – rebuild v2

## Table

- Table name: `pranaytable`
- Billing mode: on-demand (`PAY_PER_REQUEST`)
- Partition key: `feedbackId` (String)

## Feedback item

| Attribute | Type | Purpose |
|---|---|---|
| feedbackId | String | Unique ID for each submission; table partition key |
| fname | String | Submitter name |
| email | String | Submitter email |
| appName | String | Selected health application |
| message | String | Feedback text |
| sentiment | String | POSITIVE, NEGATIVE, MIXED, or NEUTRAL |
| createdAt | String | UTC ISO-8601 timestamp |

## Global secondary index

- Name: `AppNameCreatedAtIndex`
- Partition key: `appName` (String)
- Sort key: `createdAt` (String)
- Projection: `INCLUDE` with `sentiment`

This index lets AppSync query feedback for one selected app and return the fields required by the dashboard without scanning the entire table. The timestamp sort key also supports chronological ordering.

## Access boundaries

- Feedback Lambda: `dynamodb:PutItem` on this table only.
- AppSync resolver role: `dynamodb:Query` on this table's index only (to be defined with the AppSync data source).
- The dashboard GraphQL type does not expose name, email, or feedback message.

## Important

The SAM template defines this table as infrastructure. It does not create anything until a deployment is explicitly run and approved. If a table named `pranaytable` already exists in the new account, deployment needs an import/retention decision rather than an attempted duplicate table creation.
