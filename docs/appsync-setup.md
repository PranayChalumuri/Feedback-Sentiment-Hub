# AppSync setup – rebuild v2

## GraphQL API

The infrastructure template creates a new GraphQL API in the deployment region. The API uses AWS_IAM authentication; do not reuse the old API ID, endpoint, or API key.

The schema is defined in `template.yaml` and mirrored in `graphql/schema.graphql`. Keep both definitions aligned when changing the GraphQL contract.

## DynamoDB data source

The template creates a DynamoDB data source pointing to the configured feedback table (default: `pranaytable`). AppSync assumes a dedicated IAM role with only `dynamodb:Query` access to the `AppNameCreatedAtIndex` GSI ARN.

The Lambda execution role and AppSync data source role remain separate.

## Resolver and pagination

The template creates a UNIT resolver on `Query.getSentiments` using the DynamoDB data source.

- Request mapping template: `graphql/resolvers/getSentiments.request.vtl`
- Response mapping template: `graphql/resolvers/getSentiments.response.vtl`
- The resolver queries the GSI by `appName`, newest records first.
- Each resolver request asks DynamoDB for up to 100 records. DynamoDB may return fewer when the 1 MB response limit is reached.
- The response includes `items` and an opaque `nextToken`. The token is passed back on the next GraphQL request until it is null.

The index projection includes `appName`, `createdAt`, and `sentiment`, matching the GraphQL `Sentiment` type.

## Authentication and request flow

- Browser → API Gateway: the dashboard calls the same-origin `/api/sentiments?app=...` endpoint.
- API Gateway → Lambda: Lambda validates the selected app and optional pagination token.
- Lambda → AppSync: Lambda signs each GraphQL page request with its execution-role credentials using AWS Signature Version 4.
- AppSync → DynamoDB: AppSync uses its separate data-source role to query the GSI.
- Lambda returns one page and its opaque cursor to the browser. The dashboard requests subsequent pages sequentially and aggregates the rows for its charts.

The Lambda role receives `appsync:GraphQL` permission scoped to the single `Query.getSentiments` field ARN. No AppSync API key is created, stored in an environment variable, or exposed to the browser.

## Verification after deployment

Use the AppSync Queries page or the signed Lambda proxy to run:

```graphql
query TestSentiments($appName: String!, $nextToken: String) {
  getSentiments(appName: $appName, nextToken: $nextToken) {
    items {
      appName
      sentiment
      createdAt
    }
    nextToken
  }
}
```

Pass the returned `nextToken` as the next request's `nextToken` variable. An empty `items` list with a null token is a valid response when no matching feedback exists. Direct console query testing must use an IAM-authorized identity.

## Operational note

The dashboard retrieves every page sequentially to calculate totals across all feedback. A refresh is skipped while the previous refresh is still running. For very large datasets, consider server-side aggregate counters or time-window filtering rather than repeatedly downloading the full history every five seconds.
