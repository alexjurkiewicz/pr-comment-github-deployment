#!/usr/bin/env python3

import json
import os
import sys

import requests


class DeploymentFailure(Exception):
    pass


def debug(msg: str) -> None:
    print(f"::debug::{msg}")


def error(msg: str) -> None:
    print(f"::error ::{msg}")


def add_comment(url: str, msg: str, is_error: bool = False) -> None:
    debug(f"Add comment to {url}")
    if is_error:
        error(msg)
    else:
        print(msg)
    if CONFIG["comment"]:
        comment_resp = requests.post(
            url, headers=BASE_GH_REQUEST_HEADERS, json={"body": msg}
        )
        debug(f"Response: {comment_resp.text}")
        comment_resp.raise_for_status()


def parse_message(comment: dict) -> str:
    """Load the environment from the message."""
    debug("Parse comment")
    message = comment["body"]
    author = comment["user"]["login"]

    if not message.startswith(CONFIG["trigger"]):
        print(
            f"Comment from {author} does not match the comment trigger (`{CONFIG['trigger']}`)."
        )
        sys.exit(0)

    environment = message[len(CONFIG["trigger"]) :].strip()

    if not environment:
        raise DeploymentFailure(
            f"No environment specified (usage: `{CONFIG['trigger']} environment`)."
        )

    return environment


def get_environment(environment: str) -> dict:
    if not CONFIG["env_file"]:
        return {"name": environment}
    debug("Get environment")
    envs = json.load(open(CONFIG["env_file"]))
    debug("Loaded environment validation file")
    for env in envs:
        name = env["name"]
        debug(f"Checking environment {name}")
        if name == environment:
            return env
    raise DeploymentFailure(
        f"Environment '{environment}' doesn't exist in CONFIG['env_file'] ({CONFIG['env_file']})."
    )


def load_pr(url: str) -> dict:
    debug("Requesting PR details")
    pr_resp = requests.get(
        CONFIG["pr_url"],
        headers={
            **BASE_GH_REQUEST_HEADERS,
            "Accept": "application/vnd.github.shadow-cat-preview+json, application/vnd.github.sailor-v-preview+json",
        },
    )
    debug(f"Response: {pr_resp.text}")
    pr_resp.raise_for_status()
    return pr_resp.json()


def check_commit(head_repo: str, sha: str) -> None:
    if CONFIG["ignore_status_checks"]:
        return
    debug(f"Checking commit status of {head_repo}#{sha}")
    status_url = f"https://api.github.com/repos/{head_repo}/commits/{sha}/status"
    status_resp = requests.get(status_url, headers=BASE_GH_REQUEST_HEADERS)
    debug(f"Response: {status_resp.text}")
    status_resp.raise_for_status()
    status = status_resp.json()

    state = status["state"]
    if state != "success":
        debug(f"Commit status is {state}")
        failed = "\n".join(["* %s" % s["context"] for s in status["statuses"]])
        raise DeploymentFailure(
            f"The following status checks are not green for {sha}:\n{failed}."
        )


def trigger_deployment(
    head_repo: str, ref: str, environment: dict, description: str
) -> None:
    url = f"https://api.github.com/repos/{head_repo}/deployments"
    debug(
        f"Triggering a deployment for {head_repo}#{ref} to {environment} with URL {url}"
    )
    transient = environment.get("transient", False)
    production = environment.get("production", True)
    params = {
        "ref": ref,
        "environment": environment["name"],
        "description": description,
        "transient_environment": transient,
        "production_environment": production,
    }
    if CONFIG["ignore_status_checks"]:
        params["required_contexts"] = []

    trigger_resp = requests.post(
        url,
        json=params,
        headers={
            **BASE_GH_REQUEST_HEADERS,
            "Accept": "application/vnd.github.ant-man-preview+json",
        },
    )
    debug(f"Response: {trigger_resp.text}")
    try:
        trigger_resp.raise_for_status()
    except:
        raise DeploymentFailure(f"Failed to trigger deployment ({trigger_resp.text})")

    set_deployment_outputs(trigger_resp)


def set_deployment_outputs(deployment_response):
    # Set outputs
    deployment = deployment_response.json()
    _id = deployment["id"]
    api_url = deployment["url"]
    print(f"::set-output name=deployment_id::{_id}")
    print(f"::set-output name=deployment_api_url::{api_url}")


