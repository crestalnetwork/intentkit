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
    DEFAULT_PLATFORM_ACCOUNT_FEE,
    DEFAULT_PLATFORM_ACCOUNT_MEDIA,
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
from intentkit.models.llm import LLMModelInfo

from .base import FOURPLACES, SkillCost

logger = logging.getLogger(__name__)

# =============================================================================
# PAYMENT FLOW OVERVIEW
# =============================================================================
#
# The three main expense functions below (expense_message, expense_skill,
# expense_summarize) share ~80% identical structure. This is INTENTIONAL.
#
# Why the duplication exists and why it should NOT be refactored:
#
# 1. CLARITY OVER ABSTRACTION: Payment/billing code is among the most
#    audited and debugged code in any system. Each function represents a
#    distinct billing event type (message, skill call, memory/summarize)
#    with its own event type, upstream transaction IDs, destination
#    accounts, and transaction types. Abstracting the shared logic into
#    a helper would obscure the full payment flow when reading any single
#    function, making auditing and debugging harder.
#
# 2. INDEPENDENT EVOLUTION: Each expense type may diverge over time
#    (e.g. skill expenses already have a separate skill_cost() pre-check,
#    message expenses track hourly budget). Keeping them separate means
#    changes to one billing path never accidentally affect another.
#
# 3. FINANCIAL SAFETY: In payment code, an easy-to-follow linear flow
#    is worth more than DRY. Every function tells the complete story from
#    validation to final transaction records without jumping to helpers.
#
# SHARED PAYMENT FLOW (common to all three functions):
#   Step 0: Idempotency check — reject duplicate upstream transaction IDs
#   Step 1: Validate & quantize the base amount (LLM cost or skill price)
#   Step 2: Compute fees — discount, platform fee %, agent fee %
#   Step 3: Deduct total from team's credit account (or get/create if $0)
#   Step 4: Track free credit usage against agent's daily quota
#   Step 5: Split the deducted amount by credit type (free/reward/permanent)
#   Step 6: Proportionally allocate platform & agent fees across credit types
#   Step 7: Derive base amounts per credit type via subtraction
#   Step 8: Credit the destination accounts (message/skill/memory + platform fee + agent fee)
#   Step 9: Create the CreditEvent record with full breakdown
#   Step 10: Create CreditTransaction records (one debit + N credits)
#
# DIFFERENCES between the three functions:
#   - expense_message: EventType.MESSAGE, destination = PLATFORM_ACCOUNT_MESSAGE,
#     tracks hourly LLM budget via accumulate_hourly_base_llm_amount
#   - expense_skill: EventType.SKILL_CALL, destination = PLATFORM_ACCOUNT_SKILL,
#     uses skill_cost() for pre-calculation, upstream_tx_id includes skill_call_id
#   - expense_summarize: EventType.MEMORY, destination = PLATFORM_ACCOUNT_MEMORY,
#     similar to message but billed to the memory account
# =============================================================================


