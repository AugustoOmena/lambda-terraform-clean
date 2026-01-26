# Módulo Profiles - Gerenciamento de Usuários (Backoffice)

API para administração de perfis de usuários no painel administrativo (Frontend React).

## Endpoints

### GET /usuarios

Lista perfis com filtros, paginação e ordenação.

**Query Parameters:**

- `page` (int, default: 1): Página atual
- `limit` (int, default: 10, max: 100): Itens por página
- `email` (string, optional): Filtro parcial por email (case-insensitive)
- `role` (string, optional): Filtro exato por role ('admin' ou 'user')
- `sort` (string, default: 'newest'): Ordenação
  - `newest`: Mais recentes primeiro (created_at desc)
  - `role_asc`: Por role ascendente (admin → user)
  - `role_desc`: Por role descendente (user → admin)

**Response (200):**

```json
{
  "data": [
    {
      "id": "uuid-123",
      "email": "admin@example.com",
      "role": "admin",
      "created_at": "2026-01-25T10:00:00Z"
    }
  ],
  "count": 150
}
```

**Exemplo de chamada:**

```bash
GET /usuarios?page=2&limit=20&email=joao&role=admin&sort=role_asc
```

---

### PUT /usuarios

Atualiza email e/ou role de um perfil.

**Body (JSON):**

```json
{
  "id": "uuid-123",
  "email": "novo@example.com",
  "role": "admin"
}
```

**Campos:**

- `id` (string, obrigatório): UUID do perfil
- `email` (string, opcional): Novo email
- `role` (string, opcional): Nova role ('admin' ou 'user')

**Validações:**

- Ao menos um campo (email ou role) deve ser fornecido
- Email deve conter '@' e '.'

**Response (200):**

```json
{
  "id": "uuid-123",
  "email": "novo@example.com",
  "role": "admin",
  "created_at": "2026-01-25T10:00:00Z"
}
```

**Erros:**

- `400`: Dados inválidos (email malformado, role inválida)
- `500`: Perfil não encontrado ou erro no banco

---

### DELETE /usuarios

Remove um perfil do sistema.

**Body (JSON):**

```json
{
  "id": "uuid-123"
}
```

**Regras de negócio:**

- ⚠️ Administradores não podem deletar seu próprio perfil (quando autenticação estiver implementada)

**Response (200):**

```json
{
  "message": "Perfil removido com sucesso",
  "id": "uuid-123"
}
```

**Erros:**

- `400`: ID inválido
- `403`: Admin tentando deletar a si mesmo (quando auth implementado)
- `500`: Perfil não encontrado ou erro no banco

---

## Arquitetura

```
src/profiles/
├── __init__.py          # Módulo marker
├── schemas.py           # Pydantic models (Profile, ProfileFilter, ProfileUpdate, ProfileDelete)
├── repository.py        # Queries Supabase (list_all, update, delete, get_by_id)
├── service.py           # Regras de negócio
└── handler.py           # Lambda handler (rotas GET, PUT, DELETE)
```

### Dependências

- `shared.database`: Cliente Supabase (singleton)
- `shared.responses`: Formatação de respostas HTTP com CORS
- `pydantic`: Validação de dados
- `aws_lambda_powertools`: Logs estruturados

---

## Implementação Técnica

### Repository (`repository.py`)

**Paginação:**

```python
start = (page - 1) * limit
end = start + limit - 1
query.range(start, end)  # Supabase range é 0-indexed e inclusivo
```

**Filtros:**

```python
# Email parcial (case-insensitive)
query.ilike("email", f"%{email}%")

# Role exato
query.eq("role", role)
```

**Ordenação:**

```python
sort_mapping = {
    "newest": ("created_at", {"ascending": False}),
    "role_asc": ("role", {"ascending": True}),
    "role_desc": ("role", {"ascending": False}),
}
```

**Count total:**

```python
query.select("*", count="exact")  # Retorna count mesmo com paginação
```

---

## Exemplos de Uso Frontend (TypeScript)

```typescript
// GET: Listagem com filtros
const params = new URLSearchParams();
params.append("page", "2");
params.append("limit", "20");
params.append("email", "joao");
params.append("role", "admin");
params.append("sort", "role_asc");

const response = await fetch(`/usuarios?${params}`);
const { data, count } = await response.json();
console.log(`Total: ${count}, Página atual: ${data.length}`);

// PUT: Atualizar role
await fetch("/usuarios", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    id: "uuid-123",
    role: "admin",
  }),
});

// DELETE: Remover perfil
await fetch("/usuarios", {
  method: "DELETE",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ id: "uuid-456" }),
});
```

---

## TODO / Melhorias Futuras

- [ ] Implementar autenticação JWT para extrair `current_user_id`
- [ ] Adicionar endpoint POST para criar novos perfis
- [ ] Adicionar mais filtros (created_at range, busca por nome)
- [ ] Implementar soft delete (flag `deleted_at` ao invés de remover)
- [ ] Adicionar auditoria de ações (log de quem alterou o quê)
- [ ] Implementar rate limiting
- [ ] Adicionar testes unitários (handler, service, repository)

---

## Schema da Tabela (SQL)

```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY,
    email TEXT,
    role TEXT DEFAULT 'user'::text,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
```

**Roles disponíveis:**

- `admin`: Administrador do sistema
- `user`: Usuário comum

---

## Logs Estruturados

O módulo usa `aws_lambda_powertools.Logger` para logs em formato JSON:

```json
{
  "level": "INFO",
  "service": "profiles",
  "message": "Listando perfis: page=2, limit=20",
  "timestamp": "2026-01-25T10:00:00.000Z"
}
```

---

## Testes

Execute os testes unitários:

```bash
pytest tests/profiles/ -v
```
