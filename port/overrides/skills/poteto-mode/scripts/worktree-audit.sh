#!/usr/bin/env bash
# Worktree prune audit. Classifies every git worktree by size, merge state,
# uncommitted work, remote/PR state, and the most recent Claude session that
# operated in it. Emits a table sorted by size with a suggested bucket. Never
# deletes anything; deletion stays a human-gated step in the playbook. The only
# write is the best-effort fetch of the base ref for the merge check
# (`git fetch origin main` when the base is origin/main).
#
# Usage: worktree-audit.sh [-b|--base <ref>] [repo-path]
#   repo-path defaults to the current repo.
#   -b sets the ref the MERGED column checks against (e.g. origin/integration).
#   Without it the base is origin/HEAD, then origin/main, then origin/master.
#   origin/HEAD is the remote's default branch, not necessarily the branch PRs
#   merge into; pass -b when they differ.
set -u

base=""
while [ $# -gt 0 ]; do
	case "$1" in
	-b|--base) [ $# -ge 2 ] || { echo "error: $1 needs a ref" >&2; exit 2; }; base="$2"; shift 2 ;;
	-h|--help) sed -n '2,/^set -u/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
	-*) echo "error: unknown option: $1" >&2; exit 2 ;;
	*) break ;;
	esac
done

repo="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$repo" ] && { echo "not in a git repo; pass a repo path" >&2; exit 1; }
cd "$repo" || exit 1
git rev-parse --git-dir >/dev/null 2>&1 || { echo "error: not a git repo: $repo" >&2; exit 1; }

# Main worktree is the first entry; everything else is a candidate.
main_wt=$(git worktree list --porcelain | awk '/^worktree /{print $2; exit}')

if [ -z "$base" ]; then
	for cand in "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" origin/main origin/master; do
		[ -n "$cand" ] && git rev-parse --verify --quiet "$cand^{commit}" >/dev/null && { base="$cand"; break; }
	done
	[ -z "$base" ] && { echo "error: no base ref (origin/HEAD, origin/main, origin/master all missing); pass -b <ref>" >&2; exit 1; }
	echo "warn: no -b given; MERGED checks against $base" >&2
fi

# The base drives the merge check. The fetch is best-effort (stale is fine for
# a first pass) and runs before the check, since -b may name a branch not
# fetched yet. The explicit refspec creates it even in a single-branch clone.
case "$base" in
origin/*) git fetch origin "+refs/heads/${base#origin/}:refs/remotes/$base" --quiet 2>/dev/null \
	|| echo "warn: could not fetch $base; merged column may be stale" >&2 ;;
esac
git rev-parse --verify --quiet "$base^{commit}" >/dev/null 2>&1 || { echo "error: base ref not found: $base" >&2; exit 1; }

# PR state by branch, fetched once as [{number, state, head, oid}] with a
# lowercase state. Origin when its CLI can read this repo's PRs, otherwise gh.
# Empty when neither can. oid is the PR's head commit, null when unknown.
prs=$(mktemp)
if command -v origin >/dev/null 2>&1 \
	&& raw=$(origin pr list --author "@me" --state all --limit 1000 \
		--json number,status,headRef 2>/dev/null); then
	printf '%s' "$raw" | jq '[.[] | {number, state: .status, head: .headRef, oid: null}]' > "$prs" 2>/dev/null
elif raw=$(gh pr list --author "@me" --state all --limit 1000 \
	--json number,state,headRefName,headRefOid 2>/dev/null); then
	printf '%s' "$raw" | jq '[.[] | {number, state: (.state | ascii_downcase), head: .headRefName, oid: .headRefOid}]' > "$prs" 2>/dev/null
fi
[ -s "$prs" ] || echo "[]" > "$prs"

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

echo "# base: $base"
printf "SIZE\tAGE\tMERGED\tDIRTY\tREMOTE\tPR\tLAST_CHAT\tBUCKET\tWORKTREE\n"

git worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r wt; do
	[ "$wt" = "$main_wt" ] && continue

	size=$(du -sh "$wt" 2>/dev/null | awk '{print $1}')
	head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
	head_ts=$(git -C "$wt" log -1 --format='%ct' HEAD 2>/dev/null || echo 0)
	age=$([ "$head_ts" -gt 0 ] 2>/dev/null && echo "$(( (now - head_ts) / 86400 ))d" || echo "?")

	# Squash-merged branches are not ancestors of the base, so PR state is the
	# real signal; merge-base only catches fast-forward/rebase merges.
	git merge-base --is-ancestor "$head" "$base" 2>/dev/null && merged=YES || merged=no

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

	# Several PRs can share a branch name; prefer the one whose head is HEAD.
	pr_record=$([ -n "$branch" ] && jq -r --arg b "$branch" --arg h "$head" \
		'[.[] | select(.head==$b)] | (map(select(.oid==$h)) + .)[0]
		| select(.) | "#\(.number)/\(.state)\t\(.oid // "")"' "$prs" 2>/dev/null)
	pr=${pr_record%%$'\t'*}
	pr_head=${pr_record#*$'\t'}
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

	# Only ancestry of the base, or a merged PR whose head is this exact commit,
	# proves the work lives elsewhere. A closed PR proves nothing about a merge.
	# Commits ahead of the remote, on no remote branch, or detached off the base
	# exist only here, unless HEAD is the head of one of the branch's PRs (the
	# remote branch was deleted after merging, or lives on a fork).
	pr_merged=$([ -n "$branch" ] && [ -n "$head" ] && jq -r --arg b "$branch" --arg h "$head" \
		'any(.[]; .head==$b and .state=="merged" and .oid==$h)' "$prs" 2>/dev/null)
	# A branch behind its merged PR's head is covered too: every commit here is
	# in that head. A head commit this clone does not have proves nothing.
	if [ "$pr_merged" != true ] && [ "$remote" = behind ]; then
		for oid in $(jq -r --arg b "$branch" '.[] | select(.head==$b and .state=="merged") | .oid // empty' "$prs" 2>/dev/null); do
			git -C "$wt" merge-base --is-ancestor "$head" "$oid" 2>/dev/null && { pr_merged=true; break; }
		done
	fi
	case "$remote" in ahead*|no-remote|detached) unpushed=yes ;; *) unpushed=no ;; esac
	[ "$merged" = YES ] && unpushed=no
	[ -n "$pr_head" ] && [ "$head" = "$pr_head" ] && unpushed=no

	case "$dirty" in wip:*|unknown) bucket=hold-wip ;; *)
		case "$dirty" in *untracked:*|*ignored:*) bucket=hold-local ;; *)
			case "$pr" in */open|*/draft) bucket=hold-open-pr ;; *)
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
