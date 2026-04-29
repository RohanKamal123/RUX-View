"""Load balancer configuration module for Vision OS (Sprint 10.2).

Configures Google Cloud Load Balancer with HTTPS, CDN, Cloud Armor,
WebSocket support, and SSL certificate auto-provisioning.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import yaml
import json
from datetime import datetime, timedelta


@dataclass
class LBConfig:
    """Load balancer configuration dataclass."""
    domain: str = "visionos.app"
    ssl_certificate: str = "managed"  # managed by Google
    backend_service: str = "vision-os-backend"
    static_bucket: str = "vision-os-static"
    region: str = "asia-south1"
    enable_cdn: bool = True
    enable_armor: bool = True
    websocket_timeout: int = 3600  # 1 hour in seconds
    enable_geo_restriction: bool = True
    allowed_countries: List[str] = field(default_factory=lambda: ["BD"])

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CostEstimate:
    """Cost estimate for load balancer resources."""
    min_instances: int
    max_instances: int
    estimated_monthly_min: float
    estimated_monthly_max: float
    estimated_monthly_avg: float
    cost_per_instance_hour: float
    assumptions: list[str]


class LoadBalancerConfig:
    """Manages load balancer configuration generation and validation."""

    def __init__(self):
        self.VALID_REGIONS = {
            "asia-south1", "asia-east1", "asia-east2",
            "asia-southeast1", "asia-southeast2",
            "us-central1", "us-east1", "us-west1",
            "europe-west1", "europe-west2", "europe-west4",
        }
        self.VALID_WEBSOCKET_TIMEOUTS = list(range(60, 7201, 60))  # 1 min to 2 hours

    def generate_config(self, domain: str) -> LBConfig:
        """Generate a default load balancer config for the given domain."""
        if not domain or "." not in domain:
            raise ValueError(f"Invalid domain: {domain}")

        return LBConfig(
            domain=domain,
            ssl_certificate="managed",
            backend_service="vision-os-backend",
            static_bucket="vision-os-static",
            region="asia-south1",
            enable_cdn=True,
            enable_armor=True,
            websocket_timeout=3600,
        )

    def validate_config(self, config: LBConfig) -> bool:
        """Validate load balancer configuration."""
        # Check domain
        if not config.domain or "." not in config.domain:
            return False

        # Check region
        if config.region not in self.VALID_REGIONS:
            return False

        # Check backend service
        if not config.backend_service:
            return False

        # Check websocket timeout
        if config.websocket_timeout < 60 or config.websocket_timeout > 7200:
            return False

        # Check CDN and Armor are not both disabled (for production)
        if not config.enable_cdn and not config.enable_armor:
            return False

        return True

    def generate_url_map(self, config: LBConfig) -> dict:
        """Generate URL map configuration."""
        return {
            "name": "vision-os-url-map",
            "defaultService": config.backend_service,
            "hostRules": [
                {
                    "hosts": [config.domain],
                    "pathMatcher": "vision-os-path-matcher",
                }
            ],
            "pathMatchers": [
                {
                    "name": "vision-os-path-matcher",
                    "defaultService": config.backend_service,
                    "pathRules": [
                        {
                            "paths": ["/api/*"],
                            "service": config.backend_service,
                            "routeAction": {
                                "corsPolicy": {
                                    "allowOrigins": [f"https://{config.domain}"],
                                    "allowMethods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                                    "allowHeaders": ["Content-Type", "Authorization", "X-Requested-With"],
                                    "maxAge": 3600,
                                    "allowCredentials": True,
                                }
                            },
                        },
                        {
                            "paths": ["/static/*"],
                            "service": config.static_bucket,
                            "routeAction": {
                                "cdnPolicy": {
                                    "enabled": config.enable_cdn,
                                    "cacheMode": "CACHE_ALL_STATIC",
                                    "defaultTtl": 3600,
                                    "maxTtl": 86400,
                                    "clientTtl": 3600,
                                    "negativeCaching": True,
                                }
                            },
                        },
                        {
                            "paths": ["/health"],
                            "service": config.backend_service,
                        },
                        {
                            "paths": ["/login"],
                            "service": config.backend_service,
                        },
                        {
                            "paths": ["/admin/*"],
                            "service": config.backend_service,
                            "routeAction": {
                                "urlRewrite": {
                                    "pathPrefixRewrite": "/admin",
                                }
                            },
                        },
                        {
                            "paths": ["/ws/*"],
                            "service": config.backend_service,
                            "routeAction": {
                                "timeout": f"{config.websocket_timeout}s",
                            },
                        },
                        {
                            "paths": ["/*"],
                            "service": config.backend_service,
                        },
                    ],
                }
            ],
        }

    def generate_ssl_config(self, domain: str) -> dict:
        """Generate SSL certificate configuration."""
        if not domain or "." not in domain:
            raise ValueError(f"Invalid domain: {domain}")

        return {
            "name": "vision-os-ssl-cert",
            "managed": {
                "domains": [domain],
                "state": "PROVISIONING",
            },
            "type": "MANAGED",
            "scope": "global",
        }

    def generate_cloud_armor_policy(self) -> dict:
        """Generate Cloud Armor security policy configuration."""
        return {
            "name": "vision-os-armor-policy",
            "type": "CLOUD_ARMOR",
            "description": "Cloud Armor policy for Vision OS - WAF + DDoS protection",
            "rules": [
                {
                    "action": "throttle",
                    "priority": 1000,
                    "match": {
                        "expr": {
                            "expression": "origin.ip_rate_limit() >= 1000",
                        }
                    },
                    "rateLimitOptions": {
                        "rateLimitThreshold": {
                            "count": 1000,
                            "intervalSec": 60,
                        },
                        "conformAction": "allow",
                        "exceedAction": "deny(429)",
                        "enforceOnKey": "IP",
                    },
                    "description": "Rate limiting: 1000 requests/min per IP",
                },
                {
                    "action": "deny(403)",
                    "priority": 2000,
                    "match": {
                        "expr": {
                            "expression": (
                                "evaluatePreconfiguredExpr('sqli-v33-stable')"
                            ),
                        }
                    },
                    "description": "SQL injection prevention",
                },
                {
                    "action": "deny(403)",
                    "priority": 3000,
                    "match": {
                        "expr": {
                            "expression": (
                                "evaluatePreconfiguredExpr('xss-v33-stable')"
                            ),
                        }
                    },
                    "description": "Cross-site scripting prevention",
                },
                {
                    "action": "deny(403)",
                    "priority": 4000,
                    "match": {
                        "expr": {
                            "expression": (
                                "evaluatePreconfiguredExpr('bot-v33-stable')"
                            ),
                        }
                    },
                    "description": "Bot detection and blocking",
                },
                {
                    "action": "throttle",
                    "priority": 5000,
                    "match": {
                        "expr": {
                            "expression": "evaluatePreconfiguredExpr('http-v33-stable')",
                        }
                    },
                    "rateLimitOptions": {
                        "rateLimitThreshold": {
                            "count": 500,
                            "intervalSec": 60,
                        },
                        "conformAction": "allow",
                        "exceedAction": "deny(429)",
                        "enforceOnKey": "IP",
                    },
                    "description": "HTTP anomaly detection with rate limiting",
                },
                {
                    "action": "allow",
                    "priority": 2147483647,
                    "match": {
                        "expr": {
                            "expression": "true",
                        }
                    },
                    "description": "Default allow",
                },
            ],
        }

    def estimate_cost(self, config: LBConfig) -> CostEstimate:
        """Estimate monthly cost for load balancer resources."""
        # Fixed costs
        monthly_fixed = 18.00  # Forwarding rule
        if config.enable_armor:
            monthly_fixed += 55.00  # Cloud Armor managed protection

        # Data processing costs (rough estimates)
        data_gb = 500  # Estimated monthly data transfer in GB
        data_cost = data_gb * 0.008  # $0.008/GB data processing

        # CDN costs
        cdn_cost = 0
        if config.enable_cdn:
            cdn_cost = data_gb * 0.02  # $0.02/GB CDN egress

        # Armor costs
        armor_cost = 0
        if config.enable_armor:
            armor_cost = 3.00  # Per rule cost for additional rules (approx)

        total = monthly_fixed + data_cost + cdn_cost + armor_cost

        # Instance costs
        cost_per_instance_hour = 0.10  # $0.10/hr per instance (approx)
        min_instances = 1
        max_instances = 10

        # Monthly estimates based on instance hours
        hours_per_month = 730  # avg hours in a month
        estimated_monthly_min = min_instances * cost_per_instance_hour * hours_per_month
        estimated_monthly_max = max_instances * cost_per_instance_hour * hours_per_month
        estimated_monthly_avg = (estimated_monthly_min + estimated_monthly_max) / 2

        return CostEstimate(
            min_instances=min_instances,
            max_instances=max_instances,
            estimated_monthly_min=estimated_monthly_min,
            estimated_monthly_max=estimated_monthly_max,
            estimated_monthly_avg=estimated_monthly_avg,
            cost_per_instance_hour=cost_per_instance_hour,
            assumptions=[
                f"Estimated {data_gb}GB data transfer per month",
                "SSL certificate provisioning is free (managed by Google)",
                "Cloud Armor standard tier pricing applied",
                "Costs may vary based on actual traffic patterns",
                "Additional costs for Cloud Run backend instances not included",
            ],
        )

    def generate_yaml_config(self, config: LBConfig) -> str:
        """Generate full YAML configuration for the load balancer."""
        config_dict = {
            "name": "vision-os-load-balancer",
            "project": "vision-os-project",
            "region": config.region,
            "loadBalancer": {
                "type": "global_https",
                "domain": config.domain,
                "ssl": self.generate_ssl_config(config.domain),
                "urlMap": self.generate_url_map(config),
                "backendServices": [
                    {
                        "name": config.backend_service,
                        "type": "serverless",
                        "backends": [
                            {
                                "group": "vision-os-cloud-run",
                                "balancingMode": "UTILIZATION",
                                "capacityScaler": 1.0,
                            }
                        ],
                        "enableCDN": config.enable_cdn,
                        "securityPolicy": "vision-os-armor-policy" if config.enable_armor else None,
                    },
                    {
                        "name": config.static_bucket,
                        "type": "storage_bucket",
                        "backends": [
                            {
                                "bucketName": config.static_bucket,
                            }
                        ],
                        "enableCDN": config.enable_cdn,
                        "cdnPolicy": {
                            "cacheMode": "CACHE_ALL_STATIC",
                            "defaultTtl": 3600,
                            "maxTtl": 86400,
                        },
                    },
                ],
                "cloudArmor": self.generate_cloud_armor_policy() if config.enable_armor else None,
            },
            "features": {
                "websocket": {
                    "enabled": True,
                    "timeout": config.websocket_timeout,
                },
                "ddosProtection": {
                    "enabled": True,
                    "type": "cloud_armor",
                },
            },
        }
        return yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
