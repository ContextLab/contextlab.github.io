"""Tests for the Dartmouth Chat client.

Real calls to the real service, per the no-mocks rule. They skip when
DARTMOUTH_CHAT_API_KEY is absent, which is the case for anyone who has not set
one up; CI supplies it from the repository secret, so the calling method and
the response shape are verified on every change.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import dartmouth_chat as dc  # noqa: E402


requires_key = pytest.mark.skipif(
    not dc.is_configured(),
    reason=(
        "DARTMOUTH_CHAT_API_KEY not set -- create a key at "
        "chat.dartmouth.edu -> Settings -> Account -> API Keys"
    ),
)


class TestStripReasoning:
    """Pure text handling; no network, so these always run."""

    def test_removes_a_think_block(self):
        assert dc.strip_reasoning(
            "<think>hmm, what to say</think>Alex studies memory."
        ) == "Alex studies memory."

    def test_removes_a_multiline_think_block(self):
        text = "<think>\nline one\nline two\n</think>\nThe bio."
        assert dc.strip_reasoning(text) == "The bio."

    def test_unterminated_block_does_not_leak_the_monologue(self):
        """A truncated response must not put the scratchpad in someone's bio."""
        assert dc.strip_reasoning("The bio.<think>still thinking") == "The bio."

    def test_leaves_ordinary_text_alone(self):
        assert dc.strip_reasoning("  Alex studies memory.  ") == "Alex studies memory."

    def test_is_case_insensitive(self):
        assert dc.strip_reasoning("<THINK>x</THINK>done") == "done"


class TestConfiguration:
    def test_default_model_is_named(self):
        assert dc.DEFAULT_MODEL == "qwen.qwen3.5-122b"

    def test_missing_key_raises_with_instructions(self, monkeypatch):
        monkeypatch.setattr(dc, "get_api_key", lambda: None)
        with pytest.raises(dc.DartmouthChatError, match="Settings"):
            dc.chat("hello")


@requires_key
class TestRealService:
    """These make live calls."""

    def test_lists_models(self):
        models = dc.list_models()
        assert len(models) > 1
        assert all(isinstance(m, str) for m in models)

    def test_the_default_model_actually_exists(self):
        """Guards against the deployment retiring the model we name."""
        assert dc.DEFAULT_MODEL in dc.list_models()

    def test_returns_text(self):
        out = dc.chat("Reply with exactly: ok", max_tokens=50, temperature=0)
        assert isinstance(out, str)
        assert out.strip()

    def test_reasoning_is_off_by_default(self):
        """The whole reason bios work.

        qwen3.5-122b spends its entire budget deliberating when thinking is
        on: 2000 tokens produced 6883 characters of reasoning and a null
        `content`. With it off the same prompt answers in about 20 tokens.
        """
        out = dc.chat(
            "Write a one sentence bio for Alex, an undergraduate who joined a "
            "memory lab in 2026. Output ONLY the bio.",
            max_tokens=200,
        )
        assert 15 < len(out) < 500
        assert "<think>" not in out.lower()

    def test_empty_content_raises_rather_than_returning_blank(self):
        """A blank must never reach people.xlsx as somebody's bio.

        Forcing reasoning on with a tiny budget reproduces the null `content`
        the service returns when it runs out mid-thought.
        """
        with pytest.raises(dc.DartmouthChatError, match="no content"):
            dc.chat(
                "Explain memory consolidation thoroughly.",
                max_tokens=30,
                reasoning=True,
            )

    def test_a_bad_model_name_raises(self):
        with pytest.raises(dc.DartmouthChatError):
            dc.chat("hi", model="definitely-not-a-real-model", max_tokens=20)


@requires_key
class TestOnboardingBios:
    """The two functions onboarding actually calls."""

    @staticmethod
    def _bios():
        from onboard_member import edit_bio_with_llm, generate_bio_with_llm

        return generate_bio_with_llm, edit_bio_with_llm

    def test_generates_a_usable_bio(self):
        generate, _ = self._bios()
        bio = generate("Alex", "2026")
        assert len(bio) > 15
        # The generic fallback means the service call failed.
        assert "interested in how people learn and remember" not in bio

    def test_edit_removes_first_person(self):
        _, edit = self._bios()
        out = edit("hi im jamie and i love memory research", "Jamie")
        assert not out.lower().startswith(("hi", "i am", "i'm"))

    def test_edit_strips_a_phone_number(self):
        _, edit = self._bios()
        out = edit(
            "Hi I'm Alex, I study memory. Call me at 555-123-4567.", "Alex"
        )
        assert "555-123-4567" not in out

    def test_edit_does_not_invent_gendered_pronouns(self):
        """These are real people on a public page.

        The model was guessing pronouns from the first name until the prompt
        told it not to, so this pins the behaviour.
        """
        _, edit = self._bios()
        out = edit("im jamie, a sophomore who likes fMRI and coding", "Jamie")
        lowered = f" {out.lower()} "
        assert " he " not in lowered and " his " not in lowered
        assert " she " not in lowered and " her " not in lowered
