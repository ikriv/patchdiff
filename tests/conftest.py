import textwrap

import pytest

from patchdiff.model.patch_model import Patch, PatchText
from patchdiff.parser import parse_patch


@pytest.fixture
def make_patch():
    """Gives a test a function that builds a Patch from CSV text written inside the test.

    The text goes through the real parser. No file is read or written.

        patch = make_patch('''
            BeginDate,EndDate,Issuer,Country
            ,,JBL,USA
        ''')

    The text may be indented to line up with the test code: the common indent and the
    empty first line are removed before parsing. Line 1 is the header, so the first
    data row is row 2, the same as in a real file.

    `name` is optional and can only be passed by keyword: make_patch(text, name="old.csv").
    It is not a file to open. It is what the report and the error messages call the patch.
    """

    def make(text: str, *, name: str = "patch.csv") -> Patch:
        lines = textwrap.dedent(text).lstrip("\n").splitlines(keepends=True)
        return parse_patch(PatchText(name, tuple(lines)))

    return make
