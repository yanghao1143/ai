#!/bin/bash
# Memory Integrity Check
# Inspired by SandyBlake's "Your Memory Is Your Attack Surface" on Moltbook
# Checks if memory files were modified outside of expected patterns

WORKSPACE="/home/jinyang/.openclaw/workspace"
cd "$WORKSPACE" || exit 1

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 Memory Integrity Check - $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ISSUES=0

# Check for unexpected modifications to critical files
CRITICAL_FILES="MEMORY.md HEARTBEAT.md AGENTS.md"
for f in $CRITICAL_FILES; do
    if [ -f "$f" ]; then
        # Check if modified since last git commit
        if git diff --name-only 2>/dev/null | grep -q "^$f$"; then
            LINES_CHANGED=$(git diff --stat "$f" 2>/dev/null | tail -1)
            echo "⚠️  $f has uncommitted changes: $LINES_CHANGED"
            ISSUES=$((ISSUES + 1))
        else
            echo "✅ $f — clean"
        fi
    fi
done

# Check memory directory for unexpected files
echo ""
echo "📁 Memory directory scan:"
KNOWN_PATTERNS="^(2025|2026|heartbeat|workflow|nightly|archive|cache|channels|context|evolution|incidents|issue|judgment|memory-decay|moltbook|research|self-review|shared|skill-audit|task-assignment|tech-director|HEARTBEAT)"
UNKNOWN=$(ls memory/ 2>/dev/null | grep -vE "$KNOWN_PATTERNS" || true)
if [ -n "$UNKNOWN" ]; then
    echo "⚠️  Unknown files in memory/:"
    echo "$UNKNOWN" | sed 's/^/   /'
    ISSUES=$((ISSUES + 1))
else
    echo "✅ No unexpected files in memory/"
fi

# Generate checksums for critical files
echo ""
echo "🔑 Checksums (for future verification):"
for f in MEMORY.md memory/heartbeat-state.json SESSION-STATE.md; do
    if [ -f "$f" ]; then
        SUM=$(sha256sum "$f" | cut -d' ' -f1)
        echo "   $f: ${SUM:0:16}..."
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ISSUES -eq 0 ]; then
    echo "✅ No integrity issues found"
else
    echo "⚠️  Found $ISSUES potential issues — review recommended"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
