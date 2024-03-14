import base64
import os

import functions_framework
from google.cloud.bigquery import Client


BIGQUERY_EVENTS_TABLE = os.environ["BIGQUERY_EVENTS_TABLE"]


@functions_framework.cloud_event
def store_pub_sub_event_in_bigquery(cloud_event):
    """Decode a Google Cloud Pub/Sub message into an Octue service event and its attributes, then store it in a BigQuery
    table.

    :param cloudevents.http.CloudEvent cloud_event: a Google Cloud Pub/Sub message as a CloudEvent
    :return None:
    """
    event = base64.b64decode(cloud_event.data["message"]["data"]).decode()
    attributes = cloud_event.data["message"]["attributes"]
    client = Client()

    errors = client.insert_rows(
        table=BIGQUERY_EVENTS_TABLE,
        rows=[
            {
                "event": event,
                # All attributes.
                "attributes": attributes,
                # Attributes pulled out into columns for querying.
                "question_uuid": attributes["question_uuid"],
                "sender_type": attributes["sender_type"],
                "version": attributes["version"],
                "event_number": attributes["message_number"],
                "sender": attributes["sender"],
            }
        ],
    )

    if errors:
        raise ValueError(errors)
