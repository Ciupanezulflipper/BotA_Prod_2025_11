# … after primary decision …
if os.getenv("ENABLE_MULTI_TF","false").lower()=="true":
    for higher_tf in ["H1","H4","D1"]:
        candles_htf, src_htf = fetch_candles(pair, higher_tf, limit=200)
        act_htf, score_htf, reason_htf = decide(candles_htf, higher_tf)
        print(f"[info] MultiTF {pair} {higher_tf} → {act_htf} (score {score_htf})")
        if act_htf == action and action in ("BUY","SELL"):
            card2 = compose_card(pair, higher_tf, action, score_htf, reason_htf, src_htf)
            ok2, err2 = send_alert("⚡️ Fusion " + card2)
            if ok2: print("✅ Fusion alert sent.")
