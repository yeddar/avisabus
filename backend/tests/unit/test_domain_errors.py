import pytest

from avisabus.domain.errors import DomainError


@pytest.mark.spec("project_scaffold.AC-06")
def test_domain_error_is_the_base_exception_measured_by_coverage() -> None:
    # Keeps domain coverage measurable while the domain layer is still empty.
    with pytest.raises(DomainError):
        raise DomainError("boom")
    assert issubclass(DomainError, Exception)
