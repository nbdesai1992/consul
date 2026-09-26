"""Offline tests for the Consul wizard. Run: python3 -m unittest discover -s tests

Each test runs onboard.py for real into a temp folder with --no-github and
--no-provision, under a throwaway HOME with no Render credential, so nothing
touches the network, GitHub, Render, or your own settings.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONBOARD = REPO / "onboard.py"


def load_onboard():
    spec = importlib.util.spec_from_file_location("onboard", ONBOARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WizardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="consul-test-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k != "RENDER_API_KEY"}
        self.env.update({
            "HOME": str(self.home),
            "GIT_AUTHOR_NAME": "Consul Test", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Consul Test", "GIT_COMMITTER_EMAIL": "test@example.com",
        })

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def wizard(self, *args, stdin=""):
        p = subprocess.run([sys.executable, str(ONBOARD), *args], input=stdin, capture_output=True,
                           text=True, env=self.env, timeout=180)
        return p.returncode, p.stdout + p.stderr

    def quick(self, name="Test App", folder="test-app"):
        target = self.tmp / folder
        code, out = self.wizard(str(target), "--quick", "--yes", "--name", name, "--description", "Tracks tests",
                                "--domain", "testers", "--login", "no", "--no-github", "--no-provision")
        self.assertEqual(code, 0, out)
        return target, out

    # ── the tests ──

    def test_help_prints_usage_and_exits(self):
        for flag in ("--help", "-h"):
            code, out = self.wizard(flag)
            self.assertEqual(code, 0, out)
            self.assertIn("Usage:", out)
            self.assertIn("--reconfigure", out)
            self.assertNotIn("--- Machine check ---", out)   # it must not start the wizard

    def test_quick_start_builds_a_complete_project(self):
        target, out = self.quick()
        self.assertIn("CONSUL — Quick Start", out)
        for rel in ["CLAUDE.md", "render.yaml", ".gitignore", "briefs/README.md",
                    ".claude/settings.json", ".claude/consul.json",
                    "backend", "frontend", "briefs/1-backlog", "briefs/2-active", "briefs/3-blocked", "briefs/4-done"]:
            self.assertTrue((target / rel).exists(), rel)
        cfg = json.loads((target / ".claude" / "consul.json").read_text())
        self.assertEqual((cfg["mode"], cfg["push_policy"]), ("quick", "consul"))
        self.assertIn("Push policy: consul.", (target / "CLAUDE.md").read_text())
        json.loads((target / ".claude" / "settings.json").read_text())
        log = subprocess.run(["git", "log", "--oneline"], cwd=target, capture_output=True, text=True).stdout
        self.assertIn("consul setup", log)

    def test_no_placeholder_left_unrendered(self):
        target, _ = self.quick()
        leftovers = []
        for path in [target / "CLAUDE.md", target / "render.yaml", *sorted((target / ".claude").rglob("*"))]:
            if path.is_file() and path.suffix in {".md", ".json", ".py", ".sh", ".yaml", ""}:
                for m in re.finditer(r"\{\{[A-Z_]+\}\}", path.read_text(encoding="utf-8", errors="ignore")):
                    leftovers.append(f"{path.relative_to(target)}: {m.group(0)}")
        self.assertEqual(leftovers, [])

    def test_installed_hooks_and_scripts_are_valid(self):
        target, _ = self.quick()
        hooks = sorted((target / ".claude" / "hooks").glob("*.sh"))
        self.assertEqual({h.name for h in hooks}, set(load_onboard().HOOK_FILES))
        for sh in [*hooks, *(target / ".claude" / "scripts").glob("*.sh")]:
            self.assertTrue(os.access(sh, os.X_OK), f"{sh.name} not executable")
            r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{sh.name}: {r.stderr}")
        for py in (target / ".claude" / "scripts").glob("*.py"):
            compile(py.read_text(encoding="utf-8"), str(py), "exec")

    def test_settings_wire_every_installed_hook(self):
        target, _ = self.quick()
        settings = (target / ".claude" / "settings.json").read_text()
        for hook in load_onboard().HOOK_FILES:
            self.assertIn(f".claude/hooks/{hook}", settings)

    def test_render_yaml_declares_db_and_two_services(self):
        target, _ = self.quick(name="Invoice Tracker", folder="invoice-tracker")
        sys.path.insert(0, str(target / ".claude" / "scripts"))
        try:
            render_yaml = importlib.import_module("render_yaml")
            spec = render_yaml.load(target)
        finally:
            sys.path.pop(0)
            sys.modules.pop("render_yaml", None)
        self.assertEqual(sorted(s["name"] for s in spec["services"]), ["invoice-tracker-api", "invoice-tracker-frontend"])
        self.assertEqual([d["name"] for d in spec["databases"]], ["invoice-tracker-db"])

    def test_gitignore_keeps_secrets_out(self):
        target, _ = self.quick()
        gi = (target / ".gitignore").read_text()
        for entry in (".env", ".claude/settings.local.json", "session/"):
            self.assertIn(entry, gi)

    def test_custom_mode_uses_folder_name_and_human_push(self):
        target = self.tmp / "my-custom-app"
        code, out = self.wizard(str(target), "--custom", "--yes", "--no-github", "--no-provision")
        self.assertEqual(code, 0, out)
        cfg = json.loads((target / ".claude" / "consul.json").read_text())
        self.assertEqual((cfg["mode"], cfg["project_name"], cfg["push_policy"]), ("custom", "my-custom-app", "human"))

    def test_reconfigure_reads_legacy_config_and_keeps_old_claude_md(self):
        for legacy, policy in (("shipwright.json", "shipwright"), ("factory-config.json", "factory")):
            with self.subTest(legacy=legacy):
                target, _ = self.quick(folder=f"legacy-{policy}")
                claude = target / ".claude"
                cfg = json.loads((claude / "consul.json").read_text())
                (claude / "consul.json").unlink()
                cfg["push_policy"] = policy
                (claude / legacy).write_text(json.dumps(cfg))
                (target / "CLAUDE.md").write_text("# hand-edited notes\n")
                code, out = self.wizard(str(target), "--reconfigure", "--quick", "--yes", "--no-github", "--no-provision")
                self.assertEqual(code, 0, out)
                self.assertIn(f"Loading saved configuration from {legacy}", out)
                self.assertEqual(json.loads((claude / "consul.json").read_text())["push_policy"], "consul")
                self.assertIn("Push policy: consul.", (target / "CLAUDE.md").read_text())
                backup = target / "session" / "CLAUDE.md.before-reconfigure"
                self.assertEqual(backup.read_text(), "# hand-edited notes\n")

    def test_orchestrate_still_accepts_legacy_push_policies(self):
        skill = (REPO / "consul" / "skills" / "orchestrate" / "SKILL.md").read_text()
        for value in ("`consul`", "`shipwright`", "`factory`"):
            self.assertIn(value, skill)


if __name__ == "__main__":
    unittest.main()
