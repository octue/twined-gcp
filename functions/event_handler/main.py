import base64
import copy
import json
import logging
import os
import sys
import tempfile

import functions_framework
import google.auth
import google.auth.transport.requests
from google.cloud.bigquery import Client as BigQueryClient
from google.cloud.container_v1 import ClusterManagerClient
import kubernetes

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


BACKEND = "GoogleCloudPubSub"
COMPUTE_PROVIDER = "GOOGLE_KUEUE"


@functions_framework.cloud_event
def handle_event(cloud_event):
    """Handle a single Pub/Sub message.

    1. Decode the Pub/Sub message into an Octue Twined service event and its attributes
    2. Store it in a BigQuery table
    3. If it's a question, dispatch it as a job to Kueue
    4. If it's a cancellation, request cancellation of the given question

    :param cloudevents.http.CloudEvent cloud_event: a Google Cloud Pub/Sub message
    :return None:
    """
    logger.info("Received event.")

    bigquery_events_table = os.environ["BIGQUERY_EVENTS_TABLE"]
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
        "parent_question_uuid": attributes.pop("parent_question_uuid", None),
        "originator_question_uuid": attributes.pop("originator_question_uuid"),
        # Backend-specific metadata.
        "backend": BACKEND,
        "backend_metadata": backend_metadata,
    }

    logger.info("Attempting to store event: %r.", row)

    bigquery_client = BigQueryClient()
    errors = bigquery_client.insert_rows(table=bigquery_client.get_table(bigquery_events_table), rows=[row])

    if errors:
        raise ValueError(errors)

    logger.info("Successfully stored event in %r.", bigquery_events_table)

    if original_event["kind"] not in {"question", "cancellation"}:
        return

    _authenticate_with_kubernetes_cluster()
    batch_api = kubernetes.client.BatchV1Api()

    if original_event["kind"] == "question":
        _dispatch_question_as_kueue_job(original_event, original_attributes, batch_api)
    elif original_event["kind"] == "cancellation":
        _cancel_kueue_job(original_attributes["question_uuid"], batch_api)


def _dispatch_question_as_kueue_job(event, attributes, batch_api):
    """Dispatch a question event to Kueue as a job.

    :param dict event: a question event from an Octue Twined service
    :param dict attributes: the attributes accompanying the question event
    :param kubernetes.client.BatchV1Api batch_api: the kubernetes batch API
    :return None:
    """
    twined_services_topic_name = os.environ["TWINED_SERVICES_TOPIC_NAME"]
    kubernetes_service_account_name = os.environ["KUBERNETES_SERVICE_ACCOUNT_NAME"]
    kueue_local_queue = os.environ["KUEUE_LOCAL_QUEUE"]
    artifact_registry_repository_url = os.environ["ARTIFACT_REGISTRY_REPOSITORY_URL"]
    question_default_cpus = int(os.environ["QUESTION_DEFAULT_CPUS"])
    question_default_memory = os.environ["QUESTION_DEFAULT_MEMORY"]
    question_default_ephemeral_storage = os.environ["QUESTION_DEFAULT_EPHEMERAL_STORAGE"]

    # Encode question as JSON to be passed to the `octue` CLI in the container.
    job_args = ["--attributes", json.dumps(attributes)]

    if event.get("input_values"):
        job_args.extend(["--input-values", json.dumps(event["input_values"])])

    if event.get("input_manifest"):
        job_args.extend(["--input-manifest", json.dumps(event["input_manifest"])])

    resources = {
        "requests": {
            "cpu": attributes.get("cpus", question_default_cpus),
            "memory": attributes.get("memory", question_default_memory),
            "ephemeral-storage": attributes.get("ephemeral_storage", question_default_ephemeral_storage),
        }
    }

    job_name = f"question-{attributes['question_uuid']}"
    service_revision_tag = attributes["recipient"].split(":")[-1]

    job_template = {
        "spec": {
            "containers": [
                kubernetes.client.V1Container(
                    image=artifact_registry_repository_url + "/" + attributes["recipient"],
                    name=job_name,
                    args=job_args,
                    resources=resources,
                    env=[
                        kubernetes.client.V1EnvVar(name="TWINED_SERVICES_TOPIC_NAME", value=twined_services_topic_name),
                        kubernetes.client.V1EnvVar(name="COMPUTE_PROVIDER", value=COMPUTE_PROVIDER),
                        kubernetes.client.V1EnvVar(name="OCTUE_SERVICE_REVISION_TAG", value=service_revision_tag),
                    ],
                )
            ],
            "restartPolicy": "Never",
            "serviceAccountName": kubernetes_service_account_name,
        }
    }

    job_metadata = kubernetes.client.V1ObjectMeta(
        name=job_name,
        labels={"kueue.x-k8s.io/queue-name": kueue_local_queue},
    )

    job = kubernetes.client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=job_metadata,
        spec=kubernetes.client.V1JobSpec(
            parallelism=1,
            completions=1,
            # Jobs must be suspended at creation for Kueue to manage them.
            suspend=True,
            template=job_template,
        ),
    )

    batch_api.create_namespaced_job(namespace="default", body=job)
    logger.info("Dispatched to Kueue (%r): question %r.", attributes["recipient"], attributes["question_uuid"])


def _cancel_kueue_job(question_uuid, batch_api):
    """Request cancellation of a question currently running on Kueue.

    :param str question_uuid: the question UUID of the question to cancel
    :param kubernetes.client.BatchV1Api batch_api: the kubernetes batch API
    :return None:
    """
    batch_api.delete_namespaced_job(name=f"question-{question_uuid}", namespace="default")
    logger.info("Requested cancellation of question %r on Kueue.", question_uuid)


def _authenticate_with_kubernetes_cluster():
    """Authenticate with the kubernetes cluster using the default credentials.

    :return None:
    """
    credentials, project_id = google.auth.default()
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)

    cluster_manager_client = ClusterManagerClient(credentials=credentials)
    cluster = cluster_manager_client.get_cluster(name=os.environ["KUBERNETES_CLUSTER_ID"])

    configuration = kubernetes.client.Configuration()
    configuration.host = f"https://{cluster.endpoint}:443"

    with tempfile.NamedTemporaryFile(delete=False) as ca_cert:
        ca_cert.write(base64.b64decode(cluster.master_auth.cluster_ca_certificate))
        configuration.ssl_ca_cert = ca_cert.name

    configuration.api_key = {"authorization": "Bearer " + credentials.token}
    kubernetes.client.Configuration.set_default(configuration)
