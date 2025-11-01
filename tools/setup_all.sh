# Create token, env sync, and run scripts
bash -c "$(curl -fsSL https://raw.githubusercontent.com/TomaForex/scripts/main/tele_env_sync_v2.sh)"
bash -c "$(curl -fsSL https://raw.githubusercontent.com/TomaForex/scripts/main/token_smoke_v2.sh)"
bash -c "$(curl -fsSL https://raw.githubusercontent.com/TomaForex/scripts/main/run_bot_v2.sh)"
