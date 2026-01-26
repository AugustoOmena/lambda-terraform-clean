SELECT 
    t.table_name AS "Tabela",
    c.column_name AS "Coluna",
    UPPER(c.data_type) AS "Tipo",
    CASE WHEN c.is_nullable = 'NO' THEN '⛔ OBRIGATÓRIO' ELSE '✅ OPCIONAL' END AS "Nulidade",
    COALESCE(c.column_default, '-') AS "Default"
FROM 
    information_schema.tables t
JOIN 
    information_schema.columns c ON t.table_name = c.table_name
WHERE 
    t.table_schema = 'public' 
    AND t.table_type = 'BASE TABLE'
ORDER BY 
    t.table_name, c.ordinal_position;