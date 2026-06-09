ALTER TABLE borrowers
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_borrowers_phone_number ON borrowers (phone_number);
CREATE INDEX IF NOT EXISTS idx_borrowers_full_name ON borrowers (full_name);
CREATE INDEX IF NOT EXISTS idx_borrowers_status ON borrowers (status);
