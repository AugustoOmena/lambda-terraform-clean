import pytest
from pydantic import ValidationError

from src.payment.schemas import Identification, Address, Payer, Item, PaymentInput


class TestIdentificationValidation:
    """Testes para validação do campo 'number' da classe Identification."""

    def test_clean_number_removes_special_characters(self) -> None:
        """CPF formatado (123.456.789-00) deve ser limpo para apenas dígitos."""
        identification = Identification(type="CPF", number="123.456.789-00")
        assert identification.number == "12345678900"

    def test_clean_number_keeps_only_digits(self) -> None:
        """RG com letras e caracteres especiais (MG-12.345.678) mantém apenas dígitos."""
        identification = Identification(type="RG", number="MG-12.345.678")
        assert identification.number == "12345678"

    def test_clean_number_already_clean(self) -> None:
        """Número sem formatação mantém-se igual."""
        identification = Identification(type="CPF", number="12345678900")
        assert identification.number == "12345678900"

    def test_clean_number_empty_string(self) -> None:
        """String vazia resulta em string vazia (sem dígitos)."""
        identification = Identification(type="CPF", number="")
        assert identification.number == ""

    def test_identification_type_default_is_cpf(self) -> None:
        """Tipo padrão de identificação deve ser CPF."""
        identification = Identification(number="12345678900")
        assert identification.type == "CPF"


class TestPaymentInputValidation:
    """Testes de validação básica do PaymentInput."""

    def test_payment_input_requires_mandatory_fields(self) -> None:
        """transaction_amount, payment_method_id, payer, user_id, items, frete e cep são obrigatórios."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentInput()
        
        errors = exc_info.value.errors()
        required_fields = {err["loc"][0] for err in errors if err["type"] == "missing"}
        
        assert "transaction_amount" in required_fields
        assert "payment_method_id" in required_fields
        assert "payer" in required_fields
        assert "user_id" in required_fields
        assert "items" in required_fields
        assert "frete" in required_fields
        assert "frete_service" in required_fields
        assert "cep" in required_fields

    def test_payment_input_default_installments_is_1(self) -> None:
        """installments deve ter valor padrão 1."""
        payload = PaymentInput(
            transaction_amount=100.0,
            payment_method_id="pix",
            payer=Payer(
                email="test@example.com",
                identification=Identification(number="12345678900")
            ),
            user_id="user-123",
            items=[Item(id=1, name="Produto", price=100.0, quantity=1)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310100",
        )
        assert payload.installments == 1

    def test_payment_input_cep_normalized_to_eight_digits(self) -> None:
        """CEP com formatação (01310-100) é normalizado para 8 dígitos."""
        payload = PaymentInput(
            transaction_amount=100.0,
            payment_method_id="pix",
            payer=Payer(email="a@b.com", identification=Identification(number="12345678900")),
            user_id="u",
            items=[Item(id=1, name="P", price=100.0, quantity=1)],
            frete=25.90,
            frete_service="jadlog_package",
            cep="01310-100",
        )
        assert payload.cep == "01310100"

    def test_payment_input_cep_invalid_length_raises(self) -> None:
        """CEP com menos ou mais de 8 dígitos levanta ValidationError."""
        with pytest.raises(ValidationError):
            PaymentInput(
                transaction_amount=100.0,
                payment_method_id="pix",
                payer=Payer(email="a@b.com", identification=Identification(number="12345678900")),
                user_id="u",
                items=[Item(id=1, name="P", price=100.0, quantity=1)],
                frete=25.90,
                frete_service="jadlog_package",
                cep="1234567",
            )
        with pytest.raises(ValidationError):
            PaymentInput(
                transaction_amount=100.0,
                payment_method_id="pix",
                payer=Payer(email="a@b.com", identification=Identification(number="12345678900")),
                user_id="u",
                items=[Item(id=1, name="P", price=100.0, quantity=1)],
                frete=25.90,
                frete_service="jadlog_package",
                cep="123456789",
            )

    def test_payment_input_frete_ge_zero(self) -> None:
        """frete deve ser >= 0."""
        payload = PaymentInput(
            transaction_amount=100.0,
            payment_method_id="pix",
            payer=Payer(email="a@b.com", identification=Identification(number="12345678900")),
            user_id="u",
            items=[Item(id=1, name="P", price=100.0, quantity=1)],
            frete=0.0,
            frete_service="jadlog_package",
            cep="01310100",
        )
        assert payload.frete == 0.0
        with pytest.raises(ValidationError):
            PaymentInput(
                transaction_amount=100.0,
                payment_method_id="pix",
                payer=Payer(email="a@b.com", identification=Identification(number="12345678900")),
                user_id="u",
                items=[Item(id=1, name="P", price=100.0, quantity=1)],
                frete=-1.0,
                frete_service="jadlog_package",
                cep="01310100",
            )

    def test_item_default_size_is_unico(self) -> None:
        """size padrão de Item deve ser 'Único'."""
        item = Item(id=1, name="Camiseta", price=50.0, quantity=2)
        assert item.size == "Único"


class TestAddressValidation:
    """Testes para classe Address."""

    def test_address_requires_all_fields(self) -> None:
        """Todos os campos de Address são obrigatórios."""
        with pytest.raises(ValidationError) as exc_info:
            Address()
        
        errors = exc_info.value.errors()
        required_fields = {err["loc"][0] for err in errors if err["type"] == "missing"}
        
        assert "zip_code" in required_fields
        assert "street_name" in required_fields
        assert "street_number" in required_fields
        assert "neighborhood" in required_fields
        assert "city" in required_fields
        assert "federal_unit" in required_fields

    def test_address_valid_creation(self) -> None:
        """Criação válida de Address com todos os campos."""
        address = Address(
            zip_code="30130-100",
            street_name="Av. Afonso Pena",
            street_number="1000",
            neighborhood="Centro",
            city="Belo Horizonte",
            federal_unit="MG"
        )
        assert address.zip_code == "30130-100"
        assert address.city == "Belo Horizonte"
