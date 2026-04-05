from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Question
from .views import evaluate_answer_with_ai, extract_questions


class ExtractQuestionsTests(TestCase):
    def test_extract_questions_normalizes_bullets_and_adds_question_mark(self):
        text = "1. What is HTML?\n2. Explain semantic tags\n- What does the a tag do?"

        self.assertEqual(
            extract_questions(text),
            [
                "What is HTML?",
                "Explain semantic tags?",
                "What does the a tag do?",
            ],
        )


class GenerateAIQuestionsTests(TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False)
    @patch("accounts.views.generate_questions_with_gemini")
    def test_generate_ai_questions_creates_questions_and_redirects(self, mock_generate_questions):
        mock_generate_questions.return_value = SimpleNamespace(
            text="1. What is HTML?\n2. What is the purpose of semantic HTML?\n3. What does the <a> tag do?"
        )

        response = self.client.post(
            reverse("generate_ai_questions"),
            {
                "prompt": "Generate HTML interview questions",
                "subject": "HTML",
            },
        )

        self.assertRedirects(response, reverse("question_list"))
        self.assertEqual(Question.objects.filter(subject="HTML", source_type="AI").count(), 3)

    def test_generate_ai_questions_requires_prompt(self):
        response = self.client.post(
            reverse("generate_ai_questions"),
            {
                "prompt": "",
                "subject": "HTML",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a prompt.")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False)
    @patch("accounts.views.generate_questions_with_gemini")
    def test_generate_ai_questions_shows_friendly_quota_message(self, mock_generate_questions):
        mock_generate_questions.side_effect = Exception("429 quota exceeded for model")

        response = self.client.post(
            reverse("generate_ai_questions"),
            {
                "prompt": "Generate HTML interview questions",
                "subject": "HTML",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gemini quota is currently unavailable for this API key.")


class EvaluateAnswerWithAITests(TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False)
    @patch("accounts.views.generate_gemini_text")
    def test_evaluate_answer_with_ai_returns_feedback(self, mock_generate_gemini_text):
        mock_generate_gemini_text.return_value = "Verdict: Strong\nGood explanation\nNeeds more detail on semantics"

        feedback = evaluate_answer_with_ai("What is HTML?", "HTML is the structure of a web page.")

        self.assertIn("Verdict: Strong", feedback)
        mock_generate_gemini_text.assert_called_once()

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False)
    @patch("accounts.views.generate_gemini_text")
    def test_evaluate_answer_with_ai_handles_quota_error(self, mock_generate_gemini_text):
        mock_generate_gemini_text.side_effect = Exception("429 quota exceeded")

        feedback = evaluate_answer_with_ai("What is HTML?", "HTML is markup.")

        self.assertEqual(
            feedback,
            "AI feedback unavailable right now because Gemini quota was exceeded.",
        )
