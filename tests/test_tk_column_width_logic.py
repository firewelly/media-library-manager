import json
import os
import sys
import tempfile
import unittest


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media_library_fixed import MediaLibrary


class FakeTreeWidget:
    def __init__(self, columns, widths=None):
        self._columns = tuple(columns)
        self._widths = {col: (widths or {}).get(col, 100) for col in self._columns}
        self.heading_calls = []
        self.column_calls = []

    def __getitem__(self, key):
        if key == "columns":
            return self._columns
        raise KeyError(key)

    def winfo_exists(self):
        return True

    def heading(self, col_name, **kwargs):
        self.heading_calls.append((col_name, kwargs))

    def column(self, col_name, option=None, **kwargs):
        if kwargs:
            self.column_calls.append((col_name, kwargs))
            if "width" in kwargs:
                self._widths[col_name] = kwargs["width"]
            return None
        if option == "width":
            return self._widths[col_name]
        raise KeyError(option)


class TkColumnWidthLogicTests(unittest.TestCase):
    def create_media_library_stub(self, default_columns):
        app = MediaLibrary.__new__(MediaLibrary)
        app.default_columns = default_columns
        app.column_config = app._clone_default_columns()
        return app

    def test_sanitize_column_config_handles_invalid_widths_and_positions(self):
        app = self.create_media_library_stub({
            "title": {"width": 400, "position": 0, "text": "标题"},
            "actors": {"width": 150, "position": 1, "text": "演员"},
            "stars": {"width": 75, "position": 2, "text": "星级"},
        })

        sanitized = app._sanitize_column_config({
            "title": {"width": 12, "position": 9, "text": "旧标题"},
            "actors": {"width": "bad", "position": 9},
        })

        self.assertEqual(set(sanitized.keys()), {"title", "actors", "stars"})
        self.assertEqual(sanitized["title"]["width"], 50)
        self.assertEqual(sanitized["actors"]["width"], 150)
        self.assertEqual(sanitized["stars"]["width"], 75)

        positions = sorted(cfg["position"] for cfg in sanitized.values())
        self.assertEqual(positions, [0, 1, 2])

    def test_configure_treeview_columns_disables_stretch_for_all_columns(self):
        app = self.create_media_library_stub({
            "title": {"width": 400, "position": 0, "text": "标题"},
            "actors": {"width": 120, "position": 1, "text": "演员"},
            "stars": {"width": 75, "position": 2, "text": "星级"},
            "tags": {"width": 30, "position": 3, "text": "标签"},
        })
        tree = FakeTreeWidget(["title", "actors", "stars", "tags"])

        app._configure_treeview_columns(tree, ["title", "actors", "stars", "tags"])

        self.assertEqual(len(tree.heading_calls), 4)
        self.assertEqual(len(tree.column_calls), 4)
        for _, kwargs in tree.heading_calls:
            self.assertNotIn("command", kwargs)
        for col_name, kwargs in tree.column_calls:
            self.assertIn("stretch", kwargs)
            self.assertFalse(kwargs["stretch"])
            self.assertGreaterEqual(kwargs["width"], 50)
            self.assertEqual(kwargs["minwidth"], 50)

        self.assertEqual(tree._widths["tags"], 50)

    def test_save_column_config_after_resize_persists_current_widths_with_minimum(self):
        app = self.create_media_library_stub({
            "title": {"width": 400, "position": 0, "text": "标题"},
            "actors": {"width": 150, "position": 1, "text": "演员"},
            "stars": {"width": 75, "position": 2, "text": "星级"},
        })
        app.video_tree = FakeTreeWidget(
            ["title", "actors", "stars"],
            widths={"title": 520, "actors": 48, "stars": 90},
        )

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            app.config_path = tmp_path
            app._last_column_widths = {"title": 400, "actors": 150, "stars": 75}

            app.save_column_config_after_resize()

            self.assertEqual(app.column_config["title"]["width"], 520)
            self.assertEqual(app.column_config["actors"]["width"], 50)
            self.assertEqual(app.column_config["stars"]["width"], 90)
            self.assertEqual(app._last_column_widths["actors"], 48)

            with open(tmp_path, "r", encoding="utf-8") as f:
                saved = json.load(f)

            self.assertEqual(saved["columns"]["title"]["width"], 520)
            self.assertEqual(saved["columns"]["actors"]["width"], 50)
            self.assertEqual(saved["columns"]["stars"]["width"], 90)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_column_widths_changed_detects_different_column_sets(self):
        app = self.create_media_library_stub({
            "title": {"width": 400, "position": 0, "text": "标题"},
            "actors": {"width": 150, "position": 1, "text": "演员"},
        })
        app.video_tree = FakeTreeWidget(["title", "actors"], widths={"title": 400, "actors": 180})

        app._last_column_widths = {"title": 400}
        self.assertTrue(app._column_widths_changed())

        app._last_column_widths = {"title": 400, "actors": 180}
        self.assertFalse(app._column_widths_changed())

    def test_handle_single_click_returns_break_for_heading_drag_start(self):
        app = self.create_media_library_stub({
            "title": {"width": 400, "position": 0, "text": "标题"},
        })

        class ClickTree:
            def identify_region(self, x, y):
                return "heading"

        app.video_tree = ClickTree()
        app.on_drag_start = lambda event: "break"

        result = app.handle_single_click(type("Event", (), {"x": 10, "y": 5})())

        self.assertEqual(result, "break")


if __name__ == "__main__":
    unittest.main()
