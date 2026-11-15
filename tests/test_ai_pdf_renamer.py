"""
tests/test_ai_pdf_renamer.py - Unit Tests for the local PDF Renamer

PURPOSE:
--------
Verifies the on-device rules that pick a scan's recipient company from the
known list, and the evidence check that stops the local model from inventing
a sender. Pure functions only — no OCR, model, or network calls.
All company names below are fictional.

TEST CASES:
-----------
1. Recipient from the filename (exact, typed prefix, typo) and from the letter text
2. Conflicts and ambiguity are left unresolved instead of guessed
3. A sender is kept only when the model's quote really appears in the letter
   and it isn't the recipient itself

HOW TO RUN:
-----------
    # Run just this test file
    python -m unittest tests.test_ai_pdf_renamer -v

    # Or run all tests
    python run_tests.py
"""

import unittest
import sys
import os

# Add project root to path so we can import the renamer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_pdf_renamer import match_company, grounded_sender, hide_recipient, rename_pdf


COMPANIES = [
    {"name": "Fabrikam Holdings LLC", "addresses": ["742 Evergreen Terrace, Suite 12, Springfield, IL 62704"]},
    {"name": "Contoso Ltd",           "addresses": ["1 Contoso Way, Redmond, WA 98052"]},
    {"name": "Tailspin Toys Inc",     "addresses": ["100 Main St, Austin, TX 73301"]},
    {"name": "Wingtip Toys Inc",      "addresses": ["100 Main Street, Austin, TX 73301"]},  # shared address
    {"name": "Tailwind Traders",      "addresses": []},                                      # shares "tail" prefix
    {"name": "ABC Inc",               "addresses": []},                                      # short name
]

LETTER = """NORTHWIND UTILITIES CORPORATION
500 Harbor Blvd, Seattle, WA 98101
May 14, 2026
Fabrikam Holdings LLC
742 Evergreen Terrace, Suite 12
Springfield, IL 62704
Dear Customer,
Sincerely,
Northwind Utilities Corporation"""

FABRIKAM = "Fabrikam Holdings LLC"


class TestMatchCompany(unittest.TestCase):
    """Recipient comes only from the known list, and only with evidence."""

    def test_filename_and_letter_agree(self):
        self.assertEqual(match_company("fabrikam holdings llc05142026212549.pdf", LETTER, COMPANIES),
                         (FABRIKAM, "hint-exact+name-in-text"))

    def test_typed_filename_prefix(self):
        self.assertEqual(match_company("fabrik05142026212549.pdf", LETTER, COMPANIES),
                         (FABRIKAM, "hint-prefix+name-in-text"))

    def test_filename_typo(self):
        self.assertEqual(match_company("fabrikam holdngs llc05142026212549.pdf", "Hello", COMPANIES),
                         (FABRIKAM, "hint-fuzzy"))

    def test_name_in_letter_without_filename_hint(self):
        self.assertEqual(match_company("scan0001.pdf", LETTER, COMPANIES), (FABRIKAM, "name-in-text"))

    def test_unique_address_in_one_block(self):
        text = "742 Evergreen Terrace Ste 12\nSpringfield IL 62704-1234"
        self.assertEqual(match_company("scan.pdf", text, COMPANIES), (FABRIKAM, "address"))

    def test_filename_and_letter_disagree_is_unresolved(self):
        self.assertEqual(match_company("contoso05142026212549.pdf", LETTER, COMPANIES), (None, "conflict"))

    def test_ambiguous_or_too_short_prefix_is_ignored(self):
        self.assertEqual(match_company("tail05142026212549.pdf", LETTER, COMPANIES), (FABRIKAM, "name-in-text"))
        self.assertEqual(match_company("t05142026212549.pdf", LETTER, COMPANIES), (FABRIKAM, "name-in-text"))

    def test_scattered_address_numbers_do_not_match(self):
        text = "Invoice 742\n" + "x\n" * 10 + "Suite 12\n" + "x\n" * 10 + "Springfield IL 62704"
        self.assertEqual(match_company("scan.pdf", text, COMPANIES), (None, None))

    def test_shared_address_is_unresolved(self):
        self.assertEqual(match_company("scan.pdf", "100 Main St\nAustin TX 73301", COMPANIES), (None, None))

    def test_two_client_names_without_other_evidence(self):
        self.assertEqual(match_company("scan.pdf", "Contoso Ltd\nFabrikam Holdings LLC", COMPANIES), (None, None))

    def test_short_name_not_matched_inside_words(self):
        self.assertEqual(match_company("scan.pdf", "abcdef labs", COMPANIES), (None, None))

    def test_duplicate_list_entries_are_unresolved(self):
        dupes = [{"name": "Acme Widgets Inc"}, {"name": "ACME Widgets, Inc."}]
        self.assertEqual(match_company("scan.pdf", "Acme Widgets Inc", dupes), (None, None))


class TestGroundedSender(unittest.TestCase):
    """The local model must quote the sender as printed; otherwise UNKNOWN."""

    def test_quote_found_keeps_sender(self):
        data = {"sender_as_printed": "NORTHWIND UTILITIES CORPORATION", "sender": "Northwind Utilities"}
        self.assertEqual(grounded_sender(data, LETTER, FABRIKAM), "Northwind Utilities")

    def test_invented_sender_is_rejected(self):
        data = {"sender_as_printed": "Wells Fargo Bank", "sender": "Wells Fargo"}
        self.assertEqual(grounded_sender(data, LETTER, FABRIKAM), "UNKNOWN")

    def test_short_quote_needs_whole_word(self):
        data = {"sender_as_printed": "IRS", "sender": "IRS"}
        self.assertEqual(grounded_sender(data, "Notice from the IRS", FABRIKAM), "IRS")
        self.assertEqual(grounded_sender(data, "your first notice", FABRIKAM), "UNKNOWN")

    def test_model_unknown_stays_unknown(self):
        data = {"sender_as_printed": "UNKNOWN", "sender": "UNKNOWN"}
        self.assertEqual(grounded_sender(data, LETTER, FABRIKAM), "UNKNOWN")


    def test_recipient_is_never_the_sender(self):
        data = {"sender_as_printed": "Fabrikam Holdings LLC", "sender": "Fabrikam Holdings LLC"}
        self.assertEqual(grounded_sender(data, LETTER, FABRIKAM), "UNKNOWN")

    def test_recipient_with_ocr_noise_is_rejected(self):
        data = {"sender_as_printed": "DES FABRIKAM HOLDINGS LLC", "sender": "DES FABRIKAM HOLDINGS LLC"}
        self.assertEqual(grounded_sender(data, "DES FABRIKAM HOLDINGS LLC\n" + LETTER, FABRIKAM), "UNKNOWN")


    def test_recipient_lines_are_hidden_from_the_model(self):
        hidden = hide_recipient("DES FABRIKAM HOLDINGS LLC\n" + LETTER, FABRIKAM)
        self.assertNotIn("FABRIKAM", hidden.upper())
        self.assertEqual(hidden.count("[RECIPIENT]"), 2)
        self.assertIn("NORTHWIND UTILITIES CORPORATION", hidden)

class TestRenamePdf(unittest.TestCase):
    """Filename formatting."""

    def test_sender_trailing_dot_does_not_double(self):
        self.assertEqual(rename_pdf("/nonexistent/scan.pdf", "Contoso Ltd", "Northwind Inc.", dry_run=True),
                         "Contoso Ltd - From Northwind Inc.pdf")


if __name__ == "__main__":
    unittest.main()
