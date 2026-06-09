CREATE INDEX IF NOT EXISTS idx_borrowers_full_name_prefix
    ON borrowers (lower(full_name) text_pattern_ops);
