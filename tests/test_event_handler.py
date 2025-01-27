import base64
import copy
import json
import os
import unittest
from unittest.mock import patch

from functions.event_handler.main import handle_event
from tests.mocks import MockBigQueryClient, MockCloudEvent

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))
QUESTION_UUID = "ca534cdd-24cb-4ed2-af57-e36757192acb"
SRUID = "octue/another-service:1.0.0"

EVENT_ATTRIBUTES = {
    "datetime": "2024-04-11T09:26:39.144818",
    "uuid": "c8bda9fa-f072-4330-92b1-96920d06b28d",
    "parent": "octue/parent-test-service:5.6.3",
    "originator": "octue/ancestor-test-service:5.6.3",
    "sender": "octue/test-service:5.6.3",
    "sender_type": "PARENT",
    "sender_sdk_version": "1.0.3",
    "recipient": SRUID,
    "question_uuid": QUESTION_UUID,
    "parent_question_uuid": "1d897229-155d-498d-b6ae-21960fab3754",
    "originator_question_uuid": "fb6cf9a3-84fb-45ce-a4da-0d2257bec319",
    "forward_logs": True,
}


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
                    "attributes": copy.copy(EVENT_ATTRIBUTES),
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
                "recipient": SRUID,
                "question_uuid": QUESTION_UUID,
                "parent_question_uuid": "1d897229-155d-498d-b6ae-21960fab3754",
                "originator_question_uuid": "fb6cf9a3-84fb-45ce-a4da-0d2257bec319",
                "backend": "GoogleCloudPubSub",
                "backend_metadata": {"message_id": "1234", "ordering_key": None},
            },
        )

    def test_question_is_dispatched_to_kueue(self):
        """Test that questions are dispatched to Kueue correctly."""
        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b'{"kind": "question", "input_values": {"some": "data"}}'),
                    "attributes": copy.copy(EVENT_ATTRIBUTES),
                    "messageId": "1234",
                }
            }
        )

        mock_big_query_client = MockBigQueryClient()

        with patch("functions.event_handler.main.BigQueryClient", return_value=mock_big_query_client):
            with patch("kubernetes.client.BatchV1Api.create_namespaced_job") as mock_create_namespaced_job:
                with patch("kubernetes.config.load_kube_config"):
                    handle_event(cloud_event)

        job = mock_create_namespaced_job.call_args.args[1]
        self.assertEqual(job.metadata.name, f"octue-another-service-1.0.0-question-{QUESTION_UUID}")
        self.assertEqual(job.metadata.labels["kueue.x-k8s.io/queue-name"], "test-queue")

        container = job.spec.template["spec"]["containers"][0]
        self.assertEqual(container.name, f"octue-another-service-1.0.0-question-{QUESTION_UUID}")
        self.assertEqual(container.image, f"some-artifact-registry-url/{SRUID}")
        self.assertEqual(container.command, ["octue", "question", "ask", "local"])
        self.assertEqual(container.resources, {"requests": {"cpu": 2, "memory": "2Gi"}})

        self.assertEqual(
            container.args,
            ["--attributes", json.dumps(EVENT_ATTRIBUTES), "--input-values", '{"some": "data"}'],
        )

        environment_variables = [variable.to_dict() for variable in container.env]

        self.assertEqual(
            environment_variables,
            [
                {"name": "OCTUE_SERVICES_TOPIC", "value": "test.octue.services", "value_from": None},
                {"name": "COMPUTE_PROVIDER", "value": "GOOGLE_KUEUE", "value_from": None},
                {"name": "OCTUE_SERVICE_REVISION_TAG", "value": "1.0.0", "value_from": None},
            ],
        )
