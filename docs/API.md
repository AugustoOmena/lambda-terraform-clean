# API HTTP — Loja Omena (API Gateway v2)

Documentação dos endpoints expostos pelo API Gateway HTTP (`$default`). Base URL: output `api_url` do Terraform (`aws_apigatewayv2_api.main.api_endpoint`).

**CORS:** `Access-Control-Allow-Origin: *`; headers permitidos incluem `Content-Type`, `Authorization`, `x-backoffice` / `X-Backoffice`.

**Convenções:**

- Corpo JSON quando indicado; `Content-Type: application/json`.
- Respostas de erro comuns: `400` (`{"error": "...", "details": "..."}` quando há validação), `403`, `404` implícito em alguns fluxos, `500` (`{"error": "..."}`), `502` em falhas de integrações externas (frete/pagamento).

---

## Índice

1. [Pagamento](#1-pagamento)
2. [Produtos](#2-produtos)
3. [Usuários / perfis (backoffice)](#3-usuários--perfis-backoffice)
4. [Pedidos](#4-pedidos)
5. [Frete](#5-frete)

---

## 1. Pagamento

| Método    | Rota         | Lambda         |
| --------- | ------------ | -------------- |
| `POST`    | `/pagamento` | `payment`      |
| `OPTIONS` | `/pagamento` | Preflight CORS |

### `POST /pagamento`

Cria cobrança no Mercado Pago, valida frete com Melhor Envio, persiste pedido e atualiza estoque.

**Body (JSON)** — schema `PaymentInput` (`src/payment/schemas.py`):

| Campo                | Tipo          | Obrigatório | Notas                                                                                    |
| -------------------- | ------------- | ----------- | ---------------------------------------------------------------------------------------- |
| `token`              | string        | Não         | Token do cartão (fluxo card); pode ser omitido em PIX/boleto conforme MP                 |
| `transaction_amount` | number        | Sim         | Valor total da transação                                                                 |
| `payment_method_id`  | string        | Sim         | Ex.: `pix`, ids de cartão, boleto (`bol...` / `pec`)                                     |
| `installments`       | int           | Não         | Padrão `1`                                                                               |
| `issuer_id`          | string        | Não         | Emissor (cartão)                                                                         |
| `payer`              | object        | Sim         | Ver abaixo                                                                               |
| `user_id`            | string (UUID) | Sim         | Usuário Supabase/Auth                                                                    |
| `items`              | array         | Sim         | Ver abaixo                                                                               |
| `frete`              | number (≥ 0)  | Sim         | Valor do frete em R$ (deve bater com cotação validada no backend)                        |
| `frete_service`      | string        | Sim         | Identificador do serviço escolhido (ex.: campo `service` em `opcoes[]` do `POST /frete`) |
| `cep`                | string        | Sim         | CEP destino, 8 dígitos (pode vir formatado; só dígitos são usados)                       |

**`payer`:**

| Campo            | Tipo   | Obrigatório | Notas                                                                                                                  |
| ---------------- | ------ | ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| `email`          | string | Sim         |                                                                                                                        |
| `first_name`     | string | Não         | Padrão `"Cliente"`                                                                                                     |
| `last_name`      | string | Não         | Padrão `"Desconhecido"`                                                                                                |
| `identification` | object | Sim         | `type` (padrão `"CPF"`), `number` (só dígitos após normalização)                                                       |
| `address`        | object | Não         | `zip_code`, `street_name`, `street_number`, `neighborhood`, `city`, `federal_unit`, `complement` (opc., máx. 30 chars) |

**`items[]`:**

| Campo      | Tipo   | Obrigatório |
| ---------- | ------ | ----------- | ---------------- |
| `id`       | int    | Sim         | ID do produto    |
| `name`     | string | Sim         |
| `price`    | number | Sim         |
| `quantity` | int    | Sim         |
| `image`    | string | Não         |
| `color`    | string | Não         |
| `size`     | string | Não         | Padrão `"Único"` |

**Respostas:**

- `201` — JSON com campos mínimos:
  - `id` (id do pagamento MP), `status`, `status_detail`, `order_db_id` (UUID do pedido no banco), `payment_method_id`
  - PIX: `qr_code`, `qr_code_base64`, `ticket_url` (quando aplicável)
  - Boleto/PEC: `ticket_url` quando aplicável
- `400` — validação / frete não confere / regra de negócio
- `502` — falha Melhor Envio (`{"error": "..."}`)
- `500` — erro interno

---

## 2. Produtos

| Método | Rota                 | Lambda                                 |
| ------ | -------------------- | -------------------------------------- |
| `ANY`  | `/produtos`          | `products`                             |
| `ANY`  | `/produtos/{proxy+}` | `products` (ID numérico ou `exportar`) |

### `GET /produtos`

Lista paginada com filtros.

**Query:**

| Parâmetro                | Tipo          | Padrão   | Descrição                                 |
| ------------------------ | ------------- | -------- | ----------------------------------------- |
| `page`                   | int           | `1`      |                                           |
| `limit`                  | int           | `10`     |                                           |
| `name` ou `search`       | string        | —        | Busca por nome (usa um ou outro)          |
| `category`               | string        | —        |                                           |
| `min_price`, `max_price` | string/number | —        | Repassados ao repositório                 |
| `sort`                   | string        | `newest` | Valores suportados no repo (ex. `newest`) |
| `size`                   | string        | —        | Filtro por tamanho                        |

**Resposta `200`:**

```json
{
  "data": [{ "...": "produto" }],
  "meta": {
    "total": 0,
    "page": 1,
    "limit": 10,
    "nextPage": null
  }
}
```

### `GET /produtos/{id}`

`{id}` numérico. **Resposta `200`:** objeto produto com `variants` (array). Se não existir, o corpo pode ser `null` (comportamento atual do handler).

### `GET /produtos/exportar`

**Resposta `200`:** corpo **texto CSV** (não JSON), headers `Content-Type: text/csv` e `Content-Disposition: attachment`.

### `POST /produtos`

**Body:** `ProductInput` (`src/products/schemas.py`):
| Campo | Tipo | Obrigatório | Notas |
|--------|------|-------------|--------|
| `name` | string | Sim | |
| `price` | number | Sim | > 0, 2 casas decimais |
| `description`, `category`, `size`, `image`, `material`, `pattern` | string | Não | |
| `quantity` | int | Não | Padrão `0` |
| `images` | string[] | Não | Padrão `[]` |
| `stock` | object (mapa tamanho → int) | Não | Padrão `{}` |
| `is_featured` | bool | Não | |
| `variants` | array | Não | Itens: `color`, `size`, `stock_quantity` (≥ 0), `sku` opcional |

**Resposta `201`:** produto criado (formato do serviço/repositório).

### `PUT /produtos/{id}` ou `PUT /produtos` com `id` no body

**Body:** `ProductUpdate` — todos os campos opcionais (mesma forma que `ProductInput` onde aplicável).

**Resposta `200`:** produto atualizado.

**`400`:** se não houver ID válido.

### `DELETE /produtos/{id}`

**Resposta `204`:** corpo `{}` em JSON no wrapper atual.  
**`400`:** ID ausente.

---

## 3. Usuários / perfis (backoffice)

| Método | Rota                 | Lambda                                                                |
| ------ | -------------------- | --------------------------------------------------------------------- |
| `ANY`  | `/usuarios`          | `profiles`                                                            |
| `ANY`  | `/usuarios/{proxy+}` | `profiles` (path extra aceito pelo gateway; lógica principal na raiz) |

### `GET /usuarios`

Lista perfis com paginação e filtros.

**Query:**

| Parâmetro | Tipo          | Padrão   | Descrição                                                                                                |
| --------- | ------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `page`    | int           | `1`      | ≥ 1                                                                                                      |
| `limit`   | int           | `10`     | 1–100                                                                                                    |
| `email`   | string        | —        | Filtro parcial (ilike)                                                                                   |
| `role`    | string        | —        | `admin` ou `user`                                                                                        |
| `sort`    | string        | `newest` | `newest`, `role_asc`, `role_desc`                                                                        |
| `user_id` | string (UUID) | —        | Opcional; se informado, o backend tenta RPC `backoffice_list_profiles` no Supabase antes da query direta (ver **Glossário**: RPC) |

**Headers opcionais:**

- `Authorization: Bearer <access_token>` — repassado internamente para fluxos alinhados ao JWT do usuário (uso principal forte em **pedidos**).

**Resposta `200`:**

```json
{
  "data": [ { "id", "email", "role", "created_at", ... } ],
  "count": 0
}
```

(`count` = total aproximado/exato conforme PostgREST/Supabase.)

### `PUT /usuarios`

**Body (`ProfileUpdate`):**

| Campo   | Tipo              | Obrigatório                       |
| ------- | ----------------- | --------------------------------- |
| `id`    | string (UUID)     | Sim                               |
| `email` | string            | Não (validação básica se enviado) |
| `role`  | `admin` \| `user` | Não                               |

Pelo menos um de `email` ou `role` deve ser enviado (regra no service).

**Resposta `200`:** perfil atualizado (objeto).

### `DELETE /usuarios`

**Body (`ProfileDelete`):**

| Campo | Tipo          | Obrigatório |
| ----- | ------------- | ----------- |
| `id`  | string (UUID) | Sim         |

**Resposta `200`:** `{"message": "...", "id": "..."}`.

### Erros

- `400` — validação Pydantic / regras de negócio
- `500` — erro genérico (`{"error": "..."}`)

---

## 4. Pedidos

| Método | Rota                | Lambda                            |
| ------ | ------------------- | --------------------------------- |
| `ANY`  | `/pedidos`          | `orders`                          |
| `ANY`  | `/pedidos/{proxy+}` | `orders` (`{order_id}`, subpaths) |

Path: `proxy` pode ser `{uuid}`, `{uuid}/solicitar-cancelamento`, etc., conforme implementação do handler.

### `GET /pedidos/{order_id}?user_id=<uuid>`

Detalhe do pedido **do cliente** (deve ser o dono).

**Query obrigatória:** `user_id`

**Resposta `200`:** objeto pedido com itens, `refund_requests`, `user_email`, `shipping_address`, etc.  
**`400`:** sem `user_id`.  
**`500`:** pedido não encontrado / erro.

### `GET /pedidos?user_id=...&page=&limit=`

**Modo cliente (lista “meus pedidos”):**

- **Query obrigatória:** `user_id`
- `page` (padrão `1`), `limit` (padrão `20`)
- **Sem** header `x-backoffice: true`

**Resposta `200`:** `{ "data": [ ... ], "count": N }` (pedidos simplificados + itens anexados pelo serviço).

**Modo backoffice (lista todos):**

- **Header:** `x-backoffice: true` (valor case-insensitive no código; API Gateway pode entregar em minúsculas)
- **Query obrigatória:** `user_id` — UUID do **admin logado** (checagem de role + lista via RPC Supabase quando a função existir; ver glossário)
- **Recomendado:** `Authorization: Bearer <jwt da sessão Supabase>` — necessário se a role não for
  resolvida só com a chave server-side (ex.: fallback REST)

**Resposta `200`:** mesma forma `{ "data", "count" }` com todos os pedidos (campos de listagem + itens).  
**`403`:** usuário não é `admin` (`{"error": "..."}`).  
**`400`:** falta `user_id`.

### `POST /pedidos/{order_id}/solicitar-cancelamento?user_id=<uuid>`

Cliente solicita cancelamento/reembolso (regra de 7 dias no service).

**Query obrigatória:** `user_id`

**Body (`CancelRequestInput`):**

| Campo            | Tipo     | Descrição                                        |
| ---------------- | -------- | ------------------------------------------------ |
| `total`          | bool     | Padrão `false`; `true` = cancelamento total      |
| `order_item_ids` | string[] | Obrigatório se `total` é `false`: itens parciais |

Não enviar `total=true` e `order_item_ids` preenchido ao mesmo tempo.

**Resposta `201`:** registro criado (formato do serviço).  
**`400`:** validação.

### `PUT /pedidos/{order_id}` — backoffice

**Header obrigatório:** `x-backoffice: true`

**Caso A — só status**

**Body (`OrderStatusUpdate`):**

```json
{ "status": "shipped" }
```

**Resposta `200`:** pedido completo com itens e enriquecimentos.

**Caso B — cancelamento / reembolso operado pelo backoffice**

**Body (`BackofficeCancelInput`):**

| Campo             | Tipo     | Descrição                                               |
| ----------------- | -------- | ------------------------------------------------------- |
| `refund_method`   | string   | Obrigatório: `"mp"` ou `"voucher"`                      |
| `cancel_item_ids` | string[] | Opcional; IDs de `order_items`; vazio com `full_cancel` |
| `full_cancel`     | bool     | Padrão `false`                                          |

**Resposta `200`:** resultado do fluxo de cancel/reembolso.

**`403`:** sem header backoffice.  
**`400`:** body inválido ou ambíguo.

---

## 5. Frete

| Método    | Rota     | Lambda     |
| --------- | -------- | ---------- |
| `POST`    | `/frete` | `shipping` |
| `OPTIONS` | `/frete` | CORS       |

### `POST /frete`

**Body (`FreightQuoteInput`):**

| Campo         | Tipo           | Descrição               |
| ------------- | -------------- | ----------------------- |
| `cep_destino` | string         | 8 dígitos (normalizado) |
| `itens`       | array (mín. 1) | Ver abaixo              |

**`itens[]` (`ShippingItemInput`):**

| Campo                       | Tipo      | Descrição                                                              |
| --------------------------- | --------- | ---------------------------------------------------------------------- |
| `width`, `height`, `length` | int (> 0) | cm, inteiros (frações devem ser arredondadas para cima antes do envio) |
| `weight`                    | number    | kg, até 3 casas decimais                                               |
| `quantity`                  | int       | Padrão `1`, ≥ 1                                                        |
| `insurance_value`           | number    | Padrão `0`, ≥ 0                                                        |

**Resposta `200`:**

```json
{
  "opcoes": [
    {
      "transportadora": "...",
      "preco": 0,
      "prazo_entrega_dias": 0,
      "service": "identificador_para_frete_service_no_checkout"
    }
  ]
}
```

(Chaves exatas adicionais podem existir conforme `shared/melhor_envio.get_quote`.)

**`400`:** validação.  
**`502`:** falha API Melhor Envio.  
**`405`:** método diferente de POST.

---

## Notas para o front

1. **Checkout:** usar o mesmo `service` retornado em `opcoes[].service` no campo `frete_service` do `POST /pagamento`, e o mesmo pacote/dimensões coerentes com a política de frete (o pagamento revalida no backend).
2. **Backoffice pedidos:** sempre `x-backoffice: true` + `user_id` do admin + `Authorization` Bearer quando o backend precisar confirmar `admin` via JWT/anon.
3. **Lambda só via EventBridge:** `cleanup-orphan-images` não expõe rota HTTP; não consta neste documento.

---

## Glossário

- **RPC (Supabase / PostgREST):** chamada HTTP à API do projeto que executa uma **função PostgreSQL** (ex.: `backoffice_list_orders`, `backoffice_list_profiles`), tipicamente via `POST /rest/v1/rpc/<nome>`. No código Python: `supabase.rpc("nome", { "p_arg": ... })`. Útil para lógica e permissões concentradas no banco; se a função não existir ou falhar, o backend pode cair em outro caminho (query direta ou REST).

---

_Gerado a partir dos handlers e schemas em `src/*` e rotas em `infra/envs/*/main.tf`._
