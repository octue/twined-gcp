import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

import requests

from functions.service_registry.main import handle_request

ARTIFACT_REPOSITORY_ID = "projects/my-project/locations/my-location/repositories/my-repo"
SUID = "my-org/my-service"
QUOTED_SUID = urllib.parse.quote(SUID)
REVISION_TAG = "0.1.0"


class TestServiceRegistry(unittest.TestCase):
    def test_400_returned_if_revision_tag_not_supplied(self):
        """Test that a 400 is returned if a revision tag isn't supplied."""
        request = requests.Request(url=f"https://my-service-registry.com/{SUID}")

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
            response = handle_request(request)

        self.assertEqual(
            response,
            (
                "This service registry doesn't support getting default SRUIDs. Please provide the `revision_tag` parameter",
                400,
            ),
        )

    def test_404_returned_for_nonexistent_service_revision(self):
        """Test that a 404 is returned when checking for a non-existent service revision."""
        request = requests.Request(url=f"https://my-service-registry.com/{SUID}", params={"revision_tag": REVISION_TAG})

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
            with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient"):
                with patch(
                    "google.cloud.artifactregistry_v1.services.artifact_registry.client.ArtifactRegistryClient.list_docker_images",
                    return_value=[],
                ):
                    response = handle_request(request)

        self.assertEqual(response, ("Service revision does not exist", 404))

    def test_200_returned_for_existing_service_revision(self):
        """Test that a 200 is returned when checking for an existing service revision."""
        request = requests.Request(url=f"https://my-service-registry.com/{SUID}", params={"revision_tag": REVISION_TAG})

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
            with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient", MockArtifactRegistryClient):
                response = handle_request(request)

        self.assertEqual(response, ("", 200))


class MockArtifactRegistryClient:
    def list_docker_images(self, *args, **kwargs):
        return [
            SimpleNamespace(
                name=f"{ARTIFACT_REPOSITORY_ID}/dockerImages/{QUOTED_SUID}@some-sha",
                tags=[REVISION_TAG],
            )
        ]
