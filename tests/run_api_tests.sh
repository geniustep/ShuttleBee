#!/bin/bash
# =============================================================================
# ShuttleBee Mobile API Test Runner
# =============================================================================
#
# This script runs the Mobile API tests against a live Odoo server.
#
# Usage:
#   ./run_api_tests.sh                     # Use defaults
#   ./run_api_tests.sh http://localhost:8069 mydb admin admin
#
# Environment variables (alternative to arguments):
#   ODOO_URL      - Odoo server URL (default: http://localhost:8069)
#   ODOO_DB       - Database name (default: odoo)
#   ODOO_USER     - Username (default: admin)
#   ODOO_PASSWORD - Password (default: admin)
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments or use environment variables
export ODOO_URL="${1:-${ODOO_URL:-http://localhost:8069}}"
export ODOO_DB="${2:-${ODOO_DB:-odoo}}"
export ODOO_USER="${3:-${ODOO_USER:-admin}}"
export ODOO_PASSWORD="${4:-${ODOO_PASSWORD:-admin}}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  ShuttleBee Mobile API Test Runner${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "  ${YELLOW}Odoo URL:${NC}  $ODOO_URL"
echo -e "  ${YELLOW}Database:${NC}  $ODOO_DB"
echo -e "  ${YELLOW}User:${NC}      $ODOO_USER"
echo ""

# Check if Odoo is running
echo -e "${BLUE}Checking Odoo connection...${NC}"
if curl -s -o /dev/null -w "%{http_code}" "$ODOO_URL/web/login" 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}✓ Odoo is running${NC}"
else
    echo -e "${RED}✗ Cannot connect to Odoo at $ODOO_URL${NC}"
    echo ""
    echo "Please ensure Odoo is running. To start Odoo:"
    echo "  cd /path/to/odoo"
    echo "  ./odoo-bin -c odoo.conf"
    exit 1
fi

echo ""
echo -e "${BLUE}Running tests...${NC}"
echo ""

# Run the tests
cd "$SCRIPT_DIR"
python3 -m pytest test_mobile_api.py -v --tb=short 2>/dev/null || python3 test_mobile_api.py

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Tests completed${NC}"
echo -e "${GREEN}============================================${NC}"
