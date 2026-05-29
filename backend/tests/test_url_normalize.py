from sitree.core.url_normalize import TemplateOptions, normalize, templatize


class TestNormalize:
    def test_lowercases_scheme_and_host(self) -> None:
        assert normalize("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_strips_fragment(self) -> None:
        assert normalize("https://example.com/a#section") == "https://example.com/a"

    def test_resolves_relative(self) -> None:
        assert normalize("/b", base="https://example.com/a/") == "https://example.com/b"

    def test_resolves_relative_with_dot_segments(self) -> None:
        assert normalize("../c", base="https://example.com/a/b/") == "https://example.com/a/c"

    def test_drops_default_port(self) -> None:
        assert normalize("https://example.com:443/x") == "https://example.com/x"
        assert normalize("http://example.com:80/x") == "http://example.com/x"

    def test_keeps_non_default_port(self) -> None:
        assert normalize("http://example.com:8080/x") == "http://example.com:8080/x"

    def test_empty_path_becomes_slash(self) -> None:
        assert normalize("https://example.com") == "https://example.com/"

    def test_strips_tracking_params(self) -> None:
        result = normalize("https://example.com/p?id=1&utm_source=ad&gclid=xyz")
        assert result == "https://example.com/p?id=1"

    def test_sorts_query_keys(self) -> None:
        result = normalize("https://example.com/p?z=1&a=2&m=3")
        assert result == "https://example.com/p?a=2&m=3&z=1"

    def test_preserves_userinfo(self) -> None:
        assert normalize("https://user:pass@example.com/x") == "https://user:pass@example.com/x"

    def test_idempotent(self) -> None:
        once = normalize("HTTPS://Example.COM/a?utm_source=x&id=1#frag")
        twice = normalize(once)
        assert once == twice


class TestTemplatize:
    def test_empty_input(self) -> None:
        assert templatize([]) == {}

    def test_low_cardinality_keeps_segment(self) -> None:
        """Only 2 distinct product slugs → not enough to collapse."""
        urls = [
            "https://example.com/about",
            "https://example.com/contact",
        ]
        result = templatize(urls)
        assert result["https://example.com/about"] == "/about"
        assert result["https://example.com/contact"] == "/contact"

    def test_high_cardinality_collapses_to_id(self) -> None:
        urls = [f"https://example.com/product/{i}" for i in range(10)]
        result = templatize(urls)
        for u in urls:
            assert result[u] == "/product/{id}"

    def test_uuid_segments_collapse(self) -> None:
        uuids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440001",
            "550e8400-e29b-41d4-a716-446655440002",
            "550e8400-e29b-41d4-a716-446655440003",
            "550e8400-e29b-41d4-a716-446655440004",
        ]
        urls = [f"https://example.com/u/{u}" for u in uuids]
        result = templatize(urls)
        assert all(v == "/u/{id}" for v in result.values())

    def test_slug_segments_collapse(self) -> None:
        urls = [f"https://example.com/blog/{slug}" for slug in [
            "hello-world", "foo-bar-baz", "great-post-here", "another-one", "five-words-now"
        ]]
        result = templatize(urls)
        assert all(v == "/blog/{id}" for v in result.values())

    def test_version_segments_collapse(self) -> None:
        # Dotted version dirs (docs.python.org/3.10, /3.11, …) should group.
        versions = ["3.7", "3.8", "3.9", "3.10", "3.11", "3.12"]
        urls = [f"https://docs.example.com/{v}/library/index.html" for v in versions]
        result = templatize(urls)
        assert all(v == "/{id}/library/index.html" for v in result.values())

    def test_version_with_v_prefix_and_patch(self) -> None:
        urls = [f"https://example.com/docs/{v}" for v in ["v1.0", "v1.1", "v2.0", "v2.1.3", "v3.0"]]
        result = templatize(urls)
        assert all(v == "/docs/{id}" for v in result.values())

    def test_dotted_filename_not_treated_as_version(self) -> None:
        # `index.html` has a dot but is not all-numeric → must stay literal.
        urls = [
            "https://example.com/a/index.html",
            "https://example.com/b/index.html",
        ]
        result = templatize(urls)
        assert result["https://example.com/a/index.html"] == "/a/index.html"

    def test_root_path(self) -> None:
        result = templatize(["https://example.com/"])
        assert result["https://example.com/"] == "/"

    def test_identity_query_kept_as_star(self) -> None:
        urls = [f"https://example.com/search?q={q}" for q in ["a", "b", "c"]]
        result = templatize(urls)
        for u in urls:
            assert result[u] == "/search?q=*"

    def test_non_identity_query_dropped(self) -> None:
        """sort, view aren't in IDENTITY_KEYS — should be dropped from template."""
        urls = [
            "https://example.com/list?sort=asc",
            "https://example.com/list?sort=desc",
        ]
        result = templatize(urls)
        assert result["https://example.com/list?sort=asc"] == "/list"

    def test_mixed_paths_do_not_pollute_each_other(self) -> None:
        """`/product/1..5` should collapse but `/about` should remain."""
        product_urls = [f"https://example.com/product/{i}" for i in range(5)]
        other_urls = ["https://example.com/about", "https://example.com/contact"]
        result = templatize(product_urls + other_urls)
        for u in product_urls:
            assert result[u] == "/product/{id}"
        assert result["https://example.com/about"] == "/about"

    def test_respects_min_group_size(self) -> None:
        urls = [f"https://example.com/p/{i}" for i in range(3)]
        result = templatize(urls, TemplateOptions(min_group_size=10))
        # Below threshold → segments kept literal
        assert result["https://example.com/p/0"] == "/p/0"
