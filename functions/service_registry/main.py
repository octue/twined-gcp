import os
import urllib.parse

import functions_framework
from google.cloud import artifactregistry_v1


@functions_framework.http
def handle_request(request):
    """Handle a service registry request. This service registry supports:
    - Checking if a service revision exists
    - Getting the default SRUID for a service

    :param flask.Request request: the request
    :return tuple(str, int): a message and HTTP response code
    """
    suid = urllib.parse.urlparse(request.path).path.strip("/")
    revision_tag = request.args.get("revision_tag")
    tagged_images = _get_tagged_images(repository_id=os.environ["ARTIFACT_REGISTRY_REPOSITORY_ID"])

    if not revision_tag:
        return _get_default_revision(suid, tagged_images)

    sruid = f"{suid}:{revision_tag}"

    if sruid in tagged_images:
        return ("", 200)

    return ("Service revision does not exist", 404)


def _get_tagged_images(repository_id):
    """Get representations of the tagged images from the artifact registry repository.

    :param str repository_id: the artifact registry repository ID in "projects/<project-id>/locations/<region>/repositories/<repository-name>" form
    :return dict: the names of the tagged images (e.g. "octue/my-image:0.1.0") mapped to the image objects
    """
    repository_id = repository_id.strip("/")

    client = artifactregistry_v1.ArtifactRegistryClient()
    request = artifactregistry_v1.ListDockerImagesRequest(parent=repository_id)
    tagged_images = {}

    for image in client.list_docker_images(request=request):
        # Untagged images aren't full service revision images.
        if not image.tags:
            continue

        image_name = urllib.parse.unquote(image.name).split(repository_id + "/dockerImages/")[-1].split("@")[0]

        for image_tag in image.tags:
            tagged_images[f"{image_name}:{image_tag}"] = image

    return tagged_images


def _get_default_revision(suid, tagged_images):
    """Get the revision tag of the default service revision for the given SUID if one exists in the dictionary of
    tagged images.

    :param str suid: the service unique identifier (SUID) to check for a default revision of
    :param dict tagged_images: the list of tagged images in the artifact registry
    :return (dict|str, int): the response
    """
    default_sruid = f"{suid}:default"

    if default_sruid in tagged_images:
        image_tags = tagged_images[default_sruid].tags

        # Try and replace "default" with an explicit revision tag.
        for tag in image_tags:
            if tag in {"default", "latest"}:
                continue

            return ({"revision_tag": tag}, 200)

        # Return "default" if one isn't found.
        return ({"revision_tag": "default"}, 200)

    return (f"No default service revision found for {suid!r}.", 404)