async def expense_message(
    session: AsyncSession,
    team_id: str,
    message_id: str,
    start_message_id: str,
    base_llm_amount: Decimal,
    agent: Agent,
    user_id: str | None = None,
) -> CreditEvent:
    """
    Deduct credits from a team account for message expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        team_id: ID of the team to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        base_llm_amount: Amount of LLM costs
        agent: Agent instance
        user_id: ID of the user who triggered the expense (for audit trail)

    Returns:
        CreditEvent: The created credit event
    """
    # --- SHARED STEP 0: Idempotency check (see module-level comment) ---
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, message_id
    )

    # --- SHARED STEP 1: Validate & quantize base amount ---
    # Ensure base_llm_amount has 4 decimal places
    base_llm_amount = base_llm_amount.quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    if base_llm_amount < Decimal("0"):
        raise ValueError("Base LLM amount must be non-negative")

    # MESSAGE-SPECIFIC: Track hourly budget usage after validation
    _ = await accumulate_hourly_base_llm_amount(f"base_llm:{team_id}", base_llm_amount)

    # --- SHARED STEP 2: Compute fees (discount, platform %, agent %) ---
    # Get payment settings
    payment_settings = await AppSetting.payment()

    # Calculate amount with exact 4 decimal places
    base_original_amount = base_llm_amount

    # Determine base_discount_amount based on payment_enabled flag
    # When payment is disabled, discount = full amount, so effective charge is $0.

    if config.payment_enabled:
        base_discount_amount = Decimal("0")
    else:
        base_discount_amount = base_original_amount

    base_amount = base_original_amount - base_discount_amount
    fee_platform_amount = (
        base_amount * payment_settings.fee_platform_percentage / Decimal("100")
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    fee_agent_amount = Decimal("0")
    if agent.fee_percentage and team_id != agent.team_id:
        fee_agent_amount = (
            (base_amount + fee_platform_amount) * agent.fee_percentage / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount + fee_agent_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # --- SHARED STEP 3: Deduct from team account ---
    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update team account - deduct credits
    details: dict[CreditType, Decimal] = {}
    if total_amount > 0:
        team_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
            amount=total_amount,
            event_id=event_id,
        )
    else:
        team_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
        )

    # --- SHARED STEP 4: Track free credit usage against agent quota ---
    # If using free credits, add to agent's free_income_daily
    free_credits_used = details.get(CreditType.FREE)
    if total_amount > 0 and free_credits_used:
        _ = await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=free_credits_used
        )

    # --- SHARED STEP 5: Split deducted amount by credit type ---
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

    # --- SHARED STEP 6: Proportionally allocate fees across credit types ---
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

    # --- SHARED STEP 7: Derive base amounts per credit type via subtraction ---
    # Calculate base amounts by credit type using subtraction method.
    # This ensures that: permanent_amount = base_permanent_amount + fee_platform_permanent_amount + fee_agent_permanent_amount
    # Note: Independent rounding of fee components may cause base amounts to become slightly
    # negative. This is acceptable and does not corrupt financial records.
    base_free_amount = free_amount - fee_platform_free_amount - fee_agent_free_amount
    base_reward_amount = (
        reward_amount - fee_platform_reward_amount - fee_agent_reward_amount
    )
    base_permanent_amount = (
        permanent_amount - fee_platform_permanent_amount - fee_agent_permanent_amount
    )

    # --- SHARED STEP 8: Credit destination accounts ---
    # 4. Update destination accounts - add credits with detailed amounts
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

    # --- SHARED STEP 9: Create CreditEvent record with full breakdown ---
    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    # MESSAGE-SPECIFIC: event_type=MESSAGE, records base_llm_amount
    event = CreditEventTable(
        id=event_id,
        account_id=team_account.id,
        event_type=EventType.MESSAGE,
        user_id=user_id,
        team_id=team_id,
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
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
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

    # --- SHARED STEP 10: Create CreditTransaction records ---
    # 4. Create credit transaction records
    if total_amount > 0:
        # 4.1 Team account transaction (debit)
        team_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=team_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(team_tx)

        # 4.2 MESSAGE-SPECIFIC: credit to PLATFORM_ACCOUNT_MESSAGE
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
    price: Decimal,
    team_id: str,
    agent: Agent,
) -> SkillCost:
    """
    Calculate the cost for a skill call including all fees.

    Args:
        price: Base price for the skill
        team_id: ID of the team paying for the skill call
        agent: Agent using the skill

    Returns:
        SkillCost: Object containing all cost components
    """
    base_skill_amount = price.quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # Get payment settings
    payment_settings = await AppSetting.payment()

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
    fee_agent_amount = Decimal("0")
    if agent.fee_percentage and team_id != agent.team_id:
        fee_agent_amount = (
            (base_amount + fee_platform_amount) * agent.fee_percentage / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount + fee_agent_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # Return the SkillCost object with all calculated values
    return SkillCost(
        total_amount=total_amount,
        base_amount=base_amount,
        base_discount_amount=base_discount_amount,
        base_original_amount=base_original_amount,
        base_skill_amount=base_skill_amount,
        fee_platform_amount=fee_platform_amount,
        fee_agent_amount=fee_agent_amount,
    )


async def expense_skill(
    session: AsyncSession,
    team_id: str,
    message_id: str,
    start_message_id: str,
    skill_call_id: str,
    skill_name: str,
    price: Decimal,
    agent: Agent,
    user_id: str | None = None,
) -> CreditEvent:
    """
    Deduct credits from a team account for skill call expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        team_id: ID of the team to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        skill_call_id: ID of the skill call
        skill_name: Name of the skill being used
        price: Base price for the skill
        agent: Agent using the skill
        user_id: ID of the user who triggered the expense (for audit trail)

    Returns:
        CreditEvent: The created credit event
    """
    # --- SHARED STEP 0: Idempotency check ---
    # SKILL-SPECIFIC: upstream_tx_id combines message_id + skill_call_id
    # Check for idempotency - prevent duplicate transactions
    upstream_tx_id = f"{message_id}_{skill_call_id}"
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, upstream_tx_id
    )
    logger.info("[%s] skill payment %s", agent.id, skill_name)

    # --- SHARED STEPS 1-2: Validate amount & compute fees ---
    # SKILL-SPECIFIC: Uses skill_cost() helper for pre-calculation
    # Calculate skill cost using the skill_cost function
    skill_cost_info = await skill_cost(price, team_id, agent)

    # --- SHARED STEP 3: Deduct from team account ---
    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update team account - deduct credits
    details = {}
    team_account: CreditAccount | None = None
    if skill_cost_info.total_amount > 0:
        team_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
            amount=skill_cost_info.total_amount,
            event_id=event_id,
        )
    else:
        team_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
        )

    # --- SHARED STEP 4: Track free credit usage against agent quota ---
    # If using free credits, add to agent's free_income_daily
    if skill_cost_info.total_amount > 0 and CreditType.FREE in details:
        await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=details[CreditType.FREE]
        )

    # --- SHARED STEP 5: Split deducted amount by credit type ---
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

    # --- SHARED STEP 6: Proportionally allocate fees across credit types ---
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

    # --- SHARED STEP 7: Derive base amounts per credit type via subtraction ---
    # Calculate base amounts by credit type using subtraction method
    base_free_amount = free_amount - fee_platform_free_amount - fee_agent_free_amount

    base_reward_amount = (
        reward_amount - fee_platform_reward_amount - fee_agent_reward_amount
    )

    base_permanent_amount = (
        permanent_amount - fee_platform_permanent_amount - fee_agent_permanent_amount
    )

    # --- SHARED STEP 8: Credit destination accounts ---
    # SKILL-SPECIFIC: base amount goes to PLATFORM_ACCOUNT_SKILL
    # 4. Update fee account - add credits
    skill_account: CreditAccount | None = None
    platform_account: CreditAccount | None = None
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

    # --- SHARED STEP 9: Create CreditEvent record with full breakdown ---
    # SKILL-SPECIFIC: event_type=SKILL_CALL, records base_skill_amount and skill metadata

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    event = CreditEventTable(
        id=event_id,
        account_id=team_account.id,
        event_type=EventType.SKILL_CALL,
        user_id=user_id,
        team_id=team_id,
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
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
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
        fee_dev_amount=Decimal("0"),
        fee_dev_account=None,
        fee_dev_free_amount=Decimal("0"),
        fee_dev_reward_amount=Decimal("0"),
        fee_dev_permanent_amount=Decimal("0"),
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
        agent_wallet_address=agent_wallet_address,
    )
    session.add(event)
    await session.flush()

    # --- SHARED STEP 10: Create CreditTransaction records ---
    # 4. Create credit transaction records
    if skill_cost_info.total_amount > 0:
        # 4.1 Team account transaction (debit)
        team_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=team_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=skill_cost_info.total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(team_tx)

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

        # 4.4 Agent fee account transaction (credit)
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
    team_id: str,
    message_id: str,
    start_message_id: str,
    base_llm_amount: Decimal,
    agent: Agent,
    user_id: str | None = None,
) -> CreditEvent:
    """
    Deduct credits from a team account for memory/summarize expenses.
    Don't forget to commit the session after calling this function.

    Args:
        session: Async session to use for database operations
        team_id: ID of the team to deduct credits from
        message_id: ID of the message that incurred the expense
        start_message_id: ID of the starting message in a conversation
        base_llm_amount: Amount of LLM costs
        agent: Agent instance
        user_id: ID of the user who triggered the expense (for audit trail)

    Returns:
        CreditEvent: The created credit event
    """
    # --- SHARED STEP 0: Idempotency check ---
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.EXECUTOR, message_id
    )

    # --- SHARED STEP 1: Validate & quantize base amount ---
    # Ensure base_llm_amount has 4 decimal places
    base_llm_amount = base_llm_amount.quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    if base_llm_amount < Decimal("0"):
        raise ValueError("Base LLM amount must be non-negative")

    # --- SHARED STEP 2: Compute fees (discount, platform %, agent %) ---
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
    if agent.fee_percentage and team_id != agent.team_id:
        fee_agent_amount = (
            (base_amount + fee_platform_amount) * agent.fee_percentage / Decimal("100")
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount + fee_agent_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # --- SHARED STEP 3: Deduct from team account ---
    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update team account - deduct credits
    details: dict[CreditType, Decimal] = {}
    team_account: CreditAccount
    if total_amount > 0:
        team_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
            amount=total_amount,
            event_id=event_id,
        )
    else:
        team_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
        )

    # --- SHARED STEP 4: Track free credit usage against agent quota ---
    # If using free credits, add to agent's free_income_daily
    free_credits_used = details.get(CreditType.FREE)
    if total_amount > 0 and free_credits_used:
        from intentkit.models.agent_data import AgentQuota

        await AgentQuota.add_free_income_in_session(
            session=session, id=agent.id, amount=free_credits_used
        )

    # --- SHARED STEP 5: Split deducted amount by credit type ---
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

    # --- SHARED STEP 6: Proportionally allocate fees across credit types ---
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

    # --- SHARED STEP 7: Derive base amounts per credit type via subtraction ---
    # Calculate base amounts by credit type using subtraction method
    base_free_amount = free_amount - fee_platform_free_amount - fee_agent_free_amount

    base_reward_amount = (
        reward_amount - fee_platform_reward_amount - fee_agent_reward_amount
    )

    base_permanent_amount = (
        permanent_amount - fee_platform_permanent_amount - fee_agent_permanent_amount
    )

    # --- SHARED STEP 8: Credit destination accounts ---
    # SUMMARIZE-SPECIFIC: base amount goes to PLATFORM_ACCOUNT_MEMORY
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

    # --- SHARED STEP 9: Create CreditEvent record with full breakdown ---
    # SUMMARIZE-SPECIFIC: event_type=MEMORY, records base_llm_amount

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    event = CreditEventTable(
        id=event_id,
        account_id=team_account.id,
        event_type=EventType.MEMORY,
        user_id=user_id,
        team_id=team_id,
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
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
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

    # --- SHARED STEP 10: Create CreditTransaction records ---
    # 4. Create credit transaction records
    if total_amount > 0:
        # 4.1 Team account transaction (debit)
        team_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=team_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(team_tx)

        # 4.2 SUMMARIZE-SPECIFIC: credit to PLATFORM_ACCOUNT_MEMORY
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
                credit_type=credit_type,
                free_amount=fee_agent_free_amount,
                reward_amount=fee_agent_reward_amount,
                permanent_amount=fee_agent_permanent_amount,
            )
            session.add(agent_tx)

    # 5. Refresh session to get updated data
    await session.refresh(team_account)
    await session.refresh(event)

    # 6. Return credit event model
    return CreditEvent.model_validate(event)


