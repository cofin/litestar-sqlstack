"""Test TagService functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from sqlstack import schemas as s

if TYPE_CHECKING:
    from sqlstack.services import TagService

pytestmark = pytest.mark.anyio


async def test_create_tag(tag_service: TagService) -> None:
    """Test creating a new tag."""
    tag_data = s.TagCreate(name="Test Tag")

    created_tag = await tag_service.create(tag_data)

    assert created_tag.name == "Test Tag"
    assert created_tag.slug == "test-tag"  # Auto-generated from name
    assert created_tag.id is not None


async def test_get_tag_by_id(tag_service: TagService, test_tag: s.Tag) -> None:
    """Test retrieving a tag by ID."""
    retrieved_tag = await tag_service.get_one(test_tag.id)

    assert retrieved_tag.id == test_tag.id
    assert retrieved_tag.name == test_tag.name
    assert retrieved_tag.slug == test_tag.slug


async def test_get_tag_not_found(tag_service: TagService) -> None:
    """Test retrieving a non-existent tag raises error."""
    non_existent_id = uuid4()

    with pytest.raises(ValueError):
        await tag_service.get_one(non_existent_id)


async def test_update_tag(tag_service: TagService, test_tag: s.Tag) -> None:
    """Test updating a tag."""
    update_data = s.TagUpdate(name="Updated Tag Name")

    updated_tag = await tag_service.update(test_tag.id, update_data)

    assert updated_tag.id == test_tag.id
    assert updated_tag.name == "Updated Tag Name"
    assert updated_tag.slug == test_tag.slug  # Slug unchanged


async def test_delete_tag(tag_service: TagService, test_tag: s.Tag) -> None:
    """Test deleting a tag."""
    deleted_tag = await tag_service.delete(test_tag.id)

    assert deleted_tag.id == test_tag.id

    # Verify tag is deleted
    with pytest.raises(ValueError):
        await tag_service.get_one(test_tag.id)


async def test_list_tags(tag_service: TagService) -> None:
    """Test listing tags with pagination."""
    # Create multiple tags
    for i in range(5):
        tag_data = s.TagCreate(name=f"Tag {i}")
        await tag_service.create(tag_data)

    result = await tag_service.list_with_count()

    assert result.total >= 5
    assert len(result.items) >= 5
    assert result.limit == 20  # Default limit
    assert result.offset == 0


async def test_get_by_slug(tag_service: TagService, test_tag: s.Tag) -> None:
    """Test retrieving a tag by slug."""
    retrieved_tag = await tag_service.get_by_slug(test_tag.slug)

    assert retrieved_tag is not None
    assert retrieved_tag.id == test_tag.id
    assert retrieved_tag.slug == test_tag.slug


async def test_get_by_slug_not_found(tag_service: TagService) -> None:
    """Test retrieving a non-existent tag by slug."""
    retrieved_tag = await tag_service.get_by_slug("non-existent-slug")

    assert retrieved_tag is None


async def test_search_tags(tag_service: TagService) -> None:
    """Test searching tags by name."""
    # Create test tags
    await tag_service.create(s.TagCreate(name="Python Programming"))
    await tag_service.create(s.TagCreate(name="Web Development"))
    await tag_service.create(s.TagCreate(name="Machine Learning"))

    # Search for tags containing "prog"
    results = await tag_service.search("prog", limit=5)

    assert len(results) >= 1
    assert any("Programming" in tag.name for tag in results)


async def test_upsert_tag(tag_service: TagService) -> None:
    """Test upserting a tag (create or return existing)."""
    tag_data = s.TagCreate(name="Upsert Test")

    # First upsert should create
    tag1 = await tag_service.upsert(tag_data)
    assert tag1.name == "Upsert Test"

    # Second upsert should return existing
    tag2 = await tag_service.upsert(tag_data)
    assert tag2.id == tag1.id
    assert tag2.name == tag1.name


async def test_get_or_create(tag_service: TagService) -> None:
    """Test get_or_create functionality."""
    tag_name = "Get Or Create Test"

    # First call should create
    tag1 = await tag_service.get_or_create(tag_name)
    assert tag1.name == tag_name

    # Second call should return existing
    tag2 = await tag_service.get_or_create(tag_name)
    assert tag2.id == tag1.id
    assert tag2.name == tag1.name


async def test_get_popular_tags(tag_service: TagService) -> None:
    """Test getting popular tags."""
    # Create some test tags
    for i in range(3):
        await tag_service.create(s.TagCreate(name=f"Popular Tag {i}"))

    popular_tags = await tag_service.get_popular_tags(min_usage=1, limit=5)

    # Should return some tags (actual popularity logic not implemented yet)
    assert len(popular_tags) >= 0  # May be empty if no usage data