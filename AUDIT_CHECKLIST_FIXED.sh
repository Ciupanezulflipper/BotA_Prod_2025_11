# ... (keeping everything same until line 108) ...

echo "3.2 409 Conflict Status"
CONFLICT_COUNT=$(grep "409" logs/telecontroller.log 2>/dev/null | wc -l)
echo "HTTP 409 errors: $CONFLICT_COUNT"
[[ $CONFLICT_COUNT -eq 0 ]] && echo "✅ No conflicts" || echo "⚠️  Found $CONFLICT_COUNT conflicts"
echo ""

# ... (rest of script) ...
