ALTER TABLE registration
  ADD COLUMN idempotency_key VARCHAR(128) DEFAULT NULL COMMENT 'AI挂号幂等键',
  ADD UNIQUE KEY uk_registration_idempotency_key (idempotency_key);
