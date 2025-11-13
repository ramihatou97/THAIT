#!/bin/bash
# NeuroscribeAI - API Key Configuration Helper
# Interactive script to add Anthropic or OpenAI API keys

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         NeuroscribeAI - API Key Configuration                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo "  Please run from the project root directory"
    exit 1
fi

echo -e "${BLUE}Which API provider would you like to configure?${NC}"
echo "  1) Anthropic Claude (Recommended for medical text)"
echo "  2) OpenAI GPT-4"
echo "  3) Both"
echo ""
read -p "Enter choice (1-3): " choice

echo ""

configure_anthropic() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Configuring Anthropic Claude${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Get your API key from: https://console.anthropic.com/"
    echo ""
    read -p "Enter your Anthropic API key (starts with sk-ant-): " anthropic_key

    if [[ $anthropic_key != sk-ant-* ]]; then
        echo -e "${RED}✗ Invalid key format. Anthropic keys should start with 'sk-ant-'${NC}"
        return 1
    fi

    # Update .env file
    if grep -q "^ANTHROPIC_API_KEY=" .env; then
        sed -i.bak "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$anthropic_key|" .env
        echo -e "${GREEN}✓ Anthropic API key updated in .env${NC}"
    else
        echo "ANTHROPIC_API_KEY=$anthropic_key" >> .env
        echo -e "${GREEN}✓ Anthropic API key added to .env${NC}"
    fi

    # Set LLM provider
    sed -i.bak "s|^LLM_PROVIDER=.*|LLM_PROVIDER=anthropic|" .env
}

configure_openai() {
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Configuring OpenAI GPT-4${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Get your API key from: https://platform.openai.com/api-keys"
    echo ""
    read -p "Enter your OpenAI API key (starts with sk-): " openai_key

    if [[ $openai_key != sk-* ]]; then
        echo -e "${RED}✗ Invalid key format. OpenAI keys should start with 'sk-'${NC}"
        return 1
    fi

    # Update .env file
    if grep -q "^OPENAI_API_KEY=" .env; then
        sed -i.bak "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$openai_key|" .env
        echo -e "${GREEN}✓ OpenAI API key updated in .env${NC}"
    else
        echo "OPENAI_API_KEY=$openai_key" >> .env
        echo -e "${GREEN}✓ OpenAI API key added to .env${NC}"
    fi

    # Set LLM provider
    sed -i.bak "s|^LLM_PROVIDER=.*|LLM_PROVIDER=openai|" .env
}

# Process choice
case $choice in
    1)
        configure_anthropic
        ;;
    2)
        configure_openai
        ;;
    3)
        configure_anthropic
        echo ""
        configure_openai
        ;;
    *)
        echo -e "${RED}✗ Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Configuration Updated${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Next step: Restart services to apply changes"
echo ""
echo "  docker-compose restart api celery-worker"
echo ""
echo "Then verify:"
echo ""
echo "  docker-compose ps"
echo "  docker-compose logs api | grep 'LLM Provider'"
echo ""
echo -e "${GREEN}Ready to use LLM-enhanced extraction!${NC}"
