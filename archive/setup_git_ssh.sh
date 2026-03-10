#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# ── Fixed to your credentials ───────────────────────────
GH_USER="Ciupanezulflipper"
GH_EMAIL="tomagm2010@gmail.com"
REPO_NAME="toma-bot-a"         # change if you want a different repo
REPO_VISIBILITY="private"      # reminder only
GIT_DISPLAY_NAME="Ciupanezul81@git"
# ────────────────────────────────────────────────────────

pkg update -y >/dev/null 2>&1 || true
pkg install -y git openssh >/dev/null

mkdir -p ~/.ssh && chmod 700 ~/.ssh

# 1) Trust GitHub SSH host keys (so no interactive prompt later)
cat > ~/.ssh/known_hosts <<'KH'
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
github.com ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBEmKSENjQEezOmxkZMy7opKgwFB9nkt5YRrYMjNuG5N87uRgg6CLrbo5wAdT/y6v0mKV0U2w0WZ2YB/++Tpockg=
github.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj7ndNxQowgcQnjshcLrqPEiiphnt+VTTvDP6mHBL9j1aNUkY4Ue1gvwnGLVlOhGeYrnZaMgRK6+PKCUXaDbC7qtbW8gIkhL7aGCsOr/C56SJMy/BCZfxd1nWzAOxSDPgVsmerOBYfNqltV9/hWCqBywINIR+5dIg6JTJ72pcEpEjcYgXkE2YEFXV1JHnsKgbLWNlhScqb2UmyRkQyytRLtL+38TGxkxCflmO+5Z8CSSNY7GidjMIZ7Q4zMjA2n1nGrlTDkzwDCsw+wqFPGQA179cnfGWOWRVruj16z6XyvxvjJwbz0wQZ75XK5tKSb7FNyeIEs4TT4jk+S4dhPeAUC5y+bDYirYgM4GC7uEnztnZyaVWQ7B381AK4Qdrwt51ZqExKbQpTUNn+EjqoTwvqNj4kqx5QUCI0ThS/YkOxJCXmPUWZbhjpCg56i+2aB6CmK2JGhn57K5mj0MNdBXA4/WnwH6XoPWJzK5Nyu2zB3nAZp+S5hpQs+p1vN1/wsjk=
KH
chmod 644 ~/.ssh/known_hosts

# 2) Force SSH over port 443 (works better on filtered Wi-Fi)
mkdir -p ~/.ssh
cat > ~/.ssh/config <<'CFG'
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_github_ed25519
  IdentitiesOnly yes
  PreferredAuthentications publickey
CFG
chmod 600 ~/.ssh/config

# 3) Generate an ed25519 key (comment = your email)
if [ ! -f ~/.ssh/id_github_ed25519 ]; then
  ssh-keygen -t ed25519 -C "tomagm2010@gmail.com" -f ~/.ssh/id_github_ed25519 -N ""
fi
chmod 600 ~/.ssh/id_github_ed25519

# 4) Start agent + add key
eval "$(ssh-agent -s)" >/dev/null
ssh-add ~/.ssh/id_github_ed25519 >/dev/null

# 5) Git identity (name shown on commits, email used for attribution)
git config --global user.name  "${GIT_DISPLAY_NAME}"
git config --global user.email "${GH_EMAIL}"
git config --global init.defaultBranch main

# 6) Show public key for GitHub → Settings → SSH and GPG keys → New SSH key
echo
echo "────────────────────────────────────────────────────────"
echo "SSH public key — copy everything below into GitHub:"
echo "Title: Termux-$(uname -n)-$(date +%Y%m%d)"
echo "────────────────────────────────────────────────────────"
cat ~/.ssh/id_github_ed25519.pub
echo "────────────────────────────────────────────────────────"
echo "Next: create an EMPTY repo named: ${REPO_NAME} (private)"
echo "URL: https://github.com/new"
echo
echo "When both are done, run:  ~/BotA/tools/first_push.sh"
