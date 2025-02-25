# twined-gcp

This repository provides helpers for running [Octue Twined](https://octue.com/tools) services on GCP. Currently, it
contains these cloud functions:

- [Event handler](#event-handler-cloud-function)
- [Service registry](#service-registry-cloud-function)

## Terraform deployment

The cloud functions are automatically deployed and configured when the
[`octue-twined-cluster` Terraform module](https://github.com/octue/terraform-octue-twined-cluster) is used.

## Event handler cloud function

This function handles Octue Twined service events asynchronously, keeping a record of them and taking actions in
response to some event kinds. One instance is spun up for each message published to the Pub/Sub topic it's subscribed
to. Its process is:

1. Extract an Octue Twined service event and attributes from the Pub/Sub message
2. Store the event and attributes in a BigQuery table
3. If the event is a question, dispatch it as a job to Kueue
4. If the event is a cancellation, request cancellation of the given question

### Configuration

The following environment variables are required.

| Name                                 | Description                                                                                                                                               |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BIGQUERY_EVENTS_TABLE`              | The full ID of the BigQuery table to store events in in `<dataset-name>.<table-name>` format                                                              |
| `OCTUE_SERVICES_TOPIC_NAME`          | The name of the Pub/Sub topic that events are published to in this Octue Twined service network.                                                          |
| `KUBERNETES_SERVICE_ACCOUNT_NAME`    | The name of the Kubernetes service account to assign to the Kueue jobs                                                                                    |
| `KUBERNETES_CLUSTER_ID`              | The ID of the Kubernetes cluster in `projects/<project-id>/locations/<region>/clusters/<cluster-name>` format                                             |
| `KUEUE_LOCAL_QUEUE`                  | The name of the local queue that jobs are dispatched to by Kueue                                                                                          |
| `ARTIFACT_REGISTRY_REPOSITORY_URL`   | The URL of the artifact registry repository that service revision images are stored in in `<region>-docker.pkg.dev/<project-id>/<repository-name>` format |
| `QUESTION_DEFAULT_CPUS`              | The number of CPUs to request for each question by default                                                                                                |
| `QUESTION_DEFAULT_MEMORY`            | The amount of memory to request for each question by default e.g. `256Mi`                                                                                 |
| `QUESTION_DEFAULT_EPHEMERAL_STORAGE` | The amount of ephemeral storage to request for each question by default e.g. `1Gi`                                                                        |

## Service registry cloud function

This function acts as a registry of available service revisions. In response to an HTTP request, it can

- Check if a service revision exists (i.e. if an image for it exists in the configured artifact registry repository)
- Get the revision tag of the default revision of a service, if one exists. This works by looking for an image for the
  service with the `default` tag and returning a more specific tag for it (e.g. `1.0.5`)

### Configuration

The following environment variables are required.

| Name                              | Description                                                                                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ARTIFACT_REGISTRY_REPOSITORY_ID` | The full ID of the artifact registry repository that service revision images are stored in in `projects/<project-id>/locations/<region>/repositories/<repository-name>` format |
