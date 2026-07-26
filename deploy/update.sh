#!/usr/bin/env bash
# Pull the latest code before the service starts.
# Run as ExecStartPre by morning-dust.service, so it must never be the reason
# the dashboard fails to come up: every failure path exits 0 and leaves the
# working tree on whatever commit is already checked out.
set -u

# The pull below can rewrite this very file, and bash reads scripts lazily —
# a changed file under a running shell garbles the rest. Re-exec from a copy
# outside the repo so the pull can't touch what we're executing. The repo path
# has to travel in the environment: from /tmp, $0 no longer points at it.
if [[ "${MD_REPO:-}" == "" ]]; then
    MD_REPO="$(cd "$(dirname "$0")/.." && pwd)" || exit 0
    COPY="$(mktemp)" || exit 0
    cp "$0" "$COPY" && chmod +x "$COPY" || { rm -f "$COPY"; exit 0; }
    MD_REPO="$MD_REPO" "$COPY"
    rm -f "$COPY"
    exit 0
fi

cd "$MD_REPO" || exit 0

# A dirty tree means someone edited on the Pi. Pulling would either fail or
# clobber that, so leave it alone and say so in the journal.
if [[ -n "$(git status --porcelain)" ]]; then
    echo "update: working tree is dirty, skipping pull" >&2
    exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" == "HEAD" ]]; then
    echo "update: detached HEAD, skipping pull" >&2
    exit 0
fi

BEFORE="$(git rev-parse HEAD)"

# Don't hang the boot on a network that isn't up yet or a host key prompt.
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10"
if ! timeout 60 git pull --ff-only origin "$BRANCH"; then
    echo "update: pull failed, starting on $BEFORE" >&2
    exit 0
fi

AFTER="$(git rev-parse HEAD)"
if [[ "$BEFORE" == "$AFTER" ]]; then
    echo "update: already up to date at $AFTER"
else
    echo "update: $BEFORE -> $AFTER"
fi
exit 0
