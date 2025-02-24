import functools
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.parse

import flask

from functions.service_registry.main import handle_request

ARTIFACT_REPOSITORY_ID = "projects/my-project/locations/my-location/repositories/my-repo"
SUID = "my-org/my-service"
QUOTED_SUID = urllib.parse.quote(SUID)
REVISION_TAG = "0.1.0"


class TestServiceRegistry(unittest.TestCase):
    def test_404_returned_for_nonexistent_service_revision(self):
        """Test that a 404 is returned when checking for a non-existent service revision."""
        request = flask.Request(environ={})
        request.path = f"https://my-service-registry.com/{SUID}"
        request.args = {"revision_tag": REVISION_TAG}

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
        request = flask.Request(environ={})
        request.path = f"https://my-service-registry.com/{SUID}"
        request.args = {"revision_tag": REVISION_TAG}

        mock_registry_client = MockArtifactRegistryClient.from_images(
            [
                SimpleNamespace(
                    name=f"{ARTIFACT_REPOSITORY_ID}/dockerImages/{QUOTED_SUID}@some-sha",
                    tags=[REVISION_TAG],
                )
            ]
        )

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
            with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient", mock_registry_client):
                response = handle_request(request)

        self.assertEqual(response, ("", 200))


class TestServiceRegistryWithDefaultServiceRevisions(unittest.TestCase):
    def test_with_nonexistent_default_service_revision(self):
        """Test that a 404 is returned when checking for a non-existent default service revision."""
        request = flask.Request(environ={})
        request.path = f"https://my-service-registry.com/{SUID}"

        MockClient = MockArtifactRegistryClient.from_images([])

        with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
            with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient", MockClient):
                response = handle_request(request)

        self.assertEqual(response, ("No default service revision found for 'my-org/my-service'.", 404))

    def test_with_default_service_revision_existing(self):
        """Test that, if no revision tag is provided, the revision tag of the default service revision is returned if it
        exists.
        """
        request = flask.Request(environ={})
        request.path = f"https://my-service-registry.com/{SUID}"

        MockClient = MockArtifactRegistryClient.from_images(
            [
                SimpleNamespace(
                    name=f"{ARTIFACT_REPOSITORY_ID}/dockerImages/{QUOTED_SUID}@some-sha",
                    tags=["default", REVISION_TAG],
                )
            ]
        )

        with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient", MockClient):
            with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
                response = handle_request(request)

        self.assertEqual(response, ({"revision_tag": "0.1.0"}, 200))

    def test_with_default_service_revision_existing_but_untagged(self):
        """Test that "default" is returned as the revision tag of the default service revision if an untagged default
        service revision exists.
        """
        request = flask.Request(environ={})
        request.path = f"https://my-service-registry.com/{SUID}"

        MockClient = MockArtifactRegistryClient.from_images(
            [
                SimpleNamespace(
                    name=f"{ARTIFACT_REPOSITORY_ID}/dockerImages/{QUOTED_SUID}@some-sha",
                    tags=["default"],
                )
            ]
        )

        with patch("google.cloud.artifactregistry_v1.ArtifactRegistryClient", MockClient):
            with patch.dict(os.environ, {"ARTIFACT_REGISTRY_REPOSITORY_ID": ARTIFACT_REPOSITORY_ID}):
                response = handle_request(request)

        self.assertEqual(response, ({"revision_tag": "default"}, 200))


class MockArtifactRegistryClient:
    def __init__(self, images=None):
        self.images = images or []

    @classmethod
    def from_images(cls, images):
        return functools.partial(cls, images=images)

    def list_docker_images(self, *args, **kwargs):
        return self.images
