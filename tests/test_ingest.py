"""Unit tests for lens.ingest."""

from pathlib import Path

from lens.ingest import AdapterRegistry, PlainTextAdapter, ImageAdapter, scan_corpus


class TestAdapterRegistry:
    def test_default_registry_handles_python(self):
        reg = AdapterRegistry.with_defaults()
        adapter = reg.find_adapter(Path("foo.py"))
        assert adapter is not None
        assert isinstance(adapter, PlainTextAdapter)

    def test_default_registry_handles_png(self):
        reg = AdapterRegistry.with_defaults()
        adapter = reg.find_adapter(Path("diagram.png"))
        assert adapter is not None
        assert isinstance(adapter, ImageAdapter)

    def test_returns_none_for_unknown(self):
        reg = AdapterRegistry.with_defaults()
        assert reg.find_adapter(Path("binary.exe")) is None


class TestPlainTextAdapter:
    def test_read(self, tmp_path: Path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n", encoding="utf-8")
        adapter = PlainTextAdapter()
        cf = adapter.read(f)
        assert cf.content == "x = 1\n"
        assert cf.language == "python"
        assert cf.content_hash  # non-empty


class TestScanCorpus:
    def test_scans_directory(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("pass", encoding="utf-8")
        (tmp_path / "b.md").write_text("# Hello", encoding="utf-8")
        (tmp_path / "c.exe").write_bytes(b"\x00\x01")  # should be skipped
        files = scan_corpus(tmp_path)
        paths = {f.path for f in files}
        assert str(tmp_path / "a.py") in paths
        assert str(tmp_path / "b.md") in paths
        assert str(tmp_path / "c.exe") not in paths

    def test_skips_git_dir(self, tmp_path: Path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("x", encoding="utf-8")
        (tmp_path / "main.py").write_text("pass", encoding="utf-8")
        files = scan_corpus(tmp_path)
        paths = {f.path for f in files}
        assert not any(".git" in p for p in paths)


class TestIncrementalIngestion:
    def test_first_run_returns_all(self, tmp_path: Path):
        corpus = tmp_path / "repo"
        corpus.mkdir()
        (corpus / "a.py").write_text("x = 1", encoding="utf-8")
        (corpus / "b.py").write_text("y = 2", encoding="utf-8")
        cache = tmp_path / "cache"
        files = scan_corpus(corpus, cache_dir=cache, incremental=True)
        assert len(files) == 2
        assert (cache / "corpus-state.db").exists()

    def test_second_run_skips_unchanged(self, tmp_path: Path):
        corpus = tmp_path / "repo"
        corpus.mkdir()
        (corpus / "a.py").write_text("x = 1", encoding="utf-8")
        (corpus / "b.py").write_text("y = 2", encoding="utf-8")
        cache = tmp_path / "cache"

        # First run — all files
        files1 = scan_corpus(corpus, cache_dir=cache, incremental=True)
        assert len(files1) == 2

        # Second run (nothing changed) — no files
        files2 = scan_corpus(corpus, cache_dir=cache, incremental=True)
        assert len(files2) == 0

    def test_detects_changed_file(self, tmp_path: Path):
        corpus = tmp_path / "repo"
        corpus.mkdir()
        (corpus / "a.py").write_text("x = 1", encoding="utf-8")
        cache = tmp_path / "cache"

        scan_corpus(corpus, cache_dir=cache, incremental=True)

        # Modify the file
        (corpus / "a.py").write_text("x = 999", encoding="utf-8")
        files = scan_corpus(corpus, cache_dir=cache, incremental=True)
        assert len(files) == 1
        assert files[0].content == "x = 999"

    def test_non_incremental_ignores_cache(self, tmp_path: Path):
        corpus = tmp_path / "repo"
        corpus.mkdir()
        (corpus / "a.py").write_text("x = 1", encoding="utf-8")
        cache = tmp_path / "cache"

        scan_corpus(corpus, cache_dir=cache, incremental=True)

        # Non-incremental should return all even if cache exists
        files = scan_corpus(corpus, cache_dir=cache, incremental=False)
        assert len(files) == 1
