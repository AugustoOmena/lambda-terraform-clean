-- database/02_security_policies.sql

-- 1. FAXINA: Remove todas as policies existentes para evitar conflitos
DO $$ 
DECLARE 
    pol record; 
BEGIN 
    FOR pol IN SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' LOOP 
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I;', pol.policyname, pol.tablename); 
    END LOOP; 
END $$;

-- 2. ATIVAÇÃO: Habilita RLS nas tabelas
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE vouchers ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_refunds ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_variants ENABLE ROW LEVEL SECURITY;

-- 3. PROFILES: Usuário vê/edita o seu; Backend total.
CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Service Role Full Access Profiles" ON profiles FOR ALL USING (auth.role() = 'service_role');

-- 4. PRODUCTS: Público lê; Backend gerencia.
CREATE POLICY "Public Read Access" ON products FOR SELECT USING (true);
CREATE POLICY "Service Role Full Access Products" ON products FOR ALL USING (auth.role() = 'service_role');

-- 4b. PRODUCT_VARIANTS: mesmo regime que products (público lê; backend gerencia).
CREATE POLICY "Public Read Access Product Variants" ON product_variants FOR SELECT USING (true);
CREATE POLICY "Service Role Full Access Product Variants" ON product_variants FOR ALL USING (auth.role() = 'service_role');

-- 5. ORDERS: Usuário vê/cria o seu; Backend total.
CREATE POLICY "Users can view own orders" ON orders FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own orders" ON orders FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Service Role Full Access Orders" ON orders FOR ALL USING (auth.role() = 'service_role');

-- 6. ORDER_ITEMS: Acesso via vínculo com o pedido.
CREATE POLICY "Users can view own order items" ON order_items FOR SELECT USING (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Users can insert own order items" ON order_items FOR INSERT WITH CHECK (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Service Role Full Access Order Items" ON order_items FOR ALL USING (auth.role() = 'service_role');

-- 7. VOUCHERS: Apenas backend; cliente vê via pedido quando recebe voucher.
CREATE POLICY "Service Role Full Access Vouchers" ON vouchers FOR ALL USING (auth.role() = 'service_role');

-- 8. ORDER_REFUNDS: Cliente cria/vê suas solicitações; Backend total.
CREATE POLICY "Users can view own order refunds" ON order_refunds FOR SELECT USING (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Users can create own order refund requests" ON order_refunds FOR INSERT WITH CHECK (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Service Role Full Access Order Refunds" ON order_refunds FOR ALL USING (auth.role() = 'service_role');