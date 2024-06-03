import base64
import json
import logging
import os
import sys

import functions_framework
from google.cloud.bigquery import Client


logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


BIGQUERY_EVENTS_TABLE = os.environ["BIGQUERY_EVENTS_TABLE"]
BACKEND = "GoogleCloudPubSub"


@functions_framework.cloud_event
def store_pub_sub_event_in_bigquery(cloud_event):
    """Decode a Google Cloud Pub/Sub message into an Octue service event and its attributes, then store it in a BigQuery
    table.

    :param cloudevents.http.CloudEvent cloud_event: a Google Cloud Pub/Sub message as a CloudEvent
    :return None:
    """
    logger.info("Received event.")
    event = json.loads(base64.b64decode(cloud_event.data["message"]["data"]).decode())
    attributes = cloud_event.data["message"]["attributes"]

    backend_metadata = {
        "message_id": cloud_event.data["message"]["messageId"],
        "ordering_key": cloud_event.data["message"].get("orderingKey"),
    }

    row = {
        "datetime": attributes.pop("datetime"),
        "uuid": attributes.pop("uuid"),
        "kind": event.pop("kind"),
        "event": event,
        # Any attributes not popped below will end up in the `other_attributes` column.
        "other_attributes": attributes,
        # Pull out some attributes into columns for querying.
        "parent": attributes.pop("parent"),
        "originator": attributes.pop("originator"),
        "sender": attributes.pop("sender"),
        "sender_type": attributes.pop("sender_type"),
        "sender_sdk_version": attributes.pop("sender_sdk_version"),
        "recipient": attributes.pop("recipient"),
        "question_uuid": attributes.pop("question_uuid"),
        "parent_question_uuid": attributes.pop("parent_question_uuid"),
        "originator_question_uuid": attributes.pop("originator_question_uuid"),
        "order": attributes.pop("order"),
        # Backend-specific metadata.
        "backend": BACKEND,
        "backend_metadata": backend_metadata,
    }

    logger.info("Attempting to store row: %r.", row)

    client = Client()
    errors = client.insert_rows(table=client.get_table(BIGQUERY_EVENTS_TABLE), rows=[row])

    if errors:
        raise ValueError(errors)

    logger.info("Successfully stored row in %r.", BIGQUERY_EVENTS_TABLE)
