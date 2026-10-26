# Publication privacy audit

Reviewed on October 25, 2026.

The GitHub repository was already public at review time. Its only published
commit was `3887d22`, containing `LICENSE`. The application source was untracked.
The remote had one branch, no tags, and no releases, workflow runs, pull requests,
or issues returned by the inspected endpoints. No changes were pushed during
this audit.

## Findings and changes

A Logfire credential was embedded in `load_testing/benchmark_clustering.py`.
It was removed and replaced with the `LOGFIRE_TOKEN` environment variable.
Tracing does not send to Logfire when that variable is absent. No copy of the
credential was found in reachable Git history. Its ownership and validity were
not tested; revoke or rotate it if it is active and under your control.

Machine-specific paths were removed from the README and benchmark scripts.
Benchmark output now goes into ignored local storage. Saved notebook outputs
and execution state were cleared, including embedded output images and HTML.
The documentation screenshots and their metadata were inspected; no private
contact details, credentials, or location metadata were identified in them.

Private ChatGPT imports, normalized text, and model results remain under ignored
`.local/` storage. Ignore rules also cover credentials, environments, browser
captures, databases, archive exports, caches, and generated example reports.
Only the two deliberately bundled WildChat reports are excepted from the report
exclusion. Original demo files and notebook outputs are preserved in ignored
`.local/publication-backup/` storage.

## Intentionally public data

The owner explicitly approved keeping the original WildChat samples, including
their conversation text and derived reports. They contain third-party contact
details, correspondence, and source paths; this audit does not describe them as
free of personal information. They are public-dataset examples rather than the
owner's private ChatGPT imports. Their source attribution remains in place.

The 12 bundled WildChat source, label, analysis, UI-data, and report files are
recorded in `public-data-manifest.json`. Publication checks verify those exact
checksums and reject private or unreviewed sources in public UI profiles.
Changing the bundled data requires a new privacy review before updating the
manifest. Existing author attribution and the name in `LICENSE` are retained.

## Verification

Gitleaks 8.30.1 was downloaded from its official release and verified against the
release checksum. Its default rules, plus a repository-specific Logfire rule,
were run against a snapshot of all tracked and non-ignored untracked files and
against all reachable local Git history. Both final scans found no credentials.
The custom Logfire rule was also checked against a generated test credential.
See [Gitleaks usage](https://github.com/gitleaks/gitleaks#usage).

The application tests, privacy regression tests, frontend build, and commit-hook
configuration validation passed. Wheel and source-distribution contents were
inspected for private storage, caches, credentials, and unapproved data files.
The approved WildChat files remain in the public demos and package assets.

## Keeping later changes private

Run `python3 scripts/check_publication.py` before staging an initial import.
It checks tracked files and untracked files eligible for commit. Install the
local hooks with `.venv/bin/pre-commit install`; they run the privacy check and
Gitleaks. The publication privacy workflow also scans files and complete Git
history on pushes and pull requests.

Publish the reviewed Git contents. Uploading the entire workspace directory or
forcing ignored files into Git would include data outside this audit's public
file set.
