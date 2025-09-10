-- Fix transaction type bug: Change RECHARGE to REFILL for user transactions with FREE credit type
-- This script fixes the bug where user transactions were incorrectly marked as RECHARGE
-- when they should be REFILL for free credit transactions

-- First, let's check how many records will be affected
SELECT 
    COUNT(*) as affected_records,
    'Records to be updated' as description
FROM credit_transactions 
WHERE tx_type = 'recharge' 
  AND credit_type = 'free_credits';

-- Show some sample records before update
SELECT 
    id,
    account_id,
    event_id,
    tx_type,
    credit_type,
    credit_debit,
    change_amount,
    created_at
FROM credit_transactions 
WHERE tx_type = 'recharge' 
  AND credit_type = 'free_credits'
LIMIT 10;

-- Update the transaction type from RECHARGE to REFILL
-- for transactions that have tx_type = 'recharge' and credit_type = 'free_credits'
UPDATE credit_transactions 
SET 
    tx_type = 'refill'
WHERE tx_type = 'recharge' 
  AND credit_type = 'free_credits';

-- Verify the update was successful
SELECT 
    COUNT(*) as updated_records,
    'Records successfully updated to REFILL' as description
FROM credit_transactions 
WHERE tx_type = 'refill' 
  AND credit_type = 'free_credits';

-- Double check that no RECHARGE records with FREE credit type remain
SELECT 
    COUNT(*) as remaining_records,
    'Remaining RECHARGE records with FREE credit type (should be 0)' as description
FROM credit_transactions 
WHERE tx_type = 'recharge' 
  AND credit_type = 'free_credits';

-- Show some sample records after update
SELECT 
    id,
    account_id,
    event_id,
    tx_type,
    credit_type,
    credit_debit,
    change_amount,
    updated_at
FROM credit_transactions 
WHERE tx_type = 'refill' 
  AND credit_type = 'free_credits'
ORDER BY updated_at DESC
LIMIT 10;