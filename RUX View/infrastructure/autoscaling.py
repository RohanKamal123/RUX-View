"""
autoscaling.py — Auto-Scaling Configuration for Vision OS.

Auto-scaling configuration for Google Cloud Run deployment.
Supports scaling based on CPU utilization, concurrent requests,
and queue depth for AI-powered CCTV intelligence.

Key decisions:
- D026: All calls async
- Cloud Run for serverless scaling
- VPC connector for secure database access
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


# ── Data Classes ──────────────────────────────────────────────


@dataclass
class ScalingConfig:
    """Configuration for Cloud Run auto-scaling.

    Attributes:
        min_instances: Minimum number of warm instances (default 1).
        max_instances: Maximum instances during peak (default 10).
        concurrency: Max concurrent requests per instance (default 80).
        cpu: vCPU count per instance (default "2").
        memory: Memory per instance (default "2Gi").
        startup_cpu_boost: Enable CPU boost during startup (default True).
        request_timeout: Request timeout in seconds (default 300).
        idle_timeout: Idle instance timeout in seconds (default 300).
        vpc_connector: VPC connector name for Cloud SQL access.
        vpc_egress: VPC egress setting (default "private-ranges-only").
    """

    min_instances: int = 1
    max_instances: int = 10
    concurrency: int = 80
    cpu: str = "2"
    memory: str = "2Gi"
    startup_cpu_boost: bool = True
    request_timeout: int = 300
    idle_timeout: int = 300
    vpc_connector: Optional[str] = None
    vpc_egress: str = "private-ranges-only"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = asdict(self)
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "ScalingConfig":
        """Deserialize from dictionary.

        Args:
            data: Dictionary with config values.

        Returns:
            ScalingConfig instance.
        """
        return cls(
            min_instances=data.get("min_instances", 1),
            max_instances=data.get("max_instances", 10),
            concurrency=data.get("concurrency", 80),
            cpu=data.get("cpu", "2"),
            memory=data.get("memory", "2Gi"),
            startup_cpu_boost=data.get("startup_cpu_boost", True),
            request_timeout=data.get("request_timeout", 300),
            idle_timeout=data.get("idle_timeout", 300),
            vpc_connector=data.get("vpc_connector"),
            vpc_egress=data.get("vpc_egress", "private-ranges-only"),
        )


@dataclass
class CostEstimate:
    """Monthly cost estimate for Cloud Run deployment.

    Attributes:
        min_instances: Minimum instances configured.
        max_instances: Maximum instances configured.
        estimated_monthly_min: Estimated cost at min instances.
        estimated_monthly_max: Estimated cost at max instances.
        estimated_monthly_avg: Estimated cost at average usage.
        cost_per_instance_hour: Cost per instance per hour.
        assumptions: List of assumptions used in estimate.
    """

    min_instances: int
    max_instances: int
    estimated_monthly_min: float
    estimated_monthly_max: float
    estimated_monthly_avg: float
    cost_per_instance_hour: float
    assumptions: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """Scaling recommendation based on metrics.

    Attributes:
        metric: The metric being evaluated.
        current_value: Current metric value.
        recommended_value: Recommended metric value.
        reason: Explanation for the recommendation.
        estimated_savings: Estimated monthly savings (optional).
    """

    metric: str
    current_value: float
    recommended_value: float
    reason: str
    estimated_savings: Optional[float] = None


# ── Cloud Run YAML Template ────────────────────────────────────

CLOUD_RUN_YAML_TEMPLATE = """\
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: vision-os-api
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/ingress-status: all
    run.googleapis.com/launch-stage: stable
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "{min_instances}"
        autoscaling.knative.dev/maxScale: "{max_instances}"
        autoscaling.knative.dev/target: "{concurrency}"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/startup-cpu-boost: "{startup_cpu_boost}"
        run.googleapis.com/vpc-access-egress: "{vpc_egress}"
        run.googleapis.com/client-name: "vision-os"
    spec:
      containerConcurrency: {concurrency}
      timeoutSeconds: {request_timeout}
      serviceAccountName: vision-os-api-sa
      volumes:
        - name: cloud-sql-proxy
          emptyDir:
            sizeLimit: 1Gi
      containers:
        - image: gcr.io/vision-os/vision-os-api:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: cloud-sql-credentials
                  key: database_url
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: api-secrets
                  key: secret_key
            - name: GROQ_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ai-service-keys
                  key: groq_api_key
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: ai-service-keys
                  key: openai_api_key
            - name: TELEGRAM_BOT_TOKEN
              valueFrom:
                secretKeyRef:
                  name: notification-keys
                  key: telegram_bot_token
            - name: SMS_API_KEY
              valueFrom:
                secretKeyRef:
                  name: notification-keys
                  key: sms_api_key
            - name: STORAGE_BUCKET
              value: vision-os-clips
            - name: REGION
              value: asia-south1
            - name: VISION_OS_ENV
              value: production
          resources:
            limits:
              cpu: "{cpu}"
              memory: "{memory}"
          startupProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 5
            timeoutSeconds: 3
            failureThreshold: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          volumeMounts:
            - name: cloud-sql-proxy
              mountPath: /cloudsql
