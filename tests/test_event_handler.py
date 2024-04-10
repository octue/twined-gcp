import base64
import os
import unittest
from unittest.mock import patch

from functions.event_handler.main import store_pub_sub_event_in_bigquery
from tests.mocks import MockBigQueryClient, MockCloudEvent


REPOSITORY_ROOT = os.path.dirname(os.path.dirname(__file__))


class TestEventHandler(unittest.TestCase):
    def test_store_pub_sub_event_in_bigquery(self):
        """Test that the `event_handler` cloud function can receive, parse, and store an event in BigQuery."""
        cloud_event = MockCloudEvent(
            data={
                "message": {
                    "data": base64.b64encode(b"some-data"),
                    "attributes": {
                        "uuid": "c8bda9fa-f072-4330-92b1-96920d06b28d",
                        "originator": "octue/test-service:5.6.3",
                        "sender": "octue/test-service:5.6.3",
                        "sender_type": "PARENT",
                        "sender_sdk_version": "1.0.3",
                        "recipient": "octue/another-service:1.0.0",
                        "question_uuid": "ca534cdd-24cb-4ed2-af57-e36757192acb",
                        "order": "0",
                    },
                    "messageId": "1234",
                    "publishTime": "some-datetime",
                }
            }
        )

        mock_big_query_client = MockBigQueryClient()

        with patch("functions.event_handler.main.Client", return_value=mock_big_query_client):
            store_pub_sub_event_in_bigquery(cloud_event)

        self.assertEqual(
            mock_big_query_client.inserted_rows[0][0],
            {
                "event": "some-data",
                "other_attributes": {
                    "uuid": "c8bda9fa-f072-4330-92b1-96920d06b28d",
                },
                "originator": "octue/test-service:5.6.3",
                "sender": "octue/test-service:5.6.3",
                "sender_type": "PARENT",
                "sender_sdk_version": "1.0.3",
                "recipient": "octue/another-service:1.0.0",
                "question_uuid": "ca534cdd-24cb-4ed2-af57-e36757192acb",
                "order": "0",
                "backend": "GoogleCloudPubSub",
                "backend_metadata": {"message_id": "1234", "publish_time": "some-datetime", "ordering_key": None},
            },
        )
