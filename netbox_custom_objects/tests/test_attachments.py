"""Tests for image attachment support on custom objects.

Custom objects reuse NetBox's built-in image attachment machinery
(``extras.ImageAttachment``) via the ``ImageAttachmentsMixin`` on the
``CustomObject`` base class.  No plugin-owned attachment model is involved.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from extras.models import ImageAttachment
from netbox.models.features import ImageAttachmentsMixin, get_model_features
from users.models import ObjectPermission

from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

from .base import CustomObjectsTestCase


class CustomObjectImageAttachmentTestCase(CustomObjectsTestCase, TestCase):
    """Custom object models support image attachments at the model layer."""

    def setUp(self):
        super().setUp()
        self.cot = CustomObjectType.objects.create(
            name='AttachmentObject',
            verbose_name_plural='Attachment Objects',
            slug='attachment-objects',
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=self.cot,
            name='name', label='Name', type='text', primary=True, required=True,
        )
        self.model = self.cot.get_model()
        self.instance = self.model.objects.create(name='Test Instance')
        self.content_type = ContentType.objects.get_for_model(self.model)

    def _build_attachment(self, **kwargs):
        # Mirror NetBox's own ImageAttachment tests: assign the image as a path
        # string with explicit dimensions so no real file or Pillow call is needed.
        defaults = {
            'object_type': self.content_type,
            'object_id': self.instance.pk,
            'name': 'Diagram',
            'image': 'custom-object-diagram.png',
            'image_height': 100,
            'image_width': 100,
        }
        defaults.update(kwargs)
        return ImageAttachment(**defaults)

    def test_model_supports_image_attachments_feature(self):
        self.assertTrue(issubclass(self.model, ImageAttachmentsMixin))
        self.assertIn('image_attachments', get_model_features(self.model))
        self.assertTrue(hasattr(self.instance, 'images'))

    def test_object_type_lists_image_attachments_feature(self):
        # create_model() recomputes ObjectType.features from the model's mixins.
        self.assertIn('image_attachments', self.cot.object_type.features)

    def test_clean_accepts_custom_object_type(self):
        # ImageAttachment.clean() rejects object types lacking the feature; a custom
        # object model must be accepted.
        self._build_attachment().clean()

    def test_attach_and_retrieve_image(self):
        attachment = self._build_attachment()
        attachment.save()
        self.assertEqual(self.instance.images.count(), 1)
        self.assertEqual(self.instance.images.first().pk, attachment.pk)

    def test_deleting_custom_object_deletes_its_images(self):
        attachment = self._build_attachment()
        attachment.save()
        self.instance.delete()
        self.assertFalse(ImageAttachment.objects.filter(pk=attachment.pk).exists())


class CustomObjectImageAttachmentViewTestCase(CustomObjectsTestCase, TestCase):
    """The custom object detail page renders the Images panel."""

    def setUp(self):
        super().setUp()
        self.cot = CustomObjectType.objects.create(
            name='AttachmentViewObject',
            verbose_name_plural='Attachment View Objects',
            slug='attachment-view-objects',
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=self.cot,
            name='name', label='Name', type='text', primary=True, required=True,
        )
        self.model = self.cot.get_model()
        self.instance = self.model.objects.create(name='Test Instance')

        view_perm = ObjectPermission(name='attachment-view', actions=['view'])
        view_perm.save()
        view_perm.users.add(self.user)
        view_perm.object_types.add(ContentType.objects.get_for_model(self.model))

        add_image_perm = ObjectPermission(name='attachment-add-image', actions=['add'])
        add_image_perm.save()
        add_image_perm.users.add(self.user)
        add_image_perm.object_types.add(ContentType.objects.get_for_model(ImageAttachment))

    def _detail_url(self):
        return reverse(
            'plugins:netbox_custom_objects:customobject',
            kwargs={'pk': self.instance.pk, 'custom_object_type': self.cot.slug},
        )

    def test_detail_view_renders_images_panel(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Images', content)
        # The "Attach an image" button links to the core ImageAttachment add view.
        self.assertIn(reverse('extras:imageattachment_add'), content)
