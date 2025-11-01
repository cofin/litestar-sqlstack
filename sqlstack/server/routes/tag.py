from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide
from litestar.params import Dependency, Parameter
from sqlspec.extensions.litestar.providers import create_filter_dependencies

from sqlstack.server import deps
from sqlstack.server.security import requires_active_user, requires_superuser

if TYPE_CHECKING:
    from litestar.params import Parameter

    from sqlstack import schemas as s
    from sqlstack.services import FilterTypes, TagService
    from sqlstack.services._base import OffsetPagination


class TagController(Controller):
    """Handles the interactions within the Tag objects."""

    path = "/api/tags"
    guards = [requires_active_user]
    dependencies = {
        "tags_service": Provide(deps.provide_tag_service, sync_to_thread=False)
    } | create_filter_dependencies({
        "id_filter": UUID,
        "created_at": True,
        "updated_at": True,
        "sort_field": "name",
        "search": ["name", "slug", "description"],
    })
    tags = ["Tags"]

    @get(operation_id="ListTags")
    async def list_tags(
        self, tags_service: TagService, filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)]
    ) -> OffsetPagination[s.Tag]:
        """List tags.

        Args:
            tags_service: The tag service.
            filters: The list of filters to apply.

        Returns:
            The list of tags.
        """
        return await tags_service.list_with_count(*filters)

    @get(operation_id="GetTag", path="/{tag_id:uuid}")
    async def get_tag(
        self,
        tags_service: TagService,
        tag_id: Annotated[UUID, Parameter(title="Tag ID", description="The tag to retrieve.")],
    ) -> s.Tag:
        """Get a tag.

        Args:
            tag_id: The ID of the tag to retrieve.
            tags_service: The tag service.

        Returns:
            The tag.
        """
        return await tags_service.get_one(tag_id)

    @post(operation_id="CreateTag", guards=[requires_superuser], path="/{tag_id:uuid}")
    async def create_tag(self, tags_service: TagService, data: s.TagCreate) -> s.Tag:
        """Create a new tag.

        Args:
            data: The data to create the tag with.
            tags_service: The tag service.

        Returns:
            The created tag.
        """
        return await tags_service.create_tag(data)

    @patch(operation_id="UpdateTag", path="/{tag_id:uuid}", guards=[requires_superuser])
    async def update_tag(
        self,
        tags_service: TagService,
        data: s.TagUpdate,
        tag_id: Annotated[UUID, Parameter(title="Tag ID", description="The tag to update.")],
    ) -> s.Tag:
        """Update a tag.

        Args:
            data: The data to update the tag with.
            tag_id: The ID of the tag to update.
            tags_service: The tag service.

        Returns:
            The updated tag.
        """
        return await tags_service.update_tag(tag_id, data)

    @delete(operation_id="DeleteTag", path="/{tag_id:uuid}", guards=[requires_superuser], return_dto=None)
    async def delete_tag(
        self,
        tags_service: TagService,
        tag_id: Annotated[UUID, Parameter(title="Tag ID", description="The tag to delete.")],
    ) -> None:
        """Delete a tag.

        Args:
            tag_id: The ID of the tag to delete.
            tags_service: The tag service.
        """
        await tags_service.delete_tag(tag_id)
