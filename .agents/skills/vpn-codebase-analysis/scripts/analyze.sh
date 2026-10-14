#!/usr/bin/env bash
# ==============================================================================
# Codebase Analysis & Verification Script for VPN & Telegram Bot
# ==============================================================================
set -eo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi
cd "$REPO_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=====================================================${NC}"
echo -e "${CYAN} 🔍 VPN & Telegram Bot Codebase Analysis Report${NC}"
echo -e "${CYAN}=====================================================${NC}"

FAILURES=0

# 1. Check for Duplicate Files
echo -e "\n${YELLOW}[1/6] Checking Duplicate Files & Hygiene...${NC}"
if [ -f "telegrambot/hotspot-manager.py" ]; then
    echo -e "${RED}❌ FAILED: Duplicate hotspot-manager.py found in telegrambot/!${NC}"
    FAILURES=$((FAILURES + 1))
else
    echo -e "${GREEN}✅ PASSED: No duplicate hotspot-manager.py found.${NC}"
fi

# 2. Syntax & Compilation Check
echo -e "\n${YELLOW}[2/6] Checking Python Syntax & Compilation...${NC}"
BOT_PYTHONPATH="${REPO_ROOT}/telegrambot/.venv/lib/python3.11/site-packages:${REPO_ROOT}"
SYNTAX_ERRORS=0
while IFS= read -r pyfile; do
    if ! env PYTHONHOME="" PYTHONPATH="$BOT_PYTHONPATH" python3 -m py_compile "$pyfile" 2>/dev/null; then
        echo -e "${RED}❌ Syntax error in: $pyfile${NC}"
        SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
    fi
done < <(find scripts telegrambot tests -name "*.py" -not -path '*/.*' -not -path '*/venv/*')

if [ "$SYNTAX_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ PASSED: All Python files compiled successfully.${NC}"
else
    echo -e "${RED}❌ FAILED: $SYNTAX_ERRORS file(s) have syntax errors.${NC}"
    FAILURES=$((FAILURES + 1))
fi

# 3. File Size & Sweet Spot Architecture Check
echo -e "\n${YELLOW}[3/6] Verifying Sweet Spot Line Counts (<300 lines)...${NC}"
OVERSIZED=0
while IFS= read -r pyfile; do
    LINES=$(wc -l < "$pyfile")
    if [ "$LINES" -gt 300 ]; then
        echo -e "${RED}⚠️  Oversized: $pyfile has $LINES lines (exceeds 300 sweet spot).${NC}"
        OVERSIZED=$((OVERSIZED + 1))
    fi
done < <(find telegrambot scripts tests -name "*.py" -not -path '*/.*' -not -path '*/venv/*')

if [ "$OVERSIZED" -eq 0 ]; then
    echo -e "${GREEN}✅ PASSED: All Telegram Bot, Hotspot script, and test files are strictly in the sweet spot!${NC}"
else
    echo -e "${RED}❌ FAILED: $OVERSIZED file(s) exceed 300 lines.${NC}"
    FAILURES=$((FAILURES + 1))
fi

# 4. Modular Test Suite Isolation & Runner Purity
echo -e "\n${YELLOW}[4/6] Verifying Modular Test Suite Isolation...${NC}"
RUNNER_PURITY_FAILURES=0
for runner in tests/test_telegram_bot.py tests/test_hotspot_manager.py; do
    if [ -f "$runner" ]; then
        LINES=$(wc -l < "$runner")
        if [ "$LINES" -gt 40 ]; then
            echo -e "${RED}⚠️  Oversized runner: $runner has $LINES lines (must be thin aggregator <40 lines).${NC}"
            RUNNER_PURITY_FAILURES=$((RUNNER_PURITY_FAILURES + 1))
        fi
        if grep -q -E 'class [A-Za-z0-9_]+\(.*TestCase.*\):' "$runner"; then
            echo -e "${RED}❌ $runner defines a TestCase directly! Tests must reside in tests/bot/ or tests/hotspot/.${NC}"
            RUNNER_PURITY_FAILURES=$((RUNNER_PURITY_FAILURES + 1))
        fi
    fi
done

if [ "$RUNNER_PURITY_FAILURES" -eq 0 ]; then
    echo -e "${GREEN}✅ PASSED: All root test runners are pure thin aggregators (<40 lines, zero embedded TestCases).${NC}"
else
    echo -e "${RED}❌ FAILED: Modular test suite isolation violated!${NC}"
    FAILURES=$((FAILURES + 1))
fi

# 5. Black Formatting Check
echo -e "\n${YELLOW}[5/8] Checking Code Formatting (Black)...${NC}"
if command -v black >/dev/null 2>&1; then
    if black --check scripts/ tests/ telegrambot/; then
        echo -e "${GREEN}✅ PASSED: Black code formatting verified.${NC}"
    else
        echo -e "${RED}❌ FAILED: Black formatting check failed.${NC}"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo -e "${YELLOW}⚠️  Black not installed, skipping.${NC}"
fi

# 6. Flake8 Linting Check
echo -e "\n${YELLOW}[6/8] Checking Code Style & Linting (Flake8)...${NC}"
if command -v flake8 >/dev/null 2>&1; then
    if flake8 scripts/ tests/ telegrambot/; then
        echo -e "${GREEN}✅ PASSED: Flake8 linting passed.${NC}"
    else
        echo -e "${RED}❌ FAILED: Flake8 linting check failed.${NC}"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo -e "${YELLOW}⚠️  Flake8 not installed, skipping.${NC}"
fi

# 7. Telegram Bot Unit Tests
echo -e "\n${YELLOW}[7/8] Running Telegram Bot Unit Tests...${NC}"
if env PYTHONHOME="" PYTHONPATH="$BOT_PYTHONPATH" python3 -m unittest -v tests/test_telegram_bot.py; then
    echo -e "${GREEN}✅ PASSED: All Telegram Bot unit tests succeeded.${NC}"
else
    echo -e "${RED}❌ FAILED: Telegram Bot unit tests failed.${NC}"
    FAILURES=$((FAILURES + 1))
fi

# 8. Hotspot Manager & Routing Tests
echo -e "\n${YELLOW}[8/8] Running Hotspot Manager & Script Tests...${NC}"
if env PYTHONHOME= PYTHONPATH= python3 -m unittest -v tests/test_hotspot_manager.py; then
    echo -e "${GREEN}✅ PASSED: All Hotspot Manager unit tests succeeded.${NC}"
else
    echo -e "${RED}❌ FAILED: Hotspot Manager unit tests failed.${NC}"
    FAILURES=$((FAILURES + 1))
fi

echo -e "\n${CYAN}=====================================================${NC}"
if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL ANALYSIS CHECKS PASSED! Codebase is healthy.${NC}"
    exit 0
else
    echo -e "${RED}💥 $FAILURES CHECK(S) FAILED! Please inspect issues above.${NC}"
    exit 1
fi
