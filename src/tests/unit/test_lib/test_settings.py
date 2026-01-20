"""Unit tests for settings module - GoogleCloudSettings and TaskSettings."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from sqlstack.lib.settings import GoogleCloudSettings, TaskSettings


class TestGoogleCloudSettings:
    """Tests for GoogleCloudSettings class."""

    def test_default_values(self) -> None:
        """Test GoogleCloudSettings default values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.PROJECT_ID is None
            assert settings.REGION == "us-central1"
            assert settings.CLOUD_RUN_SERVICE is None
            assert settings.CLOUD_RUN_REVISION is None
            assert settings.CLOUD_RUN_JOB is None

    def test_is_cloud_run_false_by_default(self) -> None:
        """Test is_cloud_run returns False when not in Cloud Run environment."""
        with patch.dict(os.environ, {}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.is_cloud_run is False

    def test_is_cloud_run_true_with_service(self) -> None:
        """Test is_cloud_run returns True when K_SERVICE is set."""
        with patch.dict(os.environ, {"K_SERVICE": "my-service"}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.CLOUD_RUN_SERVICE == "my-service"
            assert settings.is_cloud_run is True

    def test_is_cloud_run_true_with_job(self) -> None:
        """Test is_cloud_run returns True when CLOUD_RUN_JOB is set."""
        with patch.dict(os.environ, {"CLOUD_RUN_JOB": "my-job"}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.CLOUD_RUN_JOB == "my-job"
            assert settings.is_cloud_run is True

    def test_is_cloud_run_true_with_both(self) -> None:
        """Test is_cloud_run returns True when both service and job are set."""
        with patch.dict(
            os.environ,
            {"K_SERVICE": "my-service", "CLOUD_RUN_JOB": "my-job"},
            clear=True,
        ):
            settings = GoogleCloudSettings()

            assert settings.CLOUD_RUN_SERVICE == "my-service"
            assert settings.CLOUD_RUN_JOB == "my-job"
            assert settings.is_cloud_run is True

    def test_project_id_from_env(self) -> None:
        """Test PROJECT_ID is read from GCP_PROJECT_ID env var."""
        with patch.dict(os.environ, {"GCP_PROJECT_ID": "my-project-123"}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.PROJECT_ID == "my-project-123"

    def test_region_from_env(self) -> None:
        """Test REGION is read from GCP_REGION env var."""
        with patch.dict(os.environ, {"GCP_REGION": "europe-west1"}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.REGION == "europe-west1"

    def test_cloud_run_revision_from_env(self) -> None:
        """Test CLOUD_RUN_REVISION is read from K_REVISION env var."""
        with patch.dict(os.environ, {"K_REVISION": "my-service-00001-abc"}, clear=True):
            settings = GoogleCloudSettings()

            assert settings.CLOUD_RUN_REVISION == "my-service-00001-abc"

    def test_full_cloud_run_environment(self) -> None:
        """Test GoogleCloudSettings with full Cloud Run environment."""
        env = {
            "GCP_PROJECT_ID": "production-project",
            "GCP_REGION": "us-east1",
            "K_SERVICE": "api-service",
            "K_REVISION": "api-service-00042-xyz",
            "CLOUD_RUN_JOB": "worker-job",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = GoogleCloudSettings()

            assert settings.PROJECT_ID == "production-project"
            assert settings.REGION == "us-east1"
            assert settings.CLOUD_RUN_SERVICE == "api-service"
            assert settings.CLOUD_RUN_REVISION == "api-service-00042-xyz"
            assert settings.CLOUD_RUN_JOB == "worker-job"
            assert settings.is_cloud_run is True


class TestTaskSettings:
    """Tests for TaskSettings class."""

    def test_default_execution_target(self) -> None:
        """Test TaskSettings defaults to local execution."""
        with patch.dict(os.environ, {}, clear=True):
            settings = TaskSettings()

            assert settings.DEFAULT_EXECUTION_TARGET == "local"

    def test_execution_target_local(self) -> None:
        """Test TaskSettings with local execution target."""
        with patch.dict(os.environ, {"EXECUTION_TARGET": "local"}, clear=True):
            settings = TaskSettings()

            assert settings.DEFAULT_EXECUTION_TARGET == "local"

    def test_execution_target_immediate(self) -> None:
        """Test TaskSettings with immediate execution target."""
        with patch.dict(os.environ, {"EXECUTION_TARGET": "immediate"}, clear=True):
            settings = TaskSettings()

            assert settings.DEFAULT_EXECUTION_TARGET == "immediate"

    def test_execution_target_cloudrun(self) -> None:
        """Test TaskSettings with cloudrun execution target."""
        with patch.dict(os.environ, {"EXECUTION_TARGET": "cloudrun"}, clear=True):
            settings = TaskSettings()

            assert settings.DEFAULT_EXECUTION_TARGET == "cloudrun"


class TestSettingsIntegration:
    """Integration tests for settings container."""

    def test_settings_contains_gcp(self) -> None:
        """Test that Settings container includes GoogleCloudSettings."""
        from sqlstack.lib.settings import Settings

        settings = Settings()

        assert hasattr(settings, "gcp")
        assert isinstance(settings.gcp, GoogleCloudSettings)

    def test_settings_contains_task(self) -> None:
        """Test that Settings container includes TaskSettings."""
        from sqlstack.lib.settings import Settings

        settings = Settings()

        assert hasattr(settings, "task")
        assert isinstance(settings.task, TaskSettings)

    def test_list_all_config_includes_gcp(self) -> None:
        """Test that list_all_config includes gcp section."""
        from sqlstack.lib.settings import Settings

        settings = Settings()
        config = settings.list_all_config()

        assert "gcp" in config
        assert "project_id" in config["gcp"]
        assert "region" in config["gcp"]
        assert "cloud_run_service" in config["gcp"]

    def test_list_all_config_includes_task(self) -> None:
        """Test that list_all_config includes task section."""
        from sqlstack.lib.settings import Settings

        settings = Settings()
        config = settings.list_all_config()

        assert "task" in config
        assert "default_execution_target" in config["task"]

    def test_get_config_value_gcp(self) -> None:
        """Test get_config_value works for gcp settings."""
        from sqlstack.lib.settings import Settings

        settings = Settings()
        region = settings.get_config_value("gcp.region")

        assert region == "us-central1"  # default value

    def test_get_config_value_task(self) -> None:
        """Test get_config_value works for task settings."""
        from sqlstack.lib.settings import Settings

        settings = Settings()
        target = settings.get_config_value("task.default_execution_target")

        assert target == "local"  # default value
