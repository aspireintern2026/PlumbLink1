from .extensions import ma
from marshmallow import fields
from .models import User, Item


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash",)


class ItemSchema(ma.SQLAlchemyAutoSchema):
    owner = fields.Nested(UserSchema)

    class Meta:
        model = Item
        load_instance = True
