# Reproducible GitHub wiki

The [project wiki](https://github.com/ha-homelab/ha-echomuse/wiki) is a navigation
and reading copy of reviewed repository documentation. The repository remains
the source of truth: open documentation PRs there instead of editing generated
wiki pages independently. English runbooks and all five localized project
READMEs are exported together.

## Ownership and first publication

The wiki feature is enabled by the EchoMuse repository entry in
[the Terraform infrastructure repository](https://github.com/4alvit/terraform-github-ha-homelab).
It does not change the visibility or access policy of any other repository.
GitHub requires creating the first page in its web interface before the separate
wiki Git repository can be cloned; see the
[GitHub wiki instructions](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages).
Keep wiki editing limited to repository collaborators.

## Build a publication snapshot

From a reviewed commit in a normal source checkout:

```sh
python3 scripts/check_docs.py
python3 scripts/check_public.py
python3 scripts/render_wiki.py --ref "$(git rev-parse HEAD)"
```

`--ref` accepts a full commit SHA. The exporter reads files from that Git commit,
not from uncommitted files, and writes only to ignored `build/wiki/`. It does not
connect to GitHub, use credentials, or publish. Every page records its source
path and revision. SVG images and non-page links use that immutable revision;
links between exported pages remain inside the wiki. Inline Markdown links are
supported; use that form when adding navigation to exported sources.

The output contains `Home`, four localized `Home-*` pages, English runbooks,
contribution/security information, and a sidebar. A private local manifest records
which files were generated. No recordings, configurations, firmware images,
private evidence or device inventory are exported.

## Publish and verify

1. Clone `https://github.com/ha-homelab/ha-echomuse.wiki.git` into a separate local
   directory outside the public source checkout.
2. Confirm the wiki remote, current branch and clean status. Preserve a local
   copy of the previous commit so the publication can be reverted.
3. Preview synchronization, then apply the reviewed local changes:

   ```sh
   python3 scripts/sync_wiki.py --wiki-checkout /path/to/ha-echomuse.wiki
   python3 scripts/sync_wiki.py --wiki-checkout /path/to/ha-echomuse.wiki --apply
   ```

   The destination must be a clean checkout of the exact project wiki remote.
   The publisher tracks generated page hashes in `.source-manifest.json` inside
   the wiki. It removes obsolete generated pages while preserving unrelated
   manual pages. It refuses to overwrite a colliding manual page or a generated
   page that somebody edited independently. Reconcile such content before retrying.
   For the initial Home page, use exactly the exported `Home.md` contents when
   creating it in GitHub so that the first synchronization can adopt it safely.
4. Inspect the complete diff, especially external links and the source revision.
   Commit the generated pages and `.source-manifest.json` with the source SHA in
   the message, then push the current wiki branch. Neither script commits or pushes.
5. Open Home, each localized Home page, the architecture page and at least one
   operational runbook. Confirm images, internal links, headings and source links.

The regular [CI gate](ci.md) checks source documentation before merge. Publishing
the wiki is a separate operation; a green source check does not prove that the
wiki was pushed or visually inspected. To roll back, revert the publication
commit in the wiki checkout. Do not rewrite shared wiki history.
