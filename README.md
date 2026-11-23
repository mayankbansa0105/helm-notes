# Helm — Daily Revision Notes

A set of short notes for revising Helm every day. Read one file a day and try the commands
in a scratch terminal as you go.

> Helm version used here: **v4** (examples were run with v4.3.2). Everything in these notes
> also works the same way in Helm v3 unless a note says otherwise.

---

## Files

| # | File | Topic |
|---|------|-------|
| 01 | [01-repo-search-show.md](01-repo-search-show.md) | Finding charts: `helm repo`, `helm search`, `helm show` |
| 02 | [02-install-inspect-uninstall.md](02-install-inspect-uninstall.md) | Releases: `helm install`, `list`, `status`, `history`, `get`, `uninstall`, and cleaning up orphaned resources |
| 03 | [03-custom-values.md](03-custom-values.md) | Custom values: `-f` files, the `--set` family, precedence, types, and values on upgrade |

More chapters will be added here as they are written.

---

## One-page cheat sheet

```
  where charts live                     find a chart                       look inside before installing
┌──────────────────────┐          ┌───────────────────────┐          ┌──────────────────────────────┐
│ HTTP chart repo      │ repo add │ helm search repo <kw> │          │ helm show chart  <chart>     │
│  (index.yaml)        │─────────►│  (your added repos)   │─────────►│ helm show values <chart>     │
│                      │ repo     │                       │  pick    │ helm show readme <chart>     │
│                      │ update   │ helm search hub <kw>  │  one     │ helm show crds   <chart>     │
│ OCI registry         │          │  (Artifact Hub)       │          │ helm show all    <chart>     │
│  oci://...           │──────────┼───── no search ───────┼─────────►│ (works with oci:// directly) │
└──────────────────────┘          └───────────────────────┘          └──────────────────────────────┘
```

**Rules of thumb**

1. `helm repo add` only saves a name → URL pair. Run `helm repo update` to refresh the local copy of each repo's index.
2. `helm search repo` searches your **local cached indexes**, so stale cache = stale results. `helm search hub` searches Artifact Hub online.
3. Charts are referred to as `<repo-name>/<chart-name>`, e.g. `ingress-nginx/ingress-nginx`.
4. OCI registries are **not** added with `helm repo add` and can't be searched. Use the full `oci://` reference.
5. Always `helm show values` before installing. It's the list of everything you're allowed to configure.
6. **Chart version** (`version`) is the package version. **App version** (`appVersion`) is the software inside it. `--version` flags mean the chart version.
7. `helm show ...` reads a **chart**. `helm get ...` reads an installed **release**. `get values` = your overrides; add `--all` for the merged result.
8. Releases are **namespaced** and stored as Secrets (`sh.helm.release.v1.<name>.v<rev>`) in that namespace. Always pass `-n`.
9. `helm uninstall` removes only what's in the release manifest. **PVCs from StatefulSets, `resource-policy: keep` objects, hooks and CRDs stay behind.**
10. Values precedence: chart defaults < `-f` files (last wins) < `--set` (last wins). **Same key in `-f` and `--set` is not an error: `--set` wins.**
11. Maps merge, lists are replaced, `null` deletes a key. Quote `--set` args in zsh and version-like values in YAML.
12. `helm upgrade` with any `--set`/`-f` **drops earlier overrides**. Pass all values every time, or use `--reset-then-reuse-values`.
