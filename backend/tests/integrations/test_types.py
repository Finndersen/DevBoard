from devboard.integrations.types import FileDiff, StructuredDiff


class TestStructuredDiffFormatSummary:
    def test_empty_diff(self):
        diff = StructuredDiff(files=[], additions=0, deletions=0)
        assert diff.format_summary() == "No file changes."

    def test_single_file_with_changes(self):
        diff = StructuredDiff(
            files=[FileDiff(file_path="src/foo.py", diff_content="", additions=10, deletions=3)],
            additions=10,
            deletions=3,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +10/-3\n  - src/foo.py (+10/-3)")

    def test_new_file(self):
        diff = StructuredDiff(
            files=[FileDiff(file_path="src/new.py", diff_content="", additions=20, deletions=0, is_new_file=True)],
            additions=20,
            deletions=0,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +20/-0\n  - src/new.py (+20/-0) (new)")

    def test_deleted_file(self):
        diff = StructuredDiff(
            files=[FileDiff(file_path="src/old.py", diff_content="", additions=0, deletions=15, is_deleted=True)],
            additions=0,
            deletions=15,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +0/-15\n  - src/old.py (+0/-15) (deleted)")

    def test_multiple_files_mixed(self):
        diff = StructuredDiff(
            files=[
                FileDiff(file_path="src/foo.py", diff_content="", additions=30, deletions=5),
                FileDiff(file_path="src/bar.py", diff_content="", additions=15, deletions=7, is_new_file=True),
                FileDiff(file_path="src/baz.py", diff_content="", additions=0, deletions=0, is_deleted=True),
            ],
            additions=45,
            deletions=12,
        )
        result = diff.format_summary()
        assert result == (
            "3 files changed, +45/-12\n"
            "  - src/foo.py (+30/-5)\n"
            "  - src/bar.py (+15/-7) (new)\n"
            "  - src/baz.py (+0/-0) (deleted)"
        )

    def test_renamed_file_annotation(self):
        diff = StructuredDiff(
            files=[
                FileDiff(
                    file_path="src/new_name.py",
                    diff_content="",
                    additions=5,
                    deletions=3,
                    old_file_path="src/old_name.py",
                )
            ],
            additions=5,
            deletions=3,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +5/-3\n  - src/new_name.py (+5/-3) (renamed from src/old_name.py)")

    def test_binary_file_annotation(self):
        diff = StructuredDiff(
            files=[FileDiff(file_path="assets/logo.png", diff_content="", additions=0, deletions=0, is_binary=True)],
            additions=0,
            deletions=0,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +0/-0\n  - assets/logo.png (+0/-0) (binary)")

    def test_mode_change_annotation(self):
        diff = StructuredDiff(
            files=[
                FileDiff(file_path="scripts/run.sh", diff_content="", additions=0, deletions=0, is_mode_change=True)
            ],
            additions=0,
            deletions=0,
        )
        result = diff.format_summary()
        assert result == ("1 files changed, +0/-0\n  - scripts/run.sh (+0/-0) (mode change)")

    def test_multiple_annotations(self):
        diff = StructuredDiff(
            files=[
                FileDiff(
                    file_path="src/new_name.py",
                    diff_content="",
                    additions=5,
                    deletions=3,
                    old_file_path="src/old_name.py",
                    is_mode_change=True,
                )
            ],
            additions=5,
            deletions=3,
        )
        result = diff.format_summary()
        assert result == (
            "1 files changed, +5/-3\n  - src/new_name.py (+5/-3) (renamed from src/old_name.py, mode change)"
        )
