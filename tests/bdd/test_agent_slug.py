"""
BDD Tests: Agent Slug Management

Feature: Agent Slug as a First-Class Identifier
As an IntentKit operator, I want to use slugs as unique, immutable identifiers
so that agents can be referenced by human-readable URLs.
"""

import pytest

from intentkit.config.db import get_session
from intentkit.core.agent import (
    create_agent,
    get_agent_by_id_or_slug,
    override_agent,
    patch_agent,
)
from intentkit.models.agent import AgentCreate, AgentUpdate
from intentkit.models.agent_activity import AgentActivityTable
from intentkit.models.agent_post import AgentPostTable
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_with_slug():
    """
    Scenario: Create Agent with Slug

    Given a clean database
    When I create an agent with slug="slug-test"
    Then the agent is persisted with that slug
    """
    agent_data = AgentCreate(
        id="slug-create-test",
        name="Slug Test Agent",
        model="gpt-4o-mini",
        slug="slug-test",
    )
    agent, _ = await create_agent(agent_data)

    assert agent.slug == "slug-test"


@pytest.mark.bdd
async def test_create_agent_without_slug():
    """
    Scenario: Create Agent without Slug

    When I create an agent without setting slug
    Then the agent has slug=None
    """
    agent_data = AgentCreate(
        id="slug-none-test",
        name="No Slug Agent",
        model="gpt-4o-mini",
    )
    agent, _ = await create_agent(agent_data)

    assert agent.slug is None


