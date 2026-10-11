#!/usr/bin/env bash
# Worktree prune audit. Classifies every git worktree by size, merge state,
# uncommitted work, remote/PR state, and the most recent Claude session that
# operated in it. Emits a table sorted by size with a suggested bucket. Never
# deletes anything; deletion stays a human-gated step in the playbook. The only
# write is `git fetch origin main`, which refreshes origin/main for the merge check.
#
# Usage: worktree-audit.sh [repo-path]   (defaults to the current repo)
set -u

repo="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$repo" ] && { echo "not in a git repo; pass a repo path" >&2; exit 1; }
cd "$repo" || exit 1

# Main worktree is the first entry; everything else is a candidate.
main_wt=$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')

# origin/main drives the merge check. Best-effort; stale is fine for a first pass.
git fetch origin main --quiet 2>/dev/null || echo "warn: could not fetch origin/main; merged column may be stale" >&2

# PR state by branch, fetched once. Empty if gh is unavailable.
prs=$(mktemp)
gh pr list --author "@me" --state all --limit 1000 \
	--json number,state,headRefName,headRefOid 2>/dev/null > "$prs" || echo "[]" > "$prs"

# Transcript dirs: Claude keeps one per working directory under
# ${CLAUDE_CONFIG_DIR:-~/.claude}/projects, named for the cwd with every
# character outside [A-Za-z0-9] turned into "-". A name over 200 characters is
# cut to 200 plus a hash suffix. Subagent transcripts sit in
# <session>/subagents/ inside the same dir. T3 threads run Claude with their
# worktree as the cwd, and T3 creates worktrees under ~/.t3/worktrees/<repo>/
# (or the folder set in its Storage settings), so scan the dir of every
# checkout of this repo, not only the main one.
projects="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
transcripts=()
while read -r p; do
	enc=$(printf '%s' "$p" | sed 's/[^a-zA-Z0-9]/-/g')
	[ ${#enc} -gt 200 ] && enc="${enc:0:200}-*"
	for d in "$projects"/$enc; do [ -d "$d" ] && transcripts+=("$d"); done
done < <(git worktree list --porcelain | awk '/^worktree /{print $2}')
command -v rg >/dev/null 2>&1 || echo "warn: rg not found; LAST_CHAT is empty, so check every row by hand" >&2
now=$(date +%s)

printf "SIZE\tAGE\tMERGED\tDIRTY\tREMOTE\tPR\tLAST_CHAT\tBUCKET\tWORKTREE\n"

git worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r wt; do
	[ "$wt" = "$main_wt" ] && continue

	size=$(du -sh "$wt" 2>/dev/null | awk '{print $1}')
	head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
	head_ts=$(git -C "$wt" log -1 --format='%ct' HEAD 2>/dev/null || echo 0)
	age=$([ "$head_ts" -gt 0 ] 2>/dev/null && echo "$(( (now - head_ts) / 86400 ))d" || echo "?")

	# Squash-merged branches are not ancestors of main, so PR state is the
	# real signal; merge-base only catches fast-forward/rebase merges.
	git merge-base --is-ancestor "$head" origin/main 2>/dev/null && merged=YES || merged=no

	# Everything that exists only in this folder is work at stake: tracked edits,
	# untracked files, and ignored files (.env, logs, build output). A plain
	# `git worktree remove` deletes ignored files without asking, so they count
	# too. --untracked-files=all beats a status.showUntrackedFiles=no config.
	# When git cannot read the folder, nothing is known, so hold it.
	if porcelain=$(git -C "$wt" status --porcelain --untracked-files=all --ignored=matching \
		--ignore-submodules=none 2>/dev/null); then
		wip=$(printf '%s\n' "$porcelain" | grep -cvE '^(\?\?|!!) |^$')
		untracked=$(printf '%s\n' "$porcelain" | grep -c '^?? ')
		ignored=$(printf '%s\n' "$porcelain" | grep -c '^!! ')
		dirty=""
		[ "$wip" -gt 0 ] && dirty="wip:$wip"
		[ "$untracked" -gt 0 ] && dirty="${dirty:+$dirty,}untracked:$untracked"
		[ "$ignored" -gt 0 ] && dirty="${dirty:+$dirty,}ignored:$ignored"
		[ -z "$dirty" ] && dirty=clean
	else dirty=unknown; fi

	branch=$(git -C "$wt" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")
	if [ -z "$branch" ]; then remote=detached
	elif git -C "$wt" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
		ahead=$(git -C "$wt" rev-list --count "origin/$branch..HEAD" 2>/dev/null)
		if [ "$(git -C "$wt" rev-parse "origin/$branch" 2>/dev/null)" = "$head" ]; then remote=pushed
		elif [ "$ahead" = 0 ]; then remote=behind
		else remote="ahead$ahead"; fi
	else remote=no-remote; fi

	pr=$([ -n "$branch" ] && jq -r --arg b "$branch" \
		'.[] | select(.headRefName==$b) | "#\(.number)/\(.state)"' "$prs" 2>/dev/null | head -1)
	[ -z "$pr" ] && pr="-"

	# Most recent session whose transcript operated in this worktree. Match path
	# followed by "/" or a quote so glint-482 does not match glint-482-r37.
	last="-"; last_ts=0
	if [ ${#transcripts[@]} -gt 0 ]; then
		f=$(rg -l -F --no-ignore --hidden -e "${wt}/" -e "${wt}\"" "${transcripts[@]}" 2>/dev/null \
			| xargs stat -f '%m %N' 2>/dev/null | sort -rn | head -1)
		if [ -n "$f" ]; then last_ts=$(echo "$f" | awk '{print $1}')
			last=$(date -r "$last_ts" '+%Y-%m-%d' 2>/dev/null); fi
	fi
	recent=$([ "$last_ts" -gt 0 ] 2>/dev/null && [ $(( (now - last_ts) / 86400 )) -le 4 ] && echo yes || echo no)

	# Only ancestry of origin/main, or a MERGED PR whose head is this exact
	# commit, proves the work lives elsewhere. A CLOSED PR proves nothing, and
	# commits ahead of the remote, on no remote branch, or detached off main
	# exist only here.
	pr_merged=$([ -n "$branch" ] && [ -n "$head" ] && jq -r --arg b "$branch" --arg h "$head" \
		'any(.[]; .headRefName==$b and .state=="MERGED" and .headRefOid==$h)' "$prs" 2>/dev/null)
	case "$remote" in ahead*|no-remote|detached) unpushed=yes ;; *) unpushed=no ;; esac
	[ "$merged" = YES ] && unpushed=no

	case "$dirty" in wip:*|unknown) bucket=hold-wip ;; *)
		case "$dirty" in *untracked:*|*ignored:*) bucket=hold-local ;; *)
			case "$pr" in *OPEN*) bucket=hold-open-pr ;; *)
				if [ "$unpushed" = yes ]; then bucket=hold-unpushed
				elif [ "$recent" = yes ]; then bucket=verify-recent-chat
				elif [ "$merged" = YES ] || [ "$pr_merged" = true ]; then bucket=safe
				else bucket=review; fi ;;
			esac ;;
		esac ;;
	esac

	printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
		"$size" "$age" "$merged" "$dirty" "$remote" "$pr" "$last" "$bucket" "$wt"
done | sort -t$'\t' -k1,1 -rh

rm -f "$prs"
