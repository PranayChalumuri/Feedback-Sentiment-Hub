# AppSync setup – rebuild v2

## GraphQL API

Create a new GraphQL API in `ap-south-1`. Do not reuse the old API ID, endpoint, or API key.

The schema is in `graphql/schema.graphql`.

## DynamoDB data source

Create a DynamoDB data source pointing to the `pranaytable` table. Use a dedicated IAM role for AppSync with only:

- `dynamodb:Query` on the table's `AppNameCreatedAtIndex` index ARN.
- The role trust policy must allow `appsync.amazonaws.com` to assume it.

The Lambda execution role and AppSync data source role must remain separate.

## Resolver

Attach a UNIT resolver to Query.getSentiments using the DynamoDB data source.

- Request mapping template: `graphql/resolvers/getSentiments.request.vtl`
- Response mapping template: `graphql/resolvers/getSentiments.response.vtl`

The request queries the GSI by appName and returns newest records first. The index projection includes appName, createdAt, and sentiment, matching the GraphQL Sentiment type.

## Authentication

For initial development, choose an authentication mode deliberately. Do not paste API keys into source control. If API key authentication is selected for the public demo dashboard, treat the key as public and restrict the schema to read-only chart data. Prefer Cognito or another authenticated flow if the dashboard later exposes user-specific data.

## Verification

Use the AppSync Queries page to run:

```graphql
query TestSentiments {
  getSentiments(appName: "Samsung Health") {
    appName
    sentiment
    createdAt
  }
}
```

An empty list is a valid response when no feedback has been submitted for that app.
