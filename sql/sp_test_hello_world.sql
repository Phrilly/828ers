DROP PROCEDURE IF EXISTS `sp_test_hello_world`;
-- END_QUERY

CREATE PROCEDURE `sp_test_hello_world`()
BEGIN
    -- WATERMARK 1.0.20
    SELECT 'The migration engine is officially working.' AS migration_status;
END;
-- END_QUERY