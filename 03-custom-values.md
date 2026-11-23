# 03 — Custom values: --set and -f

## The big picture

Every chart ships a `values.yaml` full of defaults (see them with `helm show values`).
When you install or upgrade, you **override** some of them. There are two main ways:

| Way | Looks like | Best for |
|-----|-----------|----------|
| **Values file** `-f` / `--values` | `-f prod.yaml` | Real config you keep in git, per environment |
| **`--set` family** | `--set replicaCount=3` | One-off tweaks, CI variables (image tag, build number) |

Helm merges everything into one final set of values, the **computed values**, and renders the templates with it.

> All examples were run with Helm v4.3.2. To see the merge result yourself, use the small chart in
> [`examples/values-demo`](https://github.com/mayankbansa0105/helm-notes/tree/main/examples/values-demo).
> Its only template prints the final values, so `helm template` shows exactly what won:
> ```bash
> helm template t ./examples/values-demo -f examples/values-files/prod.yaml --set replicaCount=3
> ```
> `helm template` renders locally and doesn't need a cluster, so it's the best way to practise this chapter.

The chart's defaults (`examples/values-demo/values.yaml`):
```yaml
replicaCount: 1
image:
  repository: nginx
  tag: "1.27"
service:
  type: ClusterIP
  port: 80
env: dev
labels:
  team: platform
  tier: web
hosts:
  - a.example.com
```

---

## Precedence: who wins? (the most important part)

### Using both `-f` and `--set` for the same key is **not an error**. `--set` wins.

```bash
# prod.yaml says replicaCount: 5
helm template t ./examples/values-demo -f examples/values-files/prod.yaml --set replicaCount=3
#     env: prod              ← from prod.yaml (nothing on --set for it)
#     replicaCount: 3        ← --set beat the file
```

**The position on the command line doesn't matter.** `--set` still wins even when it's written *before* `-f`:
```bash
helm template t ./examples/values-demo --set replicaCount=3 -f examples/values-files/prod.yaml
#     replicaCount: 3
```

Helm doesn't warn you that a value was overridden. It silently uses the winner.

### The full order (lowest → highest)

```
 1. chart's values.yaml               (defaults)
 2. -f / --values files               (in the order given; the LAST file wins)
 3. --set-json
 4. --set
 5. --set-string
 6. --set-file
 7. --set-literal                     (highest)
```

Within the **same** flag type, the **last one** on the command line wins.

### Proof: multiple `-f` files, last one wins

```yaml
# dev.yaml                 # prod.yaml
replicaCount: 2            replicaCount: 5
env: dev                   env: prod
                           image:
                             tag: "1.28"
```

```bash
helm template t ./examples/values-demo -f dev.yaml -f prod.yaml     # prod is last
#     env: prod
#     replicaCount: 5

helm template t ./examples/values-demo -f prod.yaml -f dev.yaml     # dev is last
#     env: dev
#     replicaCount: 2
```

That's how the common "base + environment" pattern works:
```bash
helm install shop ./chart -f values-common.yaml -f values-prod.yaml
```

### Proof: repeated `--set`, last one wins
```bash
helm template t ./examples/values-demo --set replicaCount=3 --set replicaCount=4
#     replicaCount: 4
```

### Proof: different `--set` flavours, fixed order
```bash
--set env=fromset --set-string env=fromstring      →  env: fromstring
--set-string env=fromstring --set env=fromset      →  env: fromstring   (order didn't matter)
--set-json 'env="json"' --set env=plain            →  env: plain
--set env=plain --set-json 'env="json"'            →  env: plain        (order didn't matter)
--set-literal env=lit --set env=plain              →  env: lit
```

> **Exam-style answer:** "If the same key is given with `-f` and `--set`, the install succeeds and the
> `--set` value is used. Among several `-f` files, the last file wins. Among several `--set`s, the last one wins."

---

## Values files: -f / --values

```bash
helm install web ./chart -f my-values.yaml
helm install web ./chart --values my-values.yaml          # same thing
helm install web ./chart -f base.yaml -f prod.yaml        # several; later wins
helm install web ./chart -f https://example.com/vals.yaml # a URL works too
echo 'replicaCount: 9' | helm install web ./chart -f -    # from stdin
```

Your file only needs the keys you're **changing**, not a full copy of the defaults.

### How files merge: maps merge, lists replace

**Maps are merged key by key**, so you only add or change what you name:
```yaml
# labels-extra.yaml
labels:
  owner: mayank
```
```bash
helm template t ./examples/values-demo -f labels-extra.yaml
#     labels:
#       owner: mayank        ← added
#       team: platform       ← kept from defaults
#       tier: web            ← kept from defaults
```

**Lists are replaced completely.** Helm can't merge two lists:
```yaml
# hosts.yaml
hosts:
  - c.example.com
```
```bash
helm template t ./examples/values-demo -f hosts.yaml
#     hosts:
#     - c.example.com        ← a.example.com is gone
```

To *add* to a list, repeat the original items in your file too.

### Removing a default key: set it to `null`
```yaml
# remove-tier.yaml
labels:
  tier: null
```
```bash
helm template t ./examples/values-demo -f remove-tier.yaml
#     labels:
#       team: platform       ← tier was deleted
```

### Start from the chart's own file
```bash
helm show values ingress-nginx/ingress-nginx > my-values.yaml   # edit, then delete what you didn't change
helm install ing ingress-nginx/ingress-nginx -f my-values.yaml
```

Trimming the file down to just your changes keeps upgrades clean. A full copy freezes every
default at today's value, so you'd miss improvements in newer chart versions.

---

## --set: values on the command line

### Syntax cheat sheet

| You want | Command | Result |
|----------|---------|--------|
| Simple value | `--set replicaCount=3` | `replicaCount: 3` |
| Nested key | `--set image.tag=1.29` | `image: {tag: "1.29"}` |
| Several at once | `--set replicaCount=3,env=qa` | both set |
| Whole list | `--set 'hosts={x.com,y.com}'` | `hosts: [x.com, y.com]` |
| One list item | `--set 'hosts[0]=b.example.com'` | replaces item 0 |
| Field in a list of maps | `--set 'ingress.hosts[0].host=a.com'` | `ingress.hosts: [{host: a.com}]` |
| Key that contains dots | `--set 'labels.app\.kubernetes\.io/part-of=shop'` | `labels: {app.kubernetes.io/part-of: shop}` |
| Value that contains a comma | `--set 'env=a\,b'` | `env: a,b` |
| Delete a default key | `--set labels.tier=null` | `tier` removed |

> **zsh users: quote anything with `[ ]` or `{ }`.** Unquoted, zsh treats `hosts[0]=...` as a filename pattern and fails with
> `no matches found: hosts[0]=b.example.com`. Single quotes are the safe habit for every `--set`.

### Lists: careful with indexes
Setting an index past the end pads the list with `null`s:
```bash
helm template t ./examples/values-demo --set 'hosts[2]=z.com'
#     hosts:
#     - null
#     - null                 ← a.example.com was replaced, not kept!
#     - z.com
```
A `--set` on any list item **replaces the whole default list**. For lists, prefer a values file.

### Types: the classic --set trap

`--set` guesses the type. `true`/`false` become booleans and whole numbers become integers.
Use `--set-string` when the template needs text:

```bash
--set env=true            →  env: true        (boolean)
--set-string env=true     →  env: "true"      (string)
--set image.tag=1234      →  tag: 1234        (number!)
--set-string image.tag=1234 → tag: "1234"     (string)
```

Real-world damage: a numeric image tag in a **values file** without quotes:
```yaml
image:
  tag: 20241201        # YAML reads this as a number
```
```bash
helm template t ./tdemo -f t.yaml
# image: "nginx:2.0241201e+07"      ← broken image name!
```
And `tag: 1.30` in YAML becomes the number `1.3` → `nginx:1.3`, the wrong version.
**Always quote version-like values in YAML files:** `tag: "1.30"`, `tag: "20241201"`.

(Interestingly `--set image.tag=20241201` renders fine as `nginx:20241201`, because `--set` stores big
integers as whole numbers rather than floats. The values-file case is the one that bites.)

### The rest of the --set family

```bash
# --set-string: force string type
helm install web ./chart --set-string image.tag=1234

# --set-json: complex structures in one go (maps, lists, types preserved)
helm install web ./chart --set-json 'resources={"limits":{"cpu":"500m","memory":"256Mi"}}'
helm install web ./chart --set-json 'hosts=["j1.com","j2.com"]'

# --set-file: value = contents of a file (certs, scripts, config snippets)
helm install web ./chart --set-file motd=note.txt
#     motd: |
#       line1

# --set-literal: take the value exactly as typed, no comma/escape parsing
helm install web ./chart --set-literal 'env=a,b=c'
#     env: a,b=c
```

---

## Errors vs silent surprises

**These ARE errors:**
```bash
helm install web ./chart -f nope.yaml
# Error: open nope.yaml: no such file or directory

helm install web ./chart --set replicaCount
# Error: failed parsing --set data: key "replicaCount" has no value
```

**These are NOT errors (Helm accepts them silently):**
```bash
--set replicaCont=3        # typo → adds a new unused key; replicaCount stays 1
--set image=foo            # replaces the whole image map with a string
-f a.yaml --set x=1        # same key in both → --set wins, no warning
```

### Catching mistakes: values.schema.json

If a chart ships a `values.schema.json`, Helm validates the **final merged values** against it, so bad
values fail before anything reaches the cluster:
```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "replicaCount": { "type": "integer", "minimum": 1 },
    "env": { "type": "string", "enum": ["dev", "qa", "prod"] }
  }
}
```
```bash
helm install web ./chart --set replicaCount=0
# values-demo:
# - at '/replicaCount': minimum: got 0, want 1

helm install web ./chart --set env=staging
# values-demo:
# - at '/env': value must be one of 'dev', 'qa', 'prod'
```
`--skip-schema-validation` turns this off (avoid it in normal use).

### Always preview first
```bash
helm template web ./chart -f prod.yaml --set image.tag=1.29        # render locally
helm install  web ./chart -f prod.yaml --set image.tag=1.29 --dry-run=server   # validate with the cluster
```

---

## After install: what got stored?

Helm saves the merged **user-supplied** values (your `-f` files + `--set`s, combined) in the release:
```bash
helm install demo ./examples/values-demo -n helm-lab --create-namespace \
  -f examples/values-files/prod.yaml --set replicaCount=3

helm get values demo -n helm-lab
# USER-SUPPLIED VALUES:
# env: prod
# image:
#   tag: "1.28"
# replicaCount: 3            ← --set already applied; the file and flag aren't stored separately
```

Helm doesn't remember *where* each value came from. Keep your values files in git so you know.

---

## Upgrades: the values trap

**By default, `helm upgrade` with any `-f` or `--set` throws away your previous overrides**, and starts
again from the chart defaults plus only what you pass *this time*.

Starting point for every row below: installed with `-f prod.yaml --set replicaCount=3`
→ stored values `{env: prod, image.tag: "1.28", replicaCount: 3}`.

| Upgrade command | Stored values afterwards |
|-----------------|--------------------------|
| `helm upgrade demo ./chart` (no values flags) | `{env: prod, image.tag: "1.28", replicaCount: 3}`, previous values kept |
| `helm upgrade demo ./chart --set env=qa` | `{env: qa}` ⚠️ **everything else reset to defaults** |
| `helm upgrade demo ./chart --reuse-values --set env=qa` | `{env: qa, image.tag: "1.28", replicaCount: 3}` |
| `helm upgrade demo ./chart --reset-values` | `null`, back to pure chart defaults |
| `helm upgrade demo ./chart --reset-then-reuse-values --set env=qa` | `{env: qa, image.tag: "1.28", replicaCount: 3}` |

### --reuse-values vs --reset-then-reuse-values

They look the same above, but they behave differently when the **new chart version adds new defaults**:

- `--reuse-values` reuses the old release's **full computed values** and ignores the new chart's `values.yaml`.
  Any key the new version added is missing:
  ```bash
  # chart 0.2.0 added `probes.path` to values.yaml and uses it in a template
  helm upgrade demo ./values-demo-v2 -n helm-lab --reuse-values
  # executing "values-demo/templates/probe.yaml" at <.Values.probes.path>:
  #     nil pointer evaluating interface {}.path
  ```
- `--reset-then-reuse-values` takes the **new** chart defaults, then re-applies only your old overrides. It works:
  ```bash
  helm upgrade demo ./values-demo-v2 -n helm-lab --reset-then-reuse-values
  # STATUS: deployed
  helm get values demo -n helm-lab --all -o json | jq -c '{env,replicaCount,probes}'
  # {"env":"qa","replicaCount":3,"probes":{"path":"/healthz"}}
  ```

**Safest habit:** always pass the **full** set of values on every upgrade, e.g.
`helm upgrade --install web ./chart -f common.yaml -f prod.yaml --set image.tag=$TAG`,
so nothing depends on what's stored in the release.

---

## Subcharts and globals (quick look)

If a chart depends on other charts, nest their values under the subchart's **name**:
```yaml
# parent chart values / your -f file
replicaCount: 2           # parent chart
redis:                    # subchart called "redis"
  architecture: standalone
  auth:
    enabled: false
global:                   # visible to the parent AND every subchart as .Values.global
  imageRegistry: my-registry.example.com
```
Same on the command line: `--set redis.auth.enabled=false`, `--set global.imageRegistry=my-registry.example.com`.

---

## Putting it together

```bash
helm show values podinfo/podinfo > defaults.yaml          # 1. see what's configurable
vi values-prod.yaml                                       # 2. write ONLY your changes
helm template web podinfo/podinfo -f values-prod.yaml \
  --set-string image.tag=6.17.0 | less                    # 3. preview the result
helm upgrade --install web podinfo/podinfo -n shop \
  -f values-prod.yaml --set-string image.tag=6.17.0 \
  --create-namespace                                      # 4. install or upgrade
helm get values web -n shop                               # 5. confirm what's stored
```

---

## Gotchas

- **`-f` + `--set` on the same key = no error; `--set` wins**, wherever it appears on the command line.
- **Last `-f` wins** among files; **last `--set` wins** among `--set`s.
- **Lists are replaced, never merged.** Same for `--set 'list[0]=...'`, which wipes the default list.
- **Quote `[` `]` `{` `}` in zsh**, or you'll get `no matches found`.
- **Typos are silent.** `--set replicaCont=3` happily adds a junk key. Check with `helm template` or `helm get values`.
- **Quote version-like values in YAML** (`"1.30"`, `"20241201"`), or they turn into floats.
- **`helm upgrade --set x=y` alone resets all your earlier overrides.** Pass everything again, or use `--reset-then-reuse-values`.
- **`--reuse-values` can break upgrades to newer chart versions** that added new defaults.

## Remember
> **Order:** chart defaults < `-f` files (last wins) < `--set-json` < `--set` < `--set-string` < `--set-file` < `--set-literal`.
> **Same key in `-f` and `--set` = no error, `--set` wins.**
> Maps merge, lists replace, `null` deletes. On upgrade, always pass all your values again.
