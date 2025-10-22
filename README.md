# BotA_Termux

A stable Termux-based Forex bot that runs on Android (no server needed).  
It fetches EURUSD and GBPUSD every 15 minutes and sends signals to Telegram.

---

## 🔧 Setup (one time)

```bash
pkg install git python cronie -y
pip install -r requirements.txt

cat > README.md <<'MD'
