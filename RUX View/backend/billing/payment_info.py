"""
payment_info.py — Manual Payment Info for Vision OS.

NO bKash API integration — just display payment info.
Users manually send money to a bKash/Nagad number.
Admin verifies payment manually and upgrades tier.

Key decisions:
- D011: bKash for billing (but manual, not API)
- D014: Three pricing tiers
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PaymentMethod:
    provider: str  # "bKash" / "Nagad"
    number: str
    account_holder: str


@dataclass
class PricingTier:
    name: str  # free / household / business
    price_bdt: float
    price_usd: float
    cameras: str
    features: list[str]


@dataclass
class PaymentInfo:
    methods: list[PaymentMethod]
    tiers: list[PricingTier]
    instructions: str
    admin_contact: str  # phone number for verification


# ── Default Configuration ──────────────────────────────────────

DEFAULT_PAYMENT_INFO = PaymentInfo(
    methods=[
        PaymentMethod(provider="bKash", number="017XXXXXXXX", account_holder="Vision OS"),
        PaymentMethod(provider="Nagad", number="017XXXXXXXX", account_holder="Vision OS"),
    ],
    tiers=[
        PricingTier(
            name="free",
            price_bdt=0,
            price_usd=0,
            cameras="1-2",
            features=[
                "7 day history",
                "Indoor only",
                "Telegram alerts (20/day cap)",
                "Daily digest",
            ],
        ),
        PricingTier(
            name="household",
            price_bdt=299,
            price_usd=2.72,
            cameras="1-5",
            features=[
                "30 day history",
                "All modes",
                "Unlimited Telegram",
                "Re-ID",
                "Cross-camera",
                "Ghost detection",
                "NL Queries",
                "Emergency voice notes",
            ],
        ),
        PricingTier(
            name="business",
            price_bdt=499,
            price_usd=4.54,
            cameras="1-5",
            features=[
                "90 day history",
                "All modes + Shop analytics",
                "Unlimited Telegram",
                "Re-ID + Staff filter",
                "Cross-camera + Ghost",
                "NL Queries",
                "Emergency voice notes",
                "SMS fallback",
                "Weekly reports",
            ],
        ),
    ],
    instructions=(
        "To upgrade your Vision OS subscription:\n"
        "1. Send the amount to the bKash or Nagad number above\n"
        "2. Send a screenshot to the admin contact via WhatsApp\n"
        "3. Your tier will be upgraded within 24 hours"
    ),
    admin_contact="017XXXXXXXX",
)


class PaymentConfig:
    """Payment configuration and info provider."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize payment config.

        Args:
            config_path: Path to JSON config file (optional).
                If provided, loads config from file.
                If not, uses DEFAULT_PAYMENT_INFO.
        """
        if config_path:
            self._info = self.load_from_file(config_path)
        else:
            # Deep copy to avoid mutating the global default
            self._info = PaymentInfo(
                methods=[PaymentMethod(**asdict(m)) for m in DEFAULT_PAYMENT_INFO.methods],
                tiers=[PricingTier(**asdict(t)) for t in DEFAULT_PAYMENT_INFO.tiers],
                instructions=DEFAULT_PAYMENT_INFO.instructions,
                admin_contact=DEFAULT_PAYMENT_INFO.admin_contact,
            )

    def get_payment_info(self) -> PaymentInfo:
        """Get all payment information.

        Returns:
            PaymentInfo with methods, tiers, instructions.
        """
        return self._info

    def get_tiers(self) -> list[PricingTier]:
        """Get pricing tiers.

        Returns:
            List of PricingTier with features.
        """
        return self._info.tiers

    def get_methods(self) -> list[PaymentMethod]:
        """Get available payment methods.

        Returns:
            List of PaymentMethod (bKash, Nagad).
        """
        return self._info.methods

    def get_instructions(self) -> str:
        """Get payment instructions text.

        Returns:
            Formatted instructions string with payment details.
        """
        # If instructions have been customized, return them as-is
        if self._info.instructions != DEFAULT_PAYMENT_INFO.instructions:
            return self._info.instructions

        # Build dynamic instructions with actual payment numbers
        methods = self._info.methods
        if methods:
            method = methods[0]
            return (
                f"To upgrade your Vision OS subscription:\n"
                f"1. Send the amount to {method.provider} number: {method.number}\n"
                f"2. Send a screenshot to {self._info.admin_contact} via WhatsApp\n"
                f"3. Your tier will be upgraded within 24 hours"
            )
        return self._info.instructions

    def get_tier_by_name(self, name: str) -> Optional[PricingTier]:
        """Get a pricing tier by name.

        Args:
            name: Tier name (free/household/business).

        Returns:
            PricingTier if found, None otherwise.
        """
        for tier in self._info.tiers:
            if tier.name == name:
                return tier
        return None

    def load_from_file(self, config_path: str) -> PaymentInfo:
        """Load payment config from JSON file.

        Args:
            config_path: Path to JSON config file.

        Returns:
            PaymentInfo loaded from file.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            json.JSONDecodeError: If config file is invalid JSON.
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            methods = [
                PaymentMethod(**m) for m in data.get("methods", [])
            ]
            tiers = [
                PricingTier(**t) for t in data.get("tiers", [])
            ]

            return PaymentInfo(
                methods=methods or DEFAULT_PAYMENT_INFO.methods,
                tiers=tiers or DEFAULT_PAYMENT_INFO.tiers,
                instructions=data.get(
                    "instructions", DEFAULT_PAYMENT_INFO.instructions
                ),
                admin_contact=data.get(
                    "admin_contact", DEFAULT_PAYMENT_INFO.admin_contact
                ),
            )
        except FileNotFoundError:
            logger.warning(
                "Config file not found: %s. Using defaults.", config_path
            )
            return DEFAULT_PAYMENT_INFO

    def save_to_file(self, config_path: str) -> None:
        """Save payment config to JSON file.

        Args:
            config_path: Path to save JSON config file.
        """
        data = {
            "methods": [asdict(m) for m in self._info.methods],
            "tiers": [asdict(t) for t in self._info.tiers],
            "instructions": self._info.instructions,
            "admin_contact": self._info.admin_contact,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Payment config saved to: %s", config_path)

    def update_method(self, provider: str, number: str,
                      account_holder: str) -> bool:
        """Update a payment method.

        Args:
            provider: Provider name (bKash/Nagad).
            number: Payment number.
            account_holder: Account holder name.

        Returns:
            True if updated, False if provider not found.
        """
        for method in self._info.methods:
            if method.provider.lower() == provider.lower():
                method.number = number
                method.account_holder = account_holder
                return True
        return False

    def update_instructions(self, instructions: str) -> None:
        """Update payment instructions.

        Args:
            instructions: New instructions text.
        """
        self._info.instructions = instructions

    def update_admin_contact(self, contact: str) -> None:
        """Update admin contact number.

        Args:
            contact: New admin contact number.
        """
        self._info.admin_contact = contact