"""


# ── Main Class ────────────────────────────────────────────────


class AutoScalingConfig:
    """Auto-scaling configuration manager for Vision OS.

    Handles configuration validation, Cloud Run YAML generation,
    cost estimation, and scaling recommendations based on metrics.
    """

    INSTANCE_HOURLY_COST = 0.10  # $0.10/hr per instance (2 vCPU, 2GB)
    AVG_UTILIZATION = 0.45  # Typical avg utilization factor
    HOURS_PER_MONTH = 730  # Average hours per month

    def __init__(self, config: Optional[ScalingConfig] = None):
        """Initialize auto-scaling configuration.

        Args:
            config: ScalingConfig instance. Uses defaults if None.
        """
        self.config = config or ScalingConfig()

    def load_config(self) -> ScalingConfig:
        """Load the current scaling configuration.

        Returns:
            The current ScalingConfig instance.
        """
        return self.config

    def validate_config(self, config: ScalingConfig) -> bool:
        """Validate scaling configuration parameters.

        Checks:
        - min_instances >= 0
        - max_instances >= min_instances
        - concurrency > 0 and <= 250
        - cpu is valid
        - memory is valid
        - timeouts are positive

        Args:
            config: ScalingConfig to validate.

        Returns:
            True if config is valid, False otherwise.
        """
        if config.min_instances < 0:
            logger.error("min_instances must be >= 0, got %d", config.min_instances)
            return False

        if config.max_instances < config.min_instances:
            logger.error(
                "max_instances (%d) must be >= min_instances (%d)",
                config.max_instances, config.min_instances,
            )
            return False

        if config.concurrency <= 0 or config.concurrency > 250:
            logger.error(
                "concurrency must be between 1 and 250, got %d",
                config.concurrency,
            )
            return False

        # CPU must be a valid Cloud Run value
        valid_cpus = {"1", "2", "4", "6", "8"}
        if config.cpu not in valid_cpus:
            logger.error("Invalid CPU value '%s'. Must be one of: %s", config.cpu, valid_cpus)
            return False

        # Memory must be a valid Cloud Run value
        valid_memories = {"512Mi", "1Gi", "2Gi", "4Gi", "8Gi", "16Gi", "32Gi"}
        if config.memory not in valid_memories:
            logger.error(
                "Invalid memory value '%s'. Must be one of: %s",
                config.memory, valid_memories,
            )
            return False

        if config.request_timeout <= 0 or config.request_timeout > 3600:
            logger.error(
                "request_timeout must be between 1 and 3600, got %d",
                config.request_timeout,
            )
            return False

        if config.idle_timeout <= 0 or config.idle_timeout > 3600:
            logger.error(
                "idle_timeout must be between 1 and 3600, got %d",
                config.idle_timeout,
            )
            return False

        return True

    def generate_cloud_run_yaml(self, config: ScalingConfig) -> str:
        """Generate Cloud Run YAML configuration.

        Args:
            config: ScalingConfig to use for YAML generation.

        Returns:
            Formatted YAML string for Cloud Run deployment.
        """
        startup_boost = "true" if config.startup_cpu_boost else "false"

        yaml_content = CLOUD_RUN_YAML_TEMPLATE.format(
            min_instances=config.min_instances,
            max_instances=config.max_instances,
            concurrency=config.concurrency,
            cpu=config.cpu,
            memory=config.memory,
            startup_cpu_boost=startup_boost,
            request_timeout=config.request_timeout,
            idle_timeout=config.idle_timeout,
            vpc_egress=config.vpc_egress,
        )

        # Add VPC connector if configured
        if config.vpc_connector:
            vpc_block = f"""
      vpcAccess:
        connector: {config.vpc_connector}
        egress: {config.vpc_egress}
