# Security Guide

## Security Features

### 1. Authentication
- **All API endpoints are protected** with API key authentication
- Uses secure comparison (`secrets.compare_digest`) to prevent timing attacks
- Supports multiple authentication methods (Bearer token, x-api-key header)

### 2. Network Security
- **Port 8000 is bound to localhost only** (`127.0.0.1:8000`)
- External access only through Cloudflare tunnel
- No direct internet exposure

### 3. Cloudflare Tunnel Protection
- All traffic goes through Cloudflare's network
- DDoS protection included
- SSL/TLS encryption enforced
- Option to add Cloudflare Access for additional authentication

## Security Best Practices

### DO:
✅ Keep your LOCAL_API_KEY secret  
✅ Use HTTPS URLs only (Cloudflare handles this)  
✅ Regularly update Docker images  
✅ Monitor logs for suspicious activity  
✅ Use custom domain for production  

### DON'T:
❌ Share your API keys  
❌ Expose port 8000 to the internet  
❌ Disable authentication  
❌ Use default/weak API keys  

## Hardening Steps

### 1. Add Cloudflare Access (Optional)
For additional security, configure Cloudflare Access:
1. Go to Cloudflare Zero Trust dashboard
2. Navigate to Access > Applications
3. Add your domain
4. Configure authentication rules

### 2. Rate Limiting
Add rate limiting in Cloudflare:
1. Go to your domain in Cloudflare
2. Security > WAF > Rate limiting rules
3. Create rules based on your needs

### 3. IP Whitelisting
If you have static IPs:
1. Use Cloudflare WAF rules
2. Create "Block all except" rules
3. Add your allowed IPs

## Security Checklist

- [ ] Strong LOCAL_API_KEY (auto-generated)
- [ ] POE_API_KEY kept secret
- [ ] Port 8000 bound to localhost only
- [ ] Using HTTPS through Cloudflare
- [ ] Regular Docker updates
- [ ] Monitoring enabled

## Incident Response

If you suspect a security breach:
1. Regenerate LOCAL_API_KEY immediately
2. Check logs: `docker logs poe-wrapper`
3. Review Cloudflare analytics for anomalies
4. Rotate POE_API_KEY if compromised

## No Vulnerabilities

This setup protects against:
- Direct internet exposure (localhost only)
- Unauthorized access (API key required)
- Man-in-the-middle attacks (HTTPS enforced)
- DDoS attacks (Cloudflare protection)
- Timing attacks (secure comparison)