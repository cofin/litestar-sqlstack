from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from litestar import Controller, delete, get, patch, post
from litestar.di import Provide

from sqlstack.server import deps
from sqlstack.server.security import requires_active_user, requires_superuser

if TYPE_CHECKING:
    from uuid import UUID

    from litestar.params import Parameter

    from sqlstack import schemas as s
    from sqlstack.services import TagService
    from sqlstack.services._base import OffsetPagination


class TagController(Controller):
    """Handles the interactions within the Tag objects."""

    path = "/api/tags"
    guards = [requires_active_user]
    dependencies = {
        "tags_service": Provide(deps.provide_tags_service, sync_to_thread=False),
    }
    tags = ["Tags"]

    @get(operation_id="ListTags")
    async def list_tags(
        self,
        tags_service: TagService,
    ) -> OffsetPagination[s.Tag]:
        """List tags.

        Args:
            tags_service: The tag service.

        Returns:
            The list of tags.
        """
        return await tags_service.list_with_count()

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
        return await tags_service.create(data)

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
        return await tags_service.update(tag_id, data)

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
        await tags_service.delete(tag_id)
