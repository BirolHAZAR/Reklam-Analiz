import unittest
from unittest.mock import patch
import subprocess

from sync_celery_release import docker, monitoring_env_changes


class MonitoringEnvironmentTests(unittest.TestCase):
    def test_missing_background_monitoring_is_added(self):
        self.assertEqual(monitoring_env_changes(["SENTRY_DSN=private", "DJANGO_ENV=production", "DB_PASSWORD=secret"], ["DB_PASSWORD=different"]), ["--env-add", "SENTRY_DSN=private", "--env-add", "DJANGO_ENV=production"])

    def test_equal_environment_does_not_restart_services(self):
        self.assertEqual(monitoring_env_changes(["SENTRY_DSN=private"], ["SENTRY_DSN=private"]), [])

    def test_retired_monitoring_values_are_removed(self):
        self.assertEqual(monitoring_env_changes([], ["SENTRY_DSN=private", "DB_PASSWORD=secret"]), ["--env-rm", "SENTRY_DSN"])

    def test_failed_docker_does_not_expose_arguments(self):
        with patch("sync_celery_release.subprocess.run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(RuntimeError) as error:
                docker("service", "update", "--env-add", "SENTRY_DSN=private")
            self.assertNotIn("private", str(error.exception))

    def test_timed_out_docker_does_not_expose_arguments(self):
        with patch("sync_celery_release.subprocess.run", side_effect=subprocess.TimeoutExpired(["SENTRY_DSN=private"], 120)):
            with self.assertRaises(RuntimeError) as error:
                docker("service", "update", "--env-add", "SENTRY_DSN=private")
            self.assertNotIn("private", str(error.exception))


if __name__ == "__main__":
    unittest.main()
