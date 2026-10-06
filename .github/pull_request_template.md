## What does this PR do?

<!-- One paragraph: the change and why. -->

## Related issue

<!-- e.g. Closes #12 -->

## Checklist

- [ ] `ruff check contentforge tests scripts` passes
- [ ] `pytest -m "not rpa and not network and not integration"` passes
- [ ] New logic has tests under `tests/` (network/RPA tests marked with
      `@pytest.mark.network` / `@pytest.mark.rpa`)
- [ ] User-facing changes update `README.md` and/or `docs/`
- [ ] No CAPTCHA / anti-detection / scraping-circumvention code (see
      `CONTRIBUTING.md`)

## Test plan

<!-- How did you verify it works? Paste key output. -->
