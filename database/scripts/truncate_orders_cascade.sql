-- Remove todos os pedidos e dados dependentes em cascata.
-- vouchers: desvincula order_id (não tem ON DELETE CASCADE).
-- order_items e order_refunds: apagados em cascata ao apagar orders.

BEGIN;

UPDATE vouchers SET order_id = NULL WHERE order_id IS NOT NULL;
DELETE FROM orders;

COMMIT;
