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

-- 2b. HELPER: consulta role admin sem recursão de RLS na própria tabela profiles.
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.profiles
        WHERE id = auth.uid()
          AND lower(coalesce(role, '')) = 'admin'
    );
$$;

GRANT EXECUTE ON FUNCTION public.is_admin() TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.backoffice_list_profiles(
    p_admin_user_id uuid,
    p_page integer DEFAULT 1,
    p_limit integer DEFAULT 10,
    p_email text DEFAULT NULL,
    p_role text DEFAULT NULL,
    p_sort text DEFAULT 'newest'
)
RETURNS TABLE (
    id uuid,
    email text,
    role text,
    created_at timestamptz,
    total_count bigint
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_offset integer := GREATEST((COALESCE(p_page, 1) - 1) * COALESCE(p_limit, 10), 0);
    v_limit integer := GREATEST(COALESCE(p_limit, 10), 1);
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE profiles.id = p_admin_user_id
          AND lower(coalesce(profiles.role, '')) = 'admin'
    ) THEN
        RAISE EXCEPTION 'Apenas usuários com role admin podem listar usuários';
    END IF;

    RETURN QUERY
    WITH filtered AS (
        SELECT p.id, p.email, p.role, p.created_at
        FROM public.profiles p
        WHERE (p_email IS NULL OR coalesce(p.email, '') ILIKE '%' || p_email || '%')
          AND (p_role IS NULL OR p.role = p_role)
    ),
    counted AS (
        SELECT f.*, COUNT(*) OVER() AS total_count
        FROM filtered f
    )
    SELECT c.id, c.email, c.role, c.created_at, c.total_count
    FROM counted c
    ORDER BY
        CASE WHEN p_sort = 'role_asc' THEN c.role END ASC,
        CASE WHEN p_sort = 'role_desc' THEN c.role END DESC,
        CASE WHEN p_sort = 'newest' THEN c.created_at END DESC,
        c.created_at DESC
    OFFSET v_offset
    LIMIT v_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.backoffice_list_profiles(uuid, integer, integer, text, text, text)
TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.backoffice_list_orders(
    p_admin_user_id uuid,
    p_page integer DEFAULT 1,
    p_limit integer DEFAULT 20
)
RETURNS TABLE (
    id uuid,
    user_id uuid,
    status text,
    total_amount numeric,
    created_at timestamptz,
    payment_method text,
    payment_id text,
    payer jsonb,
    payment_code text,
    payment_url text,
    payment_expiration timestamptz,
    user_email text,
    total_count bigint
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_offset integer := GREATEST((COALESCE(p_page, 1) - 1) * COALESCE(p_limit, 20), 0);
    v_limit integer := GREATEST(COALESCE(p_limit, 20), 1);
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE profiles.id = p_admin_user_id
          AND lower(coalesce(profiles.role, '')) = 'admin'
    ) THEN
        RAISE EXCEPTION 'Apenas usuários com role admin podem listar todos os pedidos';
    END IF;

    RETURN QUERY
    WITH counted AS (
        SELECT
            o.id,
            o.user_id,
            o.status,
            o.total_amount,
            o.created_at,
            o.payment_method,
            o.payment_id,
            o.payer,
            o.payment_code,
            o.payment_url,
            o.payment_expiration,
            p.email AS user_email,
            COUNT(*) OVER() AS total_count
        FROM public.orders o
        LEFT JOIN public.profiles p ON p.id = o.user_id
    )
    SELECT
        c.id,
        c.user_id,
        c.status,
        c.total_amount,
        c.created_at,
        c.payment_method,
        c.payment_id,
        c.payer,
        c.payment_code,
        c.payment_url,
        c.payment_expiration,
        c.user_email,
        c.total_count
    FROM counted c
    ORDER BY c.created_at DESC
    OFFSET v_offset
    LIMIT v_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.backoffice_list_orders(uuid, integer, integer)
TO anon, authenticated, service_role;

-- 3. PROFILES: Usuário vê/edita o seu; Backend total.
CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Admins can view all profiles" ON profiles FOR SELECT USING (public.is_admin());
CREATE POLICY "Admins can update all profiles"
ON profiles FOR UPDATE
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Admins can delete profiles" ON profiles FOR DELETE USING (public.is_admin());
CREATE POLICY "Service Role Full Access Profiles" ON profiles FOR ALL USING (auth.role() = 'service_role');

-- 4. PRODUCTS: Público lê; Backend gerencia.
CREATE POLICY "Public Read Access" ON products FOR SELECT USING (true);
CREATE POLICY "Admins can manage products"
ON products FOR ALL
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Service Role Full Access Products" ON products FOR ALL USING (auth.role() = 'service_role');

-- 4b. PRODUCT_VARIANTS: mesmo regime que products (público lê; backend gerencia).
CREATE POLICY "Public Read Access Product Variants" ON product_variants FOR SELECT USING (true);
CREATE POLICY "Admins can manage product variants"
ON product_variants FOR ALL
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Service Role Full Access Product Variants" ON product_variants FOR ALL USING (auth.role() = 'service_role');

-- 5. ORDERS: Usuário vê/cria o seu; Backend total.
CREATE POLICY "Users can view own orders" ON orders FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own orders" ON orders FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Admins can view all orders" ON orders FOR SELECT USING (public.is_admin());
CREATE POLICY "Admins can update all orders"
ON orders FOR UPDATE
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Service Role Full Access Orders" ON orders FOR ALL USING (auth.role() = 'service_role');

-- 6. ORDER_ITEMS: Acesso via vínculo com o pedido.
CREATE POLICY "Users can view own order items" ON order_items FOR SELECT USING (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Users can insert own order items" ON order_items FOR INSERT WITH CHECK (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Admins can view all order items" ON order_items FOR SELECT USING (public.is_admin());
CREATE POLICY "Service Role Full Access Order Items" ON order_items FOR ALL USING (auth.role() = 'service_role');

-- 7. VOUCHERS: Apenas backend; cliente vê via pedido quando recebe voucher.
CREATE POLICY "Admins can manage vouchers"
ON vouchers FOR ALL
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Service Role Full Access Vouchers" ON vouchers FOR ALL USING (auth.role() = 'service_role');

-- 8. ORDER_REFUNDS: Cliente cria/vê suas solicitações; Backend total.
CREATE POLICY "Users can view own order refunds" ON order_refunds FOR SELECT USING (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Users can create own order refund requests" ON order_refunds FOR INSERT WITH CHECK (
    order_id IN (SELECT id FROM orders WHERE user_id = auth.uid())
);
CREATE POLICY "Admins can manage order refunds"
ON order_refunds FOR ALL
USING (public.is_admin())
WITH CHECK (public.is_admin());
CREATE POLICY "Service Role Full Access Order Refunds" ON order_refunds FOR ALL USING (auth.role() = 'service_role');

-- STORAGE product-images: leitura pública (imagens de catálogo); upload via authenticated/service_role
CREATE POLICY "Public read product images"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'product-images');

CREATE POLICY "Allow authenticated uploads"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'product-images');

CREATE POLICY "Service role full access product images"
ON storage.objects FOR ALL
TO service_role
USING (bucket_id = 'product-images');