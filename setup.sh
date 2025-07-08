#!/bin/bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

POE_API_KEY=""
LOCAL_API_KEY=""
ENV_COMPLETE=false

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
    command -v python >/dev/null 2>&1 || {
        print_error "Python is not installed or not in PATH"
        exit 1
    }
}

setup_directories() {
    mkdir -p logs
}

check_env_file() {
    [ -f ".env" ] || {
        print_info ".env file not found"
        return 1
    }
    
    print_info "Found existing .env file, checking configuration..."
    
    set -o allexport
    source .env 2>/dev/null || true
    set +o allexport
    
    [ -n "${POE_API_KEY:-}" ] && [ -n "${LOCAL_API_KEY:-}" ] && {
        print_status ".env file is complete"
        ENV_COMPLETE=true
        return 0
    }
    
    print_warning ".env file exists but is missing required values"
    return 1
}

get_poe_api_key() {
    [ -n "${POE_API_KEY:-}" ] && {
        print_status "POE API key found in .env"
        return 0
    }
    
    echo "Please get your POE API key from: https://poe.com/api_key"
    read -p "Enter your POE API key: " POE_API_KEY
    
    [ -n "$POE_API_KEY" ] || {
        print_error "POE API key is required"
        exit 1
    }
}


generate_local_api_key() {
    [ -n "${LOCAL_API_KEY:-}" ] && {
        print_status "Local API key found in .env"
        return 0
    }
    
    print_info "Generating Local API Key..."
    LOCAL_API_KEY=$(python scripts/generate_api_key.py) || {
        print_error "Failed to generate API key"
        exit 1
    }
    print_status "Local API key generated: ${LOCAL_API_KEY:0:20}..."
}

create_env_file() {
    print_info "Creating/updating .env file..."
    python scripts/create_env.py "$POE_API_KEY" "$LOCAL_API_KEY" || {
        print_error "Failed to create .env file"
        exit 1
    }
}

setup_configuration() {
    check_env_file && return 0
    
    echo ""
    print_info "Setting up environment configuration..."
    
    get_poe_api_key
    generate_local_api_key
    create_env_file
}

manage_docker_services() {
    echo ""
    print_info "Managing Docker services..."
    
    cd docker
    
    docker-compose ps | grep -q "Up" && {
        print_info "Services are running, restarting..."
        docker-compose down
        docker-compose up --build -d  
        print_status "Services restarted"
    } || {
        print_info "Starting services..."
        docker-compose up -d || {
            print_error "Failed to start services"
            exit 1
        }
        print_status "Services started"
    }
    
    cd ..
}

check_service_health() {
    echo ""
    print_info "Checking service health..."
    python scripts/check_services.py
}

get_cloudflare_url() {
    echo ""
    print_info "Getting Cloudflare tunnel URL..."
    sleep 5
    
    local cloudflare_output cloudflare_url
    cloudflare_output=$(python scripts/get_cloudflare_url.py 2>/dev/null)
    cloudflare_url=$(echo "$cloudflare_output" | grep "API Base URL:" | cut -d' ' -f4)
    
    echo "$cloudflare_url"
}

display_success_info() {
    local cloudflare_url="$1"
    
    [ -n "$cloudflare_url" ] && {
        print_status "Cloudflare tunnel established"
        echo ""
        echo "🎉 Setup Complete!"
        echo "=================="
        echo ""
        echo "📋 Configuration Summary:"
        echo "Local API URL: http://localhost:8000/v1"
        echo "Public API URL: ${cloudflare_url}"
        echo "Local API Key: ${LOCAL_API_KEY}"
        echo ""
        
        #For xCode no need for tunneling
        echo "🔧 Xcode Configuration:"
        echo "Host URL: http://localhost:8000"
        echo "API Token: ${LOCAL_API_KEY}"
        echo "AI Token Header: x-api-key"
        echo ""

        #Use Tunnel. Cursor doesnt work with localhost. They want to access to the host url from their server.
        echo "🔧 Cursor Configuration:"
        echo "Host URL: ${cloudflare_url}"
        echo "API Token: ${LOCAL_API_KEY}"
        echo ""

        echo "📝 Useful Commands:"
        echo "View logs: cd docker && docker-compose logs -f poe-wrapper"
        echo "Restart: cd docker && docker-compose restart"
        echo "Stop: cd docker && docker-compose down"
        echo "Get cloudflare URL: python scripts/get_cloudflare_url.py"
    } || {
        print_warning "Could not get cloudflare URL automatically"
        echo ""
        echo "🎉 Setup Complete!"
        echo "=================="
        echo ""
        echo "📋 Configuration Summary:"
        echo "Local API URL: http://localhost:8000/v1"
        echo "Local API Key: ${LOCAL_API_KEY}"
        echo ""
        echo "To get your cloudflare URL, run: python scripts/get_cloudflare_url.py"
    }
    
    echo ""
    echo "🚀 Your POE OpenAI Wrapper is ready to use!"
}

main() {
    print_banner
    validate_environment
    setup_directories
    setup_configuration
    manage_docker_services
    check_service_health
    
    local cloudflare_url
    cloudflare_url=$(get_cloudflare_url)
    display_success_info "$cloudflare_url"
}

[ "${BASH_SOURCE[0]}" = "${0}" ] && main "$@"