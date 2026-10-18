create or replace view TRANSACTION_METRICS_V(
	TOTAL_TRANSACTIONS,
	TOTAL_AMOUNT
) as
SELECT
    COUNT(*) AS TOTAL_TRANSACTIONS,
    COALESCE(SUM(AMOUNT), 0) AS TOTAL_AMOUNT
FROM TRANSACTIONS_T;

--This comment is used as a test 
--The addition of these comments will be the SQL change which we push to main
--Th push to main should pass SQL validation and be automatically pushed to QA