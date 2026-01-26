import pytest
from unittest.mock import patch, MagicMock

from service import ProductService
from schemas import ProductInput, ProductUpdate


@pytest.fixture
def mock_repository():
    with patch("service.ProductRepository") as mock_repo_class:
        mock_instance = MagicMock()
        mock_repo_class.return_value = mock_instance
        yield mock_instance


class TestCreateProduct:
    """Testes para o método create_product do ProductService."""

    def test_create_product_success_returns_product_from_repository(
        self, mock_repository: MagicMock
    ) -> None:
        payload = ProductInput(name="Camiseta", price=29.90)
        expected = {"id": 1, "name": "Camiseta", "price": 29.90}
        mock_repository.create.return_value = expected

        service = ProductService()
        result = service.create_product(payload)

        assert result == expected
        mock_repository.create.assert_called_once()

    def test_create_product_calls_repository_with_dict_exclude_none(
        self, mock_repository: MagicMock
    ) -> None:
        payload = ProductInput(
            name="Calça",
            price=99.90,
            description="Confortável",
            category="Roupas",
        )
        mock_repository.create.return_value = {"id": 1, "name": "Calça"}

        service = ProductService()
        service.create_product(payload)

        call_args = mock_repository.create.call_args[0][0]
        assert call_args["name"] == "Calça"
        assert call_args["price"] == 99.90
        assert call_args["description"] == "Confortável"
        assert call_args["category"] == "Roupas"
        # exclude_none=True remove campos None; valores default como 0 ou [] permanecem
        assert "quantity" in call_args
        assert "images" in call_args

    def test_create_product_returns_none_when_repository_returns_none(
        self, mock_repository: MagicMock
    ) -> None:
        payload = ProductInput(name="Produto", price=10.0)
        mock_repository.create.return_value = None

        service = ProductService()
        result = service.create_product(payload)

        assert result is None
        mock_repository.create.assert_called_once()

    def test_create_product_with_stock_passes_stock_to_repository(
        self, mock_repository: MagicMock
    ) -> None:
        payload = ProductInput(
            name="Tênis",
            price=199.90,
            stock={"P": 2, "M": 3, "G": 1},
        )
        mock_repository.create.return_value = {"id": 2, "name": "Tênis"}

        service = ProductService()
        service.create_product(payload)

        call_args = mock_repository.create.call_args[0][0]
        assert call_args["stock"] == {"P": 2, "M": 3, "G": 1}

    def test_create_product_with_only_required_fields(
        self, mock_repository: MagicMock
    ) -> None:
        payload = ProductInput(name="Mínimo", price=1.0)
        mock_repository.create.return_value = {"id": 3, "name": "Mínimo"}

        service = ProductService()
        service.create_product(payload)

        call_args = mock_repository.create.call_args[0][0]
        assert call_args["name"] == "Mínimo"
        assert call_args["price"] == 1.0
        # Campos com default não-None (quantity=0, images=[]) devem aparecer
        assert "quantity" in call_args
        assert call_args["quantity"] == 0


