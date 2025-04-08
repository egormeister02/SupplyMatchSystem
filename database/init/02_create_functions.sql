-- Function to delete physical file
CREATE OR REPLACE FUNCTION delete_physical_file()
RETURNS TRIGGER AS $$
DECLARE
    storage_path TEXT := '/home/egor/projects/SupplyMatchBot/storage';
    full_path TEXT;
    result BOOLEAN;
BEGIN
    -- Log what we're trying to delete
    RAISE NOTICE 'Attempting to delete file: %', OLD.file_path;
    
    -- Construct full path
    full_path := storage_path || '/' || OLD.file_path;
    RAISE NOTICE 'Full path to delete: %', full_path;
    
    -- Try to delete using pg_file_unlink
    BEGIN
        result := pg_catalog.pg_file_unlink(full_path);
        IF result THEN
            RAISE NOTICE 'Successfully deleted file: %', full_path;
        ELSE
            RAISE NOTICE 'Failed to delete file (returned false): %', full_path;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'Error deleting file %: %', full_path, SQLERRM;
    END;
    
    RETURN OLD;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public; 