import urllib.parse

from google.cloud import artifactregistry_v1


def _check_service_revision_existence(sruid, repository_id):
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
