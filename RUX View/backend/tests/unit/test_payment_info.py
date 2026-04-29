"""
Tests for Sprint 5.3 — Manual Payment Info.

Tests PaymentConfig class, dataclasses, default configuration,
file I/O, and tier information.
"""

import json
import os
import tempfile

import pytest

from backend.billing.payment_info import (
    PaymentConfig,
    PaymentInfo,
    PaymentMethod,
    PricingTier,
    DEFAULT_PAYMENT_INFO,
)


# ── Tests ──────────────────────────────────────────────────────


class TestPaymentConfig:
    def test_get_payment_info_returns_methods(self):
        """get_payment_info should return payment methods."""
        config = PaymentConfig()
        info = config.get_payment_info()
        assert len(info.methods) > 0
        assert all(isinstance(m, PaymentMethod) for m in info.methods)

    def test_get_tiers_returns_three_tiers(self):
        """get_tiers should return three pricing tiers."""
        config = PaymentConfig()
        tiers = config.get_tiers()
        assert len(tiers) == 3

    def test_free_tier_price_is_zero(self):
        """Free tier price should be 0 BDT."""
        config = PaymentConfig()
        tier = config.get_tier_by_name("free")
        assert tier is not None
        assert tier.price_bdt == 0
        assert tier.price_usd == 0

    def test_household_tier_price_is_299(self):
        """Household tier price should be 299 BDT."""
        config = PaymentConfig()
        tier = config.get_tier_by_name("household")
        assert tier is not None
        assert tier.price_bdt == 299
        assert tier.price_usd == 2.72

    def test_business_tier_price_is_499(self):
        """Business tier price should be 499 BDT."""
        config = PaymentConfig()
        tier = config.get_tier_by_name("business")
        assert tier is not None
        assert tier.price_bdt == 499
        assert tier.price_usd == 4.54

    def test_get_instructions_contains_number(self):
        """get_instructions should contain the payment number."""
        config = PaymentConfig()
        instructions = config.get_instructions()
        assert "017XXXXXXXX" in instructions
        assert "bKash" in instructions or "Nagad" in instructions

    def test_load_from_file(self):
        """load_from_file should load config from JSON file."""
        data = {
            "methods": [
                {"provider": "bKash", "number": "018XXXXXXXX",
                 "account_holder": "Test"},
            ],
            "tiers": [
                {"name": "test", "price_bdt": 100, "price_usd": 1.0,
                 "cameras": "1", "features": ["Test feature"]},
            ],
            "instructions": "Test instructions",
            "admin_contact": "018XXXXXXXX",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            config = PaymentConfig(config_path=temp_path)
            info = config.get_payment_info()
            assert len(info.methods) == 1
            assert info.methods[0].provider == "bKash"
            assert info.admin_contact == "018XXXXXXXX"
        finally:
            os.unlink(temp_path)

    def test_save_to_file(self):
        """save_to_file should save config to JSON file."""
        config = PaymentConfig()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            temp_path = f.name

        try:
            config.save_to_file(temp_path)

            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "methods" in data
            assert "tiers" in data
            assert "instructions" in data
            assert "admin_contact" in data
            assert len(data["methods"]) == 2
            assert len(data["tiers"]) == 3
        finally:
            os.unlink(temp_path)

    def test_default_config_has_bkash_and_nagad(self):
        """Default config should have both bKash and Nagad."""
        config = PaymentConfig()
        methods = config.get_methods()
        providers = [m.provider for m in methods]
        assert "bKash" in providers
        assert "Nagad" in providers

    def test_tier_features_are_correct(self):
        """Tier features should match expected values."""
        config = PaymentConfig()

        free = config.get_tier_by_name("free")
        assert free is not None
        assert "7 day history" in free.features
        assert "Indoor only" in free.features

        household = config.get_tier_by_name("household")
        assert household is not None
        assert "30 day history" in household.features
        assert "NL Queries" in household.features

        business = config.get_tier_by_name("business")
        assert business is not None
        assert "90 day history" in business.features
        assert "Shop analytics" in " ".join(business.features)
        assert "SMS fallback" in business.features

    def test_get_methods_returns_list(self):
        """get_methods should return a list of PaymentMethod."""
        config = PaymentConfig()
        methods = config.get_methods()
        assert isinstance(methods, list)
        assert all(isinstance(m, PaymentMethod) for m in methods)

    def test_get_tier_by_name_returns_none_for_invalid(self):
        """get_tier_by_name should return None for invalid tier."""
        config = PaymentConfig()
        tier = config.get_tier_by_name("nonexistent")
        assert tier is None

    def test_update_method_updates_existing(self):
        """update_method should update an existing payment method."""
        config = PaymentConfig()
        result = config.update_method(
            "bKash", "019XXXXXXXX", "New Holder"
        )
        assert result is True

        methods = config.get_methods()
        bkash = next(m for m in methods if m.provider == "bKash")
        assert bkash.number == "019XXXXXXXX"
        assert bkash.account_holder == "New Holder"

    def test_update_method_returns_false_for_unknown(self):
        """update_method should return False for unknown provider."""
        config = PaymentConfig()
        result = config.update_method(
            "Unknown", "0000000000", "No one"
        )
        assert result is False

    def test_update_instructions(self):
        """update_instructions should update instructions text."""
        config = PaymentConfig()
        config.update_instructions("New instructions")
        assert config.get_instructions() == "New instructions"

    def test_update_admin_contact(self):
        """update_admin_contact should update contact number."""
        config = PaymentConfig()
        config.update_admin_contact("019XXXXXXXX")
        assert config.get_payment_info().admin_contact == "019XXXXXXXX"

    def test_load_from_file_fallback_on_missing(self):
        """load_from_file should fall back to defaults if file missing."""
        config = PaymentConfig(config_path="/nonexistent/path.json")
        info = config.get_payment_info()
        assert len(info.methods) == 2
        assert len(info.tiers) == 3


class TestDataclasses:
    def test_payment_method_dataclass(self):
        """PaymentMethod dataclass should work correctly."""
        method = PaymentMethod(
            provider="bKash",
            number="017XXXXXXXX",
            account_holder="Vision OS",
        )
        assert method.provider == "bKash"
        assert method.number == "017XXXXXXXX"

    def test_pricing_tier_dataclass(self):
        """PricingTier dataclass should work correctly."""
        tier = PricingTier(
            name="test",
            price_bdt=100,
            price_usd=1.0,
            cameras="1-2",
            features=["Feature 1", "Feature 2"],
        )
        assert tier.name == "test"
        assert tier.price_bdt == 100
        assert len(tier.features) == 2

    def test_payment_info_dataclass(self):
        """PaymentInfo dataclass should work correctly."""
        info = PaymentInfo(
            methods=[
                PaymentMethod(
                    provider="bKash",
                    number="017XXXXXXXX",
                    account_holder="Vision OS",
                ),
            ],
            tiers=[
                PricingTier(
                    name="free",
                    price_bdt=0,
                    price_usd=0,
                    cameras="1-2",
                    features=["Test"],
                ),
            ],
            instructions="Test instructions",
            admin_contact="017XXXXXXXX",
        )
        assert len(info.methods) == 1
        assert len(info.tiers) == 1
        assert info.admin_contact == "017XXXXXXXX"


class TestDefaultConfig:
    def test_default_payment_info_exists(self):
        """DEFAULT_PAYMENT_INFO should be defined."""
        assert DEFAULT_PAYMENT_INFO is not None
        assert len(DEFAULT_PAYMENT_INFO.methods) == 2
        assert len(DEFAULT_PAYMENT_INFO.tiers) == 3

    def test_default_tier_names(self):
        """Default tiers should have correct names."""
        names = [t.name for t in DEFAULT_PAYMENT_INFO.tiers]
        assert names == ["free", "household", "business"]

    def test_default_method_providers(self):
        """Default methods should have correct providers."""
        providers = [m.provider for m in DEFAULT_PAYMENT_INFO.methods]
        assert "bKash" in providers
        assert "Nagad" in providers

    def test_default_instructions_not_empty(self):
        """Default instructions should not be empty."""
        config = PaymentConfig()
        instructions = config.get_instructions()
        assert len(instructions) > 0
        assert "bKash" in instructions
