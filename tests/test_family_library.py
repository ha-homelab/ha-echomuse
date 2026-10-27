"""Audit the reviewed literary corpus independently of runtime matching.

This is intentionally offline: an upstream page changing must not silently
replace the words that the household speaker has been approved to recite.
"""

import hashlib
import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit


LIBRARY = Path(__file__).resolve().parents[1] / "custom_components/myshka_family/library.json"
# Reviewed full poem bodies, excluding titles, bylines, footnotes and dates.
REVIEWED = {
    "blok_zaychik": ("Александр Блок", "Зайчик", 24, "3b9214af15802e8ee4bcdef0215a8b8da902be2dbcb0dad0c3c398d560af43e1"),
    "maykov_lullaby": ("Аполлон Майков", "Колыбельная песня", 16, "340c57e361efd52a719cfb20eb823daf0b3d8faae6a661471d71ee8aeff588da"),
    "maykov_swallow": ("Аполлон Майков", "Ласточка примчалась", 7, "932ccbf4aef5c5b2fb271560d0c89ce085eb9c7e964746a78876a8a86d87685b"),
    "esenin_birch": ("Сергей Есенин", "Берёза", 16, "439f7ef8374f0cdc0f7ae97266b939cd3622dd0517a25277f4bf3ad5bea486b0"),
}


class FamilyLibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = json.loads(LIBRARY.read_text(encoding="utf-8"))

    def test_reviewed_complete_poems_and_attribution(self):
        self.assertEqual(self.library["schema_version"], 1)
        entries = self.library["entries"]
        self.assertEqual({entry["id"] for entry in entries}, REVIEWED.keys())
        self.assertEqual(len(entries), len(REVIEWED))
        for entry in entries:
            with self.subTest(entry=entry["id"]):
                author, title, lines, digest = REVIEWED[entry["id"]]
                self.assertEqual(entry["author"], author)
                self.assertEqual(entry["title"], title)
                self.assertEqual(entry["language"], "ru")
                self.assertEqual(entry["kind"], "poem")
                self.assertEqual(len([line for line in entry["text"].splitlines() if line]), lines)
                self.assertEqual(entry["sha256"], digest)
                self.assertEqual(hashlib.sha256(entry["text"].encode("utf-8")).hexdigest(), digest)
                self.assertLessEqual(len(f"{author}. {title}. {entry['text']}"), 600)
                self.assertNotRegex(entry["text"], r"[<>\[\]{}]")

    def test_each_source_has_explicit_reuse_and_normalization_provenance(self):
        for entry in self.library["entries"]:
            with self.subTest(entry=entry["id"]):
                source, rights = entry["source"], entry["rights"]
                self.assertEqual(rights["status"], "public-domain")
                self.assertLessEqual(rights["author_death_year"], 1925)
                self.assertEqual(source["accessed"], self.library["reviewed_on"])
                for key in ("edition", "normalization"):
                    self.assertGreater(len(source[key]), 20)
                self.assertGreater(len(rights["note"]), 50)
                for link in (source["url"], rights["evidence_url"]):
                    parsed = urlsplit(link)
                    self.assertEqual(parsed.scheme, "https")
                    self.assertIn(parsed.netloc, {"ilibrary.ru", "ru.wikisource.org"})
                    self.assertNotIn("@", parsed.netloc)
                if "revision_id" in source:
                    self.assertEqual(parse_qs(urlsplit(source["revision_url"]).query)["oldid"], [str(source["revision_id"])])
                published = rights["first_publication_year"]
                if published is not None:
                    self.assertGreaterEqual(published, rights["written_year"])
                    self.assertLess(published, 1931)
                else:
                    self.assertEqual(entry["id"], "blok_zaychik")
                    self.assertIn("not a verified first-publication year", rights["note"])

    def test_aliases_do_not_invent_authors_or_include_commands(self):
        for entry in self.library["entries"]:
            with self.subTest(entry=entry["id"]):
                for key in ("author_aliases", "title_aliases", "topics"):
                    self.assertTrue(entry[key])
                    self.assertEqual(len(set(entry[key])), len(entry[key]))
                    for alias in entry[key]:
                        self.assertEqual(alias, alias.lower())
                        self.assertNotRegex(alias, r"(?:включи|выключи|барто|маршак|чуковск)")


if __name__ == "__main__":
    unittest.main()
