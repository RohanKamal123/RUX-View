@pytest.fixture
def manager():
    """Create ApiKeyManager with mock session factory."""
    from unittest.mock import MagicMock, AsyncMock
    
        class MockSession:
            def __init__(self):
                self.stored_keys = []
                self.usage_records = []
                self.execute = AsyncMock(side_effect=self._execute)
                self.add = AsyncMock(side_effect=self._add)
                self.commit = AsyncMock()
                self.refresh = AsyncMock()
            
            async def _execute(self, stmt):
                result = AsyncMock()
                if "api_keys" in str(stmt):
                    result.scalar_one_or_none.side_effect = lambda: self.stored_keys[0]["model"] if self.stored_keys else None
                    result.scalars.return_value.all.side_effect = lambda: [k["model"] for k in self.stored_keys]
                else:
                    result.scalar_one_or_none.return_value = None
                    result.scalars.return_value.all.return_value = []
                return result
            
            async def _add(self, obj):
                if hasattr(obj, "__tablename__"):
                    if obj.__tablename__ == "api_keys":
                        self.stored_keys.append({"model": obj, "user_id": obj.user_id})
                    elif obj.__tablename__ == "api_key_usage":
                        self.usage_records.append(obj)
        
        session_factory = MagicMock()
        session = MockSession()
        session_factory.return_value.__aenter__.return_value = session
        session_factory.return_value.__aexit__.return_value = None
        return ApiKeyManager(session_factory), session