class TestListProducts:
    """Testes para o método list_products do ProductService."""

    def test_list_products_pagination_calculates_start_end_correctly(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_products_paginated.return_value = ([], 0)

        service = ProductService()
        service.list_products(page=1, limit=10)

        mock_repository.get_products_paginated.assert_called_once_with(0, 9, None)

    def test_list_products_pagination_page_2_limit_10(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_products_paginated.return_value = ([], 25)

        service = ProductService()
        result = service.list_products(page=2, limit=10)

        mock_repository.get_products_paginated.assert_called_once_with(10, 19, None)
        assert result["meta"]["page"] == 2
        assert result["meta"]["limit"] == 10
        assert result["meta"]["total"] == 25
        assert result["meta"]["nextPage"] == 3  # has_next: 20 < 25

    def test_list_products_pagination_last_page_no_next_page(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_products_paginated.return_value = ([{"id": 1}], 15)

        service = ProductService()
        result = service.list_products(page=2, limit=10)

        mock_repository.get_products_paginated.assert_called_once_with(10, 19, None)
        assert result["meta"]["nextPage"] is None  # 20 >= 15, has_next=False

    def test_list_products_passes_filters_to_repository(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_products_paginated.return_value = ([], 0)
        filters = {"name": "camiseta", "category": "Roupas", "min_price": 10, "max_price": 100}

        service = ProductService()
        service.list_products(page=1, limit=5, filters=filters)

        mock_repository.get_products_paginated.assert_called_once_with(0, 4, filters)

    def test_list_products_returns_data_and_meta_structure(
        self, mock_repository: MagicMock
    ) -> None:
        data = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        mock_repository.get_products_paginated.return_value = (data, 2)

        service = ProductService()
        result = service.list_products(page=1, limit=10)

        assert result["data"] == data
        assert result["meta"]["total"] == 2
        assert result["meta"]["page"] == 1
        assert result["meta"]["limit"] == 10
        assert result["meta"]["nextPage"] is None

    def test_list_products_normalizes_image_to_images_when_images_empty(
        self, mock_repository: MagicMock
    ) -> None:
        data = [{"id": 1, "name": "P", "image": "https://x/img.png", "images": []}]
        mock_repository.get_products_paginated.return_value = (data, 1)

        service = ProductService()
        result = service.list_products(page=1, limit=10)

        assert result["data"][0]["images"] == ["https://x/img.png"]

    def test_list_products_does_not_overwrite_existing_images(
        self, mock_repository: MagicMock
    ) -> None:
        data = [{"id": 1, "name": "P", "image": "a.png", "images": ["a.png", "b.png"]}]
        mock_repository.get_products_paginated.return_value = (data, 1)

        service = ProductService()
        result = service.list_products(page=1, limit=10)

        assert result["data"][0]["images"] == ["a.png", "b.png"]


class TestGetProduct:
    """Testes para o método get_product do ProductService."""

    def test_get_product_success_returns_product_when_found(
        self, mock_repository: MagicMock
    ) -> None:
        expected = {"id": 1, "name": "Camiseta", "price": 29.90}
        mock_repository.get_by_id.return_value = expected

        service = ProductService()
        result = service.get_product(1)

        assert result == expected
        mock_repository.get_by_id.assert_called_once_with(1)

    def test_get_product_returns_none_when_not_found(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_by_id.return_value = None

        service = ProductService()
        result = service.get_product(999)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(999)


class TestUpdateProduct:
    """Testes para o método update_product do ProductService."""

    def test_update_product_success_returns_updated_product(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_by_id.return_value = {"id": 1, "name": "Antigo"}
        expected = {"id": 1, "name": "Atualizado", "price": 49.90}
        mock_repository.update.return_value = expected

        service = ProductService()
        payload = ProductUpdate(name="Atualizado", price=49.90)
        result = service.update_product(1, payload)

        assert result == expected
        mock_repository.update.assert_called_once_with(1, {"name": "Atualizado", "price": 49.90})

    def test_update_product_deletes_old_image_when_image_changes(
        self, mock_repository: MagicMock
    ) -> None:
        old_url = "https://bucket.s3/product-images/old.png"
        mock_repository.get_by_id.return_value = {"id": 1, "name": "P", "image": old_url}
        mock_repository.update.return_value = {"id": 1, "image": "https://bucket.s3/product-images/new.png"}

        service = ProductService()
        payload = ProductUpdate(image="https://bucket.s3/product-images/new.png")
        service.update_product(1, payload)

        mock_repository.delete_storage_file.assert_called_once_with(old_url)
        mock_repository.update.assert_called_once()

    def test_update_product_does_not_call_delete_storage_file_when_image_unchanged(
        self, mock_repository: MagicMock
    ) -> None:
        same_url = "https://x/product-images/same.png"
        mock_repository.get_by_id.return_value = {"id": 1, "image": same_url}
        mock_repository.update.return_value = {"id": 1}

        service = ProductService()
        payload = ProductUpdate(image=same_url)
        service.update_product(1, payload)

        mock_repository.delete_storage_file.assert_not_called()
        mock_repository.update.assert_called_once()


class TestDeleteProduct:
    """Testes para o método delete_product do ProductService."""

    def test_delete_product_success_calls_repository_delete(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_by_id.return_value = {"id": 1, "name": "P", "image": "https://x/product-images/img.png"}
        mock_repository.delete.return_value = []

        service = ProductService()
        result = service.delete_product(1)

        assert result == []
        mock_repository.delete.assert_called_once_with(1)

    def test_delete_product_calls_delete_storage_file_when_product_has_image(
        self, mock_repository: MagicMock
    ) -> None:
        image_url = "https://bucket/product-images/foto.png"
        mock_repository.get_by_id.return_value = {"id": 1, "name": "P", "image": image_url}
        mock_repository.delete.return_value = []

        service = ProductService()
        service.delete_product(1)

        mock_repository.delete_storage_file.assert_called_once_with(image_url)
        mock_repository.delete.assert_called_once_with(1)

    def test_delete_product_does_not_call_delete_storage_file_when_no_image(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_by_id.return_value = {"id": 1, "name": "P"}
        mock_repository.delete.return_value = []

        service = ProductService()
        service.delete_product(1)

        mock_repository.delete_storage_file.assert_not_called()
        mock_repository.delete.assert_called_once_with(1)


class TestExportProductsCsv:
    """Testes para o método export_products_csv do ProductService."""

    def test_export_products_csv_returns_string_with_correct_header(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_all_raw.return_value = []

        service = ProductService()
        result = service.export_products_csv()

        assert isinstance(result, str)
        assert "ID" in result
        assert "Nome" in result
        assert "Preco" in result
        assert "Categoria" in result
        assert "Estoque" in result
        assert "Tamanho" in result
        assert "Criado em" in result
        mock_repository.get_all_raw.assert_called_once()

    def test_export_products_csv_includes_product_rows(
        self, mock_repository: MagicMock
    ) -> None:
        mock_repository.get_all_raw.return_value = [
            {
                "id": 1,
                "name": "Camiseta",
                "price": 29.90,
                "category": "Roupas",
                "quantity": 5,
                "size": "M",
                "created_at": "2024-01-15",
            }
        ]

        service = ProductService()
        result = service.export_products_csv()

        assert "1" in result
        assert "Camiseta" in result
        assert "29.90" in result
        assert "Roupas" in result
        assert "5" in result
        assert "M" in result
        assert "2024-01-15" in result
