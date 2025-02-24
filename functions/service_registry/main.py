import os
import urllib.parse

import functions_framework
from google.cloud import artifactregistry_v1


@functions_framework.http
def handle_request(request):
    """Handle a service registry request. This service registry supports:
    - Checking if a service revision exists

    It does not support:
    - Getting the default SRUID for a service

    :param flask.Request request: the request
    :return tuple(str, int): a message and HTTP response code
    """
    suid = urllib.parse.urlparse(request.path).path.strip("/")
    revision_tag = request.args.get("revision_tag")

    if not revision_tag:
        return (
            "This service registry doesn't support getting default SRUIDs. Please provide the `revision_tag` parameter",
            400,
        )

    sruid = f"{suid}:{revision_tag}"

    tagged_images = _get_tagged_images(repository_id=os.environ["ARTIFACT_REGISTRY_REPOSITORY_ID"])

    if sruid in tagged_images:
        return ("", 200)

    return ("Service revision does not exist", 404)


def _get_tagged_images(repository_id):
    """Get the names of the tagged images from the artifact registry repository.

    :param str repository_id: the artifact registry repository ID in "projects/<project-id>/locations/<region>/repositories/<repository-name>" form
    :return set(str): the names of the tagged images e.g. "octue/my-image:0.1.0"
    """
    repository_id = repository_id.strip("/")

    client = artifactregistry_v1.ArtifactRegistryClient()
    request = artifactregistry_v1.ListDockerImagesRequest(parent=repository_id)
    tagged_images = set()

    for image in client.list_docker_images(request=request):
        # Untagged images aren't full service revision images.
        if not image.tags:
            continue

        image_name = urllib.parse.unquote(image.name).split(repository_id + "/dockerImages/")[-1].split("@")[0]
        image_tag = image.tags[0]
        tagged_images.add(f"{image_name}:{image_tag}")

    return tagged_images
