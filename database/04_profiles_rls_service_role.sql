-- Política explícita para o role PostgreSQL service_role (além de auth.role() em JWT).
-- Rode no SQL Editor do Supabase se o backoffice ainda não enxergar profiles com a service_role key.

DROP POLICY IF EXISTS "Service Role Full Access Profiles" ON public.profiles;

CREATE POLICY "Service Role Full Access Profiles" ON public.profiles
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
