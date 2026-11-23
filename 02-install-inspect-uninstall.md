# 02 — Install, inspect and uninstall a release

## The big picture

Chapter 01 was about **charts** (packages sitting in a repo). This chapter is about **releases**:
a chart installed into a cluster under a name.

```
 chart (in a repo)                   release (in the cluster)
┌──────────────────────┐ helm install ┌────────────────────────────────────────────┐
│ podinfo/podinfo      │─────────────►│ name: web     namespace: helm-lab          │
│  6.17.0              │              │ revision 1 ─► 2 ─► 3   (each upgrade/rollback)│
└──────────────────────┘              └────────────────────────────────────────────┘
   helm show ...                         helm list / status / history / get ...
   (reads the chart)                     (reads the release)
```

| Command | Reads from | Question it answers |
|---------|-----------|---------------------|
| `helm show values <chart>` | the **chart** | "What *can* I configure?" (defaults) |
| `helm get values <release>` | the **release** | "What *did* we configure?" |
| `helm list` | releases in a namespace | "What's installed here?" |
| `helm status <release>` | one release | "Is it healthy? What did it create?" |
| `helm history <release>` | one release | "What changed, and when?" |
| `helm get ... <release>` | one release revision | "Show me the exact values / manifest / notes / hooks" |

> All examples were run with Helm v4.3.2 on a GKE test cluster, using the
> [podinfo](https://github.com/stefanprodan/podinfo) chart, a tiny demo web app.

Setup used throughout:
```bash
helm repo add podinfo https://stefanprodan.github.io/podinfo
helm repo update
```

---

## helm install

```
helm install [RELEASE_NAME] [CHART] [flags]
```

### Basic install
```bash
helm install web podinfo/podinfo -n helm-lab --create-namespace
# NAME: web
# LAST DEPLOYED: Mon Nov 23 10:11:58 2026
# NAMESPACE: helm-lab
# STATUS: deployed
# REVISION: 1
# DESCRIPTION: Install complete
# NOTES:
# 1. Get the application URL by running these commands:
#   echo "Visit http://127.0.0.1:8080 to use your application"
#   kubectl -n helm-lab port-forward deploy/web-podinfo 8080:9898
```

- `web` is the **release name**. It must be unique within the namespace.
- `-n helm-lab` is the namespace the release (and its resources) go into. Without `-n`, Helm uses your kubeconfig's current namespace.
- `--create-namespace` creates the namespace if it doesn't exist. Without it, a missing namespace is an error.
- `NOTES` is the chart's `templates/NOTES.txt`, rendered with your values.

### Useful install variations

```bash
# A specific chart version (chart version, not app version!)
helm install api podinfo/podinfo -n helm-lab --version 6.16.0

# Let Helm pick a name
helm install podinfo/podinfo -n helm-lab --generate-name
# NAME: podinfo-1795408976

# Wait until Deployments/Pods etc. are actually ready, up to a timeout
helm install api podinfo/podinfo -n helm-lab --wait --timeout 3m

# Override a value quickly (chapter 03 covers values in depth)
helm install api podinfo/podinfo -n helm-lab --set replicaCount=2

# Tag the release itself with labels and a description, for filtering later
helm install tagged podinfo/podinfo -n helm-lab -l team=payments,env=dev --description "first try"

# Install straight from a URL or OCI registry, no `repo add` needed
helm install web podinfo --repo https://stefanprodan.github.io/podinfo -n helm-lab
helm install cache oci://registry-1.docker.io/bitnamicharts/redis -n helm-lab
```

### Preview before you install

```bash
# Render everything locally, don't touch the cluster
helm install web podinfo/podinfo -n helm-lab --dry-run=client

# Render AND validate against the real API server (catches bad apiVersions, quota, admission webhooks)
helm install web podinfo/podinfo -n helm-lab --dry-run=server
# NAME: web
# STATUS: pending-install
# DESCRIPTION: Dry run complete
# ...
```

The dry-run output shows `HOOKS:` and `MANIFEST:`, the full YAML that *would* be applied.

### When an install fails

```bash
helm install broken2 podinfo/podinfo -n helm-lab --set image.tag=does-not-exist --wait --timeout 30s
# Error: INSTALLATION FAILED: resource Deployment/helm-lab/broken2-podinfo not ready. status: InProgress, message: Available: 0/1
# context deadline exceeded

helm list -n helm-lab --failed
# NAME     NAMESPACE  REVISION  STATUS  CHART
# broken2  helm-lab   1         failed  podinfo-6.17.0
```

The failed release **still exists** (with its broken resources). To have Helm clean up on failure:
```bash
helm install broken podinfo/podinfo -n helm-lab --set image.tag=does-not-exist --rollback-on-failure --timeout 40s
# Error: INSTALLATION FAILED: release broken failed, and has been uninstalled due to rollback-on-failure being set: ...
```

> `--rollback-on-failure` is the Helm v4 name for v3's `--atomic`. It turns on `--wait` for you.

### Name already taken

```bash
helm install web podinfo/podinfo -n helm-lab
# Error: INSTALLATION FAILED: release name check failed: cannot reuse a name that is still in use
```

Use `helm upgrade` to change an existing release, or `helm upgrade --install` to "install if missing, else upgrade"
(the usual choice in CI pipelines):
```bash
helm upgrade --install web podinfo/podinfo -n helm-lab
```

---

## helm show values vs helm get values

This pair confuses everyone at first.

```bash
# Upgrade `api` with two overrides, so there's something to look at
helm upgrade api podinfo/podinfo -n helm-lab --set replicaCount=2 --set ui.message="hello from helm"
```

**`helm show values`**: the chart's **defaults**. Same output no matter what's installed:
```bash
helm show values podinfo/podinfo | head -4
# # Default values for podinfo.
#
# replicaCount: 1
# logLevel: info
```

**`helm get values`**: only what **you** overrode for this release:
```bash
helm get values api -n helm-lab
# USER-SUPPLIED VALUES:
# replicaCount: 2
# ui:
#   message: hello from helm
```

**`helm get values --all`**: defaults merged with your overrides, i.e. what the templates actually used:
```bash
helm get values api -n helm-lab --all | head -5
# COMPUTED VALUES:
# affinity: {}
# backends: []
# cache: ""
# certificate:
```

Older revisions and other formats:
```bash
helm get values api -n helm-lab --revision 1
# USER-SUPPLIED VALUES:
# null                          ← revision 1 had no overrides

helm get values api -n helm-lab -o json
# {"replicaCount":2,"ui":{"message":"hello from helm"}}
```

Handy trick: copy one release's settings into a file to reuse elsewhere:
```bash
helm get values api -n helm-lab -o yaml > api-values.yaml
```

---

## Finding releases: helm list

```bash
helm list -n helm-lab              # alias: helm ls
# NAME                NAMESPACE  REVISION  UPDATED                    STATUS    CHART           APP VERSION
# api                 helm-lab   2         2026-11-23 10:12:47 +0530  deployed  podinfo-6.17.0  6.17.0
# podinfo-1795408976  helm-lab   1         2026-11-23 10:12:58 +0530  deployed  podinfo-6.17.0  6.17.0
# web                 helm-lab   1         2026-11-23 10:11:58 +0530  deployed  podinfo-6.17.0  6.17.0
```

| Want | Command |
|------|---------|
| Every namespace | `helm list -A` |
| Just names (for scripts) | `helm list -n helm-lab -q` |
| Names matching a regex | `helm list -n helm-lab --filter '^web'` |
| By release label (set with `install -l`) | `helm list -n helm-lab -l team=payments` |
| Only failed ones | `helm list -A --failed` |
| Stuck mid-install/upgrade | `helm list -A --pending` |
| Uninstalled but history kept | `helm list -A --uninstalled` |
| Old revisions | `helm list -n helm-lab --superseded` |
| Newest first | `helm list -n helm-lab -d -r` |
| JSON / YAML | `helm list -n helm-lab -o json` |

By default `helm list` shows **deployed** and **failed** releases.

> Helm v3's `helm list -a` / `--all` is **gone in v4**. Combine the status flags instead
> (`--deployed --failed --pending --uninstalled ...`).

Script example: names of all failed releases, cluster-wide:
```bash
helm list -A --failed -o json | jq -r '.[] | "\(.namespace)/\(.name)"'
```

---

## One release in detail: status, history, get

### helm status
```bash
helm status api -n helm-lab
# NAME: api
# LAST DEPLOYED: Mon Nov 23 10:12:47 2026
# NAMESPACE: helm-lab
# STATUS: deployed
# REVISION: 2
# DESCRIPTION: Upgrade complete
# RESOURCES:
# ==> v1/Service
# NAME          TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)             AGE
# api-podinfo   ClusterIP   34.118.228.54   <none>        9898/TCP,9999/TCP   45s
#
# ==> v1/Deployment
# NAME          READY   UP-TO-DATE   AVAILABLE   AGE
# api-podinfo   1/1     1            1           45s
#
# ==> v1/Pod(related)
# NAME                           READY   STATUS    RESTARTS   AGE
# api-podinfo-59dc874785-xkxkt   1/1     Running   0          24s
#
# NOTES:
# ...
```

> In Helm v4, `RESOURCES` is always shown. v3 needed `--show-resources`, which no longer exists.

```bash
helm status api -n helm-lab --revision 1   # status as of an older revision
helm status api -n helm-lab -o json        # for scripts
```

### helm history
Every install, upgrade and rollback creates a new **revision**:
```bash
helm history api -n helm-lab
# REVISION  UPDATED                   STATUS      CHART           APP VERSION  DESCRIPTION
# 1         Mon Nov 23 10:12:26 2026  superseded  podinfo-6.16.0  6.16.0       Install complete
# 2         Mon Nov 23 10:12:47 2026  superseded  podinfo-6.17.0  6.17.0       Upgrade complete
# 3         Mon Nov 23 10:13:27 2026  superseded  podinfo-6.17.0  6.17.0       Upgrade complete
# 4         Mon Nov 23 10:14:17 2026  deployed    podinfo-6.16.0  6.16.0       Rollback to 1
```

Revision 4 came from a rollback. A rollback doesn't rewind history, it **adds** a new revision that copies an old one:
```bash
helm rollback api 1 -n helm-lab --wait
# Rollback was a success! Happy Helming!
```

### helm get — the stored details of a release

| Subcommand | Shows |
|------------|-------|
| `helm get values <rel>` | User-supplied values (`--all` for computed) |
| `helm get manifest <rel>` | The exact Kubernetes YAML Helm applied |
| `helm get notes <rel>` | The rendered NOTES.txt |
| `helm get hooks <rel>` | Hook resources (tests, pre/post-install jobs...) |
| `helm get metadata <rel>` | Chart name/version, revision, status, deploy time |
| `helm get all <rel>` | Everything above in one dump |

All of them take `--revision N` to look at an older revision.

```bash
helm get manifest api -n helm-lab | grep -E '^(kind:|  name:)'
# kind: Service
#   name: api-podinfo
# kind: Deployment
#   name: api-podinfo

helm get hooks api -n helm-lab | grep -E '^kind:|helm.sh/hook"'
# kind: Pod
#     "helm.sh/hook": test-success
# ...   (podinfo ships three test pods, run by `helm test`)

helm get metadata api -n helm-lab
# NAME: api
# CHART: podinfo
# VERSION: 6.17.0
# APP_VERSION: 6.17.0
# NAMESPACE: helm-lab
# REVISION: 3
# STATUS: deployed
# DEPLOYED_AT: 2026-11-23T10:13:27+05:30
# APPLY_METHOD: server-side apply
```

Compare what changed between two revisions:
```bash
diff <(helm get manifest api -n helm-lab --revision 1) <(helm get manifest api -n helm-lab --revision 2)
```

---

## Where Helm keeps release info (and how resources are labelled)

### Release storage = Secrets

Each revision is stored as a Secret **in the release's namespace**:
```bash
kubectl get secret -n helm-lab -l owner=helm
# NAME                                       TYPE                 DATA   AGE
# sh.helm.release.v1.api.v1                  helm.sh/release.v1   1      2m18s
# sh.helm.release.v1.api.v2                  helm.sh/release.v1   1      117s
# sh.helm.release.v1.api.v3                  helm.sh/release.v1   1      76s
# sh.helm.release.v1.api.v4                  helm.sh/release.v1   1      27s
# sh.helm.release.v1.web.v1                  helm.sh/release.v1   1      2m45s
```

Name pattern: `sh.helm.release.v1.<release>.v<revision>`. Labels on them:
`owner=helm, name=<release>, status=deployed|superseded|failed|..., version=<revision>`.

```bash
kubectl get secret -n helm-lab -l owner=helm,name=api,status=deployed
```

That's why `helm list -n X` only sees releases in namespace X: it's reading Secrets in X.
Deleting these Secrets makes Helm "forget" the release, while its resources stay in the cluster. **Don't do it by hand.**

### Labels and annotations on the resources

```bash
kubectl get deploy api-podinfo -n helm-lab -o jsonpath='{.metadata.labels}{"\n"}{.metadata.annotations}'
# {"app.kubernetes.io/managed-by":"Helm","app.kubernetes.io/name":"api-podinfo","app.kubernetes.io/version":"6.16.0","helm.sh/chart":"podinfo-6.16.0"}
# {"meta.helm.sh/release-name":"api","meta.helm.sh/release-namespace":"helm-lab", ...}
```

| Marker | Set by | Reliable? |
|--------|--------|-----------|
| Annotation `meta.helm.sh/release-name` / `release-namespace` | **Helm itself**, on every resource it manages | Yes. This is how Helm tracks ownership |
| Label `app.kubernetes.io/managed-by: Helm` | Helm itself | Yes, but doesn't say *which* release |
| Label `app.kubernetes.io/instance: <release>` | The **chart author** (convention) | Only if the chart sets it. podinfo doesn't! |

```bash
kubectl get all -n helm-lab -l app.kubernetes.io/instance=api
# No resources found in helm-lab namespace.     ← podinfo doesn't set this label

kubectl get deploy,svc -A -l app.kubernetes.io/managed-by=Helm
# NAMESPACE   NAME                          READY ...
# helm-lab    deployment.apps/api-podinfo   1/1
# helm-lab    deployment.apps/web-podinfo   1/1
# ...
```

**Most reliable list of a release's resources:** `helm get manifest`, because it's exactly what Helm applied.

---

## helm uninstall

```bash
helm uninstall web -n helm-lab           # aliases: del, delete, un
# release "web" uninstalled
```

This deletes every resource in the release's manifest **and** all its history Secrets.

| Flag | Effect |
|------|--------|
| `--dry-run` | Show what would happen, delete nothing |
| `--wait` | Block until the resources are actually gone |
| `--keep-history` | Delete resources but keep the release record (status `uninstalled`) |
| `--ignore-not-found` | Don't error if the release doesn't exist (useful in scripts) |
| `--no-hooks` | Skip pre/post-delete hooks |
| `--cascade foreground` | Wait for dependents (e.g. Pods of a Deployment) to go first |

### --keep-history

```bash
helm uninstall podinfo-1795408976 -n helm-lab --keep-history
helm list -n helm-lab --uninstalled
# NAME                NAMESPACE  REVISION  STATUS       CHART
# podinfo-1795408976  helm-lab   1         uninstalled  podinfo-6.17.0

helm history podinfo-1795408976 -n helm-lab     # still works
```

The name is still taken, so a plain install fails. Use `--replace` to reuse it:
```bash
helm install podinfo-1795408976 podinfo/podinfo -n helm-lab
# Error: INSTALLATION FAILED: release name check failed: cannot reuse a name that is still in use
helm install podinfo-1795408976 podinfo/podinfo -n helm-lab --replace
# STATUS: deployed
# REVISION: 2
```

### Uninstalling an already-gone release
```bash
helm uninstall demo -n helm-lab
# Error: uninstall: Release not loaded: demo: release: not found
helm uninstall demo -n helm-lab --ignore-not-found     # exit code 0
```

---

## Orphaned resources: what uninstall leaves behind

`helm uninstall` only deletes what's in the **release manifest**. Four common things are not in it, or are skipped on purpose:

| Leftover | Why it survives |
|----------|----------------|
| **PVCs from a StatefulSet's `volumeClaimTemplates`** | Created by the StatefulSet controller, not by Helm. (Their PVs, and your data, live on too.) |
| **Resources annotated `helm.sh/resource-policy: keep`** | The chart asked Helm to never delete them |
| **Hook resources without a delete policy** | Hooks aren't part of the manifest. Without `helm.sh/hook-delete-policy` they're never cleaned up |
| **CRDs from the chart's `crds/` folder** | Helm installs them but **never** deletes or upgrades them, by design |

Plus anything else a running app or operator created at runtime (Jobs, ConfigMaps, Secrets, PVCs...).

### Demo

A small local chart, [`examples/orphan-demo`](https://github.com/mayankbansa0105/helm-notes/tree/main/examples/orphan-demo), with one of each:
```bash
helm install demo ./examples/orphan-demo -n helm-lab --wait

kubectl get sts,pvc,cm,widgets -n helm-lab -l app.kubernetes.io/instance=demo
# statefulset.apps/demo-db                 1/1
# persistentvolumeclaim/data-demo-db-0     Bound   1Gi
# configmap/demo-install-marker            ← post-install hook
# configmap/demo-settings                  ← resource-policy: keep
# widget.demo.example.com/demo-widget      ← custom resource, CRD from crds/

helm uninstall demo -n helm-lab --wait
# These resources were kept due to the resource policy:
# [ConfigMap] demo-settings
#
# release "demo" uninstalled
```

Helm warns about `keep` resources, but **says nothing** about the others. After uninstall:
```bash
kubectl get all,pvc,cm -n helm-lab -l app.kubernetes.io/instance=demo
# persistentvolumeclaim/data-demo-db-0   Bound   1Gi    ← orphan
# configmap/demo-install-marker                         ← orphan (hook)
# configmap/demo-settings                               ← orphan (keep)

kubectl get crd widgets.demo.example.com
# widgets.demo.example.com   2026-11-23T04:45:22Z       ← orphan (CRD)
```

### Finding orphans

**Tip: save the list before uninstalling.** It's the easiest way to know what to look for afterwards:
```bash
helm get manifest demo -n helm-lab > demo-manifest.yaml
helm get hooks    demo -n helm-lab > demo-hooks.yaml
helm show crds    ./examples/orphan-demo     > demo-crds.yaml
```

**Method 1: by the chart's instance label** (if the chart sets `app.kubernetes.io/instance`).
`kubectl get all` misses PVCs, ConfigMaps, Secrets, CRs etc., so sweep **every** listable type:
```bash
types=$(kubectl api-resources --verbs=list --namespaced -o name | grep -v '^events' | paste -sd, -)
kubectl get "$types" -n helm-lab -l app.kubernetes.io/instance=demo --ignore-not-found -o name
# configmap/demo-install-marker
# configmap/demo-settings
# persistentvolumeclaim/data-demo-db-0
```

**Method 2: by Helm's own annotation, for releases that no longer exist.**
Works for any chart, but only finds resources Helm itself applied (catches `keep`; misses hooks and controller-made PVCs):
```bash
# releases that still exist
helm list -A -o json | jq -r '.[] | "\(.namespace)/\(.name)"' > live.txt

# every Helm-annotated resource, tagged with the release it claims to belong to
kubectl get "$types" -A -o json 2>/dev/null | jq -r '.items[]
  | select(.metadata.annotations["meta.helm.sh/release-name"] != null)
  | "\(.metadata.annotations["meta.helm.sh/release-namespace"])/\(.metadata.annotations["meta.helm.sh/release-name"])  \(.kind)/\(.metadata.name)"' \
  | sort -u > owned.txt

# owned by a release that's gone = orphan
grep -vFf <(sed 's/$/ /' live.txt) owned.txt
# helm-lab/demo  ConfigMap/demo-settings
```

**Method 3: cluster-scoped leftovers.** CRDs, ClusterRoles, ClusterRoleBindings, webhooks...
```bash
kubectl get crd | grep demo.example.com
kubectl get clusterrole,clusterrolebinding,mutatingwebhookconfiguration,validatingwebhookconfiguration \
  -l app.kubernetes.io/instance=demo
```

### Deleting orphans safely

1. **Look first** with `--dry-run=client`:
   ```bash
   kubectl delete pvc,configmap -n helm-lab -l app.kubernetes.io/instance=demo --dry-run=client
   # persistentvolumeclaim "data-demo-db-0" deleted from helm-lab namespace (dry run)
   # configmap "demo-install-marker" deleted from helm-lab namespace (dry run)
   # configmap "demo-settings" deleted from helm-lab namespace (dry run)
   ```
2. **PVCs = data.** Check the PV's reclaim policy. With `Delete` (the default on most cloud
   StorageClasses), deleting the PVC **destroys the disk**. Take a backup or snapshot first if the data matters.
   ```bash
   kubectl get pv -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,POLICY:.spec.persistentVolumeReclaimPolicy
   # NAME                                       CLAIM            POLICY
   # pvc-13037656-91dd-487e-bc80-5d5912643cf1   data-demo-db-0   Delete
   ```
3. **Delete:**
   ```bash
   kubectl delete pvc,configmap -n helm-lab -l app.kubernetes.io/instance=demo
   ```
4. **CRDs last, and carefully.** Deleting a CRD deletes **every custom resource of that type in the whole cluster**,
   including ones other releases or teams created. Check first:
   ```bash
   kubectl get widgets -A               # must be empty, or all yours
   kubectl delete crd widgets.demo.example.com
   ```
5. If the release had its own namespace and nothing else lives there, `kubectl delete namespace <ns>`
   removes all namespaced leftovers at once (but not CRDs, PVs or other cluster-scoped objects).

---

## Putting it together

```bash
helm install web podinfo/podinfo -n helm-lab --create-namespace --wait   # install
helm list -n helm-lab                                                    # is it there?
helm status web -n helm-lab                                              # healthy? what did it create?
helm get values web -n helm-lab --all                                    # what config is it running?
helm history web -n helm-lab                                             # what changed?
helm get manifest web -n helm-lab > web-manifest.yaml                    # save before removing
helm uninstall web -n helm-lab --wait                                    # remove
# then sweep for PVCs, keep-policy objects, hooks and CRDs (see above)
```

---

## Gotchas

- **Namespaces everywhere.** Releases are namespaced. `helm list`, `status`, `get`, `uninstall` without the right `-n` say "not found". Use `helm list -A` to find which namespace a release lives in.
- **`show values` ≠ `get values`.** `show` = chart defaults; `get` = your overrides; `get --all` = merged.
- **A failed install isn't cleaned up** unless you used `--rollback-on-failure`. It sits there with status `failed`.
- **Rollback adds a revision**, it doesn't remove later ones.
- **`app.kubernetes.io/instance` is a convention, not a guarantee.** Use `helm get manifest` or the `meta.helm.sh/release-name` annotation when the label is missing.
- **`helm uninstall` is silent about PVCs, hooks and CRDs.** Always check for leftovers, especially before reinstalling a chart with the same name: an old PVC will be reused, with old data.
- **Deleting a CRD deletes all of its custom resources, cluster-wide.**
- **v3 → v4 renames:** `--atomic` → `--rollback-on-failure`; `helm status --show-resources` → always on; `helm list -a/--all` → removed.

## Remember
> **`install`** creates a release, **`list / status / history / get`** inspect it
> (**`get values`** = your overrides, **`show values`** = chart defaults),
> **`uninstall`** removes only what's in the manifest. Sweep for **PVCs, keep-policy objects, hooks and CRDs** afterwards.

Next chapter: installing with custom values via `--set` and `-f values.yaml`.
