# 04 — helm upgrade and helm rollback

## The big picture

Every `install`, `upgrade` and `rollback` creates a new **revision**. Rollback doesn't rewind history.
It adds a new revision that copies an older one:

```
revision   action                       deployed chart / values
   1       install                      podinfo 6.15.0
   2       upgrade                      podinfo 6.16.0
   3       upgrade                      podinfo 6.17.0
   4       rollback (to 2)              podinfo 6.16.0     ← copy of revision 2, new number
```

Two things to keep in mind throughout this chapter:

1. **`helm upgrade` can fail half-way.** Some objects may be updated and others not.
2. **Without `--wait`, Helm reports success as soon as the manifests are *applied*.** It does not wait for pods to become healthy.

> All examples were run with Helm v4.3.2 on a GKE test cluster, using the
> [`examples/upgrade-demo`](https://github.com/mayankbansa0105/helm-notes/tree/main/examples/upgrade-demo) chart,
> which has a switch for each failure mode, and podinfo for the version examples.

---

## helm upgrade: the happy path

```
helm upgrade [RELEASE] [CHART] [flags]
```

### Change the chart version
```bash
helm upgrade web podinfo/podinfo -n helm-lab --version 6.16.0 --wait
# Release "web" has been upgraded. Happy Helming!
# NAME: web
# REVISION: 2
# DESCRIPTION: Upgrade complete
```

### Change only values
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set message="hello v2" --wait
# STATUS: deployed
# REVISION: 5
```

Remember from chapter 03: `--set` on upgrade **replaces** earlier overrides unless you pass them again, or use
`--reuse-values` / `--reset-then-reuse-values`.

### Install if missing, upgrade if present
```bash
helm upgrade --install web podinfo/podinfo -n helm-lab --create-namespace --version 6.17.0 --wait
# Release "web" does not exist. Installing it now.     ← first run
# Release "web" has been upgraded. Happy Helming!      ← later runs
```

This is the command to use in CI/CD, because you don't need to know whether the release exists yet.
`-i` is the short form.

### Record why you changed something
```bash
helm upgrade --install web podinfo/podinfo -n helm-lab --version 6.17.0 --description "bump to 6.17.0, JIRA-123"
helm history web -n helm-lab | tail -1
# 3   Mon Nov 23 12:27:33 2026   deployed   podinfo-6.17.0   6.17.0   bump to 6.17.0, JIRA-123
```

---

## helm rollback: the happy path

```
helm rollback <RELEASE> [REVISION] [flags]
```

With the history `1 (6.15.0) → 2 (6.16.0) → 3 (6.17.0)`:

```bash
helm rollback web -n helm-lab --wait          # no revision = the previous one (2)
# Rollback was a success! Happy Helming!
helm history web -n helm-lab | tail -1
# 4   ...   deployed   podinfo-6.16.0   6.16.0   Rollback to 2

helm rollback web 1 -n helm-lab --wait        # a specific revision
helm history web -n helm-lab | tail -1
# 5   ...   deployed   podinfo-6.15.0   6.15.0   Rollback to 1

helm rollback web 0 -n helm-lab --wait        # 0 is the same as "no revision"
helm history web -n helm-lab | tail -1
# 6   ...   deployed   podinfo-6.16.0   6.16.0   Rollback to 4
```

> **Watch out:** `helm rollback` with no revision goes to the **previous revision**, not to the last good one.
> Run it twice and you flip back and forth between the last two revisions. To go back to a known-good state,
> name the revision: `helm rollback web 2`.

### Preview a rollback
```bash
helm rollback web 3 -n helm-lab --dry-run=client
helm history web -n helm-lab | tail -1     # unchanged: nothing was persisted
```

---

## The bad paths, one at a time

These use `upgrade-demo`. Turn a failure on with `--set`, then see what Helm does.

### Bad 1: a broken image, without --wait (the silent failure)
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set image.tag=does-not-exist
# STATUS: deployed
# DESCRIPTION: Upgrade complete

kubectl get pods -n helm-lab -l app.kubernetes.io/instance=demo
# demo-app-5c8f5bd88b-b4p78   1/1   Running
# demo-app-5c8f5bd88b-ccbfj   1/1   Running
# demo-app-6d786b8cb-6j58t    0/1   ImagePullBackOff   ← new pod, broken
```

**Helm says "deployed", but the new version is broken.** The manifests were applied, nothing waited for pods.
Without `--wait`, the only way to find out is to check yourself.

### Bad 2: the same failure, with --wait
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set image.tag=does-not-exist --wait --timeout 60s
# Error: UPGRADE FAILED: resource Deployment/helm-lab/demo-app not ready. status: InProgress, message: Updated: 1/2
# context deadline exceeded

helm list -n helm-lab --failed
# demo   helm-lab   4   failed   upgrade-demo-1.0.0   6.16.0
```

Now the release is `failed`, but **nothing was rolled back**. The new pod still fails, and the old pods still serve traffic.
The release is in an in-between state until you act. Two ways out:

```bash
# (a) roll back by hand
helm rollback demo -n helm-lab --wait

# (b) fix forward with a corrected upgrade
helm upgrade demo ./upgrade-demo -n helm-lab --set message="hello v2" --wait
```

### Bad 3: a bad revision number
```bash
helm rollback web 42 -n helm-lab
# Error: release has no 42 version
```

### Bad 4: a pre-upgrade hook fails
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set hookFail=true --set message="v3" --timeout 90s
# Error: UPGRADE FAILED: pre-upgrade hooks failed: resource Job/helm-lab/demo-pre-upgrade not ready. status: Failed
```

The hook runs **before** the Deployment is touched, so the app itself is unchanged:
```bash
kubectl get deploy demo-app -n helm-lab -o jsonpath='{.spec.template.spec.containers[0].env[0].value}'
# hello v2                        ← still the old value
```
The release is `failed`. Note that `demo-pre-upgrade` (a failed Job) is **still there** afterwards: the hook's
delete policy only removes it on success.

### Bad 5: a migration Job fails, and you didn't pass --wait-for-jobs (the dangerous one)
`migrationFail=true` makes a normal (non-hook) Job exit 1:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set migrationFail=true --wait --timeout 90s
# STATUS: deployed            ← Helm says success

kubectl get jobs -n helm-lab
# demo-migrate-r13   Failed   0/1
```

`--wait` only waits for Deployments, Pods and similar resources. **It does not wait for Jobs unless you ask.**
Your migration failed, and the release still says `deployed`.

Add `--wait-for-jobs`:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set migrationFail=true --wait --wait-for-jobs --timeout 90s
# Error: UPGRADE FAILED: resource Job/helm-lab/demo-migrate-r14 not ready. status: Failed
helm list -n helm-lab --failed
```

### Bad 6: an immutable field changes (the selector)
A Deployment's `spec.selector` can't be changed after creation. Here, `selectorTrack` changes it:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set selectorTrack=canary --wait
# Error: UPGRADE FAILED: server-side apply failed for object helm-lab/demo-app ...
#   spec.selector: Invalid value: ...: field is immutable
```

**`--dry-run` doesn't catch this.** Both of these print no error, and only the real apply fails:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set selectorTrack=canary --dry-run=server
helm upgrade demo ./upgrade-demo -n helm-lab --set selectorTrack=canary --dry-run=client
```

What fixes it:

| Attempt | Result |
|---------|--------|
| `--force-replace` (default apply method) | `invalid operation: cannot use server-side apply and force replace together` |
| `--force-replace --server-side=false` | still `field is immutable` ← replacing does not bypass the rule |
| `kubectl delete deploy demo-app`, then upgrade | works, **but the app is down during the delete** |

For an immutable change in production, plan a new Deployment name (e.g. `demo-app-v2`), run both for a while,
switch the Service over, then remove the old one. Don't delete a live Deployment just to make Helm happy.

### Bad 7: someone changed the object outside Helm (drift)
Helm uses server-side apply. If another tool owns a field, the upgrade stops:

```bash
kubectl scale deploy demo-app -n helm-lab --replicas=4        # manual change
helm upgrade demo ./upgrade-demo -n helm-lab --wait
# Error: conflict occurred while applying object ...: Apply failed with 1 conflict:
#   conflict with "kubectl" with subresource "scale" using apps/v1: .spec.replicas
```

Another manager (here, `kubectl apply --server-side --field-manager=hotfix-team`) causes the same:
```
conflict with "hotfix-team": .spec.replicas
```

Fix it on purpose, with `--force-conflicts`:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --force-conflicts --wait
# STATUS: deployed
kubectl get deploy demo-app -n helm-lab -o jsonpath='{.spec.replicas}'
# 2                             ← back to the value in Git
```

`--force-conflicts` **takes ownership of the fields** the other manager had, and overwrites them. That's usually what you
want when Git is the source of truth. Still, find out *why* someone made the change first.

---

## Auto rollback: the safety net

These flags make Helm fix a failed upgrade itself.

### --rollback-on-failure (the one you want in production)

```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set image.tag=does-not-exist --rollback-on-failure --timeout 60s
# Error: UPGRADE FAILED: release demo failed, and has been rolled back due to rollback-on-failure being set:
#   resource Deployment/helm-lab/demo-app not ready. status: InProgress, message: Updated: 1/2

helm history demo -n helm-lab | tail -2
# 6   ...   failed     Upgrade "demo" failed: ...
# 7   ...   deployed   Rollback to 5

kubectl get deploy demo-app -n helm-lab -o jsonpath='{.spec.template.spec.containers[0].image}'
# ghcr.io/stefanprodan/podinfo:6.16.0      ← back to the working image
```

It also works for a failing pre-upgrade hook, on a clean release:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set hookFail=true --set message="v3" --rollback-on-failure --timeout 90s
# Error: UPGRADE FAILED: release demo failed, and has been rolled back due to rollback-on-failure being set: pre-upgrade hooks failed: ...
helm history demo -n helm-lab | tail -1
# 3   ...   deployed   Rollback to 1
```

What it does:
- Turns on `--wait` for you, with the `watcher` strategy, so you don't need to pass `--wait`.
- Rolls back to the **last successful** revision, not just the previous one.
- Reports the failure as an error, so your CI job fails.

> In Helm v3 this flag was called `--atomic`. It still works in v4 under the new name.

**Limit:** the rollback is only as good as the state it returns to. If the rollback itself fails (see the next section),
the release is left as `failed`.

### --cleanup-on-fail: remove what a failed upgrade created

An upgrade that **adds** a new object leaves it behind when it fails, unless you ask Helm to delete it.
With `extraConfig=true` (adds a ConfigMap) plus a broken image:

```bash
# Without --cleanup-on-fail
helm upgrade demo ./upgrade-demo -n helm-lab --set image.tag=does-not-exist --set extraConfig=true --wait --timeout 45s
kubectl get cm demo-extra -n helm-lab
# demo-extra   1   49s                  ← new object, left behind after the failed upgrade

# With --cleanup-on-fail
helm upgrade demo ./upgrade-demo -n helm-lab --set image.tag=does-not-exist --set extraConfig=true --wait --timeout 45s --cleanup-on-fail
kubectl get cm demo-extra -n helm-lab
# Error from server (NotFound): configmaps "demo-extra" not found    ← removed
```

Note what it **does not** do: the Deployment still has the broken image afterwards. `--cleanup-on-fail` deletes
**new** objects only. It doesn't revert **changed** ones. For that you need `--rollback-on-failure`.

### --wait and --wait-for-jobs: what "success" means

| Flags | Waits for | Bad migration Job |
|-------|-----------|-------------------|
| (none) | hooks only (the default `hookOnly`) | release says `deployed` |
| `--wait` | Deployments, Pods, StatefulSets, PVCs... | release says `deployed` |
| `--wait --wait-for-jobs` | all of the above, plus Jobs | release says `failed` ✅ |

Production rule: **always pass `--wait --wait-for-jobs`** (or `--rollback-on-failure`, which sets `--wait`
and should be used with `--wait-for-jobs` too).

---

## Rollbacks can fail too

A rollback applies an *old* set of manifests, so it's subject to the same rules as an upgrade. We saw it fail
in a messy cluster state, where the live Deployment had the `canary` selector and the old revision had `stable`:

```bash
helm rollback demo -n helm-lab --wait
# Error: server-side apply failed ...: spec.selector: ... field is immutable

helm list -n helm-lab -f '^demo$'
# demo   failed   ← still failed; the rollback didn't stick
```

The same happens with `--rollback-on-failure` when the rollback fails:
```
Error: UPGRADE FAILED: an error occurred while rolling back the release. original upgrade error: ...
```

When a rollback fails:
1. `helm history <release>` tells you which revision you were trying to go back to.
2. `kubectl describe deploy <name>` shows the live state and any field managers.
3. Fix the field or the manifest, then `helm upgrade` forward to a good state. Don't keep retrying the same rollback.

---

## Limit the history Helm keeps

Every revision is a Secret. Helm keeps 10 by default (`--history-max`). With `--history-max 3`, older ones are
deleted on each release:
```bash
helm upgrade demo ./upgrade-demo -n helm-lab --set message="hm" --history-max 3 --wait
helm history demo -n helm-lab --max 50
# REVISION  ...   (only the newest 3 remain)
```

Use `--history-max 0` for no limit, but be careful: a large history slows `helm list` and makes the Secrets pile up.
Rolling back is only possible to a revision that still exists in the history.

---

## Flag reference

### helm upgrade

| Flag | What it's for | Production? |
|------|---------------|-------------|
| `-i, --install` | Install if the release doesn't exist | ✅ use it in CI |
| `--version X` | Pin the chart version | ✅ always pin |
| `-f`, `--set`, `--set-string` | Values (chapter 03) | ✅ `--set-string` for image tags |
| `--reuse-values` / `--reset-then-reuse-values` | Keep old overrides | ⚠️ read chapter 03 first |
| `--wait` | Wait for resources to be ready | ✅ |
| `--wait-for-jobs` | Also wait for Jobs (migrations) | ✅ with `--wait` |
| `--timeout 5m` | How long to wait for each operation | ✅ set it explicitly |
| `--rollback-on-failure` | Roll back automatically on failure (sets `--wait`) | ✅ the main safety net |
| `--cleanup-on-fail` | Delete objects the failed upgrade created | ✅ |
| `--history-max N` | Limit saved revisions (default 10) | ✅ |
| `--description "..."` | Note the reason, shown in `helm history` | ✅ put the ticket number here |
| `--force-conflicts` | Take over fields another manager owns | ⚠️ only on purpose |
| `--force-replace` | Replace objects instead of patching | ⚠️ add `--server-side=false`; it doesn't fix immutable fields |
| `--server-side true\|false\|auto` | Apply method | Leave `auto` unless you know why |
| `--dry-run=client\|server` | Render, or validate on the server | ✅ preview, but it misses immutable-field errors |
| `--no-hooks` | Skip pre/post hooks | ❌ only in a recovery |
| `-l key=value` | Labels on the release (not the resources) | optional |
| `--skip-schema-validation` | Skip `values.schema.json` | ❌ |
| `--take-ownership` | Adopt resources that already exist without Helm labels | ⚠️ one-time migrations only |

### helm rollback

| Flag | What it's for |
|------|---------------|
| `[REVISION]` | Which revision to go back to. Omit or `0` = the previous one |
| `--wait`, `--timeout` | Wait for the rollback to finish, and how long |
| `--wait-for-jobs` | Also wait for Jobs |
| `--dry-run=client\|server` | Preview; nothing is persisted |
| `--cleanup-on-fail` | Delete objects created by the failed rollback |
| `--force-conflicts`, `--force-replace`, `--server-side` | Same as upgrade |
| `--no-hooks` | Skip hooks during rollback |
| `--description "..."` | Note the reason, e.g. `"rollback: INC-482 error rate"` |
| `--history-max N` | Same as upgrade |

---

## The scenario table

| Scenario | Flags used | Helm's result | Outcome |
|----------|-----------|---------------|---------|
| Good upgrade | `--wait` | `deployed` | ✅ |
| Bad image, no wait | none | `deployed` | ❌ silent failure |
| Bad image, with wait | `--wait` | `failed`, not rolled back | ⚠️ fix by hand |
| Bad image, auto rollback | `--rollback-on-failure` | rolled back, `deployed` at the old revision | ✅ |
| Pre-upgrade hook fails | `--rollback-on-failure` | rolled back | ✅ |
| Migration Job fails | `--wait` only | `deployed` | ❌ silent failure |
| Migration Job fails | `--wait --wait-for-jobs` | `failed` | ✅ detected |
| New object left by a failed upgrade | none | object remains | ⚠️ |
| New object left by a failed upgrade | `--cleanup-on-fail` | object removed | ✅ |
| Immutable field changed | any | error on real apply; `--dry-run` shows nothing | ❌ needs a new Deployment name |
| Someone changed a field | none | conflict, upgrade stops | ✅ safe default |
| Someone changed a field | `--force-conflicts` | overwritten | ⚠️ only on purpose |
| Rollback itself fails | any | release left `failed` | ❌ fix forward |

---

## A production-safe upgrade

```bash
# 0. Check what would change (client render + server validation)
helm lint ./chart
helm upgrade --install web ./chart -n prod -f values-prod.yaml --set-string image.tag=$TAG --version 1.4.2 \
  --dry-run=server

# 1. The release: pinned, explained, auto-rolled-back, migrations checked
helm upgrade --install web ./chart -n prod \
  -f values-prod.yaml --set-string image.tag=$TAG --version 1.4.2 \
  --rollback-on-failure --wait-for-jobs --timeout 5m \
  --cleanup-on-fail --history-max 10 \
  --description "release $TAG (INC-482)"

# 2. Confirm the outcome, don't just trust the exit code
helm status web -n prod
helm history web -n prod --max 3
kubectl rollout status deploy/web -n prod

# 3. If it went wrong AFTER the upgrade succeeded (e.g. error rate went up), roll back to the last good revision
helm rollback web <good-revision> -n prod --wait --wait-for-jobs \
  --description "rollback: error rate after $TAG"
```

Why each flag:
- **`--version`**: the same chart is deployed every time, not "whatever is newest today."
- **`--set-string`**: keeps `"1.4.2"`-style tags from being turned into numbers.
- **`--rollback-on-failure`**: a failed upgrade goes back to the last good revision, and CI sees a failure.
- **`--wait-for-jobs`**: a failed migration counts as a failed release.
- **`--cleanup-on-fail`**: no half-created objects left over.
- **`--history-max`**: the history stays small enough for `helm list` to stay fast.
- **`--description`**: `helm history` explains each change later.

> **Limits of this setup:** `--rollback-on-failure` only covers failures *during* the upgrade. A bug that shows up
> after Helm reports success (for example, a slow memory leak) needs step 3, and that's a human decision.
> Also, the flags above are the ones I've tested together; I haven't run this exact combination on a live release.

---

## Gotchas

- **No `--wait` = no readiness check.** Helm reports `deployed` once objects are applied (plus the hook check). A broken Deployment still shows `deployed`.
- **`--wait` ignores Jobs** unless you add `--wait-for-jobs`. Migrations need it.
- **`rollback` with no revision flips between the last two.** Name the revision you want.
- **A failed upgrade leaves the release `failed`** unless `--rollback-on-failure` is set. The workloads are a mix of old and new.
- **`--dry-run` doesn't catch immutable-field errors.** Only the real apply does.
- **`--force-replace` doesn't bypass immutable fields**, and in v4 it needs `--server-side=false`.
- **`--force-conflicts` overwrites someone else's change.** Find out why they made it first.
- **Rollbacks can fail** with the same errors as upgrades. A failed rollback leaves the release `failed`.
- **`--cleanup-on-fail` doesn't revert changed objects.** Only `--rollback-on-failure` does that.
- **Pre-upgrade hook Jobs that fail stay behind** until you delete them.
- **Old revisions are deleted** beyond `--history-max`, so you can't roll back to them.

## Remember
> **`upgrade --install --version X --rollback-on-failure --wait-for-jobs --description "..."`** is the production default.
> **`rollback` with no revision goes to the previous one**, so name the good revision.
> **`--wait` and `--wait-for-jobs`** decide whether Helm checks anything. Without them, "deployed" means "applied".
