GitHub PAT Rotation — Termux (no downtime)

What this delivers
- tools/github_token_rotate.sh — safely rotate your Personal Access Token (classic or fine-grained) and store it in ~/.git-credentials.
- tools/github_token_check.sh  — quick auth smoke test (no push).
- Works with any local repo (ex: ~/BotA, ~/forex_profit_lab). Keeps remotes HTTPS.

Prereqs (once)
1) On GitHub > Settings > Developer settings > Personal access tokens:
   - Regenerate or create a new token with at least "repo" scope (for private pushes).
   - Copy the token string (keep secret).

How to rotate (every time the token changes)
1) Export your GitHub username, email, and the NEW token (paste between single quotes):
   export GITHUB_USER='your_username'
   export GITHUB_EMAIL='you@example.com'
   export NEW_PAT='ghp_xxx…'   # or fine-grained token

2) Run the rotator (idempotent):
   $HOME/BotA/tools/github_token_rotate.sh  ~/BotA

   # You can pass multiple repos in one go, e.g.:
   $HOME/BotA/tools/github_token_rotate.sh  ~/BotA  ~/forex_profit_lab

3) Smoke test (auth only, no write):
   $HOME/BotA/tools/github_token_check.sh  ~/BotA

What the script does
- Backs up ~/.git-credentials (date-stamped) before changing.
- Ensures: git config --global credential.helper store
- Writes a single prefix credential line: https://GITHUB_USER:NEW_PAT@github.com
- Normalizes each repo’s 'origin' to HTTPS if needed.
- Validates with 'git ls-remote' and prints PASS/FAIL per repo.

Acceptance criteria
- Running rotate + check prints PASS for each repo.
- A file ~/.git-credentials exists and contains exactly one github.com line.
- Subsequent 'git push' in your repos completes without auth prompts.

Security notes
- ~/.git-credentials is plain text. Your device is single-user Termux; keep it locked.
- If you lose the phone, immediately revoke the token on GitHub.
