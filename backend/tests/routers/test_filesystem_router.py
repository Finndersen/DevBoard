"""Test filesystem router functionality."""


class TestFilesystemRouter:
    """Test cases for Filesystem Router."""

    def test_browse_default_home_directory(self, client):
        """Test browsing with no path defaults to home directory."""
        response = client.get("/api/filesystem/browse")

        assert response.status_code == 200
        data = response.json()
        assert "current_path" in data
        assert "parent_path" in data
        assert "directories" in data
        assert isinstance(data["directories"], list)

    def test_browse_specific_directory(self, client, tmp_path):
        """Test browsing a specific directory."""
        # Create test directory structure
        subdir1 = tmp_path / "subdir1"
        subdir2 = tmp_path / "subdir2"
        subdir1.mkdir()
        subdir2.mkdir()

        # Also create a hidden directory and a file (should be excluded)
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (tmp_path / "file.txt").write_text("test")

        response = client.get(f"/api/filesystem/browse?path={tmp_path}")

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == str(tmp_path)
        assert data["parent_path"] == str(tmp_path.parent)
        assert "subdir1" in data["directories"]
        assert "subdir2" in data["directories"]
        # Hidden directories should be excluded
        assert ".hidden" not in data["directories"]
        # Files should not appear
        assert "file.txt" not in data["directories"]

    def test_browse_nonexistent_path(self, client):
        """Test browsing a path that doesn't exist."""
        response = client.get("/api/filesystem/browse?path=/nonexistent/path/12345")

        assert response.status_code == 404
        data = response.json()
        assert "does not exist" in data["detail"]

    def test_browse_file_path(self, client, tmp_path):
        """Test browsing a file path instead of directory."""
        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        response = client.get(f"/api/filesystem/browse?path={test_file}")

        assert response.status_code == 400
        data = response.json()
        assert "not a directory" in data["detail"]

    def test_browse_root_has_no_parent(self, client):
        """Test that browsing root directory has no parent path."""
        response = client.get("/api/filesystem/browse?path=/")

        assert response.status_code == 200
        data = response.json()
        assert data["current_path"] == "/"
        assert data["parent_path"] is None

    def test_browse_empty_directory(self, client, tmp_path):
        """Test browsing an empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        response = client.get(f"/api/filesystem/browse?path={empty_dir}")

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == []

    def test_browse_directories_are_sorted(self, client, tmp_path):
        """Test that directories are returned in sorted order."""
        # Create directories in non-alphabetical order
        (tmp_path / "zebra").mkdir()
        (tmp_path / "alpha").mkdir()
        (tmp_path / "middle").mkdir()

        response = client.get(f"/api/filesystem/browse?path={tmp_path}")

        assert response.status_code == 200
        data = response.json()
        assert data["directories"] == ["alpha", "middle", "zebra"]

    def test_browse_path_with_spaces(self, client, tmp_path):
        """Test browsing a path that contains spaces."""
        dir_with_spaces = tmp_path / "path with spaces"
        dir_with_spaces.mkdir()
        subdir = dir_with_spaces / "subdir"
        subdir.mkdir()

        response = client.get(f"/api/filesystem/browse?path={dir_with_spaces}")

        assert response.status_code == 200
        data = response.json()
        assert "subdir" in data["directories"]

    def test_browse_empty_path_parameter(self, client):
        """Test that empty path parameter defaults to home directory."""
        response = client.get("/api/filesystem/browse?path=")

        assert response.status_code == 200
        data = response.json()
        # Should default to home directory (same as no path)
        assert "current_path" in data
