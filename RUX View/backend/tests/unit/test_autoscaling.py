"""Tests for the auto-scaling configuration module (Sprint 10.1)."""
import pytest
import json
import yaml
from datetime import datetime, timedelta
from infrastructure.autoscaling import (
    AutoScalingConfig,
    ScalingConfig,
    CostEstimate,
    Recommendation,
)


class TestAutoScalingConfig:
    """Test suite for AutoScalingConfig."""

    def setup_method(self):
        self.config_manager = AutoScalingConfig()

    def test_load_config_returns_defaults(self):
        """Test that load_config returns defaults when no file path given."""
        config = self.config_manager.load_config()
        assert isinstance(config, ScalingConfig)
        assert config.min_instances == 1
        assert config.max_instances == 10
        assert config.concurrency == 80
        assert config.cpu == "2"
        assert config.memory == "2Gi"
        assert config.startup_cpu_boost is True
        assert config.request_timeout == 300
        assert config.idle_timeout == 300

    def test_validate_config_valid(self):
        """Test that a valid config passes validation."""
        config = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=80,
            cpu="2",
            memory="2Gi",
            startup_cpu_boost=True,
            request_timeout=300,
            idle_timeout=300,
        )
        assert self.config_manager.validate_config(config) is True

    def test_validate_config_invalid_min_instances(self):
        """Test validation rejects config with min > max instances."""
        config = ScalingConfig(
            min_instances=10,
            max_instances=5,
            concurrency=80,
            cpu="2",
            memory="2Gi",
        )
        assert self.config_manager.validate_config(config) is False

    def test_validate_config_invalid_concurrency(self):
        """Test validation rejects config with concurrency <= 0."""
        config = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=0,
            cpu="2",
            memory="2Gi",
        )
        assert self.config_manager.validate_config(config) is False

    def test_validate_config_invalid_timeout(self):
        """Test validation rejects config with timeout <= 0."""
        config = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=80,
            cpu="2",
            memory="2Gi",
            request_timeout=0,
        )
        assert self.config_manager.validate_config(config) is False

    def test_generate_cloud_run_yaml_contains_required_fields(self):
        """Test that generated YAML includes all required Cloud Run fields."""
        config = ScalingConfig()
        yaml_content = self.config_manager.generate_cloud_run_yaml(config)
        parsed = yaml.safe_load(yaml_content)

        # Check metadata
        assert parsed["metadata"]["name"] == "vision-os-api"

        # Check scaling annotations
        annotations = parsed["spec"]["template"]["metadata"]["annotations"]
        assert annotations["autoscaling.knative.dev/minScale"] == "1"
        assert annotations["autoscaling.knative.dev/maxScale"] == "10"
        assert annotations["autoscaling.knative.dev/target"] == "80"
        assert annotations["run.googleapis.com/startup-cpu-boost"] == "true"

        # Check container specs
        container = parsed["spec"]["template"]["spec"]["containers"][0]
        assert container["ports"][0]["containerPort"] == 8080
        assert container["resources"]["limits"]["cpu"] == "2"
        assert container["resources"]["limits"]["memory"] == "2Gi"

        # Check timeouts
        assert parsed["spec"]["template"]["spec"]["timeoutSeconds"] == 300
        assert parsed["spec"]["template"]["spec"]["containerConcurrency"] == 80

        # Check VPC
        assert "vpcAccess" in parsed["spec"]["template"]["spec"]

        # Check health probes
        assert "startupProbe" in container
        assert container["startupProbe"]["httpGet"]["path"] == "/health"
        assert "livenessProbe" in container
        assert container["livenessProbe"]["httpGet"]["path"] == "/health"

    def test_estimate_cost_calculation(self):
        """Test that cost estimation returns valid numbers."""
        estimate = self.config_manager.estimate_cost(
            instances=5,
            hours=720.0,  # 30 days
        )
        assert isinstance(estimate, CostEstimate)
        assert estimate.min_instances == 1
        assert estimate.max_instances == 10
        assert estimate.estimated_monthly_min > 0
        assert estimate.estimated_monthly_max > 0
        assert estimate.estimated_monthly_avg > 0
        assert estimate.cost_per_instance_hour > 0
        assert len(estimate.assumptions) > 0
        # Min should be less than or equal to max
        assert estimate.estimated_monthly_min <= estimate.estimated_monthly_max

    def test_estimate_cost_with_zero_hours(self):
        """Test cost estimation with zero hours returns zero."""
        estimate = self.config_manager.estimate_cost(instances=0, hours=0)
        assert estimate.estimated_monthly_min == 0
        assert estimate.estimated_monthly_max == 0
        assert estimate.estimated_monthly_avg == 0

    def test_get_scaling_recommendations_high_cpu(self):
        """Test that high CPU utilization triggers scale-up recommendation."""
        metrics = {
            "cpu_utilization": 85.0,
            "concurrent_requests": 60,
            "queue_depth": 20,
            "memory_utilization": 45.0,
            "error_rate": 0.5,
            "request_latency_p95_ms": 800,
        }
        recommendations = self.config_manager.get_scaling_recommendations(metrics)
        assert len(recommendations) > 0
        # Should recommend increasing max instances for high CPU
        cpu_recs = [r for r in recommendations if "CPU" in r.metric or "cpu" in r.metric.lower()]
        assert len(cpu_recs) > 0
        for rec in cpu_recs:
            assert rec.current_value == 85.0
            assert rec.recommended_value > rec.current_value

    def test_get_scaling_recommendations_low_usage(self):
        """Test that low usage doesn't trigger scale-up recommendations."""
        metrics = {
            "cpu_utilization": 15.0,
            "concurrent_requests": 5,
            "queue_depth": 0,
            "memory_utilization": 20.0,
            "error_rate": 0.1,
            "request_latency_p95_ms": 200,
        }
        recommendations = self.config_manager.get_scaling_recommendations(metrics)
        # Should not have any scale-up recommendations
        scale_up_recs = [
            r for r in recommendations
            if r.recommended_value > r.current_value
        ]
        assert len(scale_up_recs) == 0

    def test_get_scaling_recommendations_high_queue_depth(self):
        """Test that high queue depth triggers recommendation."""
        metrics = {
            "cpu_utilization": 45.0,
            "concurrent_requests": 70,
            "queue_depth": 50,
            "memory_utilization": 55.0,
            "error_rate": 1.0,
            "request_latency_p95_ms": 900,
        }
        recommendations = self.config_manager.get_scaling_recommendations(metrics)
        queue_recs = [
            r for r in recommendations
            if "queue" in r.metric.lower() or "Queue" in r.metric
        ]
        assert len(queue_recs) > 0

    def test_config_serialization_deserialization(self):
        """Test that config can be serialized to dict and reconstructed."""
        config = ScalingConfig(
            min_instances=2,
            max_instances=8,
            concurrency=60,
            cpu="4",
            memory="4Gi",
            startup_cpu_boost=False,
            request_timeout=600,
            idle_timeout=600,
            vpc_connector="custom-connector",
            vpc_egress="all-traffic",
        )
        # Serialize to dict
        config_dict = {
            "min_instances": config.min_instances,
            "max_instances": config.max_instances,
            "concurrency": config.concurrency,
            "cpu": config.cpu,
            "memory": config.memory,
            "startup_cpu_boost": config.startup_cpu_boost,
            "request_timeout": config.request_timeout,
            "idle_timeout": config.idle_timeout,
            "vpc_connector": config.vpc_connector,
            "vpc_egress": config.vpc_egress,
        }
        # Deserialize back
        restored = ScalingConfig(**config_dict)
        assert restored == config

    def test_concurrency_limit_enforced(self):
        """Test that concurrency values outside valid range are rejected."""
        # Test concurrency too high
        config_high = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=250,  # Above typical max of 250
            cpu="2",
            memory="2Gi",
        )
        assert self.config_manager.validate_config(config_high) is False

        # Test concurrency too low
        config_low = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=0,  # Invalid
            cpu="2",
            memory="2Gi",
        )
        assert self.config_manager.validate_config(config_low) is False

        # Test concurrency at boundary
        config_ok = ScalingConfig(
            min_instances=1,
            max_instances=10,
            concurrency=1,  # Minimum valid
            cpu="2",
            memory="2Gi",
        )
        assert self.config_manager.validate_config(config_ok) is True

    def test_recommendation_dataclass(self):
        """Test the Recommendation dataclass construction and defaults."""
        rec = Recommendation(
            metric="CPU Utilization",
            current_value=85.0,
            recommended_value=70.0,
            reason="High CPU usage suggests need for more instances",
        )
        assert rec.metric == "CPU Utilization"
        assert rec.current_value == 85.0
        assert rec.recommended_value == 70.0
        assert rec.estimated_savings is None

    def test_recommendation_with_savings(self):
        """Test Recommendation with cost savings estimate."""
        rec = Recommendation(
            metric="CPU Utilization",
            current_value=85.0,
            recommended_value=70.0,
            reason="High CPU usage suggests need for more instances",
            estimated_savings=150.50,
        )
        assert rec.estimated_savings == 150.50
