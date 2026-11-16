import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from html import escape
from urllib.parse import parse_qs

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

AWS_REGION = os.getenv("AWS_REGION")
TABLE_NAME = os.getenv("FEEDBACK_TABLE_NAME", "pranaytable")

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

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
comprehend = boto3.client("comprehend", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)


class ValidationError(ValueError):
    """Raised when submitted feedback does not meet application rules."""


def _response(status_code, body, content_type="application/json"):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": os.getenv("CORS_ALLOW_ORIGIN", "*"),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
        "isBase64Encoded": False,
    }


def _request_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

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

    # HTML form submissions use application/x-www-form-urlencoded.
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

    return {
        "fname": name,
        "email": email,
        "appName": app_name,
        "message": message,
    }


def _thank_you_page():
    # A small inline confirmation keeps the submission flow functional while
    # the original HTML pages are integrated into the new deployment package.
    return """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thank you</title></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:12vh auto;padding:24px;text-align:center">
<h1>Thank you for your feedback!</h1>
<p>Your feedback has been received successfully.</p>
<a href="/">Return to the feedback form</a>
</body></html>"""


def lambda_handler(event, context):
    """Accept feedback through API Gateway REST (proxy integration)."""
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS":
        return _response(204, "")

    if method != "POST":
        return _response(405, {"message": "Method not allowed."})

    try:
        payload = _validate(_request_body(event))

        sentiment_result = comprehend.detect_sentiment(
            Text=payload["message"],
            LanguageCode="en",
        )
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

        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(feedbackId)",
        )

        logger.info(
            "Feedback stored successfully: appName=%s sentiment=%s feedbackId=%s",
            item["appName"],
            item["sentiment"],
            item["feedbackId"],
        )
        return _response(200, _thank_you_page(), "text/html; charset=utf-8")

    except ValidationError as exc:
        return _response(400, {"message": str(exc)})
    except (ClientError, BotoCoreError):
        logger.exception("AWS service error while processing feedback.")
        return _response(503, {"message": "Feedback could not be saved right now. Please try again."})
    except Exception:
        logger.exception("Unexpected error while processing feedback.")
        return _response(500, {"message": "An unexpected error occurred. Please try again."})
