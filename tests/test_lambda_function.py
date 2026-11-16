import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import lambda_function as app


class RequestParsingTests(unittest.TestCase):
    def test_urlencoded_form_decodes_plus_as_space(self):
        event = {
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "body": "fname=Jane+Doe&email=JANE%40EXAMPLE.COM&appName=Samsung+Health&message=Great+app",
        }
        payload = app._request_body(event)
        self.assertEqual(payload["fname"], "Jane Doe")
        self.assertEqual(payload["message"], "Great app")

    def test_json_body_must_be_an_object(self):
        event = {
            "headers": {"content-type": "application/json"},
            "body": json.dumps(["not", "an", "object"]),
        }
        with self.assertRaises(app.ValidationError):
            app._request_body(event)

    def test_invalid_json_returns_validation_error(self):
        event = {"headers": {"Content-Type": "application/json"}, "body": "{bad"}
        with self.assertRaises(app.ValidationError):
            app._request_body(event)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.valid_payload = {
            "fname": "Jane Doe",
            "email": "JANE@example.com",
            "appName": "Samsung Health",
            "message": "The app is easy to use.",
        }

    def test_valid_payload_is_normalized(self):
        result = app._validate(self.valid_payload)
        self.assertEqual(result["email"], "jane@example.com")
        self.assertEqual(result["fname"], "Jane Doe")

    def test_all_twelve_apps_are_supported(self):
        self.assertEqual(len(app.VALID_APPS), 12)
        for name in app.VALID_APPS:
            payload = dict(self.valid_payload, appName=name)
            self.assertEqual(app._validate(payload)["appName"], name)

    def test_invalid_email_is_rejected(self):
        payload = dict(self.valid_payload, email="not-an-email")
        with self.assertRaises(app.ValidationError):
            app._validate(payload)

    def test_unknown_app_is_rejected(self):
        payload = dict(self.valid_payload, appName="Unknown Health")
        with self.assertRaises(app.ValidationError):
            app._validate(payload)

    def test_empty_feedback_is_rejected(self):
        payload = dict(self.valid_payload, message="  ")
        with self.assertRaises(app.ValidationError):
            app._validate(payload)


class HandlerTests(unittest.TestCase):
    def test_options_preflight(self):
        result = app.lambda_handler({"httpMethod": "OPTIONS", "path": "/"}, None)
        self.assertEqual(result["statusCode"], 204)

    def test_unknown_method_returns_405(self):
        result = app.lambda_handler({"httpMethod": "DELETE", "path": "/"}, None)
        self.assertEqual(result["statusCode"], 405)

    def test_invalid_dashboard_app_returns_400(self):
        event = {
            "httpMethod": "GET",
            "path": "/dashboard",
            "queryStringParameters": {"app": "Unknown"},
        }
        result = app.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 400)

    def test_dashboard_route_serves_dashboard_page(self):
        event = {
            "httpMethod": "GET",
            "path": "/dashboard",
            "queryStringParameters": {"app": "Samsung Health"},
        }
        with patch.object(app, "_html_page", return_value={"statusCode": 200, "body": "dashboard"}) as page:
            result = app.lambda_handler(event, None)
        page.assert_called_once_with("dashboard.html")
        self.assertEqual(result["statusCode"], 200)

    def test_feedback_submission_saves_sentiment_and_returns_thank_you(self):
        payload = {
            "fname": "Jane Doe",
            "email": "jane@example.com",
            "appName": "Samsung Health",
            "message": "Great app",
        }
        event = {
            "httpMethod": "POST",
            "path": "/",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "body": "fname=Jane+Doe&email=jane%40example.com&appName=Samsung+Health&message=Great+app",
        }
        with patch.object(app.comprehend, "detect_sentiment", return_value={"Sentiment": "POSITIVE"}), \
             patch.object(app.table, "put_item") as put_item, \
             patch.object(app, "_html_page", return_value={"statusCode": 200, "body": "thank-you"}) as page:
            result = app.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        page.assert_called_once_with("thank-you.html")
        saved = put_item.call_args.kwargs["Item"]
        self.assertEqual(saved["fname"], payload["fname"])
        self.assertEqual(saved["email"], payload["email"])
        self.assertEqual(saved["appName"], payload["appName"])
        self.assertEqual(saved["sentiment"], "POSITIVE")
        self.assertTrue(saved["feedbackId"])
        self.assertTrue(saved["createdAt"].endswith("Z"))

    def test_missing_appsync_configuration_returns_503(self):
        with patch.dict(os.environ, {"APPSYNC_GRAPHQL_URL": ""}), patch.object(app, "AWS_REGION", None):
            result = app._get_sentiments("Samsung Health")
        self.assertEqual(result["statusCode"], 503)


if __name__ == "__main__":
    unittest.main()
