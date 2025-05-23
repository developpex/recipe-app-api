"""
Test for the tags API.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Tag

from recipe.serializers import TagSerializer

TAG_URL = reverse("recipe:tag-list")


def detail_url(tag_id):
    """Create and return a tag detail URL."""
    return reverse("recipe:tag-detail", args=[tag_id])


def create_user(**params):
    """Create and return a new user."""
    return get_user_model().objects.create_user(**params)


def create_tag(user, **params):
    """Create a tag for the tests"""
    defaults = {
        "name": "Tag Name"
    }
    defaults.update(params)

    tag = Tag.objects.create(user=user, **defaults)
    return tag


class PublicTagsApiTests(TestCase):
    """Test unauthenticated API request."""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required to call API."""
        res = self.client.get(TAG_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authenticated API request."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="user@example.com",
            password="testpass123"
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Test retrieving a list of tags."""
        create_tag(user=self.user, name="Vegan")
        create_tag(user=self.user, name="Desert")

        res = self.client.get(TAG_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        tags = Tag.objects.all().order_by("-name")
        serializer = TagSerializer(tags, many=True)
        self.assertEqual(res.data, serializer.data)

    def test_tag_list_limited_to_user(self):
        """Test list of tags is limited to authenticated user."""
        new_user = create_user(
            email="newuser@example.com",
            password="testpass123"
        )

        create_tag(user=new_user, name="fruit")
        create_tag(user=self.user, name="Italian")

        res = self.client.get(TAG_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        tags = Tag.objects.filter(user=self.user)
        serializer = TagSerializer(tags, many=True)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data, serializer.data)

    def test_update_tag(self):
        """Test for updating a tag"""
        tag = create_tag(user=self.user, name="Thai")
        payload = {
            "name": "Vietnamese"
        }
        url = detail_url(tag.id)

        res = self.client.patch(url, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        tag.refresh_from_db()
        self.assertEqual(tag.name, payload["name"])
        self.assertEqual(tag.user, self.user)

    def test_delete_tag(self):
        tag = create_tag(user=self.user, name="Ice Cream")

        url = detail_url(tag.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(Tag.objects.filter(id=tag.id).exists())