async def expense_skill_internal_llm(
    team_id: str,
    agent: Agent,
    skill_name: str,
    skill_call_id: str,
    start_message_id: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    user_id: str | None = None,
) -> None:
    """
    Bill for an LLM call made internally within a skill execution.

    This is a convenience function for skills that need to call an LLM
    (e.g. for content cleaning) and bill the team for the token cost.
    It calculates the cost from token usage and creates a SKILL_CALL credit event.

    Args:
        team_id: ID of the team to charge
        agent: Agent instance
        skill_name: Name of the skill making the LLM call
        skill_call_id: ID of the tool call (from LangChain runtime)
        start_message_id: ID of the starting user message
        model_id: ID of the LLM model used
        input_tokens: Number of input tokens used
        output_tokens: Number of output tokens used
        cached_input_tokens: Number of cached input tokens used
        user_id: ID of the user who triggered the expense (for audit trail)
    """
    from intentkit.config.db import get_session

    model_info = await LLMModelInfo.get(model_id)
    llm_cost = await model_info.calculate_cost(
        input_tokens, output_tokens, cached_input_tokens
    )

    if llm_cost <= Decimal("0"):
        return

    async with get_session() as session:
        await expense_skill(
            session,
            team_id,
            "",  # no message_id available from within skill
            start_message_id,
            skill_call_id,
            skill_name,
            llm_cost,
            agent,
            user_id=user_id,
        )
        await session.commit()


