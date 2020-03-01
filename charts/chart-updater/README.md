# Chart-updater

Chart-updater is a [Flux](https://github.com/fluxcd/flux) companion that allows
for automatic [Helm](https://helm.sh) chart updates. It monitors Helm chart
respository for new chart versions. If new version is found, related
HelmRelease manifest in the git config respository is updated in the git config
repository.

## Introduction

This chart installs a [Chart-updater](https://github.com/rossumai/chart-updater) deployment on
a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## Prerequisites

 - Kubernetes >= v1.11
 - A repo containing cluster config (i.e. Kubernetes YAML manifests)

## Installation

First, instal Flux and Helm Operator, see [Get started with Flux using
Helm](https://docs.fluxcd.io/en/stable/tutorials/get-started-helm.html) tutorial.

### Installing Flux using Helm

First, you need Flux and Helm-operator running in the cluster, see [Flux Get Started
tutorial](https://docs.fluxcd.io/en/stable/tutorials/get-started-helm.html).

The [configuration](#configuration) section lists all the parameters that can be configured during installation.

### Installing Chart-updater

Add the Rossum.ai repo:

```sh
helm repo add rossumai https://github.io/rossumai/helm-charts
```

#### Install the chart (SSH access to Git config repo)

1. Generate a SSH key: `ssh-keygen -q -N "" -f ./identity`
1. Create a Kubernetes secret: `kubectl -n flux create secret generic chart-updater-ssh --from-file=./identity`
1. Add `identity.pub` as a deployment key with write access in your Git config repo
1. Obtain Git repo host key: `ssh-keyscan <your_git_host_domain>`, e.g. for github.com:
  ```sh
  ssh-keyscan github.com
  github.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==
  ```
1. Replace `git@github.com:fluxcd/flux-get-started` with your own Git repository and run helm to install the chart:

   ```sh
   helm upgrade -i chart-updater rossumai/chart-updater \
   --set git.url=git@github.com:fluxcd/flux-get-started \
   --set git.seretName=chart-updater-ssh \
   --set git.patch=auto-deploy \
   --set ssh.knownHosts="github.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==" \
   --namespace flux
   ```

#### Install the chart (HTTPS access to Git config repo)

When using HTTPS for Git repository access, you can use `env.secretName` to set
`GIT_AUTHUSER` and `GIT_AUTHKEY` environment variables. This can be utilized in
Kubernetes manifests, e.g. Pod definition to provide HTTPS credentials in a
secure way, see [Using environment variables inside of your
config](https://kubernetes.io/docs/tasks/inject-data-application/define-environment-variable-container/#using-environment-variables-inside-of-your-config)

1. Create a personal access token to be used as the `GIT_AUTHKEY`:
   - [GitHub](https://help.github.com/en/articles/creating-a-personal-access-token-for-the-command-line)
   - [GitLab](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html#creating-a-personal-access-token)
   - [BitBucket](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

1. Create a secret with your `GIT_AUTHUSER` (the username the token belongs
   to) and the `GIT_AUTHKEY` you created in the first step:

   ```sh
   kubectl create secret generic chart-updater-git-auth --namespace flux --from-literal=GIT_AUTHUSER=<username> --from-literal=GIT_AUTHKEY=<token>
   ```

1. Replace `github.com/fluxcd/flux-get-started` with your own git repository and run helm to install the chart:

   ```sh
   helm upgrade -i chart-updater rossumai/chart-updater \
   --set git.url='https://$(GIT_AUTHUSER):$(GIT_AUTHKEY)@github.com/fluxcd/flux-get-started' \
   --set git.patch=auto-deploy \
   --set env.secretName=flux-git-auth \
   --namespace flux
   ```

### Uninstalling the Chart

To uninstall/delete the `chart-updater` deployment:

```sh
helm delete chart-updater
```

The command removes all the Kubernetes components associated with the chart and deletes the release.
You should also remove the deploy key from your GitHub repository.

### Configuration

The following tables lists the configurable parameters of the Chart-updater chart and their default values.

This chart was inspired by the [Flux Helm chart](https://github.com/fluxcd/flux/tree/master/chart/flux) so that option names should be similar.


| Parameter                                         | Default                                              | Description
| -----------------------------------------------   | ---------------------------------------------------- | ---
| `image.repository`                                | `docker.io/rossumai/chart-updater`                   | Image repository
| `image.tag`                                       | `<VERSION>`                                          | Image tag
| `replicaCount`                                    | `1`                                                  | Number of Chart-updater pods to deploy, more than one is not desirable.
| `image.pullPolicy`                                | `IfNotPresent`                                       | Image pull policy
| `image.pullSecret`                                | `None`                                               | Image pull secret
| `resources.requests.cpu`                          | `50m`                                                | CPU resource requests for the Chart-updater deployment
| `resources.requests.memory`                       | `64Mi`                                               | Memory resource requests for the Chart-updater deployment
| `resources.limits`                                | `None`                                               | CPU/memory resource limits for the Chart-updater deployment
| `nodeSelector`                                    | `{}`                                                 | Node Selector properties for the Chart-updater deployment
| `tolerations`                                     | `[]`                                                 | Tolerations properties for the Chart-updater deployment
| `affinity`                                        | `{}`                                                 | Affinity properties for the Chart-updater deployment
| `extraEnvs`                                       | `[]`                                                 | Extra environment variables for the Chart-updater pod(s)
| `env.secretName`                                  | ``                                                   | Name of the secret that contains environment variables which should be defined in the Chart-updater container (using `envFrom`)
| `serviceAccount.create`                           | `false`                                              | If `true`, create a new service account
| `serviceAccount.name`                             | `chart-updater`                                      | Service account to be used
| `service.type`                                    | `ClusterIP`                                          | Service type to be used (exposing the Chart-updater API outside of the cluster is not advised)
| `service.port`                                    | `3030`                                               | Service port to be used
| `git.url`                                         | `None`                                               | URL of git repo with Kubernetes manifests
| `git.branch`                                      | `master`                                             | Branch of git repo to use for Kubernetes manifests
| `git.path`                                        | `None`                                               | Path within git repo to locate Kubernetes manifests (relative path)
| `git.user`                                        | `Chart Sync`                                         | Username to use as git committer
| `git.email`                                       | `chart-sync@rossum.ai`                               | Email to use as git committer
| `git.pollInterval`                                | `60`                                                 | Period at which to poll git repo for new commits (seconds)
| `git.timeout`                                     | `30`                                                 | Duration after which git operations time out (seconds)
| `git.secretName`                                  | `None`                                               | Kubernetes secret with the SSH private key.
| `ssh.known_hosts`                                 | `None`                                               | The contents of an SSH `known_hosts` file, if you need to supply host key(s)
| `helm.url`                                        | `None`                                               | URL of Helm repository to scan (e.g. https://github.io/username/charts)
| `helm.username`                                   | `None`                                               | Basic authentication username for the Helm repository
| `helm.password`                                   | `None`                                               | Basic authentication password for the Helm repository

Specify each parameter using the `--set key=value[,key=value]` argument to `helm install`. For example:

```sh
helm upgrade -i chart-updater \
--set git.url=git@github.com:stefanprodan/k8s-podinfo \
--set git.path="auto-deploy" \
--namespace flux \
rossuai/chart-updater
```

### Upgrade

Update Chart-updater with:

```sh
helm upgrade --reuse-values chart-updater \
--set image.tag=1.0.2 \
rossumai/chart-updater
```
