from django.test import TestCase

from core import textutils
from courses.models import Category, Course


class NormalizeTests(TestCase):
    def test_arabic_letters_digits_and_halfspace(self):
        self.assertEqual(textutils.normalize("كتاب  يك"), "کتاب یک")
        self.assertEqual(textutils.normalize("دوره ۱۲۳ و ٤٥٦"), "دوره 123 و 456")
        self.assertEqual(textutils.normalize("می‌خواهم"), textutils.normalize("میخواهم"))
        self.assertEqual(textutils.normalize("مُدَرِّس"), "مدرس")
        self.assertEqual(textutils.normalize("Python!!"), "python")
        self.assertEqual(textutils.normalize("C++ و C#"), "c++ و c#")

    def test_synonym_variants(self):
        self.assertIn("python", textutils.query_variants("پایتون"))
        self.assertIn("پایتون مقدماتی", textutils.query_variants("python مقدماتی"))
        self.assertIn("ai", textutils.query_variants("هوش مصنوعی"))
        self.assertEqual(textutils.query_variants("   "), [])
        self.assertLessEqual(len(textutils.query_variants("پایتون جنگو وب شبکه امنیت لینوکس")), 8)

    def test_typo_correction(self):
        vocab = ["python", "network", "security"]
        self.assertEqual(textutils.suggest_correction("pyton", vocab), "python")
        self.assertEqual(textutils.suggest_correction("python", vocab), None)  # already correct
        self.assertIsNone(textutils.suggest_correction("zzzzzz", vocab))


class CourseSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name="شبکه و امنیت", slug="net")
        cls.py = Course.objects.create(title="برنامه‌نویسی پایتون", slug="py", category=cat, summary="مقدماتی",
                                       magazine_tag="python", is_published=True)
        cls.web = Course.objects.create(title="كتاب طراحي وب", slug="web", category=cat, summary="html و css",
                                        is_published=True)

    def find(self, term):
        return set(Course.objects.search(term).values_list("slug", flat=True))

    def test_persian_variants_match(self):
        self.assertEqual(self.find("طراحی وب"), {"web"})        # stored with Arabic ي/ك
        self.assertEqual(self.find("برنامه نویسی"), {"py"})     # half-space vs space
        self.assertEqual(self.find("برنامهنویسی"), {"py"})

    def test_synonyms_cross_language(self):
        self.assertEqual(self.find("python"), {"py"})
        self.assertEqual(self.find("پایتون"), {"py"})
        self.assertEqual(self.find("WEB"), {"web"})

    def test_all_words_must_match(self):
        self.assertEqual(self.find("پایتون مقدماتی"), {"py"})
        self.assertEqual(self.find("پایتون html"), set())

    def test_typo_is_corrected_only_when_nothing_matches(self):
        self.assertEqual(self.find("pyton"), {"py"})
        self.assertEqual(self.find("xyzxyz"), set())

    def test_empty_query_returns_everything_and_search_text_updates(self):
        self.assertEqual(self.find("   "), {"py", "web"})
        self.py.title = "جاوا پیشرفته"
        self.py.save()
        self.assertEqual(self.find("جاوا"), {"py"})
        self.assertEqual(self.find("پایتون"), {"py"})  # still matches through its magazine tag "python"

    def test_category_name_is_searchable(self):
        self.assertEqual(self.find("امنیت"), {"py", "web"})
