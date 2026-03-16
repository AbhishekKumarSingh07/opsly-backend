-- Patch: add missing columns to users
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT false;

-- Missing enums
DO $$ BEGIN
  CREATE TYPE import_type_enum AS ENUM ('staff', 'inventory');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE import_format_enum AS ENUM ('xlsx', 'csv', 'json');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
  CREATE TYPE import_status_enum AS ENUM ('pending', 'completed', 'partial', 'failed');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- bulk_import_logs table
CREATE TABLE IF NOT EXISTS bulk_import_logs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  imported_by UUID NOT NULL REFERENCES users(id),
  import_type import_type_enum NOT NULL,
  file_format import_format_enum NOT NULL,
  original_filename VARCHAR(512),
  total_rows INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  status import_status_enum NOT NULL DEFAULT 'pending',
  error_details JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bulk_import_logs_imported_by ON bulk_import_logs(imported_by);
CREATE INDEX IF NOT EXISTS ix_bulk_import_logs_created_at ON bulk_import_logs(created_at);
