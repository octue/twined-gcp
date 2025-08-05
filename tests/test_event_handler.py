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
    "retry_count": "0",
    "forward_logs": "1",
    "save_diagnostics": "SAVE_DIAGNOSTICS_ON_CRASH",
    "cpus": "1",
    "memory": "2Gi",
    "ephemeral_storage": "256Mi",
}


class TestEventHandler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment_variables_patch = patch.dict(
            "os.environ",
            {
                "BIGQUERY_EVENTS_TABLE": "my-table",
                "TWINED_SERVICES_TOPIC_NAME": "test.octue.services",
                "KUEUE_LOCAL_QUEUE": "test-queue",
                "ARTIFACT_REGISTRY_REPOSITORY_URL": "some-artifact-registry-url",
                "KUBERNETES_SERVICE_ACCOUNT_NAME": "kubernetes-sa",
                "KUBERNETES_CLUSTER_ID": "kubernetes-cluster",
                "QUESTION_DEFAULT_CPUS": "1",
                "QUESTION_DEFAULT_MEMORY": "500Mi",
                "QUESTION_DEFAULT_EPHEMERAL_STORAGE": "1Gi",
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
                "event": {
                    "some": "data",
                },
                "other_attributes": {
                    "retry_count": "0",
                    "forward_logs": "1",
                    "save_diagnostics": "SAVE_DIAGNOSTICS_ON_CRASH",
                    "cpus": "1",
                    "memory": "2Gi",
                    "ephemeral_storage": "256Mi",
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

    def test_store_pub_sub_event_in_bigquery_with_no_parent_question_uuid(self):
        """Test that an event with no `parent_question_uuid` attribute is handled correctly."""
        attributes = copy.copy(EVENT_ATTRIBUTES)
        attributes.pop("parent_question_uuid")

        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b'{"kind": "heart", "some": "data"}'),
                    "attributes": attributes,
                    "messageId": "1234",
                }
            }
        )

        mock_big_query_client = MockBigQueryClient()

        with patch("functions.event_handler.main.BigQueryClient", return_value=mock_big_query_client):
            handle_event(cloud_event)

        self.assertIsNone(mock_big_query_client.inserted_rows[0][0]["parent_question_uuid"])

    def test_question_is_dispatched_to_kueue(self):
        """Test that questions are dispatched to Kueue correctly."""
        event_attributes = {
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
            "retry_count": "0",
            "forward_logs": "1",
        }

        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b'{"kind": "question", "input_values": {"some": "data"}}'),
                    "attributes": copy.copy(event_attributes),
                    "messageId": "1234",
                }
            }
        )

        with patch("functions.event_handler.main.BigQueryClient", return_value=MockBigQueryClient()):
            with patch("kubernetes.client.BatchV1Api.create_namespaced_job") as mock_create_namespaced_job:
                with patch("functions.event_handler.main._authenticate_with_kubernetes_cluster"):
                    handle_event(cloud_event)

        job = mock_create_namespaced_job.call_args.kwargs["body"]
        self.assertEqual(job.metadata.name, f"question-{QUESTION_UUID}")
        self.assertEqual(job.metadata.labels["kueue.x-k8s.io/queue-name"], "test-queue")

        container = job.spec.template["spec"]["containers"][0]
        self.assertEqual(container.name, job.metadata.name)
        self.assertEqual(container.image, f"some-artifact-registry-url/{SRUID}")
        self.assertEqual(container.command, ["octue", "twined", "question", "ask", "local"])

        # Check the default resource requirements are used.
        self.assertEqual(container.resources, {"requests": {"cpu": 1, "ephemeral-storage": "1Gi", "memory": "500Mi"}})

        self.assertEqual(
            container.args,
            ["--attributes", json.dumps(event_attributes), "--input-values", '{"some": "data"}'],
        )

        environment_variables = [variable.to_dict() for variable in container.env]

        self.assertEqual(
            environment_variables,
            [
                {"name": "TWINED_SERVICES_TOPIC_NAME", "value": "test.octue.services", "value_from": None},
                {"name": "COMPUTE_PROVIDER", "value": "GOOGLE_KUEUE", "value_from": None},
                {"name": "OCTUE_SERVICE_REVISION_TAG", "value": "1.0.0", "value_from": None},
            ],
        )

    def test_question_cancellation(self):
        """Test that cancellation events result in job deletion."""
        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b'{"kind": "cancellation"}'),
                    "attributes": copy.copy(EVENT_ATTRIBUTES),
                    "messageId": "1234",
                }
            }
        )

        with patch("functions.event_handler.main.BigQueryClient", return_value=MockBigQueryClient()):
            with patch("kubernetes.client.BatchV1Api.delete_namespaced_job") as mock_delete_namespaced_job:
                with patch("functions.event_handler.main._authenticate_with_kubernetes_cluster"):
                    handle_event(cloud_event)

        job_name = mock_delete_namespaced_job.call_args.kwargs["name"]
        self.assertEqual(job_name, f"question-{EVENT_ATTRIBUTES['question_uuid']}")
