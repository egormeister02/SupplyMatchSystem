CREATE OR REPLACE FUNCTION delete_physical_file()
RETURNS TRIGGER AS $$
DECLARE
    storage_path TEXT := '/home/egor/projects/SupplyMatchBot/storage';
    full_path TEXT;
BEGIN
    full_path := storage_path || '/' || OLD.file_path;
    PERFORM pg_catalog.pg_file_unlink(full_path);
    RETURN OLD;
EXCEPTION
    WHEN OTHERS THEN
        RETURN OLD;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER; 