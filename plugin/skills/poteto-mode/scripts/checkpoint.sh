#!/usr/bin/env bash
# Pause checkpoint. Pause safely saves one after it commits and writes the
# resume note; Session pickup verifies it before trusting the note.
#
# Usage: checkpoint.sh save <slug> [--todo <file>]
#        checkpoint.sh verify <slug>
#
# Both run from the repo or any of its worktrees. The checkpoint is
# <main checkout>/.jutsu/<slug>/checkpoint, beside resume.md, so it survives T3
# deleting the worktree. It records the worktree, branch, head commit, and the
# sha256 of resume.md and the todo file (default .audit/<slug>.todo.md in the
# main checkout, when it exists).
#
# save fails, writing nothing, when the worktree has uncommitted or untracked
# files, when HEAD is detached (its commits go with the worktree), or when
# resume.md is missing. It prints the checkpoint's absolute path.
#
# verify prints one line per fact, "ok:", "changed:", or "gone:", and exits 0
# when every fact still holds, 1 when something differs (read those lines
# before trusting the note), and 2 when there is no checkpoint.
#
# Idea from pstack-claude's resume.mjs (MIT).
set -u

die() { echo "error: $*" >&2; exit "${2:-1}"; }
hash_of() {
	if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
	else shasum -a 256 "$1" | awk '{print $1}'; fi
}
dirty_count() { git -C "$1" status --porcelain --untracked-files=all --ignore-submodules=none 2>/dev/null | grep -c .; }
field() { sed -n "s/^$1: //p" "$checkpoint" | head -1; }

cmd="${1:-}"; slug="${2:-}"
case "$cmd" in save|verify) ;; -h|--help) sed -n '2,/^set -u/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
*) die "usage: checkpoint.sh save|verify <slug> [--todo <file>]" 2 ;; esac
[ -n "$slug" ] || die "missing <slug>" 2
case "$slug" in */*|.*) die "slug must be a plain name: $slug" 2 ;; esac
shift 2
todo=""
while [ $# -gt 0 ]; do
	case "$1" in
	--todo) [ $# -ge 2 ] || die "--todo needs a file" 2; todo="$2"; shift 2 ;;
	*) die "unknown argument: $1" 2 ;;
	esac
done

common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || die "not in a git repo"
main=$(dirname "$common")
store="$main/.jutsu/$slug"
checkpoint="$store/checkpoint"

if [ "$cmd" = save ]; then
	worktree=$(git rev-parse --show-toplevel) || die "not in a worktree"
	[ -f "$store/resume.md" ] || die "write $store/resume.md first (Pause safely step 4)"
	branch=$(git symbolic-ref --quiet --short HEAD) \
		|| die "HEAD is detached, and its commits go with the worktree. Create a branch first: git switch -c <name>"
	head=$(git rev-parse HEAD) || die "no commit at HEAD"
	dirty=$(dirty_count "$worktree")
	[ "$dirty" = 0 ] || die "$dirty uncommitted or untracked path(s) in $worktree. Commit them as one wip: commit first (Pause safely step 3)"
	[ -n "$todo" ] || todo="$main/.audit/$slug.todo.md"
	case "$todo" in /*) ;; *) todo="$PWD/$todo" ;; esac
	tmp="$checkpoint.tmp.$$"
	{
		echo "created: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
		echo "worktree: $worktree"
		echo "branch: $branch"
		echo "head: $head"
		echo "dirty: 0"
		echo "note: resume.md $(hash_of "$store/resume.md")"
		[ -f "$todo" ] && echo "todo: $todo $(hash_of "$todo")"
	} > "$tmp" && mv "$tmp" "$checkpoint" || { rm -f "$tmp"; die "could not write $checkpoint"; }
	echo "$checkpoint"
	exit 0
fi

[ -f "$checkpoint" ] || { echo "missing: no checkpoint at $checkpoint"; exit 2; }
status=0
fail() { echo "$1"; status=1; }

branch=$(field branch); head=$(field head); worktree=$(field worktree)
echo "checkpoint: $checkpoint (saved $(field created))"
if ! git cat-file -e "$head^{commit}" 2>/dev/null; then
	fail "gone: commit $head is not in this repo"
elif ! tip=$(git rev-parse --verify --quiet "refs/heads/$branch"); then
	fail "gone: branch $branch was deleted; the paused commit is $head"
elif [ "$tip" = "$head" ]; then
	echo "ok: $branch is at ${head:0:12}, as paused"
elif git merge-base --is-ancestor "$head" "$tip"; then
	fail "changed: $branch is $(git rev-list --count "$head..$tip") commit(s) ahead of the pause (${head:0:12}); read them before resuming"
else
	fail "changed: $branch no longer contains the paused commit ${head:0:12} (rebased or reset); compare before resuming"
fi

if [ ! -d "$worktree" ]; then
	fail "gone: worktree $worktree (T3 cleanup or a manual remove). Resume from branch $branch in a new worktree"
else
	at=$(git -C "$worktree" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "detached")
	[ "$at" = "$branch" ] || fail "changed: worktree $worktree is on $at, not $branch"
	n=$(dirty_count "$worktree")
	[ "$n" = 0 ] || fail "changed: worktree has $n uncommitted path(s); another writer may still run"
fi

note_hash=$(field note | awk '{print $2}')
if [ ! -f "$store/resume.md" ]; then fail "gone: note $store/resume.md"
elif [ "$(hash_of "$store/resume.md")" = "$note_hash" ]; then echo "ok: note $store/resume.md"
else fail "changed: note $store/resume.md was edited after the pause"; fi

todo_line=$(field todo)
if [ -n "$todo_line" ]; then
	todo_path=${todo_line% *}; todo_hash=${todo_line##* }
	if [ ! -f "$todo_path" ]; then fail "gone: todo $todo_path"
	elif [ "$(hash_of "$todo_path")" = "$todo_hash" ]; then echo "ok: todo $todo_path"
	else fail "changed: todo $todo_path was edited after the pause"; fi
fi
exit "$status"
