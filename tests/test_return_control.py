"""Tests for the return_control tool: declaration, dialog and handler."""
from tests.stubs import Base, fake_dialogs, return_control  # noqa: F401  (installs the fakes)

import unittest  # noqa: E402

from executions import tools  # noqa: E402
from executions.prompts import sys_instructions  # noqa: E402
from executions.results import Outcome, Result  # noqa: E402


class DeclarationTests(Base):
    def test_declares_status_and_message_as_required_parameters(self):
        params = tools.RETURN_CONTROL_TOOL["parameters"]
        self.assertEqual(params["type"], "object")
        self.assertEqual(sorted(params["required"]), ["message", "status"])
        self.assertEqual(params["properties"]["status"]["enum"], ["done", "need_input", "stuck"])
        self.assertEqual(params["properties"]["message"]["type"], "string")

    def test_tool_is_sent_to_the_model(self):
        self.assertIn(tools.RETURN_CONTROL_TOOL, tools.TOOLS)

    def test_system_prompt_matches_the_new_tool(self):
        self.assertIn("return_control", sys_instructions)
        self.assertIn("status", sys_instructions)
        self.assertIn("message", sys_instructions)
        self.assertNotIn("takes no arguments", sys_instructions)
        self.assertNotIn("STATUS:", sys_instructions)


class HandlerTests(Base):
    def test_reply_becomes_a_return_control_result(self):
        fake_dialogs.input_answer = "  try the File menu  "
        result = tools.return_control("stuck", "I cannot find the Save button.")
        self.assertEqual(result, Result(Outcome.RETURN_CONTROL, "The user replied: try the File menu"))

    def test_dialog_shows_status_heading_and_model_message(self):
        fake_dialogs.input_answer = "ok"
        tools.return_control("stuck", "I cannot find the Save button.")
        (kind, prompt), = fake_dialogs.shown
        self.assertEqual(kind, "input")
        self.assertIn("The agent is stuck", prompt)
        self.assertIn("I cannot find the Save button.", prompt)

    def test_each_status_has_its_own_wording(self):
        fake_dialogs.input_answer = "ok"
        for status, heading in (("done", "complete"), ("need_input", "needs your input"), ("stuck", "stuck")):
            fake_dialogs.shown.clear()
            tools.return_control(status, "msg")
            self.assertIn(heading, fake_dialogs.shown[0][1], status)

    def test_blank_whitespace_or_cancel_ends_the_run(self):
        for answer in (None, "", "   "):
            fake_dialogs.input_answer = answer
            result = tools.return_control("done", "Finished.")
            self.assertEqual(result, Result(Outcome.END_RUN), repr(answer))

    def test_long_messages_are_wrapped(self):
        fake_dialogs.input_answer = "ok"
        tools.return_control("need_input", "word " * 80)
        prompt = fake_dialogs.shown[0][1]
        self.assertTrue(all(len(line) <= 70 for line in prompt.splitlines()))

    def test_unknown_status_falls_back_to_need_input(self):
        fake_dialogs.input_answer = "ok"
        tools.HANDLERS["return_control"]({"status": "banana", "message": "x"})
        self.assertIn("needs your input", fake_dialogs.shown[0][1])

    def test_missing_or_extra_arguments_do_not_crash(self):
        fake_dialogs.input_answer = "ok"
        for arguments in (None, {}, {"status": "done", "message": "m", "intent": "extra"}):
            fake_dialogs.shown.clear()
            result = tools.HANDLERS["return_control"](arguments)
            self.assertEqual(result.outcome, Outcome.RETURN_CONTROL, arguments)


if __name__ == "__main__":
    unittest.main()
