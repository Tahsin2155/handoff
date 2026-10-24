"""End-to-end test of main()'s loop with a scripted model (no API, no screen)."""
from tests.stubs import (  # noqa: F401  (installs the fakes)
    Base, actions, call, click, fake_dialogs, require_confirmation, return_control,
)

import os  # noqa: E402
import tempfile  # noqa: E402
import types  # noqa: E402
import unittest  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest import mock  # noqa: E402

import main  # noqa: E402


def interaction(*steps):
    return SimpleNamespace(steps=list(steps), output_text="", model_dump=lambda: {})


class LoopTests(Base):
    def setUp(self):
        super().setUp()
        sys_genai = __import__("sys").modules["google.genai"]
        sys_genai.Client = lambda api_key: object()
        env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test"})
        env.start()
        self.addCleanup(env.stop)
        # main() writes convo_history/ into the current directory: use a temp one
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old_cwd = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, old_cwd)

    def run_loop(self, scripted, answers):
        """Run main() with the model replaced by `scripted` (a list of interactions)."""
        fake_dialogs.input_answer = list(answers)
        texts = []

        def fake_get_interaction(text=None, image=False):
            texts.append(text)
            return scripted.pop(0)

        with mock.patch.object(main, "get_interaction", side_effect=fake_get_interaction):
            main.main()
        return texts

    def test_return_control_reply_is_sent_back_and_blank_reply_ends_the_run(self):
        scripted = [
            interaction(click(), return_control("done", "Opened it.")),
            interaction(return_control("done", "Typed it.")),
        ]
        texts = self.run_loop(scripted, ["open notepad", "now type hello", None])
        self.assertEqual(texts[0], "open notepad")
        self.assertEqual(texts[1], "return_control: The user replied: now type hello")
        self.assertEqual(len(texts), 2)           # blank reply -> no third request
        self.assertEqual(scripted, [])            # both scripted turns were consumed
        self.assertEqual([a[0] for a in actions], ["click"])
        self.assertIn(2, self.sleeps)             # the settle-time sleep after a reply

    def test_denied_action_is_reported_and_the_batch_is_cut(self):
        fake_dialogs.confirm_answer = False
        scripted = [
            interaction(click(safety_decision=require_confirmation()),
                        call("type", text="x", intent="t")),
            interaction(return_control("stuck", "User denied it.")),
        ]
        texts = self.run_loop(scripted, ["do the risky thing", None])
        self.assertEqual(actions, [])             # neither the click nor the type ran
        self.assertIn("click: Denied by user.", texts[1])
        self.assertIn("Not executed because the turn stopped early: type", texts[1])
        self.assertEqual(len(texts), 2)

    def test_empty_task_exits_without_calling_the_model(self):
        texts = self.run_loop([], ["   "])
        self.assertEqual(texts, [])


if __name__ == "__main__":
    unittest.main()
