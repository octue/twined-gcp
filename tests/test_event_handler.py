import base64
import os
import unittest
from unittest.mock import patch

from functions.event_handler.main import handle_event
from tests.mocks import MockBigQueryClient, MockCloudEvent

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))


class TestEventHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment_variables_patch = patch.dict(
            "os.environ",
            {
                "BIGQUERY_EVENTS_TABLE": "my-table",
                "OCTUE_SERVICES_TOPIC": "test.octue.services",
                "KUEUE_LOCAL_QUEUE": "test-queue",
                "ARTIFACT_REGISTRY_REPOSITORY_URL": "some-artifact-registry-url",
            },
        )

        cls.environment_variables_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment_variables_patch.stop()

    def test_store_pub_sub_event_in_bigquery(self):
        """Test that the `event_handler` cloud function can receive, parse, and store an event in BigQuery."""
        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b'{"kind": "heart", "some": "data"}'),
                    "attributes": {
                        "datetime": "2024-04-11T09:26:39.144818",
                        "uuid": "c8bda9fa-f072-4330-92b1-96920d06b28d",
                        "parent": "octue/parent-test-service:5.6.3",
                        "originator": "octue/ancestor-test-service:5.6.3",
                        "sender": "octue/test-service:5.6.3",
                        "sender_type": "PARENT",
                        "sender_sdk_version": "1.0.3",
                        "recipient": "octue/another-service:1.0.0",
                        "question_uuid": "ca534cdd-24cb-4ed2-af57-e36757192acb",
                        "parent_question_uuid": "1d897229-155d-498d-b6ae-21960fab3754",
                        "originator_question_uuid": "fb6cf9a3-84fb-45ce-a4da-0d2257bec319",
                        "forward_logs": True,
                    },
                    "messageId": "1234",
                }
            }
        )

        mock_big_query_client = MockBigQueryClient()

        with patch("functions.event_handler.main.BigQueryClient", return_value=mock_big_query_client):
            handle_event(cloud_event)

        self.assertEqual(
            mock_big_query_client.inserted_rows[0][0],
            {
                "datetime": "2024-04-11T09:26:39.144818",
                "uuid": "c8bda9fa-f072-4330-92b1-96920d06b28d",
                "kind": "heart",
                "event": {"some": "data"},
                "other_attributes": {
                    "forward_logs": True,
                },
                "parent": "octue/parent-test-service:5.6.3",
                "originator": "octue/ancestor-test-service:5.6.3",
                "sender": "octue/test-service:5.6.3",
                "sender_type": "PARENT",
                "sender_sdk_version": "1.0.3",
                "recipient": "octue/another-service:1.0.0",
                "question_uuid": "ca534cdd-24cb-4ed2-af57-e36757192acb",
                "parent_question_uuid": "1d897229-155d-498d-b6ae-21960fab3754",
                "originator_question_uuid": "fb6cf9a3-84fb-45ce-a4da-0d2257bec319",
                "backend": "GoogleCloudPubSub",
                "backend_metadata": {"message_id": "1234", "ordering_key": None},
            },
        )
