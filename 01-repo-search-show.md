# 01 — helm repo, helm search, helm show

## The big picture

Before you install anything, you need to **find** a chart and **look inside** it.
Three command groups do that:

| Command | Question it answers | Talks to the cluster? |
|---------|---------------------|-----------------------|
| `helm repo` | "Where do charts come from?" | No |
| `helm search` | "Which chart (and which version) do I want?" | No |
| `helm show` | "What's in this chart, and what can I configure?" | No |

None of these touch Kubernetes, so you can practise all of them without a cluster.

---

## helm repo — manage chart repositories

A **chart repository** is just a web server that hosts an `index.yaml` (the catalogue) plus packaged
charts (`.tgz` files). Helm keeps a list of the repos you've added and a local cache of their indexes.

| Subcommand | What it does |
|------------|--------------|
| `helm repo add <name> <url>` | Save a repo under a short name |
| `helm repo list` | Show the repos you've added |
| `helm repo update [name...]` | Download the latest `index.yaml` for all (or some) repos |
| `helm repo remove <name>` | Forget a repo |
| `helm repo index <dir>` | Generate an `index.yaml` for charts in a directory (for hosting your **own** repo) |

### Examples

Add some repos:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
# "bitnami" has been added to your repositories
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

List them:
```bash
helm repo list
# NAME                  URL
# bitnami               https://charts.bitnami.com/bitnami
# ingress-nginx         https://kubernetes.github.io/ingress-nginx
# prometheus-community  https://prometheus-community.github.io/helm-charts
```

Refresh the indexes (do this before searching or upgrading):
```bash
helm repo update
# Hang tight while we grab the latest from your chart repositories...
# ...Successfully got an update from the "ingress-nginx" chart repository
# ...Successfully got an update from the "prometheus-community" chart repository
# ...Successfully got an update from the "bitnami" chart repository
# Update Complete. ⎈Happy Helming!⎈

helm repo update ingress-nginx      # refresh just one repo
```

Remove one:
```bash
helm repo remove bitnami
# "bitnami" has been removed from your repositories
```

Other useful flags:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami --force-update   # re-add, replacing an existing entry
helm repo add private https://charts.example.com --username me --password-stdin < token.txt
helm repo list -o yaml                                                       # table | json | yaml
```

### Where Helm stores this

```bash
helm env | grep -E 'HELM_REPOSITORY_(CONFIG|CACHE)'
# HELM_REPOSITORY_CACHE="/Users/you/Library/Caches/helm/repository"            # cached index.yaml files
# HELM_REPOSITORY_CONFIG="/Users/you/Library/Preferences/helm/repositories.yaml" # name → URL list
```

The paths above are for macOS. On Linux they're under `~/.cache/helm` and `~/.config/helm`.

---

## helm search — find charts

There are two kinds of search, and they look in different places:

| Command | Searches | Needs `repo add` first? |
|---------|----------|-------------------------|
| `helm search repo <keyword>` | The **local cached indexes** of repos you've added | Yes |
| `helm search hub <keyword>` | **Artifact Hub** (artifacthub.io), online | No |

### helm search repo

The keyword matches chart names and descriptions:
```bash
helm search repo nginx
# NAME                                            CHART VERSION  APP VERSION  DESCRIPTION
# bitnami/nginx                                   25.2.16        1.31.9       NGINX Open Source is a web server that can be a...
# bitnami/nginx-ingress-controller                12.0.7         1.13.1       NGINX Ingress Controller is an Ingress controll...
# ingress-nginx/ingress-nginx                     4.15.1         1.15.1       Ingress controller for Kubernetes using NGINX a...
# prometheus-community/prometheus-nginx-exporter  1.25.1         1.5.3        A Helm chart for NGINX Prometheus Exporter
```

With no keyword, it lists **every** chart in every added repo:
```bash
helm search repo
helm search repo bitnami/          # everything in one repo
```

Show every version, not just the latest (`-l` / `--versions`):
```bash
helm search repo ingress-nginx/ingress-nginx --versions
# NAME                         CHART VERSION  APP VERSION  DESCRIPTION
# ingress-nginx/ingress-nginx  4.15.1         1.15.1       Ingress controller for Kubernetes using NGINX a...
# ingress-nginx/ingress-nginx  4.15.0         1.15.0       Ingress controller for Kubernetes using NGINX a...
# ingress-nginx/ingress-nginx  4.14.5         1.14.5       Ingress controller for Kubernetes using NGINX a...
# ...
```

Filter by a **semver constraint** on the chart version:
```bash
helm search repo ingress-nginx/ingress-nginx --versions --version '~4.14.0'   # 4.14.x only
helm search repo ingress-nginx/ingress-nginx --versions --version '>=4.12, <4.14'
```

Include pre-releases (alpha / beta / rc), which are hidden by default:
```bash
helm repo add jetstack https://charts.jetstack.io
helm search repo jetstack/cert-manager --devel
```

Other useful flags:
```bash
helm search repo nginx -o yaml                 # table | json | yaml (good for scripts)
helm search repo 'nginx-.*' --regexp           # regular expression instead of a plain keyword
helm search repo nginx --max-col-width 0       # don't truncate the description
helm search repo nosuchchart --fail-on-no-result   # exit non-zero if nothing matches (CI)
```

### helm search hub

Searches every public chart listed on Artifact Hub. You get URLs back, not `repo/chart` names:
```bash
helm search hub redis
# URL                                                   CHART VERSION  APP VERSION  DESCRIPTION
# https://artifacthub.io/packages/helm/redis-arm/redis  17.8.0         7.0.8        Redis(R) is an open source, advanced key-value...
# ...

