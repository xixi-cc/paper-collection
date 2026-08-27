# Repository publishing invariant

Every completed website update must be pushed to GitHub. This applies to paper
metadata, card links, UI code, styles, documentation, import tools, and build or
deployment configuration.

An update is not complete until all of the following hold:

1. Run `npm run lint` and `npm run build` for site-affecting changes.
2. Commit only the intended repository changes.
3. Push `main` to the configured GitHub `origin` without force.
4. Verify that `git rev-parse HEAD` equals `git ls-remote origin
   refs/heads/main`.
5. Verify the GitHub Actions / GitHub Pages result for the pushed commit.
6. When OpenAI Sites is also published, deploy the same validated source tree;
   GitHub synchronization remains mandatory and is never replaced by a Sites
   source push.

Preserve unrelated or untracked user files. If credentials, the push, CI,
Pages, or Sites deployment are ambiguous, stop and report the exact boundary.
