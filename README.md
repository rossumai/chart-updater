# Chart-updater

Chart-updater is a [Flux](https://github.com/fluxcd/flux) companion that allows
for automatic [Helm](https://helm.sh) chart updates. It monitors Helm chart
respository for new chart versions. If new version is found, related
HelmRelease manifest in the git config respository is updated in the git config
repository.

This may be useful for deploying charts of your components, especially if the
code and chart template of the component share the same repository and
life-cycle.

Flux itself is able to update K8s clusters when new images are pushed to the
container repository, but charts must be updated manually. There are plans to
extend Flux to support automatic chart updates, see the reported
[issue](https://github.com/fluxcd/helm-operator/issues/12). Until implemented,
this tool may be useful to keep your charts up-to-date.

Chart-updater may also update Docker images, so that Charts and images are
updated atomically in a single commit.

## How to use in K8s cluster

The tool is available as a Helm chart, ready to be deployed into your Kubernetes cluster.

```
helm repo add rossumai https://rossumai.github.io/helm-charts
helm install chart-updater rossumai/chart-updater
```

See [charts/chart-updater](https://github.com/rossumai/chart-updater/tree/master/charts/chart-updater#configuration)
for a complete list of available configuration options.

### Auto-update annotations

Similar to Flux, annotations are used to mark Helm charts that should be
updated. The only supported manifest type is `HelmRelease`.

* `rossum.ai/allow-chart-update` -- Switches-on chart auto-update.
* `rossum.ai/chart-version` -- Specifies which Chart versions should be used for auto-update. May be `semver`, `glob` or `regex` pattern.
* `rossum.ai/update-image.chart-image` -- Switches-on update of main chart image
* `rossum.ai/update-image.<NAME>` -- Switches-on update of a named image

In case image is updated, new tag is obtained from Chart's `appVersion`.

Example of HelmRelease with glob-base chart auto-updates:

```yaml
apiVersion: helm.fluxcd.io/v1
kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/allow-chart-update: true
    rossum.ai/chart-version: glob:1.0.*
    # rossum.ai/chart-version: semver:1.0.x
    # rossum.ai/chart-version: regex:^1\.0\..*
spec:
  chart:
    repository: https://helm.lol
    name: hello-world
    version: 4.1.0
  values:
    image:
      repository: some.docker.repo/hello-world
      tag: v0.6.1
```

Example of image auto-update:

```yaml
apiVersion: helm.fluxcd.io/v1
kind: HelmRelease
metadata:
  name: hello-world
  namespace: default
  annotations:
    rossum.ai/allow-chart-update: true
    rossum.ai/chart-version: glob:1.0.*
    rossum.ai/update-image.chart-image: true
spec:
  chart:
    repository: https://helm.lol
    name: hello-world
    version: 4.1.0
  values:
    image:
      repository: some.docker.repo/hello-world
      tag: v0.6.1
```

## Running locally

If you want to test the tool, you can use public Docker images available at [Dockerhub](https://hub.docker.com/repository/docker/rossumai/chart-updater).

```shell
docker run rossumai/chart-updater --help
```

### Install

If you want to install and run chart-updater locally, follow these steps:

* make sure you have Python 3.8+ installed
* install dependencies: `pip install -r requirements.txt`

### Run

Run `./chart-updater.py --help` to obtain list of available options:

```
Usage: chart-updater.py [OPTIONS]

Options:
  --git-url TEXT             Git config repo URL.  [required]
  --git-path TEXT            Git config path.  [default: .]
  --git-branch TEXT          Git config repo ref.  [default: master]
  --git-user TEXT            Git commit author's name.  [default: Chart Sync]
  --git-email TEXT           Git commit author's email.  [default: chart-
                             sync@rossum.ai]
  --git-timeout INTEGER      Git operations timeout (seconds).  [default: 30]
  --git-ssh-identity TEXT    Git config SSH identity file (key).
  --helm-repo-url TEXT       Helm repo URL.  [required]
  --helm-repo-username TEXT  Helm repo username (basic auth).
  --helm-repo-password TEXT  Helm repo password (basic auth).
  --sync-interval INTEGER    Period of git sync (seconds).  [default: 60]
  --annotation-prefix TEXT   Prefix of k8s annotations.  [default: rossum.ai]
  --help                     Show this message and exit.
```
