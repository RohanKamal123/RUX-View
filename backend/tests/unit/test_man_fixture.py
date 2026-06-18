@pytest.fixture
def manager():
    """Create ApiKeyManager with mock session factory."""
    from unittest.mock import MagicMock, AsyncMock
    session_factory = MagicMock()
        session = AsyncMock()
        stored_keys = []
        usage_records = []
        
        def execute_side_effect(stmt):
            mock = MagicMock()
            if "api_keys" in str(stmt):
                mock.scalar_one_or_none = MagicMock(side_effect=lambda: stored_keys[0]["model"] if stored_keys else None)
                mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(side_effect=lambda: [k["model"] for k in stored_keys])))
            else:
                mock.scalar_one_or_none.return_value = None
                mock.scalars.return_value.all.return_value = []
            return mock
        session.execute = MagicMock(side_effect=execute_side_effect)
        async def add_side_effect(obj):
            if hasattr(obj, "__tablename__"):
                if obj.__tablename__ == "api_keys":
                    stored_keys.append({"model": obj, "user_id": obj.user_id})
                elif obj.__tablename__ == "api_key_usage":
                    usage_records.append(obj)
        session.add = AsyncMock(side_effect=add_side_effect)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session_factory.return_value.__aenter__.return_value = session
        session_factory.return_value.__aexit__.return_value = None
        return ApiKeyManager(session_factory), session
