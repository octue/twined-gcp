import base64
import os

import functions_framework
from google.cloud.bigquery import Client


BIGQUERY_EVENTS_TABLE = os.environ["BIGQUERY_EVENTS_TABLE"]
BACKEND = "GoogleCloudPubSub"


@functions_framework.cloud_event
def store_pub_sub_event_in_bigquery(cloud_event):
    """Decode a Google Cloud Pub/Sub message into an Octue service event and its attributes, then store it in a BigQuery
    table.

    :param cloudevents.http.CloudEvent cloud_event: a Google Cloud Pub/Sub message as a CloudEvent
    :return None:
    """
    event = base64.b64decode(cloud_event.data["message"]["data"]).decode()
    attributes = cloud_event.data["message"]["attributes"]

    backend_metadata = {
        "message_id": cloud_event.data["message"]["messageId"],
        "publish_time": cloud_event.data["message"]["publishTime"],
        "ordering_key": cloud_event.data["message"].get("orderingKey"),
    }

    errors = Client().insert_rows(
        table=BIGQUERY_EVENTS_TABLE,
        rows=[
            {
                "event": event,
                "attributes": attributes,
                # Pull out some attributes into columns for querying.
                "uuid": attributes["uuid"],
                "originator": attributes["originator"],
                "sender": attributes["sender"],
                "sender_type": attributes["sender_type"],
                "sender_sdk_version": attributes["sender_sdk_version"],
                "recipient": attributes["recipient"],
                "question_uuid": attributes["question_uuid"],
                "order": attributes["order"],
                # Backend-specific metadata.
                "backend": BACKEND,
                "backend_metadata": backend_metadata,
            }
        ],
    )

    if errors:
        raise ValueError(errors)
