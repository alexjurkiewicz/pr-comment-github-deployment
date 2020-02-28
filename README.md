# GitHub Action for PR Comment -> GitHub Deployment Workflow

This is a GitHub Action. You can use it to watch your pull requests for comments with a certain trigger phrase, which will trigger a [deployment](https://developer.github.com/v3/repos/deployments/).

## Example

```yaml
on: issue_comment

jobs:
  deploy:
    steps:
      - uses: alexjurkiewicz/pr-comment-github-deployment@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Parameters

| Parameter | Required | Description |
| --- | --- | --- |
| trigger_phrase | Optional. Default: `deploy to` | Trigger phrase you want to activate on. This action will take the remainder of the comment body as the environment, eg a message of `deploy to web3` will trigger a deployment to `web3`. |
| environment_validation_file | Optional. Default: unset | If specified, this is a JSON file in your repository that defines a whitelist of acceptable environments, as well as metadata about them. [See below for more info.](#environment_validation_file) |
| allow_draft | Optional. Default: `false` | If set to `true`, you can deploy draft PRs. |
| ignore_status_checks | Optional. Default: `false` | If set to `true`, you can deploy PRs with pending/failed status checks. |
| comment | Optional. Default: `true` | If set to `false`, comments will not be posted to the pull request. |

### Environment Variables

You must pass in `GITHUB_TOKEN`. It requires read & write access to both the head and base repositories of the pull request.

## Outputs

If you give this action's step an `id`, you can access the following outputs:

| Output  | Description |
| --- | --- |
| deployment_id | GitHub's ID for this deployment. |
| deployment_api_url | [URL to read deployment information.](https://developer.github.com/v3/repos/deployments/#get-a-single-deployment) |

## `environment_validation_file`

The purpose of this file is to prevent deployments to non-existent / restricted environments. Use a format like this:

```js
[
  {
    "name": "production", // Required.
    "transient": false,   // Optional (default: false). Specifies if the given
                          // environment is specific to the deployment and will
                          // no longer exist at some point in the future.
    "production": true,   // Optional (default: false). Specifies if the given
                          // environment is one that end-users directly interact
                          // with.
  },
  { "name": "test" },
  { "name": "test-temp", "transient": true }
]
```

## Release Policy

This GitHub Action follows will never break backwards compatibility. Use `master` as the version specifier for this action in your workflows.

(If backwards compatibility has to be broken, a new repository will be started.)
