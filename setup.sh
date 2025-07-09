#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Initialize variables
POE_API_KEY=""
LOCAL_API_KEY=""
CUSTOM_DOMAIN=""
CLOUDFLARE_TUNNEL_TOKEN=""
USE_CUSTOM_DOMAIN=false

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_banner() {
    echo "🚀 POE OpenAI Wrapper Setup"
    echo "=============================="
}

validate_environment() {
    # Check Python
    command -v python >/dev/null 2>&1 || {
        print_error "Python is not installed"
        exit 1
    }
    
    # Check Docker
    command -v docker >/dev/null 2>&1 || {
        print_error "Docker is not installed"
        exit 1
    }
    
    # Check Docker Compose
    command -v docker-compose >/dev/null 2>&1 || {
        print_error "Docker Compose is not installed"
        exit 1
    }
}

load_env_file() {
    if [ -f ".env" ]; then
        print_info "Loading existing .env file..."
        set -o allexport
        source .env 2>/dev/null || true
        set +o allexport
        
        # Validate loaded variables
        local env_valid=true
        
        if [ -z "${POE_API_KEY:-}" ]; then
            print_warning "POE_API_KEY not found in .env"
            env_valid=false
        fi
        
        if [ -z "${LOCAL_API_KEY:-}" ] || [ "${LOCAL_API_KEY:-}" = "your-local-api-key" ]; then
            print_warning "LOCAL_API_KEY not found or invalid in .env"
            env_valid=false
        fi
        
        # Check if custom domain is configured
        if [ -n "${CUSTOM_DOMAIN:-}" ] && [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
            USE_CUSTOM_DOMAIN=true
            print_info "Custom domain detected: $CUSTOM_DOMAIN"
        fi
        
        if [ "$env_valid" = true ]; then
            print_status "Environment variables loaded successfully"
            return 0
        fi
    fi
    return 1
}

get_poe_api_key() {
    if [ -z "${POE_API_KEY:-}" ]; then
        echo ""
        echo "📋 Get your POE API key from: https://poe.com/api_key"
        read -p "Enter your POE API key: " POE_API_KEY
        
        [ -n "$POE_API_KEY" ] || {
            print_error "POE API key is required"
            exit 1
        }
    else
        print_status "Using existing POE API key"
    fi
}

generate_local_api_key() {
    if [ -z "${LOCAL_API_KEY:-}" ] || [ "${LOCAL_API_KEY:-}" = "your-local-api-key" ]; then
        print_info "Generating secure API key..."
        LOCAL_API_KEY=$(python scripts/generate_api_key.py) || {
            print_error "Failed to generate API key"
            exit 1
        }
        print_status "API key generated"
    else
        print_status "Using existing LOCAL API key"
    fi
}

setup_custom_domain() {
    if [ -n "${CUSTOM_DOMAIN:-}" ] && [ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
        print_status "Custom domain already configured: $CUSTOM_DOMAIN"
        USE_CUSTOM_DOMAIN=true
        return 0
    fi
    
    echo ""
    read -p "Use custom domain? (y/N): " use_custom
    
    if [ "$use_custom" != "y" ] && [ "$use_custom" != "Y" ]; then
        USE_CUSTOM_DOMAIN=false
        return 0
    fi
    
    if [ -z "${CUSTOM_DOMAIN:-}" ]; then
        read -p "Enter your domain (e.g., example.com): " CUSTOM_DOMAIN
        [ -n "$CUSTOM_DOMAIN" ] || {
            print_error "Domain is required"
            exit 1
        }
    fi
    
    if [ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]; then
        echo ""
        print_info "To get a Cloudflare Tunnel token:"
        echo "1. Go to https://one.dash.cloudflare.com/"
        echo "2. Navigate to Networks > Tunnels"
        echo "3. Create a tunnel and configure:"
        echo "   - Public hostname: $CUSTOM_DOMAIN"
        echo "   - Service: http://poe-wrapper:8000"
        echo "4. Copy the tunnel token"
        echo ""
        read -p "Enter your Cloudflare Tunnel token: " CLOUDFLARE_TUNNEL_TOKEN
        [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ] || {
            print_error "Token is required for custom domain"
            exit 1
        }
    fi
    
    USE_CUSTOM_DOMAIN=true
}

create_env_file() {
    print_info "Creating .env file..."
    
    cat > .env << EOF
# POE API Configuration
POE_API_KEY=${POE_API_KEY}

# Local API Configuration  
LOCAL_API_KEY=${LOCAL_API_KEY}

# Server Configuration
PORT=8000
WORKERS=1
LOG_LEVEL=info
MAX_FILE_SIZE_MB=50
ENABLE_HEALTHCHECK=true
EOF

    if [ "$USE_CUSTOM_DOMAIN" = true ]; then
        cat >> .env << EOF

# Cloudflare Custom Domain
CUSTOM_DOMAIN=${CUSTOM_DOMAIN}
CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
EOF
    fi
    
    print_status ".env file created"
}

manage_docker_services() {
    echo ""
    print_info "Managing Docker services..."
    
    cd docker
    
    # Stop any existing containers
    docker-compose down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.custom.yml down --remove-orphans 2>/dev/null || true
    
    # Build and start with appropriate compose file
    if [ "$USE_CUSTOM_DOMAIN" = true ]; then
        print_info "Starting services with custom domain..."
        docker-compose -f docker-compose.custom.yml up --build -d || {
            print_error "Failed to start services"
            exit 1
        }
    else
        print_info "Starting services with random Cloudflare URL..."
        docker-compose up --build -d || {
            print_error "Failed to start services"
            exit 1
        }
    fi
    
    cd ..
    print_status "Services started"
}

check_service_health() {
    echo ""
    print_info "Checking service health..."
    
    # Wait for services to be ready
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
            print_status "API is healthy"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    
    print_warning "API health check timed out - services may still be starting"
}

get_tunnel_url() {
    if [ "$USE_CUSTOM_DOMAIN" = true ]; then
        echo "https://${CUSTOM_DOMAIN}"
    else
        # Try to get the random Cloudflare URL
        sleep 5
        local url=$(python scripts/get_cloudflare_url.py 2>/dev/null | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1)
        echo "$url"
    fi
}

display_success_info() {
    echo ""
    echo "🎉 Setup Complete!"
    echo "=================="
    echo ""
    echo "📋 Configuration:"
    echo "• Local API: http://localhost:8000/v1"
    echo "• API Key: ${LOCAL_API_KEY}"
    
    if [ "$USE_CUSTOM_DOMAIN" = true ]; then
        echo "• Public URL: https://${CUSTOM_DOMAIN}/v1"
    else
        local tunnel_url=$(get_tunnel_url)
        if [ -n "$tunnel_url" ]; then
            echo "• Public URL: ${tunnel_url}/v1"
        else
            echo ""
            echo "To get your Cloudflare tunnel URL:"
            echo "python scripts/get_cloudflare_url.py"
        fi
    fi
    
    echo ""
    echo "📝 Quick Test:"
    echo "curl -H \"Authorization: Bearer ${LOCAL_API_KEY}\" http://localhost:8000/v1/models"
    echo ""
    echo "🔒 Security: See SECURITY.md for security information"
    echo ""
}

main() {
    print_banner
    validate_environment
    
    # Create necessary directories
    mkdir -p logs
    
    # Try to load existing config
    if ! load_env_file; then
        get_poe_api_key
        generate_local_api_key
        setup_custom_domain
        create_env_file
    else
        # Still ask about custom domain if not configured
        if [ -z "${CUSTOM_DOMAIN:-}" ]; then
            setup_custom_domain
            if [ "$USE_CUSTOM_DOMAIN" = true ]; then
                create_env_file
            fi
        fi
    fi
    
    manage_docker_services
    check_service_health
    display_success_info
}

# Run main function
main "$@"