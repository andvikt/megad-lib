from typing import Any, ClassVar

from pydantic import BaseModel, PrivateAttr


class PolymorphicBaseModel(BaseModel):
    type: str

    _subtypes: ClassVar[dict[str, Any]] = {}
    _cache: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init_subclass__(subcls: Any, type_: Any = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if type_:
            if type_ in subcls._subtypes:
                raise AttributeError(
                    f"Class {subcls} cannot be registered with polymorphic type='{type_}' "
                    f"because it's already registered "
                    f" to {subcls._subtypes[type_]}"
                )
            subcls._subtypes[type_] = subcls

    @classmethod
    def _convert_to_real_type(cls, data: Any) -> Any:
        data_type = data.get("type")

        if data_type is None:
            raise ValueError(f"Missing 'type' for {cls}")

        subcls = cls._subtypes.get(data_type)

        if subcls is None:
            raise TypeError(f"Unsupported sub-type: {data_type}")
        if not issubclass(subcls, cls):
            raise TypeError(f"Inferred class {subcls} is not a subclass of {cls}")

        return subcls(**data)

    @classmethod
    def parse_obj(cls, data: Any) -> Any:
        return cls._convert_to_real_type(data)
