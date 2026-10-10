from django.db.models.signals import post_delete, post_save

from .cache import bump_content_version


def connect(*models):
    for model in models:
        post_save.connect(bump_content_version, sender=model, weak=False,
                          dispatch_uid=f"bump_save_{model.__name__}")
        post_delete.connect(bump_content_version, sender=model, weak=False,
                            dispatch_uid=f"bump_delete_{model.__name__}")
