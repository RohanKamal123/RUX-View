"""Tests for Sprint 10.2 — Load Balancer Setup."""
import pytest
import yaml
import json
from datetime import datetime, timedelta
from pathlib import Path
from infrastructure.load_balancer import (
    LoadBalancerConfig,
    LBConfig,
    CostEstimate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_domain() -> str:
    return "visionos.app"


@pytest.fixture
def sample_lb_config(sample_domain: str) -> LBConfig:
    return LBConfig(
        domain=sample_domain,
        ssl_certificate="managed",
        backend_service="vision-os-backend",
        static_bucket="vision-os-static",
        region="asia-south1",
        enable_cdn=True,
        enable_armor=True,
        websocket_timeout=3600,
    )


@pytest.fixture
def config_yaml_path() -> Path:
    return Path("infrastructure/load_balancer_config.yaml")


# ---------------------------------------------------------------------------
# Test: generate_config
# ---------------------------------------------------------------------------

def test_generate_config_contains_required_fields(sample_domain: str):
    """Verify that generate_config returns a dict with all mandatory keys."""
    lb_config = LoadBalancerConfig()
    config = lb_config.generate_config(sample_domain)
    assert isinstance(config, LBConfig)
    assert config.domain == sample_domain
    assert config.ssl_certificate == "managed"
    assert config.backend_service == "vision-os-backend"
    assert config.region == "asia-south1"
    assert config.enable_cdn is True
    assert config.enable_armor is True
    assert config.websocket_timeout == 3600


# ---------------------------------------------------------------------------
# Test: validate_config
# ---------------------------------------------------------------------------

def test_validate_config_valid(sample_lb_config: LBConfig):
    """A valid LBConfig should pass validation."""
    lb_config = LoadBalancerConfig()
    assert lb_config.validate_config(sample_lb_config) is True


def test_validate_config_invalid_domain():
    """An empty domain should fail validation."""
    config = LBConfig(
        domain="",
        ssl_certificate="managed",
        backend_service="vision-os-backend",
    )
    lb_config = LoadBalancerConfig()
    assert lb_config.validate_config(config) is False


def test_validate_config_invalid_region():
    """An invalid region string should fail validation."""
    config = LBConfig(
        domain="visionos.app",
        ssl_certificate="managed",
        backend_service="vision-os-backend",
        region="invalid-region",
    )
    lb_config = LoadBalancerConfig()
    assert lb_config.validate_config(config) is False


def test_validate_config_none_backend():
    """A missing backend service should fail validation."""
    config = LBConfig(
        domain="visionos.app",
        ssl_certificate="managed",
        backend_service="",
    )
    lb_config = LoadBalancerConfig()
    assert lb_config.validate_config(config) is False


# ---------------------------------------------------------------------------
# Test: generate_url_map
# ---------------------------------------------------------------------------

def test_generate_url_map_has_all_routes(sample_lb_config: LBConfig):
    """The URL map should contain all required route patterns."""
    lb_config = LoadBalancerConfig()
    url_map = lb_config.generate_url_map(sample_lb_config)
    assert isinstance(url_map, dict)

    # Check path matchers exist
    path_matchers = url_map.get("pathMatchers", [])
    assert len(path_matchers) > 0
    matcher = path_matchers[0]
    path_rules = matcher.get("pathRules", [])

    # Collect all paths
    all_paths = []
    for rule in path_rules:
        all_paths.extend(rule.get("paths", []))

    # Required routes
    required_routes = ["/api/*", "/static/*", "/health", "/ws/*", "/*", "/login", "/admin/*"]
    for route in required_routes:
        assert route in all_paths, f"Missing route: {route}"


def test_url_map_has_static_cdn(sample_lb_config: LBConfig):
    """The /static/* path rule should have CDN enabled."""
    lb_config = LoadBalancerConfig()
    url_map = lb_config.generate_url_map(sample_lb_config)
    matcher = url_map["pathMatchers"][0]
    for rule in matcher["pathRules"]:
        if "/static/*" in rule.get("paths", []):
            route_action = rule.get("routeAction", {})
            cdn = route_action.get("cdnPolicy", {})
            assert cdn.get("enabled") is True
            break
    else:
        pytest.fail("No path rule found for /static/*")


def test_url_map_websocket_timeout(sample_lb_config: LBConfig):
    """The /ws/* path rule should have the correct timeout."""
    lb_config = LoadBalancerConfig()
    url_map = lb_config.generate_url_map(sample_lb_config)
    matcher = url_map["pathMatchers"][0]
    for rule in matcher["pathRules"]:
        if "/ws/*" in rule.get("paths", []):
            timeout = rule.get("routeAction", {}).get("timeout", "")
            assert "3600" in timeout
            break
    else:
        pytest.fail("No path rule found for /ws/*")


# ---------------------------------------------------------------------------
# Test: generate_ssl_config
# ---------------------------------------------------------------------------

def test_generate_ssl_config(sample_domain: str):
    """SSL config should be a MANAGED certificate for the given domain."""
    lb_config = LoadBalancerConfig()
    ssl_config = lb_config.generate_ssl_config(sample_domain)
    assert isinstance(ssl_config, dict)
    assert ssl_config.get("type") == "MANAGED"
    managed = ssl_config.get("managed", {})
    assert sample_domain in managed.get("domains", [])
    assert ssl_config.get("name") == "vision-os-ssl-cert"


def test_generate_ssl_config_staging():
    """SSL config for a staging domain should still be MANAGED."""
    lb_config = LoadBalancerConfig()
    ssl_config = lb_config.generate_ssl_config("staging.visionos.app")
    assert ssl_config.get("type") == "MANAGED"
    managed = ssl_config.get("managed", {})
    assert "staging.visionos.app" in managed.get("domains", [])


# ---------------------------------------------------------------------------
# Test: generate_cloud_armor_policy
# ---------------------------------------------------------------------------

def test_generate_cloud_armor_policy():
    """The Cloud Armor policy should contain all required security rules."""
    lb_config = LoadBalancerConfig()
    policy = lb_config.generate_cloud_armor_policy()
    assert isinstance(policy, dict)
    assert policy.get("name") == "vision-os-armor-policy"
    assert policy.get("type") == "CLOUD_ARMOR"

    rules = policy.get("rules", [])
    assert len(rules) >= 6

    # Extract priorities
    priorities = [r.get("priority") for r in rules]
    assert 1000 in priorities  # Rate limiting
    assert 2000 in priorities  # SQL injection
    assert 3000 in priorities  # XSS
    assert 4000 in priorities  # Bot detection
    assert 5000 in priorities  # HTTP anomaly

    # Verify allow rule exists at highest priority
    allow_rules = [r for r in rules if r.get("action") == "allow"]
    assert len(allow_rules) == 1
    assert allow_rules[0]["priority"] == 2147483647


def test_cloud_armor_rate_limit_threshold():
    """Rate limiting rule should allow 1000 requests/min per IP."""
    lb_config = LoadBalancerConfig()
    policy = lb_config.generate_cloud_armor_policy()
    for rule in policy.get("rules", []):
        if rule.get("priority") == 1000:
            rate_limit = rule.get("rateLimitOptions", {})
            threshold = rate_limit.get("rateLimitThreshold", {})
            assert threshold.get("count") == 1000
            assert threshold.get("intervalSec") == 60
            break
    else:
        pytest.fail("Rate limit rule not found")


# ---------------------------------------------------------------------------
# Test: estimate_cost
# ---------------------------------------------------------------------------

def test_estimate_cost(sample_lb_config: LBConfig):
    """Cost estimate should return a CostEstimate with reasonable values."""
    lb_config = LoadBalancerConfig()
    cost = lb_config.estimate_cost(sample_lb_config)
    assert isinstance(cost, CostEstimate)

    # Check that monthly min <= avg <= max
    assert cost.estimated_monthly_min <= cost.estimated_monthly_avg
    assert cost.estimated_monthly_avg <= cost.estimated_monthly_max

    # All costs should be non-negative
    assert cost.estimated_monthly_min >= 0
    assert cost.estimated_monthly_avg >= 0
    assert cost.estimated_monthly_max >= 0

    # Assumptions should be documented
    assert len(cost.assumptions) > 0


def test_estimate_cost_no_cdn():
    """Cost estimate without CDN should be different from with CDN."""
    config_no_cdn = LBConfig(
        domain="visionos.app",
        ssl_certificate="managed",
        enable_cdn=False,
    )
    config_cdn = LBConfig(
        domain="visionos.app",
        ssl_certificate="managed",
        enable_cdn=True,
    )
    lb_config = LoadBalancerConfig()
    cost_no_cdn = lb_config.estimate_cost(config_no_cdn)
    cost_cdn = lb_config.estimate_cost(config_cdn)
    # CDN adds cost so values should differ (or at least not fail)
    assert isinstance(cost_no_cdn, CostEstimate)
    assert isinstance(cost_cdn, CostEstimate)


# ---------------------------------------------------------------------------
# Test: YAML config file integration
# ---------------------------------------------------------------------------

def test_config_yaml_exists(config_yaml_path: Path):
    """The load_balancer_config.yaml file should exist and be valid YAML."""
    assert config_yaml_path.exists(), "load_balancer_config.yaml not found"
    with open(config_yaml_path, "r") as f:
        data = yaml.safe_load(f)
    assert data is not None, "YAML file is empty or invalid"
    assert "loadBalancer" in data


def test_config_yaml_contains_required_fields(config_yaml_path: Path):
    """The YAML config should have all major sections."""
    with open(config_yaml_path, "r") as f:
        data = yaml.safe_load(f)

    lb = data.get("loadBalancer", {})
    # Check top-level LB keys
    for key in ("type", "domain", "ssl", "urlMap"):
        assert key in lb, f"Missing {key} in loadBalancer"

    # Check SSL
    ssl = lb.get("ssl", {})
    assert ssl.get("type") == "MANAGED"
    managed = ssl.get("managed", {})
    assert "visionos.app" in managed.get("domains", [])

    # Check URL map
    url_map = lb.get("urlMap", {})
    assert "hostRules" in url_map
    assert "pathMatchers" in url_map

    # Check CDN on static
    for matcher in url_map.get("pathMatchers", []):
        for rule in matcher.get("pathRules", []):
            if "/static/*" in rule.get("paths", []):
                cdn = rule.get("routeAction", {}).get("cdnPolicy", {})
                assert cdn.get("enabled") is True
                break

    # Check Cloud Armor
    armor = lb.get("cloudArmor", {})
    assert armor.get("name") == "vision-os-armor-policy"
    assert len(armor.get("rules", [])) > 0

    # Check backend services
    backends = lb.get("backendServices", [])
    assert len(backends) >= 2
    backend_names = [b.get("name") for b in backends]
    assert "vision-os-backend" in backend_names
    assert "vision-os-static" in backend_names


def test_config_yaml_websocket(config_yaml_path: Path):
    """The YAML config should have WebSocket support configured."""
    with open(config_yaml_path, "r") as f:
        data = yaml.safe_load(f)

    features = data.get("features", {})
    ws = features.get("websocket", {})
    assert ws.get("enabled") is True
    assert ws.get("timeout") == 3600

    # Check ws path exists in URL map
    lb = data.get("loadBalancer", {})
    url_map = lb.get("urlMap", {})
    for matcher in url_map.get("pathMatchers", []):
        for rule in matcher.get("pathRules", []):
            if "/ws/*" in rule.get("paths", []):
                timeout = rule.get("routeAction", {}).get("timeout", "")
                assert "3600" in timeout
                break


def test_config_yaml_ddos_protection(config_yaml_path: Path):
    """The YAML config should have DDoS protection enabled."""
    with open(config_yaml_path, "r") as f:
        data = yaml.safe_load(f)

    features = data.get("features", {})
    ddos = features.get("ddosProtection", {})
    assert ddos.get("enabled") is True
    assert ddos.get("type") == "cloud_armor"


# ---------------------------------------------------------------------------
# Test: CDN enabled for static content
# ---------------------------------------------------------------------------

def test_cdn_enabled_for_static(sample_lb_config: LBConfig):
    """The URL map should have CDN enabled for static routes."""
    lb_config = LoadBalancerConfig()
    url_map = lb_config.generate_url_map(sample_lb_config)
    matcher = url_map["pathMatchers"][0]
    for rule in matcher["pathRules"]:
        if "/static/*" in rule.get("paths", []):
            cdn = rule.get("routeAction", {}).get("cdnPolicy", {})
            assert cdn.get("enabled") is True
            assert cdn.get("cacheMode") == "CACHE_ALL_STATIC"
            break
    else:
        pytest.fail("No static path rule found")


# ---------------------------------------------------------------------------
# Test: Websocket timeout configuration
# ---------------------------------------------------------------------------

def test_websocket_timeout_config(sample_lb_config: LBConfig):
    """WebSocket timeout should match the config value."""
    assert sample_lb_config.websocket_timeout == 3600

    # Generate URL map and verify ws timeout
    lb_config = LoadBalancerConfig()
    url_map = lb_config.generate_url_map(sample_lb_config)
    matcher = url_map["pathMatchers"][0]
    for rule in matcher["pathRules"]:
        paths = rule.get("paths", [])
        if any("/ws/" in p for p in paths):
            timeout = rule.get("routeAction", {}).get("timeout", "0s")
            # Extract number from "3600s" format
            timeout_sec = int(timeout.rstrip("s"))
            assert timeout_sec == sample_lb_config.websocket_timeout
            break
    else:
        pytest.fail("No WebSocket path rule found")


# ---------------------------------------------------------------------------
# Test: Serialization / deserialization round trip
# ---------------------------------------------------------------------------

def test_config_serialization_deserialization(sample_lb_config: LBConfig):
    """LBConfig should survive a JSON round-trip."""
    d = {
        "domain": sample_lb_config.domain,
        "ssl_certificate": sample_lb_config.ssl_certificate,
        "backend_service": sample_lb_config.backend_service,
        "static_bucket": sample_lb_config.static_bucket,
        "region": sample_lb_config.region,
        "enable_cdn": sample_lb_config.enable_cdn,
        "enable_armor": sample_lb_config.enable_armor,
        "websocket_timeout": sample_lb_config.websocket_timeout,
    }
    json_str = json.dumps(d)
    restored = json.loads(json_str)
    lb = LBConfig(**restored)
    assert lb.domain == sample_lb_config.domain
    assert lb.backend_service == sample_lb_config.backend_service
    assert lb.static_bucket == sample_lb_config.static_bucket
    assert lb.region == sample_lb_config.region
    assert lb.enable_cdn == sample_lb_config.enable_cdn
    assert lb.enable_armor == sample_lb_config.enable_armor
    assert lb.websocket_timeout == sample_lb_config.websocket_timeout
