import os
import urllib.parse

import functions_framework
from google.cloud import artifactregistry_v1


@functions_framework.http
def handle_request(request):
    """Handle a request to check if a service revision exists.

    :param requests.Request request: the request
    :return tuple(str, int): a message and HTTP response code
    """
    suid = urllib.parse.urlparse(request.url).path.strip("/")
    revision_tag = request.params.get("revision_tag")

    if not revision_tag:
        return (
            "This service registry doesn't support getting default SRUIDs. Please provide the `revision_tag` parameter",
            400,
        )

    sruid = f"{suid}:{revision_tag}"

    service_revision_exists = _check_service_revision_existence(
        sruid=sruid,
        repository_id=os.environ["ARTIFACT_REGISTRY_REPOSITORY_ID"],
    )

    if service_revision_exists:
        return ("", 200)

    return ("Service revision does not exist", 404)


def _check_service_revision_existence(sruid, repository_id):
    """Check if an image corresponding to the given service revision exists in the artifact registry repository.

    :param str sruid: the service revision unique identifier (SRUID) for the service revision
    :param str repository_id: the artifact registry repository ID in "projects/<project-id>/locations/<region>/repositories/<repository-name>" form
    :return bool: `True` if the service revision exists
    """
    repository_id = repository_id.strip("/")

    client = artifactregistry_v1.ArtifactRegistryClient()
    request = artifactregistry_v1.ListDockerImagesRequest(parent=repository_id)
    image_names = set()

    for image in client.list_docker_images(request=request):
        # Untagged images aren't full service revision images.
        if not image.tags:
            continue

        image_name = urllib.parse.unquote(image.name).split(repository_id + "/dockerImages/")[-1].split("@")[0]
        image_tag = image.tags[0]
        image_names.add(f"{image_name}:{image_tag}")

    return sruid in image_names
