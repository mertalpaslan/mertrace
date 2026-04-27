import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import BackgroundTasks
from app.main import app
from app.api.deps import engine
from sqlmodel import SQLModel


class NoOpBackgroundTasks(BackgroundTasks):
    """BackgroundTasks that silently drops all tasks (for tests)."""
    async def __call__(self):
        pass

    def add_task(self, func, *args, **kwargs):
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[BackgroundTasks] = NoOpBackgroundTasks
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