"""
            # Insert VPC config before containers
            yaml_content = yaml_content.replace(
                "      serviceAccountName: vision-os-api-sa",
                f"      serviceAccountName: vision-os-api-sa{vpc_block}",
            )

        # Validate YAML is parseable
        parsed = yaml.safe_load(yaml_content)
        if not parsed:
            raise ValueError("Generated YAML is not valid")

        return yaml_content

    def estimate_cost(self, instances: int, hours: float) -> CostEstimate:
        """Estimate monthly cost for given instance count.

        Args:
            instances: Number of instances.
            hours: Number of hours running.

        Returns:
            CostEstimate with cost breakdown.
        """
        cost = instances * hours * self.INSTANCE_HOURLY_COST

        # Monthly estimates
        monthly_min = (
            self.config.min_instances
            * self.HOURS_PER_MONTH
            * self.INSTANCE_HOURLY_COST
        )
        monthly_max = (
            self.config.max_instances
            * self.HOURS_PER_MONTH
            * self.INSTANCE_HOURLY_COST
        )
        avg_instances = round(
            self.config.min_instances
            + (self.config.max_instances - self.config.min_instances)
            * self.AVG_UTILIZATION
        )
        monthly_avg = avg_instances * self.HOURS_PER_MONTH * self.INSTANCE_HOURLY_COST

        assumptions = [
            f"Cost per instance/hour: ${self.INSTANCE_HOURLY_COST:.2f}",
            f"Average utilization: {self.AVG_UTILIZATION * 100:.0f}%",
            f"Hours per month: {self.HOURS_PER_MONTH}",
            "Does not include Cloud SQL, Cloud Storage, or networking costs",
            "Actual costs may vary based on actual usage patterns",
        ]

        return CostEstimate(
            min_instances=self.config.min_instances,
            max_instances=self.config.max_instances,
            estimated_monthly_min=round(monthly_min, 2),
            estimated_monthly_max=round(monthly_max, 2),
            estimated_monthly_avg=round(monthly_avg, 2),
            cost_per_instance_hour=self.INSTANCE_HOURLY_COST,
            assumptions=assumptions,
        )

    def get_scaling_recommendations(self, metrics: dict) -> list[Recommendation]:
        """Generate scaling recommendations based on metrics.

        Analyzes CPU utilization, concurrent requests, queue depth,
        and other metrics to provide optimization recommendations.

        Args:
            metrics: Dictionary with metric values.
                Expected keys:
                - cpu_utilization_pct: Average CPU utilization %
                - concurrent_requests: Current concurrent requests
                - queue_depth: Current message queue depth
                - error_rate: Current error rate %
                - p95_latency_ms: P95 API latency in ms

        Returns:
            List of Recommendation objects.
        """
        recommendations: list[Recommendation] = []

        # CPU utilization recommendations
        cpu = metrics.get("cpu_utilization_pct", 0)
        if cpu > 80:
            recommendations.append(
                Recommendation(
                    metric="cpu_utilization_pct",
                    current_value=cpu,
                    recommended_value=70.0,
                    reason=(
                        f"CPU utilization is high ({cpu:.1f}%). "
                        "Consider increasing max_instances or enabling "
                        "additional scaling metrics."
                    ),
                )
            )
        elif cpu < 20 and self.config.min_instances > 1:
            savings = (
                (self.config.min_instances - 1)
                * self.HOURS_PER_MONTH
                * self.INSTANCE_HOURLY_COST
            )
            recommendations.append(
                Recommendation(
                    metric="cpu_utilization_pct",
                    current_value=cpu,
                    recommended_value=50.0,
                    reason=(
                        f"CPU utilization is low ({cpu:.1f}%). "
                        "Consider reducing min_instances to save costs."
                    ),
                    estimated_savings=round(savings, 2),
                )
            )

        # Concurrent requests recommendations
        concurrent = metrics.get("concurrent_requests", 0)
        if concurrent > self.config.concurrency * 0.8:
            new_concurrency = min(int(self.config.concurrency * 1.5), 250)
            recommendations.append(
                Recommendation(
                    metric="concurrent_requests",
                    current_value=concurrent,
                    recommended_value=float(self.config.concurrency),
                    reason=(
                        f"Concurrent requests ({concurrent}) approaching "
                        f"limit ({self.config.concurrency}). "
                        f"Increase concurrency to {new_concurrency}."
                    ),
                )
            )

        # Queue depth recommendations
        queue = metrics.get("queue_depth", 0)
        if queue > 100:
            recommendations.append(
                Recommendation(
                    metric="queue_depth",
                    current_value=queue,
                    recommended_value=50.0,
                    reason=(
                        f"Queue depth is {queue}. "
                        "Consider increasing max_instances or optimizing "
                        "AI inference pipeline."
                    ),
                )
            )

        # P95 latency recommendations
        latency = metrics.get("p95_latency_ms", 0)
        if latency > 3000:
            recommendations.append(
                Recommendation(
                    metric="p95_latency_ms",
                    current_value=latency,
                    recommended_value=1000.0,
                    reason=(
                        f"P95 latency is high ({latency:.0f}ms). "
                        "Consider increasing CPU or optimizing AI model inference."
                    ),
                )
            )

        # Error rate recommendations
        error_rate = metrics.get("error_rate", 0)
        if error_rate > 5:
            recommendations.append(
                Recommendation(
                    metric="error_rate",
                    current_value=error_rate,
                    recommended_value=1.0,
                    reason=(
                        f"Error rate is {error_rate:.1f}%. "
                        "Investigate root cause. Consider rolling back recent "
                        "deployments if errors started after an update."
                    ),
                )
            )

        return recommendations


# ── Default Config ● Singleton ─────────────────────────────────

DEFAULT_SCALING_CONFIG = ScalingConfig(
    min_instances=1,
    max_instances=10,
    concurrency=80,
    cpu="2",
    memory="2Gi",
    startup_cpu_boost=True,
    request_timeout=300,
    idle_timeout=300,
    vpc_connector=None,
    vpc_egress="private-ranges-only",
)
