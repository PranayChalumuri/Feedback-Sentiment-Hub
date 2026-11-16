import base64
import binascii
import json
import logging
import os
import re
import uuid
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import parse_qs

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

AWS_REGION = os.getenv("AWS_REGION")
TABLE_NAME = os.getenv("FEEDBACK_TABLE_NAME", "pranaytable")
MAX_REQUEST_BODY_BYTES = 16 * 1024

# Keep this list identical to the frontend app selector.
VALID_APPS = {
    "Samsung Health",
    "LG Health",
    "Huawei Health",
    "Google Fit",
    "Mi Fit",
    "Teladoc Health",
    "MDLIVE",
    "Talkspace",
    "Zocdoc",
    "Mfine",
    "Tata 1mg",
    "GOOD MED",
}

ALLOWED_SENTIMENTS = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"}

session = boto3.Session()
dynamodb = session.resource("dynamodb", region_name=AWS_REGION)
comprehend = session.client("comprehend", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)


class ValidationError(ValueError):
    """Raised when submitted feedback does not meet application rules."""


def _response(status_code, body, content_type="application/json"):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
        "isBase64Encoded": False,
    }


def _request_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ValidationError("Request body must be valid UTF-8 form or JSON data.") from exc

    if len(body.encode("utf-8")) > MAX_REQUEST_BODY_BYTES:
        raise ValidationError("Request body exceeds the 16 KB limit.")

    headers = event.get("headers") or {}
    content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
    content_type = content_type.lower()

    if "application/json" in content_type:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValidationError("Request body must contain valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")
        return payload

    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _validate(payload):
    name = str(payload.get("fname", payload.get("name", ""))).strip()
    email = str(payload.get("email", "")).strip().lower()
    app_name = str(payload.get("appName", "")).strip()
    message = str(payload.get("message", "")).strip()

    if not name or len(name) > 100:
        raise ValidationError("Please provide a name of 1–100 characters.")

    if not email or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValidationError("Please provide a valid email address.")

    if app_name not in VALID_APPS:
        raise ValidationError("Please select a supported health app.")

    if not message or len(message) > 5000:
        raise ValidationError("Feedback must contain 1–5000 characters.")

    return {"fname": name, "email": email, "appName": app_name, "message": message}


def _html_page(filename):
    try:
        page = (Path(__file__).parent / "static" / filename).read_text(encoding="utf-8")
        return _response(200, page, "text/html; charset=utf-8")
    except OSError:
        logger.exception("Unable to load page: %s", filename)
        return _response(500, {"message": "Page is temporarily unavailable."})


def _get_sentiments(app_name, next_token=None):
    endpoint = os.getenv("APPSYNC_GRAPHQL_URL", "")
    if not endpoint or not AWS_REGION:
        return _response(503, {"message": "Dashboard API is not configured."})

    query = (
        "query GetSentiments($appName: String!, $nextToken: String) { "
        "getSentiments(appName: $appName, nextToken: $nextToken) { "
        "items { appName sentiment createdAt } nextToken } }"
    )
    variables = {"appName": app_name}
    if next_token:
        variables["nextToken"] = next_token
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")

    try:
        credentials = session.get_credentials()
        if credentials is None:
            raise RuntimeError("Lambda execution credentials are unavailable.")

        request = AWSRequest(
            method="POST",
            url=endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(credentials.get_frozen_credentials(), "appsync", AWS_REGION).add_auth(request)
        prepared = request.prepare()
        signed_request = urllib.request.Request(
            prepared.url,
            data=prepared.body,
            headers=dict(prepared.headers.items()),
            method=prepared.method,
        )

        with urllib.request.urlopen(signed_request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("errors"):
            logger.error("AppSync GraphQL errors: %s", payload["errors"])
            return _response(502, {"message": "Dashboard data could not be retrieved."})

        connection = payload.get("data", {}).get("getSentiments") or {}
        return _response(
            200,
            {
                "sentiments": connection.get("items") or [],
                "nextToken": connection.get("nextToken"),
            },
        )
    except Exception:
        logger.exception("AppSync request failed")
        return _response(502, {"message": "Dashboard data could not be retrieved."})


def lambda_handler(event, context):
    """Route page requests, dashboard reads and feedback submissions."""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("path") or event.get("rawPath") or "/"
    params = event.get("queryStringParameters") or {}

    if method == "OPTIONS":
        return _response(204, "")

    if method == "GET":
        if path.endswith("/api/sentiments"):
            app_name = (params.get("app") or "").strip()
            if app_name not in VALID_APPS:
                return _response(400, {"message": "Please select a supported health app."})
            return _get_sentiments(app_name, params.get("nextToken"))
        if path.endswith("/dashboard"):
            app_name = (params.get("app") or "").strip()
            if app_name not in VALID_APPS:
                return _response(400, {"message": "Please select a supported health app."})
            return _html_page("dashboard.html")
        if path.endswith("/app-selection") or params.get("page") == "app_selection":
            return _html_page("app-selection.html")
        return _html_page("index.html")

    if method != "POST":
        return _response(405, {"message": "Method not allowed."})

    try:
        payload = _validate(_request_body(event))
        sentiment_result = comprehend.detect_sentiment(Text=payload["message"], LanguageCode="en")
        sentiment = sentiment_result.get("Sentiment")
        if sentiment not in ALLOWED_SENTIMENTS:
            raise RuntimeError("Comprehend returned an unexpected sentiment label.")

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        item = {
            "feedbackId": str(uuid.uuid4()),
            "fname": payload["fname"],
            "email": payload["email"],
            "appName": payload["appName"],
            "message": payload["message"],
            "sentiment": sentiment,
            "createdAt": created_at,
        }
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(feedbackId)")

        logger.info(
            "Feedback stored successfully: appName=%s sentiment=%s feedbackId=%s",
            item["appName"], item["sentiment"], item["feedbackId"],
        )
        return _html_page("thank-you.html")

    except ValidationError as exc:
        return _response(400, {"message": str(exc)})
    except (ClientError, BotoCoreError):
        logger.exception("AWS service error while processing feedback.")
        return _response(503, {"message": "Feedback could not be saved right now. Please try again."})
    except Exception:
        logger.exception("Unexpected error while processing feedback.")
        return _response(500, {"message": "An unexpected error occurred. Please try again."})
