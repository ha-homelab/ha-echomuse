"""Conversation-level regressions for local, original family activities."""

import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "custom_components/myshka_family/family.py"
spec = importlib.util.spec_from_file_location("family", path)
family = importlib.util.module_from_spec(spec)
spec.loader.exec_module(family)


class FamilyTest(unittest.TestCase):
    def setUp(self):
        self.manager = family.FamilySessionManager()

    def ask(self, text, conversation_id="one", **kwargs):
        return self.manager.respond(text, conversation_id=conversation_id, **kwargs)

    def test_reported_bunny_request_gets_complete_attributed_poem(self):
        reply = self.ask("Расскажи мне стишок о зайке")
        self.assertEqual(reply.kind, "poem")
        self.assertEqual(reply.provenance, "original")
        self.assertIn("собственный", reply.speech)
        self.assertIn("Зайка", reply.speech)
        self.assertGreaterEqual(reply.speech.count("\n"), 4)
        self.assertFalse(reply.continue_conversation)

    def test_common_variations_and_politeness(self):
        for request in ("Мышка, прочитай нам короткий стих про зайчика, пожалуйста!",
                        "Пожалуйста, расскажи стих о кролике.", "Сочини стишок о зайке",
                        "Прочитай стихотворение про зайца"):
            with self.subTest(request=request):
                self.assertEqual(self.ask(request).kind, "poem")

    def test_does_not_hijack_unknown_subject_author_or_title(self):
        for request in ("Прочитай стих Агнии Барто", "Расскажи стишок про зайку Агнии Барто",
                        "Прочитай стих зайка Барто", "Расскажи стих о динозавре",
                        "Найди в интернете стих о зайке", "Прочитай Зайчик Александра Блока",
                        "Расскажи стих про зайку и включи свет", "Расскажи стих на английском"):
            with self.subTest(request=request):
                self.assertIsNone(self.ask(request))

    def test_other_supported_topics_and_nursery_rhyme(self):
        for request, kind in (("расскажи потешку", "nursery"), ("потешку про зайку", "nursery"),
                              ("стишок о котёнке", "poem"), ("стишок на ночь", "poem"),
                              ("прочитай стих про дождь", "poem")):
            with self.subTest(request=request):
                self.assertEqual(self.ask(request).kind, kind)

    def test_songs_are_not_claimed_to_be_sung(self):
        for request in ("спой песенку", "включи детскую песню", "спой про зайчика"):
            self.assertIsNone(self.ask(request))

    def test_another_poem_rotates_without_changing_topic(self):
        first = self.ask("стишок про зайку")
        second = self.ask("ещё")
        self.assertNotEqual(first.content_id, second.content_id)
        self.assertIn("зайк", second.speech.lower())
        self.assertEqual(self.ask("ещё один").content_id, first.content_id)

    def test_riddle_withholds_answer_and_accepts_natural_reply(self):
        question = self.ask("Загадай мне загадку")
        self.assertEqual(question.kind, "riddle")
        self.assertTrue(question.continue_conversation)
        self.assertNotIn("зай", question.speech.casefold())
        correct = self.ask("Я думаю, это зайчик!")
        self.assertEqual(correct.kind, "correct")
        self.assertFalse(correct.continue_conversation)
        self.assertIsNone(self.ask("котик"))

    def test_wrong_guess_hints_then_reveals_on_request(self):
        self.ask("загадай загадку")
        wrong = self.ask("белка")
        self.assertEqual(wrong.kind, "try_again")
        self.assertNotIn("зай", wrong.speech.casefold())
        self.assertEqual(self.ask("подскажи").kind, "hint")
        answer = self.ask("Не знаю")
        self.assertEqual(answer.kind, "answer")
        self.assertIn("Зайка", answer.speech)
        self.assertIsNone(self.ask("подсказка"))

    def test_explicit_native_intent_answers(self):
        self.ask("загадай загадку")
        self.assertEqual(self.ask("мой ответ заяц").kind, "correct")
        self.ask("загадай загадку")
        self.assertEqual(self.ask("ответ на загадку").kind, "answer")

    def test_next_riddle_after_answer(self):
        first = self.ask("загадай загадку")
        self.ask("скажи ответ")
        second = self.ask("следующая")
        self.assertEqual(second.kind, "riddle")
        self.assertNotEqual(first.content_id, second.content_id)

    def test_adult_activity_is_distinct(self):
        child = self.ask("загадай загадку для детей")
        adult = self.ask("загадай загадку для взрослого")
        self.assertNotEqual(child.content_id, adult.content_id)
        self.assertEqual(self.ask("три").kind, "correct")

    def test_pending_riddle_never_consumes_household_or_new_question(self):
        self.ask("загадай загадку")
        for request in ("включи свет на кухне", "выключи обогреватель", "играй музыку",
                        "какая мощность первого обогревателя", "почему идет дождь",
                        "найди песню про зайца", "это ответ на другой вопрос?"):
            with self.subTest(request=request):
                self.assertIsNone(self.ask(request))
        self.assertEqual(self.ask("это заяц").kind, "correct")

    def test_sessions_do_not_share_riddles_or_context(self):
        self.ask("загадай загадку", "a")
        self.assertIsNone(self.ask("зайка", "b"))
        self.assertIsNone(self.ask("ещё", "b"))
        self.ask("стишок", "b")
        self.assertEqual(self.ask("еще", "b").kind, "poem")
        self.assertEqual(self.ask("зайчик", "a").kind, "correct")

    def test_state_expires_and_cannot_reveal_stale_answer(self):
        self.manager = family.FamilySessionManager(ttl_seconds=10)
        self.ask("загадай загадку", now=0)
        self.assertIsNone(self.ask("скажи ответ", now=10))
        self.assertIsNone(self.ask("еще", now=11))

    def test_state_bounded_and_lru_eviction(self):
        self.manager = family.FamilySessionManager(max_sessions=2)
        self.ask("стишок", "a", now=0)
        self.ask("стишок", "b", now=1)
        self.ask("еще", "a", now=2)
        self.ask("стишок", "c", now=3)
        self.assertEqual(set(self.manager.sessions), {"a", "c"})
        self.assertIsNone(self.ask("еще", "b", now=4))

    def test_unhandled_chatter_does_not_refresh_state(self):
        self.manager = family.FamilySessionManager(ttl_seconds=10)
        self.ask("стишок", now=0)
        self.assertIsNone(self.ask("включи свет", now=9))
        self.assertIsNone(self.ask("еще", now=10))

    def test_stop_clears_only_that_conversation(self):
        self.ask("загадай загадку", "a")
        self.ask("загадай загадку", "b")
        self.assertEqual(self.ask("хватит", "a").kind, "stop")
        self.assertIsNone(self.ask("скажи ответ", "a"))
        self.assertEqual(self.ask("заяц", "b").kind, "correct")

    def test_bad_inputs_and_other_languages_not_consumed(self):
        for request in (None, 3, "", "x" * 501):
            self.assertIsNone(self.ask(request))
        self.assertIsNone(self.ask("стишок", language="en"))
        self.assertIsNotNone(self.ask("стишок", language="ru-RU"))
        self.assertIsNone(self.ask("стишок", conversation_id=""))
        self.assertIsNone(self.ask("стишок", conversation_id="x" * 257))

    def test_injected_verified_piece_precedes_original_and_keeps_source(self):
        piece = family.FamilyPiece("verified", "poem", "bunny", "Автор. Название. Проверенный текст.",
                                   "public_domain", "https://example.org/verified")
        self.manager = family.FamilySessionManager(extra_pieces=(piece,))
        reply = self.ask("стишок про зайку")
        self.assertEqual(reply.content_id, "verified")
        self.assertEqual(reply.provenance, "public_domain")
        self.assertEqual(reply.source_url, piece.source_url)
        self.assertEqual(self.ask("еще").provenance, "original")

    def test_compose_requests_and_continuations_keep_original_content(self):
        piece = family.FamilyPiece("verified", "poem", "bunny", "Автор. Название. Проверенный текст.",
                                   "public_domain", "https://example.org/verified")
        self.manager = family.FamilySessionManager(extra_pieces=(piece,))
        first = self.ask("Сочини стишок про зайку")
        self.assertEqual(first.provenance, "original")
        second = self.ask("Еще")
        self.assertEqual(second.provenance, "original")
        self.assertNotEqual(first.content_id, second.content_id)
        self.assertEqual(self.ask("Придумай стишок о зайке").provenance, "original")
        self.assertEqual(self.ask("Прочитай стих про зайку").provenance, "public_domain")

    def test_catalogue_requires_bounded_attribution_and_unique_ids(self):
        for piece in (family.FamilyPiece("bunny_stream", "poem", "bunny", "duplicate"),
                      family.FamilyPiece("long", "poem", "bunny", "x" * 601),
                      family.FamilyPiece("missing_source", "poem", "bunny", "text", "public_domain")):
            with self.subTest(piece=piece), self.assertRaises(ValueError):
                family.FamilySessionManager(extra_pieces=(piece,))
        for kwargs in ({"ttl_seconds": float("inf")}, {"max_sessions": 0}, {"ttl_seconds": False}):
            with self.assertRaises(ValueError):
                family.FamilySessionManager(**kwargs)

    def test_every_catalogue_reply_short(self):
        for piece in family.PIECES:
            self.assertLessEqual(len(piece.speech), family.MAX_SPEECH_CHARS)
        for riddle in family.RIDDLES:
            self.assertLessEqual(len(riddle.question) + len(riddle.hint), family.MAX_SPEECH_CHARS)


if __name__ == "__main__":
    unittest.main()
