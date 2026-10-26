import isolated_env  # noqa: F401  (must precede app imports)
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PRODUCTION = {
    "APP_ENV": "production",
    "DEMO_SEED": "false",
    "DATABASE_URL": "postgresql://user:pass@db.example.org:5432/rakt",
    "SECRET_KEY": "s" * 40,
    # set empty, not unset: settings loads backend/.env, which must not fill these in
    "ALLOWED_HOSTS": "",
    "FRONTEND_ORIGINS": "",
}


def load_settings(**overrides: str) -> subprocess.CompletedProcess[str]:
    """Import app.settings in a fresh interpreter (it is evaluated once, at
    import) and print the host/origin lists it settled on."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("VERCEL")}
    env.update(PRODUCTION)
    env.update(overrides)
    code = "import json, app.settings as s; print(json.dumps([s.ALLOWED_HOSTS, s.FRONTEND_ORIGINS]))"
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120)


class VercelHostTests(unittest.TestCase):
    def test_production_without_hosts_refuses_to_start(self) -> None:
        result = load_settings()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FRONTEND_ORIGINS", result.stderr)

    def test_on_vercel_the_deployment_hostnames_are_trusted(self) -> None:
        result = load_settings(
            VERCEL="1",
            VERCEL_URL="rakt-sanket-abc123-team.vercel.app",
            VERCEL_BRANCH_URL="rakt-sanket-git-feature-team.vercel.app",
            VERCEL_PROJECT_PRODUCTION_URL="rakt-sanket.vercel.app",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        hosts, origins = json.loads(result.stdout)
        self.assertEqual(hosts, ["rakt-sanket-abc123-team.vercel.app", "rakt-sanket-git-feature-team.vercel.app", "rakt-sanket.vercel.app"])
        self.assertIn("https://rakt-sanket.vercel.app", origins)
        self.assertNotIn("*", hosts)

    def test_custom_domain_is_kept_alongside_vercel_hosts(self) -> None:
        result = load_settings(
            VERCEL="1",
            VERCEL_URL="rakt-sanket-abc123-team.vercel.app",
            ALLOWED_HOSTS="raktsanket.example.org",
            FRONTEND_ORIGINS="https://raktsanket.example.org",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        hosts, origins = json.loads(result.stdout)
        self.assertEqual(hosts, ["raktsanket.example.org", "rakt-sanket-abc123-team.vercel.app"])
        self.assertEqual(origins, ["https://raktsanket.example.org", "https://rakt-sanket-abc123-team.vercel.app"])

    def test_vercel_variables_are_ignored_off_vercel(self) -> None:
        result = load_settings(VERCEL_URL="rakt-sanket-abc123-team.vercel.app")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
