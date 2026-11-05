# Daymoss legal site

Static pages for the Daymoss privacy policy, terms, and support URLs.

The six Markdown files are the only legal text. Each page records an original effective date of 2026-11-04 and a last-updated date of 2026-11-05. Publication requires `placeholder: false` on all six files. Do not publish `dist/` until that text is confirmed, and do not publish a tree that is still `placeholder: true`.

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

The same six Markdown files also generate the in-app pages:

- http://127.0.0.1:8080/daymoss/embed/privacy
- http://127.0.0.1:8080/daymoss/embed/terms
- http://127.0.0.1:8080/daymoss/embed/support
- http://127.0.0.1:8080/zh/daymoss/embed/privacy
- http://127.0.0.1:8080/zh/daymoss/embed/terms
- http://127.0.0.1:8080/zh/daymoss/embed/support

## Checking a release without unlocking this tree

```bash
python3 build.py --check
python3 build.py --check-release-copy
```

`--check` requires the preview lock, the do-not-publish marker, and `Disallow: /`. `--check-release-copy` copies the site to a temporary directory, sets `placeholder: false` only there, and runs the release checks. It leaves these six files unchanged. `--release` in this directory still refuses to write a public build while any page is `placeholder: true`.

When publication is actually approved, set all six files to `placeholder: false`, keep the confirmed dates and `developer@yunostudio.cc`, then run `python3 build.py --release`. Deployment steps are in `DEPLOYMENT.md`.