async def expense_media(
    session: AsyncSession,
    team_id: str,
    user_id: str,
    upstream_tx_id: str,
    base_original_amount: Decimal,
) -> CreditEvent:
    """Deduct credits from a team account for direct-API media generation.

    Used by endpoints that generate media (e.g. avatar) outside of a chat /
    agent context. No agent fee, no skill/message metadata. Platform fee still
    applies. Caller must commit the session.

    Args:
        session: Async session for database operations.
        team_id: Team to charge.
        user_id: User who triggered the call (audit trail).
        upstream_tx_id: Idempotency key for the upstream API call.
        base_original_amount: Base price before discount/fee.

    Returns:
        The created CreditEvent.
    """
    # --- SHARED STEP 0: Idempotency check ---
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.API, upstream_tx_id
    )

    # --- SHARED STEPS 1-2: Validate & compute fees ---
    base_original_amount = base_original_amount.quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )
    if base_original_amount < Decimal("0"):
        raise ValueError("base_original_amount must be non-negative")

    payment_settings = await AppSetting.payment()
    if config.payment_enabled:
        base_discount_amount = Decimal("0")
    else:
        base_discount_amount = base_original_amount
    base_amount = base_original_amount - base_discount_amount
    fee_platform_amount = (
        base_amount * payment_settings.fee_platform_percentage / Decimal("100")
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    total_amount = (base_amount + fee_platform_amount).quantize(
        FOURPLACES, rounding=ROUND_HALF_UP
    )

    # --- SHARED STEP 3: Deduct from team account ---
    event_id = str(XID())
    details: dict[CreditType, Decimal] = {}
    if total_amount > 0:
        team_account, details = await CreditAccount.expense_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
            amount=total_amount,
            event_id=event_id,
        )
    else:
        team_account = await CreditAccount.get_or_create_in_session(
            session=session,
            owner_type=OwnerType.TEAM,
            owner_id=team_id,
        )

    # --- SHARED STEP 5: Split deducted amount by credit type ---
    free_amount = details.get(CreditType.FREE, Decimal("0"))
    reward_amount = details.get(CreditType.REWARD, Decimal("0"))
    permanent_amount = details.get(CreditType.PERMANENT, Decimal("0"))
    if CreditType.PERMANENT in details:
        credit_type = CreditType.PERMANENT
    elif CreditType.REWARD in details:
        credit_type = CreditType.REWARD
    else:
        credit_type = CreditType.FREE

    # --- SHARED STEP 6: Proportionally allocate platform fee across credit types ---
    fee_platform_free_amount = Decimal("0")
    fee_platform_reward_amount = Decimal("0")
    fee_platform_permanent_amount = Decimal("0")
    if fee_platform_amount > Decimal("0") and total_amount > Decimal("0"):
        if free_amount > Decimal("0"):
            fee_platform_free_amount = (
                free_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        if reward_amount > Decimal("0"):
            fee_platform_reward_amount = (
                reward_amount * fee_platform_amount / total_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
        fee_platform_permanent_amount = (
            fee_platform_amount - fee_platform_free_amount - fee_platform_reward_amount
        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    # --- SHARED STEP 7: Derive base amounts per credit type by subtraction ---
    base_free_amount = free_amount - fee_platform_free_amount
    base_reward_amount = reward_amount - fee_platform_reward_amount
    base_permanent_amount = permanent_amount - fee_platform_permanent_amount

    # --- SHARED STEP 8: Credit destination accounts ---
    media_account: CreditAccount | None = None
    platform_account: CreditAccount | None = None
    if total_amount > 0:
        media_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_MEDIA,
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

    # --- SHARED STEP 9: Create CreditEvent record ---
    event = CreditEventTable(
        id=event_id,
        account_id=team_account.id,
        event_type=EventType.MEDIA,
        user_id=user_id,
        team_id=team_id,
        upstream_type=UpstreamType.API,
        upstream_tx_id=upstream_tx_id,
        direction=Direction.EXPENSE,
        total_amount=total_amount,
        credit_type=credit_type,
        credit_types=list(details.keys()) if details else [credit_type],
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
        base_amount=base_amount,
        base_original_amount=base_original_amount,
        base_discount_amount=base_discount_amount,
        base_llm_amount=Decimal("0"),
        base_skill_amount=Decimal("0"),
        base_free_amount=base_free_amount,
        base_reward_amount=base_reward_amount,
        base_permanent_amount=base_permanent_amount,
        fee_platform_amount=fee_platform_amount,
        fee_platform_free_amount=fee_platform_free_amount,
        fee_platform_reward_amount=fee_platform_reward_amount,
        fee_platform_permanent_amount=fee_platform_permanent_amount,
        fee_agent_amount=Decimal("0"),
        fee_agent_account=None,
        fee_agent_free_amount=Decimal("0"),
        fee_agent_reward_amount=Decimal("0"),
        fee_agent_permanent_amount=Decimal("0"),
        fee_dev_amount=Decimal("0"),
        fee_dev_account=None,
        fee_dev_free_amount=Decimal("0"),
        fee_dev_reward_amount=Decimal("0"),
        fee_dev_permanent_amount=Decimal("0"),
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
    )
    session.add(event)
    await session.flush()

    # --- SHARED STEP 10: Create CreditTransaction records ---
    if total_amount > 0:
        team_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=team_account.id,
            event_id=event_id,
            tx_type=TransactionType.PAY,
            credit_debit=CreditDebit.DEBIT,
            change_amount=total_amount,
            credit_type=credit_type,
            free_amount=free_amount,
            reward_amount=reward_amount,
            permanent_amount=permanent_amount,
        )
        session.add(team_tx)

        assert media_account is not None
        media_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=media_account.id,
            event_id=event_id,
            tx_type=TransactionType.RECEIVE_BASE_MEDIA,
            credit_debit=CreditDebit.CREDIT,
            change_amount=base_amount,
            credit_type=credit_type,
            free_amount=base_free_amount,
            reward_amount=base_reward_amount,
            permanent_amount=base_permanent_amount,
        )
        session.add(media_tx)

        assert platform_account is not None
        platform_tx = CreditTransactionTable(
            id=str(XID()),
            account_id=platform_account.id,
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

    await session.refresh(event)

    return CreditEvent.model_validate(event)