helm search hub redis --list-repo-url      # also show each chart's repo URL, ready for `helm repo add`
```

Typical flow: find a chart with `search hub` → `helm repo add` its repo → work with it locally.

---

## helm show — look inside a chart

`helm show` prints information from a chart **without installing it**. The chart can be a
`repo/chart` name, an `oci://` reference, a local directory, a `.tgz` file or a URL.

| Subcommand | Prints |
|------------|--------|
| `helm show chart <chart>` | `Chart.yaml`: name, version, appVersion, kubeVersion, maintainers, dependencies |
| `helm show values <chart>` | The default `values.yaml`, i.e. everything you can override |
| `helm show readme <chart>` | The chart's README |
| `helm show crds <chart>` | The CustomResourceDefinitions in the chart's `crds/` folder |
| `helm show all <chart>` | All of the above, one after another |

### Examples

Chart metadata:
```bash
helm show chart ingress-nginx/ingress-nginx
# apiVersion: v2
# appVersion: 1.15.1
# description: Ingress controller for Kubernetes using NGINX as a reverse proxy and load balancer
# home: https://github.com/kubernetes/ingress-nginx
# kubeVersion: '>=1.21.0-0'
# name: ingress-nginx
# version: 4.15.1
# ...
```

Default values, saved to a file you can edit and later pass to `helm install -f`:
```bash
helm show values ingress-nginx/ingress-nginx > ingress-values.yaml
```

Pull out just one part of the values with `--jsonpath`:
```bash
helm show values ingress-nginx/ingress-nginx --jsonpath '{.controller.image.tag}'
# v1.15.1
```

A specific (older) chart version, not the latest:
```bash
helm show values ingress-nginx/ingress-nginx --version 4.14.5
```

Read the README in the terminal:
```bash
helm show readme ingress-nginx/ingress-nginx | less
```

Check which CRDs a chart will create:
```bash
helm show crds prometheus-community/kube-prometheus-stack | grep '^  name:'
```

OCI charts work directly. There's no `repo add`, Helm pulls the chart first and then shows it:
```bash
helm show chart oci://registry-1.docker.io/bitnamicharts/redis
# Pulled: registry-1.docker.io/bitnamicharts/redis:28.3.12
# Digest: sha256:a80b...
# annotations:
#   ...
```

Local charts work too:
```bash
helm show values ./mychart
helm show chart mychart-0.1.0.tgz
```

---

## Putting it together

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx   # 1. where it comes from
helm repo update                                                          # 2. fresh catalogue
helm search repo ingress-nginx --versions | head                          # 3. pick a version
helm show chart  ingress-nginx/ingress-nginx --version 4.15.1             # 4. check kubeVersion, appVersion
helm show values ingress-nginx/ingress-nginx --version 4.15.1 > values.yaml   # 5. see what you can set
# next chapter: helm install ... -f values.yaml
```

---

## Gotchas

- **Stale cache.** `helm search repo` doesn't go online. If a new version is missing, run `helm repo update`.
- **Chart version ≠ app version.** `--version 1.15.1` on the ingress-nginx chart fails with `chart "ingress-nginx" matching 1.15.1 not found`, because 1.15.1 is the *app* version. The chart version is 4.15.1.
- **OCI can't be searched or added.** `helm repo add` with an `oci://` URL is an error. Use `helm show` / `helm pull` / `helm install` with the full `oci://` reference, and `helm registry login` for private registries.
- **Pre-releases are hidden.** Add `--devel` to `helm search repo` to see alpha / beta / rc versions.
- **The repo name is local.** `bitnami/nginx` only works because *you* named the repo `bitnami`. A teammate could name the same URL something else.
- **`helm search hub` results aren't installable directly.** Add the chart's repo first (use `--list-repo-url` to see it).

## Remember
> **`repo add` + `repo update`** = get the catalogue, **`search repo`** = pick a chart and version,
> **`show values`** = see what you can configure before installing.
