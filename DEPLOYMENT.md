# Deployment plan

Do not change DNS, mail records, or the custom domain for a content update. `python3 build.py --release` refuses a tree that is still `placeholder: true`. The original effective date is November 4, 2026 (`2026 年 11 月 4 日`). The last-updated date is November 5, 2026 (`2026 年 11 月 5 日`). The page brand is Daymoss.

The site is already published. The next content update replaces the generated HTML only, after the merged Markdown is confirmed. Do not upload before that confirmation.

## Recommendation

Host the finished static files on GitHub Pages. Leave the domain’s name servers at Alibaba Cloud (`dns1.hichina.com` and `dns2.hichina.com`).

This keeps the existing enterprise mailbox on Aliyun and serves `https://yunostudio.cc/daymoss/...` from the apex domain. GitHub Pages is free, issues a Let’s Encrypt certificate, and needs no account on the website itself.

Cloudflare Pages is not the first choice while mail stays on this domain. The apex already has MX records. An apex CNAME, which Cloudflare Pages would need under external DNS, cannot sit beside those MX records. Moving the name servers to Cloudflare would also move mail DNS, which this plan avoids.

Alibaba Cloud OSS is not recommended for the first release. A mainland China origin can bring an ICP filing requirement, and the first market is outside mainland China.

## Records that must stay as they are

Checked on 4 November 2026. Do not edit or delete them:

| Host | Type | Current value |
| --- | --- | --- |
| `@` | NS | `dns1.hichina.com`, `dns2.hichina.com` |
| `@` | MX | `5 mx1.qiye.aliyun.com`, `10 mx2.qiye.aliyun.com`, `15 mx3.qiye.aliyun.com` |
| `@` | TXT | `v=spf1 include:spf.qiye.aliyun.com -all` |
| `default._domainkey` | TXT | existing DKIM key |

The apex already serves the site. Do not add, replace, or delete A, AAAA, NS, MX, SPF, or DKIM records for a content update. Do not add a CAA record unless it allows Let’s Encrypt (`letsencrypt.org`). A restrictive CAA record would stop GitHub Pages from renewing the certificate.

Do not put a CNAME on `@`. Do not add a wildcard such as `*`.

## Records already used for the first publication

The records below are the original GitHub Pages addresses. They are already in place. Do not create them again for the November 5 text update.

| Host | Type | Value |
| --- | --- | --- |
| `@` | A | `185.199.108.153` |
| `@` | A | `185.199.109.153` |
| `@` | A | `185.199.110.153` |
| `@` | A | `185.199.111.153` |
| `@` | AAAA | `2606:50c0:8000::153` |
| `@` | AAAA | `2606:50c0:8001::153` |
| `@` | AAAA | `2606:50c0:8002::153` |
| `@` | AAAA | `2606:50c0:8003::153` |

Optional, and safe for mail: a `www` CNAME to `YOUR_GITHUB_USERNAME.github.io`. If the Pages custom domain is the apex, GitHub redirects `www` to `yunostudio.cc`. The iOS app uses the apex URLs, so `www` is not required.

After the records propagate, enable Enforce HTTPS in the Pages settings. Certificate issuance can take up to 24 hours. The site is not ready for the app until all six of these return the reviewed pages over HTTPS:

- `https://yunostudio.cc/daymoss/privacy`
- `https://yunostudio.cc/daymoss/terms`
- `https://yunostudio.cc/daymoss/support`
- `https://yunostudio.cc/zh/daymoss/privacy`
- `https://yunostudio.cc/zh/daymoss/terms`
- `https://yunostudio.cc/zh/daymoss/support`

The in-app presentation is published beside those paths. It uses the same Markdown and does not replace the six pages above:

- `https://yunostudio.cc/daymoss/embed/privacy`
- `https://yunostudio.cc/daymoss/embed/terms`
- `https://yunostudio.cc/daymoss/embed/support`
- `https://yunostudio.cc/zh/daymoss/embed/privacy`
- `https://yunostudio.cc/zh/daymoss/embed/terms`
- `https://yunostudio.cc/zh/daymoss/embed/support`

Publish the `dist/` directory produced by `--release` only. Do not publish a preview build. Preview builds include `PLACEHOLDER_DO_NOT_PUBLISH.txt` and a `robots.txt` that disallows the whole site; those markers are not a substitute for keeping the files offline.

## Repository

Use a new public repository on the personal GitHub account. GitHub Free publishes GitHub Pages from a public repository. A private repository needs a paid plan before Pages can publish it, and the published site would still be public.

This repository contains only:

```text
content/en/privacy.md
content/en/terms.md
content/en/support.md
content/zh/privacy.md
content/zh/terms.md
content/zh/support.md
assets/site.css
assets/favicon.svg
build.py
check_site.py
README.md
DEPLOYMENT.md
.github/workflows/pages.yml
```

`.github/workflows/pages.yml` runs only from the Actions tab. Its build command is `python3 build.py --release`, so a tree that is still `placeholder: true` cannot deploy.

Do not add application source, signing files, archives, backups, or private review notes.

`python3 build.py --check` checks the locked preview. `python3 build.py --check-release-copy` builds a temporary copy with the lock removed and deletes that copy. It does not change the six source files. Run `python3 build.py --release` in this repository only after those files are intentionally unlocked.

The privacy policy states that GitHub Pages logs and stores visitors’ IP addresses, and that support email is processed through Alibaba Mail. It does not claim that the website has no logs, and it does not name a mailbox storage location.

The custom domain and HTTPS are already in place. Do not change them for this content update. After the merged text is confirmed, publish a new `dist/` from `python3 build.py --release` through the existing GitHub Actions workflow. CSS and the icon are local files, with no site-added analytics script.
