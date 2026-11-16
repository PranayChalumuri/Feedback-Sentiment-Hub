# AppSync setup – rebuild v2

## GraphQL API

The infrastructure template creates a new GraphQL API in the deployment region. The API uses AWS_IAM authentication; do not reuse the old API ID, endpoint, or API key.

The schema is defined in `template.yaml` and mirrored in `graphql/schema.graphql`. Keep both definitions aligned when changing the GraphQL contract.

## DynamoDB data source

The template creates a DynamoDB data source pointing to the configured feedback table (default: `pranaytable`). AppSync assumes a dedicated IAM role with only `dynamodb:Query` access to the `AppNameCreatedAtIndex` GSI ARN.

The Lambda execution role and AppSync data source role remain separate.

## Resolver

The template creates a UNIT resolver on `Query.getSentiments` using the DynamoDB data source.

- Request mapping template: `graphql/resolvers/getSentiments.request.vtl`
- Response mapping template: `graphql/resolvers/getSentiments.response.vtl`

The resolver queries the GSI by `appName`, returns newest records first, and currently returns at most 1,000 records. The index projection includes `appName`, `createdAt`, and `sentiment`, matching the GraphQL type.

## Authentication and request flow

- Browser → API Gateway: the dashboard calls the same-origin `/api/sentiments?app=...` endpoint.
- API Gateway → Lambda: Lambda validates the selected app.
- Lambda → AppSync: Lambda signs the GraphQL request with its execution-role credentials using AWS Signature Version 4.
- AppSync → DynamoDB: AppSync uses its separate data-source role to query the GSI.

The Lambda role receives `appsync:GraphQL` permission scoped to this API's GraphQL resources. No AppSync API key is created, stored in an environment variable, or exposed to the browser.

## Verification after deployment

Use the AppSync Queries page or the signed Lambda proxy to run:

```graphql
query TestSentiments {
  getSentiments(appName: "Samsung Health") {
    appName
    sentiment
    createdAt
  }
}
```

An empty list is a valid response when no feedback has been submitted for that app. Direct console query testing must use an IAM-authorized identity.

## Current limitations

The resolver returns up to 1,000 sentiment records for the selected app. Pagination should be implemented before the application is expected to hold more than 1,000 feedback items for one app. The dashboard should handle an empty result and API errors without implying that no feedback exists when the API request itself failed.
