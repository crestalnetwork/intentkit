from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from epyxid import XID
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.core.budget import accumulate_hourly_base_llm_amount
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData, AgentQuota
from intentkit.models.app_setting import AppSetting
from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_DEV,
    DEFAULT_PLATFORM_ACCOUNT_FEE,
    DEFAULT_PLATFORM_ACCOUNT_MEMORY,
    DEFAULT_PLATFORM_ACCOUNT_MESSAGE,
    DEFAULT_PLATFORM_ACCOUNT_SKILL,
    CreditAccount,
    CreditDebit,
    CreditEvent,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    EventType,
    OwnerType,
    TransactionType,
    UpstreamType,
)
from intentkit.models.skill import Skill

from .base import FOURPLACES, SkillCost

logger = logging.getLogger(__name__)


async def expense_message(
    session: AsyncSession,
    user_id: str,
    message_id: str,
    start_message_id: str,
    base_llm_amount: Decimal,
    agent: Agent,
) -> CreditEvent:
    """
    Deduct credits from a user account for message expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        base_llm_amount: Amount of LLM costs

    Returns:
        Updated user credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, message_id
    )

    # Ensure base_llm_amount has 4 decimal places
    base_llm_amount = base_llm_amount.quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    if base_llm_amount < Decimal("0"):
        raise ValueError("Base LLM amount must be non-negative")

    # Track hourly budget usage after validation
    _ = await accumulate_hourly_base_llm_amount(f"base_llm:{user_id}", base_llm_amount)

    # Get payment settings
    payment_settings = await AppSetting.payment()

    # Calculate amount with exact 4 decimal places
    base_original_amount = base_llm_amount

    # Determine base_discount_amount based on payment_enabled flag

    if config.payment_enabled:
        base_discount_amount = Decimal("0")
    else:
        base_discount_amount = base_original_amount

    base_amount = base_original_amount - base_discount_amount
    fee_platform_amount = (
        base_amount * payment_settings.fee_platform_percentage / Decimal("100")
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    fee_agent_amount = Decimal("0")
    if agent.fee_percentage and user_id != agent.owner:
        fee_agent_amount = (
            (base_amount + fee_platform_amount) * agent.fee_percentage / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount + fee_agent_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account - deduct credits
    details: dict[CreditType, Decimal] = {}
    if total_amount > 0:
        user_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
            amount=total_amount,
            event_id=event_id,
        )
    else:
        user_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
        )

    # If using free credits, add to agent's free_income_daily
    free_credits_used = details.get(CreditType.FREE)
    if total_amount > 0 and free_credits_used:
        _ = await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=free_credits_used
        )

    # 3. Calculate detailed amounts for fees based on user payment details
    # Set the appropriate credit amount field based on credit type
    free_amount = details.get(CreditType.FREE, Decimal("0"))
    reward_amount = details.get(CreditType.REWARD, Decimal("0"))
    permanent_amount = details.get(CreditType.PERMANENT, Decimal("0"))
    if CreditType.PERMANENT in details:
        credit_type = CreditType.PERMANENT
    elif CreditType.REWARD in details:
        credit_type = CreditType.REWARD
    else:
        credit_type = CreditType.FREE

    # Calculate fee_platform amounts by credit type
    fee_platform_free_amount = Decimal("0")
    fee_platform_reward_amount = Decimal("0")
    fee_platform_permanent_amount = Decimal("0")

    if fee_platform_amount > Decimal("0") and total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_platform_free_amount = (
                free_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_platform_reward_amount = (
                reward_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_platform_amount
        fee_platform_permanent_amount = (
            fee_platform_amount - fee_platform_free_amount - fee_platform_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate fee_agent amounts by credit type
    fee_agent_free_amount = Decimal("0")
    fee_agent_reward_amount = Decimal("0")
    fee_agent_permanent_amount = Decimal("0")

    if fee_agent_amount > Decimal("0") and total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_agent_free_amount = (
                free_amount * fee_agent_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_agent_reward_amount = (
                reward_amount * fee_agent_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_agent_amount
        fee_agent_permanent_amount = (
            fee_agent_amount - fee_agent_free_amount - fee_agent_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate base amounts by credit type using subtraction method
    # This ensures that: permanent_amount = base_permanent_amount + fee_platform_permanent_amount + fee_agent_permanent_amount
    base_free_amount = free_amount - fee_platform_free_amount - fee_agent_free_amount
    base_reward_amount = (
        reward_amount - fee_platform_reward_amount - fee_agent_reward_amount
    )
    base_permanent_amount = (
        permanent_amount - fee_platform_permanent_amount - fee_agent_permanent_amount
    )

    # 4. Update fee account - add credits with detailed amounts
    agent_account: CreditAccount | None = None
    if total_amount > 0:
        _ = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_MESSAGE,
            amount_details={
                CreditType.FREE: base_free_amount,
                CreditType.REWARD: base_reward_amount,
                CreditType.PERMANENT: base_permanent_amount,
            },
            event_id=event_id,
        )
        _ = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_FEE,
            amount_details={
                CreditType.FREE: fee_platform_free_amount,
                CreditType.REWARD: fee_platform_reward_amount,
                CreditType.PERMANENT: fee_platform_permanent_amount,
            },
            event_id=event_id,
        )
        if fee_agent_amount > 0:
            agent_account = await CreditAccount.income_in_session(
                session=session,
                owner_type=OwnerType.AGENT,
                owner_id=agent.id,
                amount_details={
                    CreditType.FREE: fee_agent_free_amount,
                    CreditType.REWARD: fee_agent_reward_amount,
                    CreditType.PERMANENT: fee_agent_permanent_amount,
                },
                event_id=event_id,
            )

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    event = CreditEventTable(
        id=event_id,
        account_id=user_account.id,
        event_type=EventType.MESSAGE,
        user_id=user_id,
        upstream_type=UpstreamType.EXECUTOR,
        upstream_tx_id=message_id,
        direction=Direction.EXPENSE,
        agent_id=agent.id,
        message_id=message_id,
        start_message_id=start_message_id,
        model=agent.model,
        total_amount=total_amount,
        credit_type=credit_type,
        credit_types=list(details.keys()),
        balance_after=user_account.credits
        + user_account.free_credits
        + user_account.reward_credits,
        base_amount=base_amount,
        base_original_amount=base_original_amount,
        base_discount_amount=base_discount_amount,
        base_free_amount=base_free_amount,
        base_reward_amount=base_reward_amount,
        base_permanent_amount=base_permanent_amount,
        base_llm_amount=base_llm_amount,
        fee_platform_amount=fee_platform_amount,
        fee_platform_free_amount=fee_platform_free_amount,
        fee_platform_reward_amount=fee_platform_reward_amount,
        fee_platform_permanent_amount=fee_platform_permanent_amount,
        fee_agent_amount=fee_agent_amount,
        fee_agent_account=agent_account.id if agent_account else None,
        fee_agent_free_amount=fee_agent_free_amount,
        fee_agent_reward_amount=fee_agent_reward_amount,
        fee_agent_permanent_amount=fee_agent_permanent_amount,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
        agent_wallet_address=agent_wallet_address,
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    if total_amount > 0:
        # 4.1 User account transaction (debit)
        user_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=user_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(user_tx)

        # 4.2 Message account transaction (credit)
        message_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=DEFAULT_PLATFORM_ACCOUNT_MESSAGE,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_BASE_LLM,
            credit_debit=CreditDebit.CREDIT,
            change_amount=base_amount,
            credit_type=credit_type,
            free_amount=base_free_amount,
            reward_amount=base_reward_amount,
            permanent_amount=base_permanent_amount,
        )
        session.add(message_tx)

        # 4.3 Platform fee account transaction (credit)
        platform_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=DEFAULT_PLATFORM_ACCOUNT_FEE,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_FEE_PLATFORM,
            credit_debit=CreditDebit.CREDIT,
            change_amount=fee_platform_amount,
            credit_type=credit_type,
            free_amount=fee_platform_free_amount,
            reward_amount=fee_platform_reward_amount,
            permanent_amount=fee_platform_permanent_amount,
        )
        session.add(platform_tx)

        # 4.4 Agent fee account transaction (credit)
        if fee_agent_amount > 0 and agent_account:
            agent_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=agent_account.id,
                event_id=event_id,
                tx_type=TransactionType.RECEIVE_FEE_AGENT,
                credit_debit=CreditDebit.CREDIT,
                change_amount=fee_agent_amount,
                credit_type=credit_type,
                free_amount=fee_agent_free_amount,
                reward_amount=fee_agent_reward_amount,
                permanent_amount=fee_agent_permanent_amount,
            )
            session.add(agent_tx)

    await session.refresh(event)

    return CreditEvent.model_validate(event)


async def skill_cost(
    skill_name: str,
    user_id: str,
    agent: Agent,
) -> SkillCost:
    """
    Calculate the cost for a skill call including all fees.

    Args:
        skill_name: Name of the skill
        user_id: ID of the user making the skill call
        agent: Agent using the skill

    Returns:
        SkillCost: Object containing all cost components
    """

    skill = await Skill.get(skill_name)
    if not skill:
        raise ValueError(f"The price of {skill_name} not set yet")
    base_skill_amount = skill.price.quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    if agent.skills:
        agent_skill_config = agent.skills.get(skill.category)
        if (
            agent_skill_config
            and agent_skill_config.get("api_key_provider") == "agent_owner"
        ):
            base_skill_amount = skill.price_self_key.quantize(
                FOURPLACES, rounding=ROUND_HALF_UP
            )
    # Get payment settings
    payment_settings = await AppSetting.payment()

    # Calculate fee
    if skill.author:
        fee_dev_user = skill.author
        fee_dev_user_type = OwnerType.USER
    else:
        fee_dev_user = DEFAULT_PLATFORM_ACCOUNT_DEV
        fee_dev_user_type = OwnerType.PLATFORM
    fee_dev_percentage = payment_settings.fee_dev_percentage

    if base_skill_amount < Decimal("0"):
        raise ValueError("Base skill amount must be non-negative")

    # Calculate amount with exact 4 decimal places
    base_original_amount = base_skill_amount

    # Determine base_discount_amount based on payment_enabled flag

    if config.payment_enabled:
        base_discount_amount = Decimal("0")
    else:
        base_discount_amount = base_original_amount

    base_amount = base_original_amount - base_discount_amount
    fee_platform_amount = (
        base_amount * payment_settings.fee_platform_percentage / Decimal("100")
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    fee_dev_amount = (base_amount * fee_dev_percentage / Decimal("100")).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )
    fee_agent_amount = Decimal("0")
    if agent.fee_percentage and user_id != agent.owner:
        fee_agent_amount = (
            (base_amount + fee_platform_amount + fee_dev_amount)
            * agent.fee_percentage
            / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (
        base_amount + fee_platform_amount + fee_dev_amount + fee_agent_amount
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Return the SkillCost object with all calculated values
    return SkillCost(
        total_amount=total_amount,
        base_amount=base_amount,
        base_discount_amount=base_discount_amount,
        base_original_amount=base_original_amount,
        base_skill_amount=base_skill_amount,
        fee_platform_amount=fee_platform_amount,
        fee_dev_user=fee_dev_user,
        fee_dev_user_type=fee_dev_user_type,
        fee_dev_amount=fee_dev_amount,
        fee_agent_amount=fee_agent_amount,
    )


async def expense_skill(
    session: AsyncSession,
    user_id: str,
    message_id: str,
    start_message_id: str,
    skill_call_id: str,
    skill_name: str,
    agent: Agent,
) -> CreditEvent:
    """
    Deduct credits from a user account for message expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        skill_call_id: ID of the skill call
        skill_name: Name of the skill being used
        agent: Agent using the skill

    Returns:
        CreditEvent: The created credit event
    """
    # Check for idempotency - prevent duplicate transactions
    upstream_tx_id = f"{message_id}_{skill_call_id}"
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, upstream_tx_id
    )
    logger.info(f"[{agent.id}] skill payment {skill_name}")

    # Calculate skill cost using the skill_cost function
    skill_cost_info = await skill_cost(skill_name, user_id, agent)

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account - deduct credits
    details = {}
    user_account: CreditAccount | None = None
    if skill_cost_info.total_amount > 0:
        user_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
            amount=skill_cost_info.total_amount,
            event_id=event_id,
        )
    else:
        user_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
        )

    # If using free credits, add to agent's free_income_daily
    if skill_cost_info.total_amount > 0 and CreditType.FREE in details:
        await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=details[CreditType.FREE]
        )

    # 3. Calculate detailed amounts for fees
    # Set the appropriate credit amount field based on credit type
    free_amount = details.get(CreditType.FREE, Decimal("0"))
    reward_amount = details.get(CreditType.REWARD, Decimal("0"))
    permanent_amount = details.get(CreditType.PERMANENT, Decimal("0"))
    if CreditType.PERMANENT in details:
        credit_type = CreditType.PERMANENT
    elif CreditType.REWARD in details:
        credit_type = CreditType.REWARD
    else:
        credit_type = CreditType.FREE

    # Calculate fee_platform amounts by credit type
    fee_platform_free_amount = Decimal("0")
    fee_platform_reward_amount = Decimal("0")
    fee_platform_permanent_amount = Decimal("0")

    if skill_cost_info.fee_platform_amount > Decimal(
        "0"
    ) and skill_cost_info.total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_platform_free_amount = (
                free_amount
                * skill_cost_info.fee_platform_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_platform_reward_amount = (
                reward_amount
                * skill_cost_info.fee_platform_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_platform_amount
        fee_platform_permanent_amount = (
            skill_cost_info.fee_platform_amount
            - fee_platform_free_amount
            - fee_platform_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate fee_agent amounts by credit type
    fee_agent_free_amount = Decimal("0")
    fee_agent_reward_amount = Decimal("0")
    fee_agent_permanent_amount = Decimal("0")

    if skill_cost_info.fee_agent_amount > Decimal(
        "0"
    ) and skill_cost_info.total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_agent_free_amount = (
                free_amount
                * skill_cost_info.fee_agent_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_agent_reward_amount = (
                reward_amount
                * skill_cost_info.fee_agent_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_agent_amount
        fee_agent_permanent_amount = (
            skill_cost_info.fee_agent_amount
            - fee_agent_free_amount
            - fee_agent_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate fee_dev amounts by credit type
    fee_dev_free_amount = Decimal("0")
    fee_dev_reward_amount = Decimal("0")
    fee_dev_permanent_amount = Decimal("0")

    if skill_cost_info.fee_dev_amount > Decimal(
        "0"
    ) and skill_cost_info.total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_dev_free_amount = (
                free_amount
                * skill_cost_info.fee_dev_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_dev_reward_amount = (
                reward_amount
                * skill_cost_info.fee_dev_amount
                / skill_cost_info.total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_dev_amount
        fee_dev_permanent_amount = (
            skill_cost_info.fee_dev_amount - fee_dev_free_amount - fee_dev_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate base amounts by credit type using subtraction method
    base_free_amount = (
        free_amount
        - fee_platform_free_amount
        - fee_agent_free_amount
        - fee_dev_free_amount
    )

    base_reward_amount = (
        reward_amount
        - fee_platform_reward_amount
        - fee_agent_reward_amount
        - fee_dev_reward_amount
    )

    base_permanent_amount = (
        permanent_amount
        - fee_platform_permanent_amount
        - fee_agent_permanent_amount
        - fee_dev_permanent_amount
    )

    # 4. Update fee account - add credits
    skill_account: CreditAccount | None = None
    platform_account: CreditAccount | None = None
    dev_account: CreditAccount | None = None
    agent_account: CreditAccount | None = None

    if skill_cost_info.total_amount > 0:
        skill_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_SKILL,
            amount_details={
                CreditType.FREE: base_free_amount,
                CreditType.REWARD: base_reward_amount,
                CreditType.PERMANENT: base_permanent_amount,
            },
            event_id=event_id,
        )
        platform_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_FEE,
            amount_details={
                CreditType.FREE: fee_platform_free_amount,
                CreditType.REWARD: fee_platform_reward_amount,
                CreditType.PERMANENT: fee_platform_permanent_amount,
            },
            event_id=event_id,
        )
        if skill_cost_info.fee_dev_amount > 0:
            dev_account = await CreditAccount.income_in_session(
                session=session,
                owner_type=skill_cost_info.fee_dev_user_type,
                owner_id=skill_cost_info.fee_dev_user,
                amount_details={
                    CreditType.FREE: fee_dev_free_amount,
                    CreditType.REWARD: fee_dev_reward_amount,
                    CreditType.PERMANENT: fee_dev_permanent_amount,
                },
                event_id=event_id,
            )
        if skill_cost_info.fee_agent_amount > 0:
            agent_account = await CreditAccount.income_in_session(
                session=session,
                owner_type=OwnerType.AGENT,
                owner_id=agent.id,
                amount_details={
                    CreditType.FREE: fee_agent_free_amount,
                    CreditType.REWARD: fee_agent_reward_amount,
                    CreditType.PERMANENT: fee_agent_permanent_amount,
                },
                event_id=event_id,
            )

    # 5. Create credit event record

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    event = CreditEventTable(
        id=event_id,
        account_id=user_account.id,
        event_type=EventType.SKILL_CALL,
        user_id=user_id,
        upstream_type=UpstreamType.EXECUTOR,
        upstream_tx_id=upstream_tx_id,
        direction=Direction.EXPENSE,
        agent_id=agent.id,
        message_id=message_id,
        start_message_id=start_message_id,
        skill_call_id=skill_call_id,
        skill_name=skill_name,
        total_amount=skill_cost_info.total_amount,
        credit_type=credit_type,
        credit_types=list(details.keys()),
        balance_after=user_account.credits
        + user_account.free_credits
        + user_account.reward_credits,
        base_amount=skill_cost_info.base_amount,
        base_original_amount=skill_cost_info.base_original_amount,
        base_discount_amount=skill_cost_info.base_discount_amount,
        base_skill_amount=skill_cost_info.base_skill_amount,
        base_free_amount=base_free_amount,
        base_reward_amount=base_reward_amount,
        base_permanent_amount=base_permanent_amount,
        fee_platform_amount=skill_cost_info.fee_platform_amount,
        fee_platform_free_amount=fee_platform_free_amount,
        fee_platform_reward_amount=fee_platform_reward_amount,
        fee_platform_permanent_amount=fee_platform_permanent_amount,
        fee_agent_amount=skill_cost_info.fee_agent_amount,
        fee_agent_account=agent_account.id if agent_account else None,
        fee_agent_free_amount=fee_agent_free_amount,
        fee_agent_reward_amount=fee_agent_reward_amount,
        fee_agent_permanent_amount=fee_agent_permanent_amount,
        fee_dev_amount=skill_cost_info.fee_dev_amount,
        fee_dev_account=dev_account.id if dev_account else None,
        fee_dev_free_amount=fee_dev_free_amount,
        fee_dev_reward_amount=fee_dev_reward_amount,
        fee_dev_permanent_amount=fee_dev_permanent_amount,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
        agent_wallet_address=agent_wallet_address,
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    if skill_cost_info.total_amount > 0:
        # 4.1 User account transaction (debit)
        user_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=user_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=skill_cost_info.total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(user_tx)

        # 4.2 Skill account transaction (credit)
        assert skill_account is not None
        skill_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=skill_account.id,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_BASE_SKILL,
            credit_debit=CreditDebit.CREDIT,
            change_amount=skill_cost_info.base_amount,
            credit_type=credit_type,
            free_amount=base_free_amount,
            reward_amount=base_reward_amount,
            permanent_amount=base_permanent_amount,
        )
        session.add(skill_tx)

        # 4.3 Platform fee account transaction (credit)
        assert platform_account is not None
        platform_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=platform_account.id,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_FEE_PLATFORM,
            credit_debit=CreditDebit.CREDIT,
            change_amount=skill_cost_info.fee_platform_amount,
            credit_type=credit_type,
            free_amount=fee_platform_free_amount,
            reward_amount=fee_platform_reward_amount,
            permanent_amount=fee_platform_permanent_amount,
        )
        session.add(platform_tx)

        # 4.4 Dev user transaction (credit)
        if skill_cost_info.fee_dev_amount > 0 and dev_account:
            dev_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=dev_account.id,
                event_id=event_id,
                tx_type=TransactionType.RECEIVE_FEE_DEV,
                credit_debit=CreditDebit.CREDIT,
                change_amount=skill_cost_info.fee_dev_amount,
                credit_type=CreditType.REWARD,
                free_amount=fee_dev_free_amount,
                reward_amount=fee_dev_reward_amount,
                permanent_amount=fee_dev_permanent_amount,
            )
            session.add(dev_tx)

        # 4.5 Agent fee account transaction (credit)
        if skill_cost_info.fee_agent_amount > 0 and agent_account:
            agent_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=agent_account.id,
                event_id=event_id,
                tx_type=TransactionType.RECEIVE_FEE_AGENT,
                credit_debit=CreditDebit.CREDIT,
                change_amount=skill_cost_info.fee_agent_amount,
                credit_type=credit_type,
                free_amount=fee_agent_free_amount,
                reward_amount=fee_agent_reward_amount,
                permanent_amount=fee_agent_permanent_amount,
            )
            session.add(agent_tx)

    # Commit all changes
    await session.refresh(event)

    return CreditEvent.model_validate(event)


async def expense_summarize(
    session: AsyncSession,
    user_id: str,
    message_id: str,
    start_message_id: str,
    base_llm_amount: Decimal,
    agent: Agent,
) -> CreditEvent:
    """
    Deduct credits from a user account for memory/summarize expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        base_llm_amount: Amount of LLM costs
        agent: Agent instance

    Returns:
        Updated user credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, message_id
    )

    # Ensure base_llm_amount has 4 decimal places
    base_llm_amount = base_llm_amount.quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    if base_llm_amount < Decimal("0"):
        raise ValueError("Base LLM amount must be non-negative")

    # Get payment settings
    payment_settings = await AppSetting.payment()

    # Calculate amount with exact 4 decimal places
    base_original_amount = base_llm_amount

    # Determine base_discount_amount based on payment_enabled flag

    if config.payment_enabled:
        base_discount_amount = Decimal("0")
    else:
        base_discount_amount = base_original_amount

    base_amount = base_original_amount - base_discount_amount
    fee_platform_amount = (
        base_amount * payment_settings.fee_platform_percentage / Decimal("100")
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    fee_agent_amount = Decimal("0")
    if agent.fee_percentage and user_id != agent.owner:
        fee_agent_amount = (
            (base_amount + fee_platform_amount) * agent.fee_percentage / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount + fee_agent_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account - deduct credits
    details: dict[CreditType, Decimal] = {}
    user_account: CreditAccount
    if total_amount > 0:
        user_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
            amount=total_amount,
            event_id=event_id,
        )
    else:
        user_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
        )

    # If using free credits, add to agent's free_income_daily
    free_credits_used = details.get(CreditType.FREE)
    if total_amount > 0 and free_credits_used:
        from intentkit.models.agent_data import AgentQuota

        await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=free_credits_used
        )

    # 3. Calculate fee amounts by credit type before income_in_session calls
    # Set the appropriate credit amount field based on credit type
    free_amount = details.get(CreditType.FREE, Decimal("0"))
    reward_amount = details.get(CreditType.REWARD, Decimal("0"))
    permanent_amount = details.get(CreditType.PERMANENT, Decimal("0"))

    if CreditType.PERMANENT in details:
        credit_type = CreditType.PERMANENT
    elif CreditType.REWARD in details:
        credit_type = CreditType.REWARD
    else:
        credit_type = CreditType.FREE

    # Calculate fee_platform amounts by credit type
    fee_platform_free_amount = Decimal("0")
    fee_platform_reward_amount = Decimal("0")
    fee_platform_permanent_amount = Decimal("0")

    if fee_platform_amount > Decimal("0") and total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_platform_free_amount = (
                free_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_platform_reward_amount = (
                reward_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_platform_amount
        fee_platform_permanent_amount = (
            fee_platform_amount - fee_platform_free_amount - fee_platform_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate fee_agent amounts by credit type
    fee_agent_free_amount = Decimal("0")
    fee_agent_reward_amount = Decimal("0")
    fee_agent_permanent_amount = Decimal("0")

    if fee_agent_amount > Decimal("0") and total_amount > Decimal("0"):
        # Calculate proportions based on the formula
        if free_amount > Decimal("0"):
            fee_agent_free_amount = (
                free_amount * fee_agent_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        if reward_amount > Decimal("0"):
            fee_agent_reward_amount = (
                reward_amount * fee_agent_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate permanent amount as the remainder to ensure the sum equals fee_agent_amount
        fee_agent_permanent_amount = (
            fee_agent_amount - fee_agent_free_amount - fee_agent_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Calculate base amounts by credit type using subtraction method
    base_free_amount = free_amount - fee_platform_free_amount - fee_agent_free_amount

    base_reward_amount = (
        reward_amount - fee_platform_reward_amount - fee_agent_reward_amount
    )

    base_permanent_amount = (
        permanent_amount - fee_platform_permanent_amount - fee_agent_permanent_amount
    )

    # 4. Update fee account - add credits
    memory_account: CreditAccount | None = None
    platform_fee_account: CreditAccount | None = None
    agent_account: CreditAccount | None = None

    if total_amount > 0:
        memory_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_MEMORY,
            amount_details={
                CreditType.FREE: base_free_amount,
                CreditType.REWARD: base_reward_amount,
                CreditType.PERMANENT: base_permanent_amount,
            },
            event_id=event_id,
        )
        platform_fee_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_FEE,
            amount_details={
                CreditType.FREE: fee_platform_free_amount,
                CreditType.REWARD: fee_platform_reward_amount,
                CreditType.PERMANENT: fee_platform_permanent_amount,
            },
            event_id=event_id,
        )
        if fee_agent_amount > 0:
            agent_account = await CreditAccount.income_in_session(
                session=session,
                owner_type=OwnerType.AGENT,
                owner_id=agent.id,
                amount_details={
                    CreditType.FREE: fee_agent_free_amount,
                    CreditType.REWARD: fee_agent_reward_amount,
                    CreditType.PERMANENT: fee_agent_permanent_amount,
                },
                event_id=event_id,
            )

    # 5. Create credit event record

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    event = CreditEventTable(
        id=event_id,
        account_id=user_account.id,
        event_type=EventType.MEMORY,
        user_id=user_id,
        upstream_type=UpstreamType.EXECUTOR,
        upstream_tx_id=message_id,
        direction=Direction.EXPENSE,
        agent_id=agent.id,
        message_id=message_id,
        start_message_id=start_message_id,
        model=agent.model,
        total_amount=total_amount,
        credit_type=credit_type,
        credit_types=list(details.keys()),
        balance_after=user_account.credits
        + user_account.free_credits
        + user_account.reward_credits,
        base_amount=base_amount,
        base_original_amount=base_original_amount,
        base_discount_amount=base_discount_amount,
        base_llm_amount=base_llm_amount,
        base_free_amount=base_free_amount,
        base_reward_amount=base_reward_amount,
        base_permanent_amount=base_permanent_amount,
        fee_platform_amount=fee_platform_amount,
        fee_platform_free_amount=fee_platform_free_amount,
        fee_platform_reward_amount=fee_platform_reward_amount,
        fee_platform_permanent_amount=fee_platform_permanent_amount,
        fee_agent_amount=fee_agent_amount,
        fee_agent_account=agent_account.id if agent_account else None,
        fee_agent_free_amount=fee_agent_free_amount,
        fee_agent_reward_amount=fee_agent_reward_amount,
        fee_agent_permanent_amount=fee_agent_permanent_amount,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
        agent_wallet_address=agent_wallet_address,
    )
    session.add(event)

    # 4. Create credit transaction records
    if total_amount > 0:
        # 4.1 User account transaction (debit)
        user_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=user_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(user_tx)

        # 4.2 Memory account transaction (credit)
        assert memory_account is not None
        memory_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=memory_account.id,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_BASE_MEMORY,
            credit_debit=CreditDebit.CREDIT,
            change_amount=base_amount,
            credit_type=credit_type,
            free_amount=base_free_amount,
            reward_amount=base_reward_amount,
            permanent_amount=base_permanent_amount,
        )
        session.add(memory_tx)

        # 4.3 Platform fee account transaction (credit)
        assert platform_fee_account is not None
        platform_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=platform_fee_account.id,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_FEE_PLATFORM,
            credit_debit=CreditDebit.CREDIT,
            change_amount=fee_platform_amount,
            credit_type=credit_type,
            free_amount=fee_platform_free_amount,
            reward_amount=fee_platform_reward_amount,
            permanent_amount=fee_platform_permanent_amount,
        )
        session.add(platform_tx)

        # 4.4 Agent fee account transaction (credit) - only if there's an agent fee
        if fee_agent_amount > 0 and agent_account:
            agent_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=agent_account.id,
                event_id=event_id,
                tx_type=TransactionType.RECEIVE_FEE_AGENT,
                credit_debit=CreditDebit.CREDIT,
                change_amount=fee_agent_amount,
                credit_type=CreditType.REWARD,
                free_amount=fee_agent_free_amount,
                reward_amount=fee_agent_reward_amount,
                permanent_amount=fee_agent_permanent_amount,
            )
            session.add(agent_tx)

    # 5. Refresh session to get updated data
    await session.refresh(user_account)
    await session.refresh(event)

    # 6. Return credit event model
    return CreditEvent.model_validate(event)
