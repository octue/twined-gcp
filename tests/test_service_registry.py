import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

import requests

from functions.service_registry.main import handle_request

artifact_repository_id = "projects/my-project/locations/my-location/repositories/my-repo"
suid = "my-org/my-service"
quoted_suid = urllib.parse.quote(suid)
revision_tag = "0.1.0"


class TestServiceRegistry(unittest.TestCase):
    def test_404_returned_for_nonexistent_service_revision(self):
        """Test that a 404 is returned when checking for a non-existent service revision."""
        request = requests.Request(url=f"https://my-service-registry.com/{suid}", params={"revision_tag": revision_tag})

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": artifact_repository_id}):
            with patch(
                "google.cloud.artifactregistry_v1.services.artifact_registry.client.ArtifactRegistryClient.list_docker_images",
                return_value=[],
            ):
                response = handle_request(request)

        self.assertEqual(response, ("", 404))

    def test_200_returned_for_existing_service_revision(self):
        """Test that a 200 is returned when checking for an existing service revision."""
        request = requests.Request(url=f"https://my-service-registry.com/{suid}", params={"revision_tag": revision_tag})

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": artifact_repository_id}):
            with patch(
                "google.cloud.artifactregistry_v1.services.artifact_registry.client.ArtifactRegistryClient.list_docker_images",
                return_value=[
                    SimpleNamespace(
                        name=f"{artifact_repository_id}/dockerImages/{quoted_suid}@some-sha",
                        tags=[revision_tag],
                    )
                ],
            ):
                response = handle_request(request)

        self.assertEqual(response, ("", 200))
