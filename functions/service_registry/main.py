import os
import urllib.parse

import functions_framework
from google.cloud import artifactregistry_v1


@functions_framework.http
def handle_request(request):
    suid = urllib.parse.urlparse(request.url).path.strip("/")
    revision_tag = request.params["revision_tag"]
    sruid = f"{suid}:{revision_tag}"

    service_revision_exists = _check_service_revision_existence(
        sruid=sruid,
        repository_id=os.environ["ARTIFACT_REGISTRY_REPOSITORY_ID"],
    )

    if service_revision_exists:
        return ("", 200)

    return ("", 404)


def _check_service_revision_existence(sruid, repository_id):
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
