from intentkit.utils.error import format_validation_errors


def test_format_validation_errors_with_field_path_and_type():
    errors = [
        {
            "loc": ("body", "user", "email"),
            "msg": "value is not a valid email address",
            "type": "value_error.email",
        },
        {
            "loc": ("body", "items", 0, "price"),
            "msg": "value is not a valid decimal",
            "type": "type_error.decimal",
        },
    ]

    result = format_validation_errors(errors)

    assert (
        "Field 'user -> email' (value_error.email): value is not a valid email address"
        in result
    )
    assert (
        "Field 'items -> 0 -> price' (type_error.decimal): value is not a valid decimal"
        in result
    )


def test_format_validation_errors_without_field_path():
    errors = [
        {
            "loc": (),
            "msg": "root error",
            "type": "value_error",
        }
    ]

    assert format_validation_errors(errors) == "root error"