@pytest.mark.bdd
async def test_create_agent_duplicate_slug_fails():
    """
    Scenario: Create Agent with Duplicate Slug Fails

    Given an agent with slug="unique-slug" exists
    When I create another agent with slug="unique-slug"
    Then a SlugAlreadyExists error is raised
    """
    agent1 = AgentCreate(
        id="slug-dup-first",
        name="First Agent",
        model="gpt-4o-mini",
        slug="unique-slug",
    )
    await create_agent(agent1)

    agent2 = AgentCreate(
        id="slug-dup-second",
        name="Second Agent",
        model="gpt-4o-mini",
        slug="unique-slug",
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await create_agent(agent2)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugAlreadyExists"


@pytest.mark.bdd
async def test_patch_agent_set_slug():
    """
    Scenario: Set Slug via Patch

    Given an agent with no slug
    When I patch it to set slug="new-slug"
    Then the agent has slug="new-slug"
    """
    agent_data = AgentCreate(
        id="slug-patch-set",
        name="Patch Slug Agent",
        model="gpt-4o-mini",
    )
    await create_agent(agent_data)

    update = AgentUpdate(name="Patch Slug Agent", model="gpt-4o-mini", slug="new-slug")
    patched, _ = await patch_agent("slug-patch-set", update)

    assert patched.slug == "new-slug"


@pytest.mark.bdd
async def test_patch_agent_slug_immutable():
    """
    Scenario: Slug Cannot Be Changed Once Set

    Given an agent with slug="immutable-slug"
    When I patch it to set slug="different-slug"
    Then a SlugImmutable error is raised
    """
    agent_data = AgentCreate(
        id="slug-immutable-test",
        name="Immutable Slug Agent",
        model="gpt-4o-mini",
        slug="immutable-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(
        name="Immutable Slug Agent", model="gpt-4o-mini", slug="different-slug"
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await patch_agent("slug-immutable-test", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugImmutable"


@pytest.mark.bdd
async def test_patch_agent_slug_same_value_ok():
    """
    Scenario: Setting Slug to Same Value Does Not Error

    Given an agent with slug="keep-slug"
    When I patch it with slug="keep-slug" (same value)
    Then no error is raised
    """
    agent_data = AgentCreate(
        id="slug-same-test",
        name="Same Slug Agent",
        model="gpt-4o-mini",
        slug="keep-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(name="Same Slug Agent", model="gpt-4o-mini", slug="keep-slug")
    patched, _ = await patch_agent("slug-same-test", update)
    assert patched.slug == "keep-slug"


@pytest.mark.bdd
async def test_override_agent_slug_immutable():
    """
    Scenario: Override Cannot Change Slug

    Given an agent with slug="override-slug"
    When I override it with slug="changed-slug"
    Then a SlugImmutable error is raised
    """
    agent_data = AgentCreate(
        id="slug-override-test",
        name="Override Slug Agent",
        model="gpt-4o-mini",
        slug="override-slug",
    )
    await create_agent(agent_data)

    update = AgentUpdate(
        name="Override Slug Agent", model="gpt-4o-mini", slug="changed-slug"
    )
    with pytest.raises(IntentKitAPIError) as exc_info:
        await override_agent("slug-override-test", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugImmutable"


@pytest.mark.bdd
async def test_patch_agent_duplicate_slug_fails():
    """
    Scenario: Patch Slug to Existing Slug Fails

    Given agent-a with slug="taken-slug" and agent-b with no slug
    When I patch agent-b to set slug="taken-slug"
    Then a SlugAlreadyExists error is raised
    """
    agent_a = AgentCreate(
        id="slug-taken-a",
        name="Agent A",
        model="gpt-4o-mini",
        slug="taken-slug",
    )
    await create_agent(agent_a)

    agent_b = AgentCreate(
        id="slug-taken-b",
        name="Agent B",
        model="gpt-4o-mini",
    )
    await create_agent(agent_b)

    update = AgentUpdate(name="Agent B", model="gpt-4o-mini", slug="taken-slug")
    with pytest.raises(IntentKitAPIError) as exc_info:
        await patch_agent("slug-taken-b", update)

    assert exc_info.value.status_code == 400
    assert exc_info.value.key == "SlugAlreadyExists"


@pytest.mark.bdd
async def test_get_agent_by_slug():
    """
    Scenario: Retrieve Agent by Slug

    Given an agent with id="slug-get-test" and slug="findme"
    When I call get_agent_by_id_or_slug("findme")
    Then the correct agent is returned
    """
    agent_data = AgentCreate(
        id="slug-get-test",
        name="Find Me Agent",
        model="gpt-4o-mini",
        slug="findme",
    )
    await create_agent(agent_data)

    agent = await get_agent_by_id_or_slug("findme")

    assert agent is not None
    assert agent.id == "slug-get-test"
    assert agent.slug == "findme"


@pytest.mark.bdd
async def test_get_agent_by_id_still_works():
    """
    Scenario: Retrieve Agent by ID (Not Slug)

    Given an agent with id="slug-id-get" and slug="by-id-test"
    When I call get_agent_by_id_or_slug("slug-id-get")
    Then the correct agent is returned
    """
    agent_data = AgentCreate(
        id="slug-id-get",
        name="By ID Agent",
        model="gpt-4o-mini",
        slug="by-id-test",
    )
    await create_agent(agent_data)

    agent = await get_agent_by_id_or_slug("slug-id-get")

    assert agent is not None
    assert agent.id == "slug-id-get"


@pytest.mark.bdd
async def test_get_agent_by_slug_not_found():
    """
    Scenario: Non-Existent Slug Returns None

    When I call get_agent_by_id_or_slug("nonexistent-slug")
    Then None is returned
    """
    agent = await get_agent_by_id_or_slug("nonexistent-slug")
    assert agent is None


@pytest.mark.bdd
async def test_patch_endpoint_accepts_a_slug():
    """
    Scenario: Saving from a Slug URL

    Given an agent whose edit page has rewritten the address bar to its slug
    When the frontend PATCHes against that slug
    Then the update is applied to the right agent

    The endpoint resolves the slug itself: ``patch_agent`` looks up by id only,
    so passing the path parameter straight through 404s once the URL carries a
    slug. GET /agents/{agent_id}/editable has always accepted either form.
    """
    from fastapi import BackgroundTasks

    from app.local.agent import patch_agent_endpoint

    await create_agent(
        AgentCreate(
            id="slug-patch-id",
            name="Before",
            model="gpt-4o-mini",
            slug="patch-by-slug",
        )
    )

    await patch_agent_endpoint(
        BackgroundTasks(),
        agent_id="patch-by-slug",
        agent=AgentUpdate(name="After", model="gpt-4o-mini"),
    )

    agent = await get_agent_by_id_or_slug("slug-patch-id")
    assert agent is not None
    assert agent.name == "After"


@pytest.mark.bdd
async def test_patch_endpoint_404s_on_an_unknown_slug():
    """
    Scenario: Unknown Slug

    When the frontend PATCHes against a slug that resolves to nothing
    Then a 404 is raised rather than the request silently doing nothing
    """
    from fastapi import BackgroundTasks

    from app.local.agent import patch_agent_endpoint

    with pytest.raises(IntentKitAPIError) as exc:
        await patch_agent_endpoint(
            BackgroundTasks(),
            agent_id="no-such-slug",
            agent=AgentUpdate(name="X", model="gpt-4o-mini"),
        )
    assert exc.value.status_code == 404


@pytest.mark.bdd
async def test_override_endpoint_accepts_a_slug():
    """
    Scenario: Overriding from a Slug URL

    Given an agent with a slug
    When the frontend PUTs against that slug
    Then the override is applied to the right agent

    PUT/archive/reactivate share the PATCH endpoint's exposure: the address
    bar may carry a slug while override_agent and the row updates are id-only.
    """
    from fastapi import BackgroundTasks

    from app.local.agent import override_agent_endpoint

    await create_agent(
        AgentCreate(
            id="slug-override-id",
            name="Before Override",
            model="gpt-4o-mini",
            slug="override-by-slug",
        )
    )

    await override_agent_endpoint(
        BackgroundTasks(),
        agent_id="override-by-slug",
        agent=AgentUpdate(name="After Override", model="gpt-4o-mini"),
    )

    agent = await get_agent_by_id_or_slug("slug-override-id")
    assert agent is not None
    assert agent.name == "After Override"


@pytest.mark.bdd
async def test_content_endpoints_accept_a_slug():
    """
    Scenario: Browsing Feeds from a Slug URL

    Given an agent with a slug that has an activity and a post
    When the activities, posts and post-by-slug endpoints are called with the slug
    Then the agent's rows are returned

    Content rows store the real agent id; before the fix the endpoints filtered
    by the raw path parameter, so a slug produced a silently empty feed.
    """
    from app.local.content import (
        get_agent_activities,
        get_agent_posts,
        get_post_by_slug,
    )

    await create_agent(
        AgentCreate(
            id="slug-feed-id",
            name="Feed Agent",
            model="gpt-4o-mini",
            slug="feed-by-slug",
        )
    )
    async with get_session() as db:
        db.add(AgentActivityTable(agent_id="slug-feed-id", text="hello"))
        db.add(
            AgentPostTable(
                agent_id="slug-feed-id",
                title="Feed Post",
                markdown="body",
                slug="feed-post",
            )
        )
        await db.commit()

    async with get_session() as db:
        activities = await get_agent_activities(agent_id="feed-by-slug", db=db)
        posts = await get_agent_posts(agent_id="feed-by-slug", db=db)
        post = await get_post_by_slug(agent_id="feed-by-slug", slug="feed-post", db=db)

    assert [a.text for a in activities] == ["hello"]
    assert [p.title for p in posts] == ["Feed Post"]
    assert post.title == "Feed Post"


@pytest.mark.bdd
async def test_content_endpoints_404_on_an_unknown_agent():
    """
    Scenario: Feeds for an Unknown Agent

    When the activities endpoint is called with an id or slug that resolves
    to nothing
    Then a 404 is raised rather than an empty list
    """
    from app.local.content import get_agent_activities

    with pytest.raises(IntentKitAPIError) as exc:
        async with get_session() as db:
            await get_agent_activities(agent_id="no-such-feed-slug", db=db)
    assert exc.value.status_code == 404


@pytest.mark.bdd
async def test_team_content_endpoints_accept_a_slug():
    """
    Scenario: Team Feeds from a Slug URL

    Given a team agent with a slug that has an activity and a post
    When the team activities and posts endpoints are called with the slug
    Then the agent's rows are returned

    Before the fix the auth check resolved the slug but the row filter used
    the raw path parameter, so the feed was silently empty.
    """
    from app.team.content import get_agent_activities, get_agent_posts

    team_id = "slug-feed-team"
    await create_agent(
        AgentCreate(
            id="slug-team-feed-id",
            name="Team Feed Agent",
            model="gpt-4o-mini",
            slug="team-feed-by-slug",
            team_id=team_id,
        )
    )
    async with get_session() as db:
        db.add(AgentActivityTable(agent_id="slug-team-feed-id", text="team hello"))
        db.add(
            AgentPostTable(
                agent_id="slug-team-feed-id",
                title="Team Feed Post",
                markdown="body",
            )
        )
        await db.commit()

    auth = ("user-1", team_id)
    activities = await get_agent_activities(agent_id="team-feed-by-slug", auth=auth)
    posts = await get_agent_posts(agent_id="team-feed-by-slug", auth=auth)

    assert [a.text for a in activities] == ["team hello"]
    assert [p.title for p in posts] == ["Team Feed Post"]