def validate_pr(pr: dict) -> None:
    if pr["draft"] and not CONFIG["allow_draft"]:
        raise DeploymentFailure("Can't deploy draft PRs.")
    if pr["merged"] or pr["merged_by"]:
        raise DeploymentFailure("Can't deploy a merged PR.")
    if pr["state"] != "open":
        raise DeploymentFailure("Can't deploy a PR which isn't open.")
    mergeable_state = pr["mergeable_state"]
    if mergeable_state != "mergeable":
        if mergeable_state == "draft" and CONFIG["allow_draft"]:
            pass
        else:
            raise DeploymentFailure("PR can't be cleanly merged with base branch.")


def validate_event(event):
    if not event.get("issue"):
        error("This event doesn't seem to be an issue comment.")
        sys.exit(1)
    if event["action"] != "created":
        print("This is not a comment creation, ignoring.")
        sys.exit(0)
    if not event.get("issue").get("pull_request"):
        print("This is not a pull request comment, ignoring.")
        sys.exit(0)


def react_to_original_comment(event):
    debug("Adding reaction to original comment")
    comment_url = event["comment"]["url"]
    reaction_url = f"{comment_url}/reactions"
    reaction_resp = requests.post(
        reaction_url,
        json={"content": "rocket"},
        headers={
            **BASE_GH_REQUEST_HEADERS,
            "Accept": "application/vnd.github.squirrel-girl-preview+json",
        },
    )
    debug(f"Response: {reaction_resp.text}")
    reaction_resp.raise_for_status()


if __name__ == "__main__":
    if "GITHUB_ACTION" not in os.environ:
        error(
            r"Missing GITHUB_TOKEN environment variable. (hint: `env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}`)"
        )
        sys.exit(1)

    GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
    GITHUB_EVENT_PATH = os.environ["GITHUB_EVENT_PATH"]  # always set by GitHub Actions

    debug("Loaded environment")

    CONFIG = {
        "trigger": os.environ.get("INPUT_TRIGGER_PHRASE", "deploy to"),
        "env_file": os.environ.get("INPUT_ENVIRONMENT_VALIDATION_FILE"),
        "allow_draft": os.environ.get("INPUT_ALLOW_DRAFT_DEPLOY", "false").lower()
        == "true",
        "ignore_status_checks": os.environ.get(
            "INPUT_IGNORE_STATUS_CHECKS", "false"
        ).lower()
        == "true",
        "comment": os.environ.get("INPUT_COMMENT", "true").lower() == "true",
    }
    debug(f"Config: {json.dumps(CONFIG)}")

    BASE_GH_REQUEST_HEADERS = {
        "Authorization": "Bearer %s" % GITHUB_TOKEN,
        "Content-Type": "application/json",
    }

    event = json.load(open(GITHUB_EVENT_PATH))
    debug(f"Loaded event JSON: {json.dumps(event)}")

    validate_event(event)

    pr = load_pr(CONFIG["pr_url"])
    debug(f"Loaded PR details: {json.dumps(pr)}")
    sha = pr["head"]["sha"]
    head_repo = pr["head"]["repo"]["full_name"]
    pr_num = pr["number"]

    # We load the environment_name in a seperate try-except block so we can use
    # environment_name in further error messages
    try:
        validate_pr(pr)
        environment_name = parse_message(event["comment"])
    except DeploymentFailure as e:
        add_comment(pr["comments_url"], f"Deployment failed: {e}", is_error=True)
        sys.exit(1)

    try:
        environment = get_environment(environment_name)
        check_commit(head_repo, sha)
        trigger_deployment(
            head_repo=head_repo,
            ref=sha,
            environment=environment,
            description=f"Automatic deployment from #{pr_num}",
        )
    except DeploymentFailure as e:
        add_comment(
            pr["comments_url"],
            f"Deployment to {environment_name} failed: {e}",
            is_error=True,
        )
        sys.exit(1)
    else:
        react_to_original_comment(event)
        comment_author = event["comment"]["user"]["login"]
        add_comment(
            pr["comments_url"],
            f"@{comment_author}: Triggered [deployment](https://github.com/{head_repo}/deployments) to {environment_name}.",
            is_error=False,
        )

    debug("Finished.")
