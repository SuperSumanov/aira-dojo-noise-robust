# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import importlib
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Type

DATACLASS_TYPE_KEY = "_dojo_dataclass_type"


def dataclass_to_dict(value: Any) -> Any:
    """Serialize nested config dataclasses without losing their concrete types."""
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            DATACLASS_TYPE_KEY: f"{type(value).__module__}:{type(value).__qualname__}"
        }
        result.update(
            (class_field.name, dataclass_to_dict(getattr(value, class_field.name)))
            for class_field in fields(value)
        )
        return result
    if isinstance(value, Mapping):
        return {str(key): dataclass_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _resolve_dataclass_type(type_name: str, expected_type: Type[Any]) -> Type[Any]:
    try:
        module_name, qualname = type_name.split(":", 1)
        resolved: Any = importlib.import_module(module_name)
        for attribute in qualname.split("."):
            resolved = getattr(resolved, attribute)
    except (ImportError, AttributeError, ValueError) as error:
        raise ValueError(f"Cannot resolve serialized dataclass type {type_name!r}") from error
    if not is_dataclass(resolved):
        raise ValueError(f"Serialized type {type_name!r} is not a dataclass")
    if isinstance(expected_type, type) and is_dataclass(expected_type) and not issubclass(resolved, expected_type):
        raise ValueError(f"Serialized type {type_name!r} is not a subclass of {expected_type.__name__}")
    return resolved


def dataclass_from_dict(dataclass_type: Type[Any], data: dict) -> Any:
    """Recursively convert a dictionary to a dataclass instance."""
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type} is not a dataclass type")
    serialized_type = data.get(DATACLASS_TYPE_KEY)
    if serialized_type:
        dataclass_type = _resolve_dataclass_type(serialized_type, dataclass_type)
    init_args = {}
    for field in fields(dataclass_type):
        # Missing fields must retain their dataclass defaults so older JSON configs
        # remain loadable when optional metadata is added.
        if field.name not in data:
            continue
        field_value = data[field.name]
        if isinstance(field_value, dict) and DATACLASS_TYPE_KEY in field_value:
            expected_type = field.type if isinstance(field.type, type) else object
            nested_type = _resolve_dataclass_type(field_value[DATACLASS_TYPE_KEY], expected_type)
            init_args[field.name] = dataclass_from_dict(nested_type, field_value)
        elif is_dataclass(field.type) and isinstance(field_value, dict):
            # Recursively convert nested dataclass fields
            init_args[field.name] = dataclass_from_dict(field.type, field_value)
        elif isinstance(field_value, dict):
            init_args[field.name] = {
                key: (
                    dataclass_from_dict(
                        _resolve_dataclass_type(item[DATACLASS_TYPE_KEY], object), item
                    )
                    if isinstance(item, dict) and DATACLASS_TYPE_KEY in item
                    else item
                )
                for key, item in field_value.items()
            }
        elif isinstance(field_value, list):
            init_args[field.name] = [
                (
                    dataclass_from_dict(
                        _resolve_dataclass_type(item[DATACLASS_TYPE_KEY], object), item
                    )
                    if isinstance(item, dict) and DATACLASS_TYPE_KEY in item
                    else item
                )
                for item in field_value
            ]
        else:
            init_args[field.name] = field_value
    return dataclass_type(**init_args)
