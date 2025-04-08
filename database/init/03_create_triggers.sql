-- Trigger for file deletion
DO $$
BEGIN
    -- Проверяем существование таблицы files перед созданием триггера
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'files') THEN
        -- Удаляем триггер, если он уже существует
        DROP TRIGGER IF EXISTS delete_file_trigger ON files;
        
        -- Создаем триггер
        CREATE TRIGGER delete_file_trigger
            BEFORE DELETE ON files
            FOR EACH ROW
            EXECUTE FUNCTION delete_physical_file();
            
        RAISE NOTICE 'Trigger delete_file_trigger created successfully';
    ELSE
        RAISE NOTICE 'Table "files" does not exist, skipping trigger creation';
    END IF;
END
$$; 