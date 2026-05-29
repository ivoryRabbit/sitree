# Page Classification Prompt

You are classifying the role of a web page within a website's structure.

Given:
- URL template (with `{id}`/`*` placeholders)
- 1–3 sample URLs from that template
- Cleaned text snippet (title + first ~500 chars of body)

Choose **exactly one** label from this enum:

- `Home`     — the site root / landing page
- `Search`   — search form or search results listing
- `PLP`      — product/category list page (multiple item cards)
- `PDP`      — product detail page (single item)
- `Article`  — long-form text content (blog post, news, doc page)
- `Auth`     — login / signup / account / settings
- `Other`    — anything else

Respond with only the label string. No explanation.
