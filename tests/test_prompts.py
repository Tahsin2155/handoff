"""The system prompt adapts to the operating system it is built for."""
import tests.stubs  # noqa: F401  (must be imported before any project module)
import unittest

from executions.prompts import build_sys_instructions


class SystemPromptOsTests(unittest.TestCase):
    def test_names_the_detected_os(self):
        for system, name in (("Windows", "Windows"), ("Darwin", "macOS"), ("Linux", "Linux")):
            with self.subTest(system=system):
                self.assertIn(f"operates a {name} desktop", build_sys_instructions(system))

    def test_macos_uses_cmd_other_systems_use_ctrl(self):
        self.assertIn("Cmd+L", build_sys_instructions("Darwin"))
        self.assertNotIn("Ctrl+L", build_sys_instructions("Darwin"))
        self.assertIn("Ctrl+L", build_sys_instructions("Windows"))
        self.assertIn("Ctrl+L", build_sys_instructions("Linux"))

    def test_unknown_os_falls_back_to_generic_wording(self):
        for system in ("", "FreeBSD"):
            with self.subTest(system=system):
                text = build_sys_instructions(system)
                self.assertIn("operates a desktop (browser", text)
                self.assertNotIn("Windows", text)


if __name__ == "__main__":
    unittest.main()
