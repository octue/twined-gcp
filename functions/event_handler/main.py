import base64
import copy
import json
import logging
import os
import sys

import functions_framework
from google.cloud.bigquery import Client as BigQueryClient
import kubernetes
from kubernetes.client import V1EnvVar

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


BACKEND = "GoogleCloudPubSub"
COMPUTE_PROVIDER = "GOOGLE_KUEUE"

OCTUE_SERVICES_TOPIC = os.environ["OCTUE_SERVICES_TOPIC"]
BIGQUERY_EVENTS_TABLE = os.environ["BIGQUERY_EVENTS_TABLE"]
KUEUE_LOCAL_QUEUE = os.environ["KUEUE_LOCAL_QUEUE"]
ARTIFACT_REGISTRY_REPOSITORY_URL = os.environ["ARTIFACT_REGISTRY_REPOSITORY_URL"]


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

    original_event = copy.deepcopy(event)
    original_attributes = copy.deepcopy(attributes)

    row = {
        "datetime": attributes.pop("datetime"),
        "uuid": attributes.pop("uuid"),
        "kind": event.pop("kind"),
        "event": event,
        # Any attributes not popped will end up in the `other_attributes` column.
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
        # Backend-specific metadata.
        "backend": BACKEND,
        "backend_metadata": backend_metadata,
    }

    logger.info("Attempting to store row: %r.", row)

    bigquery_client = BigQueryClient()
    errors = bigquery_client.insert_rows(table=bigquery_client.get_table(BIGQUERY_EVENTS_TABLE), rows=[row])

    if errors:
        raise ValueError(errors)

    logger.info("Successfully stored row in %r.", BIGQUERY_EVENTS_TABLE)

    if original_event["kind"] == "question":
        _dispatch_kueue_job(original_event, original_attributes)


def _dispatch_kueue_job(event, attributes):
    kubernetes.config.load_kube_config()

    service_namespace, service_name_and_revision_tag = attributes["recipient"].split("/")
    service_name, service_revision_tag = service_name_and_revision_tag.split(":")
    job_name = f"{service_namespace}-{service_name}-{service_revision_tag}-question-{attributes['question_uuid']}"

    job_metadata = kubernetes.client.V1ObjectMeta(
        name=job_name,
        labels={"kueue.x-k8s.io/queue-name": KUEUE_LOCAL_QUEUE},
    )

    args = []

    if event.get("input_values"):
        args.extend(["--input-values", json.dumps(event["input_values"])])

    if event.get("input_manifest"):
        args.extend(["--input-manifest", json.dumps(event["input_manifest"])])

    job_template = {
        "spec": {
            "containers": [
                kubernetes.client.V1Container(
                    image=ARTIFACT_REGISTRY_REPOSITORY_URL + "/" + attributes["recipient"],
                    name=job_name,
                    command=["octue", "question", "ask", "local"],
                    args=args,
                    resources={"requests": {"cpu": 2, "memory": "2Gi"}},
                    env=[
                        V1EnvVar(name="OCTUE_SERVICES_TOPIC", value=OCTUE_SERVICES_TOPIC),
                        V1EnvVar(name="COMPUTE_PROVIDER", value=COMPUTE_PROVIDER),
                        V1EnvVar(name="OCTUE_SERVICE_REVISION_TAG", value=service_revision_tag),
                    ],
                )
            ],
            "restartPolicy": "Never",
        }
    }

    job = kubernetes.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=job_metadata,
        spec=kubernetes.client.V1JobSpec(parallelism=1, completions=1, suspend=True, template=job_template),
    )

    batch_api = kubernetes.client.BatchV1Api()
    batch_api.create_namespaced_job("default", job)
    logger.info("Dispatched to Kueue: question %r for %r.", attributes["question_uuid"], attributes["recipient"])
