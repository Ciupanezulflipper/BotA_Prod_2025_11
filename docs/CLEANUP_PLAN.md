# BotA Safe Cleanup Plan
# Generated: 2026-02-24
# Status: APPROVED FOR EXECUTION — review each section before running

## ALREADY DONE
- logs/step38C_find_cache_producers_20260210_124714.txt — DELETED (341MB)
- logs/_trace.err — DELETED (45MB)
- Total reclaimed: 384MB

---

## SAFE TO DELETE IMMEDIATELY (no archive needed)
These are debug probe outputs from old sessions. Not in call tree. Not referenced anywhere.

### logs/tmp/ debug outputs (~9MB)
rm ~/BotA/logs/tmp/step_fix_watcher_*.out
rm ~/BotA/logs/tmp/step_fix_watcher_*.txt
rm ~/BotA/logs/tmp/step64_terminal.txt
rm ~/BotA/logs/tmp/step68_terminal.txt
# KEEP: logs/tmp/*.png (test charts from this session)
# KEEP: logs/tmp/trades_*.csv (resolver outputs)

### Old audit directories (~220KB)
# BotA_audit_20251004_1415Z — already has .tgz companion, directory is redundant
rm -rf ~/BotA/BotA_audit_20251004_1415Z
rm -rf ~/BotA/botA_audit_20251004_1425Z
rm -rf ~/BotA/backup_20251004_1421Z

### Old config backups (~232KB)
# 5 identical config snapshots from Oct 30 2025 — all predating current config
rm -rf ~/BotA/config.backup-20251030T000227Z
rm -rf ~/BotA/config.backup-20251030T002605Z
rm -rf ~/BotA/config.backup-20251030T004319Z
rm -rf ~/BotA/config.backup-20251030T004841Z
rm -rf ~/BotA/config.backup-20251030T004910Z

### Test charts directory (~60KB)
rm -rf ~/BotA/charts_test/

---

## REVIEW BEFORE DELETING

### backups/ (8.8MB)
# Check contents before touching:
# ls -lh ~/BotA/backups/
# If all files are .tgz snapshots older than Oct 2025 — safe to delete after confirming
# config/strategy.env is not inside any of them unencrypted

### backup/ (511KB)
# ls -lh ~/BotA/backup/
# Same check — confirm no live credentials inside

### forks/ (203KB)
# Contains Forex_Signal_Bot fork — never referenced by call tree
# ls ~/BotA/forks/
# Safe to delete after confirming nothing in tools/ imports from it

---

## DO NOT TOUCH — LIVE CALL TREE
~/BotA/tools/signal_watcher_pro.sh
~/BotA/tools/m15_h1_fusion.sh
~/BotA/tools/scoring_engine.sh
~/BotA/tools/quality_filter.py
~/BotA/tools/market_open.sh
~/BotA/tools/news_sentiment.py
~/BotA/config/strategy.env
~/BotA/tools/indicators_updater.sh
~/BotA/tools/signal_accuracy.py
~/BotA/tools/alerts_to_trades.py
~/BotA/tools/provider_health_check.sh
~/BotA/logs/alerts.csv
~/BotA/logs/accuracy.csv
~/BotA/cache/

---

## ONGOING LOG ROTATION (already in place)
- log_rotate.sh handles cron logs
- alerts.csv: keep all (trade history — do not rotate)
- cron.signals.log: 16MB — monitor, rotate if exceeds 50MB
- tg_control.log: 6.7MB — monitor
- fusion.debug.log: 2.1MB — consider disabling debug mode in m15_h1_fusion.sh

