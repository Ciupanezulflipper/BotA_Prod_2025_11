path = "/data/data/com.termux/files/home/BotA/tools/quality_filter.py"
with open(path) as f:
    src = f.read()

insert_after = '            gating_flags.append("extended_move")\n'
patch = '''
    # 9) Trend alignment penalty
    trend_penalty = safe_float(os.environ.get("TREND_OPPOSITE_PENALTY", "0.85"), 0.85)
    if "H1_trend_opposite" in reasons:
        old_score = score
        score = score * trend_penalty
        filter_reasons.append(f"trend_opposite_penalty={old_score:.1f}->{score:.1f}")
        log(f"trend_opposite_penalty applied: {old_score:.1f} -> {score:.1f}")
        if score < score_min:
            gating_flags.append("score_below_min_after_trend_penalty")
            filter_reasons.append(f"score<{int(score_min)}_after_trend_penalty")

'''
if "trend_opposite_penalty" in src:
    print("ALREADY PATCHED")
elif insert_after not in src:
    print("INSERTION POINT NOT FOUND")
else:
    with open(path, 'w') as f:
        f.write(src.replace(insert_after, insert_after + patch, 1))
    print("PATCHED OK")
