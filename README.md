# Daymoss legal site

Static pages for the Daymoss privacy policy, terms, and support URLs.

The six Markdown files contain the reviewed legal text and the effective date 2026-11-04. Publication requires `placeholder: false` on all six files. Do not publish `dist/` from a tree that is still `placeholder: true`.

## Local preview

From this directory:

```bash
python3 build.py --check
python3 -m http.server --directory dist 8080
```

The check builds the preview and requests all six pages on localhost. Open:

- http://127.0.0.1:8080/daymoss/privacy
- http://127.0.0.1:8080/daymoss/terms
- http://127.0.0.1:8080/daymoss/support
- http://127.0.0.1:8080/zh/daymoss/privacy
- http://127.0.0.1:8080/zh/daymoss/terms
- http://127.0.0.1:8080/zh/daymoss/support

## Checking a release without unlocking this tree

```bash
python3 build.py --check
python3 build.py --check-release-copy
```

`--check` requires the preview lock, the do-not-publish marker, and `Disallow: /`. `--check-release-copy` copies the site to a temporary directory, sets `placeholder: false` only there, and runs the release checks. It leaves these six files unchanged. `--release` in this directory still refuses to write a public build while any page is `placeholder: true`.

When publication is actually approved, set all six files to `placeholder: false`, keep the confirmed dates and `developer@yunostudio.cc`, then run `python3 build.py --release`. Deployment steps are in `DEPLOYMENT.md`.
