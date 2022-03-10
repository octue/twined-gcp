import os
import json
import base64
import datetime
from google.cloud import pubsub_v1
from google.api_core.exceptions import NotFound

# Setup logging - TODO check whether this import order matters.
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()
import logging

logger = logging.getLogger(__name__)


publisher = pubsub_v1.PublisherClient()
project_id = os.getenv("GCP_PROJECT_ID")
legacy_topic_action = os.getenv("LEGACY_TOPIC_ACTION", "keep").lower()
seconds_to_keep = float(os.getenv("SECONDS_TO_KEEP", "604800"))


def helper(event, context):
    """Runs a helper action
    Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload containing attributes and message data
         context (google.cloud.functions.Context): Metadata for the event.
    """
    action = event["attributes"]["action"]

    if action == "clear-topics":
        current_posix_time = float(datetime.datetime.now().timestamp())

        for topic in publisher.list_topics(request={"project": f"projects/{project_id}"}):
            if (".answers." in topic.name) and ("octue.services" in topic.name):
                created_label = topic.labels["created"]
                try:
                    created_posix_time = float(created_label)
                    should_delete = (current_posix_time - created_posix_time) > seconds_to_keep

                except ValueError:
                    logger.info(
                        f"No (or invalid) 'created' label on topic {topic.name} - {legacy_topic_action}ing this topic!"
                    )
                    should_delete = legacy_topic_action == "delete"

                if should_delete:
                    try:
                        publisher.delete_topic(request={"topic": topic.name})
                    except NotFound:
                        # Handle race condition from running multiple instances of this function simultaneously
                        pass

                    logger.info(f"Topic deleted: {topic.name}")
